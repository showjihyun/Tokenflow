"""Thin Anthropic SDK wrapper. Loads the API key via secret_store."""
from __future__ import annotations

import logging
from functools import partial
from typing import Any

import anyio

from tokenflow.adapters.persistence import secret_store

logger = logging.getLogger(__name__)

MODEL_SONNET_4_6 = "claude-sonnet-4-6"
MODEL_OPUS_4_7 = "claude-opus-4-7"
SUPPORTED_MODELS = (MODEL_SONNET_4_6, MODEL_OPUS_4_7)
DEFAULT_MODEL = MODEL_SONNET_4_6

# Anthropic SDK retries 408/409/429/5xx internally with exponential backoff;
# we just tell it how many attempts to make before giving up.
CLIENT_MAX_RETRIES = 3


def normalize_model(model: str | None) -> str:
    """Clamp any user-provided model to the supported list. Default on unknown/None."""
    return model if model in SUPPORTED_MODELS else DEFAULT_MODEL


class CoachClientUnavailableError(RuntimeError):
    """Raised when the API key is missing or the Anthropic SDK can't be loaded."""


class CoachAuthError(RuntimeError):
    """401 from Anthropic - user's key was rejected. Surface as 400 to the UI."""


class CoachRateLimitError(RuntimeError):
    """Retries exhausted on 429 / 529. Surface as 429 so the UI can wait + retry."""


class CoachUpstreamError(RuntimeError):
    """Other upstream failure (5xx after retries, network). Surface as 502."""


def _load_api_key() -> str:
    key = secret_store.get_api_key()
    if not key:
        raise CoachClientUnavailableError("API key not configured - set it in Settings first")
    return key


def build_client() -> Any:
    """Return a live Anthropic client. Callers should catch ``CoachClientUnavailableError``."""
    try:
        import anthropic
    except ImportError as e:
        raise CoachClientUnavailableError(f"anthropic SDK not installed: {e}") from e
    api_key = _load_api_key()
    return anthropic.Anthropic(api_key=api_key, max_retries=CLIENT_MAX_RETRIES)


def chat_sonnet(
    system_prompt: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    model: str | None = None,
) -> dict[str, Any]:
    """Send a chat completion with automatic retry on transient failures.

    ``model`` defaults to Sonnet 4.6; callers can pass Opus 4.7 or any other
    supported identifier (unknown values are clamped to the default).

    Returns ``{text, usage, model}``. Raises one of:
    - CoachClientUnavailableError: no API key / SDK not installed
    - CoachAuthError: 401 (rejected key)
    - CoachRateLimitError: 429 after retries exhausted
    - CoachUpstreamError: 5xx after retries / network
    """
    import anthropic

    effective_model = normalize_model(model)
    client = build_client()
    try:
        resp = client.messages.create(
            model=effective_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )
    except anthropic.AuthenticationError as e:
        raise CoachAuthError(f"Anthropic rejected the API key: {e}") from e
    except anthropic.RateLimitError as e:
        raise CoachRateLimitError(
            f"Rate limited by Anthropic after {CLIENT_MAX_RETRIES} retries. Try again in a moment."
        ) from e
    except anthropic.APIConnectionError as e:
        raise CoachUpstreamError(f"Could not reach Anthropic: {e}") from e
    except anthropic.APIStatusError as e:
        raise CoachUpstreamError(f"Anthropic returned {e.status_code}: {e}") from e
    text_parts: list[str] = []
    for block in resp.content or []:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))
    usage = getattr(resp, "usage", None)
    return {
        "text": "".join(text_parts),
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
            "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) if usage else 0,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) if usage else 0,
        },
        "model": getattr(resp, "model", effective_model),
    }


async def chat_sonnet_async(
    system_prompt: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    model: str | None = None,
) -> dict[str, Any]:
    """Async boundary for the sync Anthropic SDK call."""
    return await anyio.to_thread.run_sync(
        partial(
            chat_sonnet,
            system_prompt,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
        )
    )
