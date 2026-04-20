"""HTTP integration tests for Coach send_message and Better-prompt error paths.

Covers the mapping from client-layer exceptions to HTTP status codes + headers,
input validation, and in-app token-bucket rate limiters. Unit-level mapping of
Anthropic SDK errors to Coach* exceptions is covered by test_coach_retry.py;
this file verifies the full FastAPI → route → client chain.
"""
from __future__ import annotations

import sys
import types
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tokenflow.adapters.persistence import secret_store
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.app import create_app
from tokenflow.adapters.web.rate_limit import better_prompt_limiter, coach_limiter


def _install_fake_anthropic(
    monkeypatch: pytest.MonkeyPatch, *, messages_create: Callable[..., Any]
) -> None:
    """Swap the `anthropic` module with a fake whose `messages.create` is user-controlled."""
    fake = types.ModuleType("anthropic")

    class FakeAnthropic:
        def __init__(self, **_: Any) -> None:
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


def _success_response(text: str = "ok") -> Callable[..., Any]:
    def _factory(**_: Any) -> Any:
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(type="text", text=text)],
            usage=types.SimpleNamespace(
                input_tokens=1,
                output_tokens=1,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            model="claude-sonnet-4-6",
        )

    return _factory


def _raise_fake(exc_name: str, *args: Any, **kwargs: Any) -> Callable[..., Any]:
    """Build a messages_create stub that raises the named fake-anthropic exception.

    Looks up the fake class lazily at call-time so the monkeypatch is definitely
    in place — eagerly evaluating ``sys.modules["anthropic"].FooError(...)`` at
    the call site would capture the *real* class if it's already imported.
    """

    def _factory(**_: Any) -> Any:
        fake = sys.modules["anthropic"]
        exc_cls: type[Exception] = getattr(fake, exc_name)
        raise exc_cls(*args, **kwargs)

    return _factory


@pytest.fixture
def with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend an API key is configured so build_client() proceeds past the gate."""
    monkeypatch.setattr(secret_store, "get_api_key", lambda: "sk-ant-fake")


@pytest.fixture(autouse=True)
def _reset_limiters() -> None:
    """Coach/better-prompt limiters are module-globals; clear between tests so burst
    tests don't leak into other tests (and vice-versa)."""
    coach_limiter._buckets.clear()
    better_prompt_limiter._buckets.clear()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _seed_thread(c: TestClient) -> str:
    r = c.post("/api/coach/threads", json={"title": "t"})
    assert r.status_code == 200
    return str(r.json()["id"])


def _seed_user_message(c: TestClient, session_id: str = "s-err") -> tuple[str, int]:
    repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
    now = datetime.now(tz=UTC)
    repo.upsert_session_started(session_id, "demo", "claude-sonnet-4-6", now)
    repo.insert_message(
        message_id=f"{session_id}-m0",
        session_id=session_id,
        ts=now,
        role="user",
        model=None,
        input_tokens=0,
        output_tokens=0,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        cost_usd=0.0,
        content_preview="show me the schema",
    )
    return session_id, 0


# --------------------------------------------------------------------------- #
# Coach: POST /coach/threads/{id}/messages
# --------------------------------------------------------------------------- #


def test_coach_send_returns_400_when_key_missing() -> None:
    """No API key configured → client-unavailable → 400 with actionable detail."""
    with TestClient(create_app()) as c:
        # Defensive: wipe any stray key a prior test left behind.
        c.delete("/api/settings/api-key")
        tid = _seed_thread(c)
        r = c.post(f"/api/coach/threads/{tid}/messages", json={"content": "hi"})
        assert r.status_code == 400
        assert "API key" in r.json()["detail"]


