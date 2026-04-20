"""Thin Anthropic SDK wrapper. Loads API key from ~/.tokenflow/secret.json on demand."""
from __future__ import annotations

import json
import logging
from typing import Any

from tokenflow.adapters.persistence import paths

logger = logging.getLogger(__name__)

MODEL_SONNET_4_6 = "claude-sonnet-4-6"


class CoachClientUnavailableError(RuntimeError):
    """Raised when the API key file is missing or the Anthropic SDK fails to initialise."""


def _load_api_key() -> str:
    secret = paths.secret_path()
    if not secret.exists():
        raise CoachClientUnavailableError("API key not configured - set it in Settings first")
    try:
        payload = json.loads(secret.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CoachClientUnavailableError(f"secret.json is not valid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise CoachClientUnavailableError("secret.json must be a JSON object")
    key = payload.get("anthropic_api_key")
    if not isinstance(key, str) or not key.strip():
        raise CoachClientUnavailableError("secret.json has no anthropic_api_key field")
    return key


def build_client() -> Any:
    """Return a live Anthropic client. Callers should catch ``CoachClientUnavailableError``."""
    try:
        import anthropic
    except ImportError as e:
        raise CoachClientUnavailableError(f"anthropic SDK not installed: {e}") from e
    api_key = _load_api_key()
    return anthropic.Anthropic(api_key=api_key)


def chat_sonnet(
    system_prompt: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Send a chat completion to Sonnet 4.6. Returns ``{text, usage}``."""
    client = build_client()
    resp = client.messages.create(
        model=MODEL_SONNET_4_6,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=messages,
    )
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
        "model": getattr(resp, "model", MODEL_SONNET_4_6),
    }
