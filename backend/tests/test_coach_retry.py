"""Tests for the Coach client's retry + error-mapping behavior.

Uses a fake ``anthropic`` module installed into sys.modules so we can drive the
client into specific error paths without touching the network. Keeps the
Anthropic SDK's real retry logic out of scope — we only verify that *our* error
mapping is correct and that ``max_retries`` is being passed through.
"""
from __future__ import annotations

import sys
import types
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from tokenflow.adapters.persistence import secret_store


def _install_fake_anthropic(
    monkeypatch: pytest.MonkeyPatch,
    *,
    messages_create: Any,
) -> MagicMock:
    """Replace the `anthropic` import with a fake module whose Anthropic client's
    messages.create delegates to the provided callable."""
    fake = types.ModuleType("anthropic")

    class FakeAnthropic:
        last_init_kwargs: ClassVar[dict[str, Any]] = {}

        def __init__(self, **kwargs: Any) -> None:
            FakeAnthropic.last_init_kwargs = kwargs
            self.messages = types.SimpleNamespace(create=messages_create)

    class AuthenticationError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class APIStatusError(Exception):
        def __init__(self, msg: str, status_code: int = 500) -> None:
            super().__init__(msg)
            self.status_code = status_code

    fake.Anthropic = FakeAnthropic  # type: ignore[attr-defined]
    fake.AuthenticationError = AuthenticationError  # type: ignore[attr-defined]
    fake.RateLimitError = RateLimitError  # type: ignore[attr-defined]
    fake.APIConnectionError = APIConnectionError  # type: ignore[attr-defined]
    fake.APIStatusError = APIStatusError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    return FakeAnthropic  # type: ignore[return-value]


@pytest.fixture
def _with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend a key is configured so build_client() proceeds past the gate."""
    monkeypatch.setattr(secret_store, "get_api_key", lambda: "sk-ant-fake")


def test_client_is_constructed_with_max_retries(_with_key: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tokenflow.adapters.coach import client as coach_client

    def success(**_: Any) -> Any:
        resp = types.SimpleNamespace(
            content=[types.SimpleNamespace(type="text", text="hi")],
            usage=types.SimpleNamespace(input_tokens=1, output_tokens=2,
                                        cache_creation_input_tokens=0, cache_read_input_tokens=0),
            model=coach_client.MODEL_SONNET_4_6,
        )
        return resp

    fake_cls = _install_fake_anthropic(monkeypatch, messages_create=success)
    out = coach_client.chat_sonnet("sys", [{"role": "user", "content": "hello"}])
    assert out["text"] == "hi"
    assert fake_cls.last_init_kwargs["max_retries"] == coach_client.CLIENT_MAX_RETRIES


def test_rate_limit_error_mapped(_with_key: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tokenflow.adapters.coach import client as coach_client

    # Mutate after we have the fake class to raise its own exception type.
    fake_cls = _install_fake_anthropic(
        monkeypatch,
        messages_create=lambda **_: (_ for _ in ()).throw(
            sys.modules["anthropic"].RateLimitError("429 Too Many Requests")
        ),
    )
    _ = fake_cls
    with pytest.raises(coach_client.CoachRateLimitError):
        coach_client.chat_sonnet("sys", [{"role": "user", "content": "q"}])


def test_auth_error_mapped(_with_key: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tokenflow.adapters.coach import client as coach_client

    _install_fake_anthropic(
        monkeypatch,
        messages_create=lambda **_: (_ for _ in ()).throw(
            sys.modules["anthropic"].AuthenticationError("invalid api-key")
        ),
    )
    with pytest.raises(coach_client.CoachAuthError):
        coach_client.chat_sonnet("sys", [{"role": "user", "content": "q"}])


def test_api_status_error_mapped_to_upstream(_with_key: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tokenflow.adapters.coach import client as coach_client

    _install_fake_anthropic(
        monkeypatch,
        messages_create=lambda **_: (_ for _ in ()).throw(
            sys.modules["anthropic"].APIStatusError("502 Bad Gateway", status_code=502)
        ),
    )
    with pytest.raises(coach_client.CoachUpstreamError):
        coach_client.chat_sonnet("sys", [{"role": "user", "content": "q"}])


def test_connection_error_mapped_to_upstream(_with_key: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tokenflow.adapters.coach import client as coach_client

    _install_fake_anthropic(
        monkeypatch,
        messages_create=lambda **_: (_ for _ in ()).throw(
            sys.modules["anthropic"].APIConnectionError("DNS failure")
        ),
    )
    with pytest.raises(coach_client.CoachUpstreamError):
        coach_client.chat_sonnet("sys", [{"role": "user", "content": "q"}])