def test_coach_send_returns_400_on_auth_error(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    _install_fake_anthropic(
        monkeypatch,
        messages_create=_raise_fake("AuthenticationError", "invalid api-key"),
    )
    with TestClient(create_app()) as c:
        tid = _seed_thread(c)
        r = c.post(f"/api/coach/threads/{tid}/messages", json={"content": "hi"})
        assert r.status_code == 400
        assert "rejected" in r.json()["detail"].lower()


def test_coach_send_returns_429_with_retry_after_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    _install_fake_anthropic(
        monkeypatch,
        messages_create=_raise_fake("RateLimitError", "429 Too Many"),
    )
    with TestClient(create_app()) as c:
        tid = _seed_thread(c)
        r = c.post(f"/api/coach/threads/{tid}/messages", json={"content": "hi"})
        assert r.status_code == 429
        assert r.headers.get("retry-after") == "30"


def test_coach_send_returns_502_on_upstream_status(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    _install_fake_anthropic(
        monkeypatch,
        messages_create=_raise_fake("APIStatusError", "502 Bad Gateway", status_code=502),
    )
    with TestClient(create_app()) as c:
        tid = _seed_thread(c)
        r = c.post(f"/api/coach/threads/{tid}/messages", json={"content": "hi"})
        assert r.status_code == 502


def test_coach_send_returns_502_on_connection_error(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    _install_fake_anthropic(
        monkeypatch,
        messages_create=_raise_fake("APIConnectionError", "dns fail"),
    )
    with TestClient(create_app()) as c:
        tid = _seed_thread(c)
        r = c.post(f"/api/coach/threads/{tid}/messages", json={"content": "hi"})
        assert r.status_code == 502


def test_coach_send_rejects_empty_content() -> None:
    with TestClient(create_app()) as c:
        tid = _seed_thread(c)
        r = c.post(f"/api/coach/threads/{tid}/messages", json={"content": ""})
        assert r.status_code == 422


def test_coach_send_rejects_oversized_content() -> None:
    with TestClient(create_app()) as c:
        tid = _seed_thread(c)
        r = c.post(f"/api/coach/threads/{tid}/messages", json={"content": "x" * 20_001})
        assert r.status_code == 422


def test_coach_send_burst_limit_returns_429(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    """coach_limiter has burst=3 — 4 rapid-fire requests means the 4th hits 429
    from our in-app limiter, *not* from upstream (which returns success here)."""
    _install_fake_anthropic(monkeypatch, messages_create=_success_response())
    with TestClient(create_app()) as c:
        tid = _seed_thread(c)
        codes = [
            c.post(f"/api/coach/threads/{tid}/messages", json={"content": "q"}).status_code
            for _ in range(4)
        ]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429


# --------------------------------------------------------------------------- #
# Better-prompt: POST /sessions/{sid}/messages/{idx}/better-prompt
# --------------------------------------------------------------------------- #


def test_better_prompt_llm_returns_400_when_key_missing() -> None:
    with TestClient(create_app()) as c:
        c.delete("/api/settings/api-key")
        sid, idx = _seed_user_message(c)
        r = c.post(f"/api/sessions/{sid}/messages/{idx}/better-prompt?mode=llm")
        assert r.status_code == 400


def test_better_prompt_llm_returns_400_on_auth(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    _install_fake_anthropic(
        monkeypatch,
        messages_create=_raise_fake("AuthenticationError", "bad key"),
    )
    with TestClient(create_app()) as c:
        sid, idx = _seed_user_message(c)
        r = c.post(f"/api/sessions/{sid}/messages/{idx}/better-prompt?mode=llm")
        assert r.status_code == 400


def test_better_prompt_llm_returns_429_on_upstream_rate_limit(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    _install_fake_anthropic(
        monkeypatch,
        messages_create=_raise_fake("RateLimitError", "429"),
    )
    with TestClient(create_app()) as c:
        sid, idx = _seed_user_message(c)
        r = c.post(f"/api/sessions/{sid}/messages/{idx}/better-prompt?mode=llm")
        assert r.status_code == 429
        assert r.headers.get("retry-after") == "30"


def test_better_prompt_llm_returns_502_on_upstream(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    _install_fake_anthropic(
        monkeypatch,
        messages_create=_raise_fake("APIStatusError", "503", status_code=503),
    )
    with TestClient(create_app()) as c:
        sid, idx = _seed_user_message(c)
        r = c.post(f"/api/sessions/{sid}/messages/{idx}/better-prompt?mode=llm")
        assert r.status_code == 502


def test_better_prompt_returns_404_on_idx_out_of_range() -> None:
    with TestClient(create_app()) as c:
        sid, _ = _seed_user_message(c)
        r = c.post(f"/api/sessions/{sid}/messages/999/better-prompt?mode=static")
        assert r.status_code == 404


def test_better_prompt_returns_404_on_nonexistent_session() -> None:
    with TestClient(create_app()) as c:
        r = c.post("/api/sessions/nonexistent/messages/0/better-prompt?mode=static")
        assert r.status_code == 404


def test_better_prompt_llm_burst_limit_returns_429(
    monkeypatch: pytest.MonkeyPatch, with_key: None
) -> None:
    """better_prompt_limiter has burst=3 — 4 distinct LLM calls means the 4th 429s.

    Uses 4 different message indices to bypass the cache (cached entries short-
    circuit the limiter check)."""
    _install_fake_anthropic(monkeypatch, messages_create=_success_response("better"))
    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started("s-lim", "demo", "claude-sonnet-4-6", now)
        for i in range(4):
            repo.insert_message(
                message_id=f"s-lim-m{i}",
                session_id="s-lim",
                ts=now,
                role="user",
                model=None,
                input_tokens=0,
                output_tokens=0,
                cache_creation_tokens=0,
                cache_read_tokens=0,
                cost_usd=0.0,
                content_preview=f"q{i}",
            )
        codes = [
            c.post(f"/api/sessions/s-lim/messages/{i}/better-prompt?mode=llm").status_code
            for i in range(4)
        ]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429


# --------------------------------------------------------------------------- #
# query-quality validation
# --------------------------------------------------------------------------- #


def test_query_quality_rejects_empty_query() -> None:
    with TestClient(create_app()) as c:
        r = c.post("/api/coach/query-quality", json={"query": "", "context": {}})
        assert r.status_code == 422


def test_query_quality_rejects_oversized_query() -> None:
    with TestClient(create_app()) as c:
        r = c.post("/api/coach/query-quality", json={"query": "x" * 20_001, "context": {}})
        assert r.status_code == 422
