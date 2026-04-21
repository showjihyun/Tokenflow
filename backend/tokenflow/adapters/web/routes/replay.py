from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from tokenflow.adapters.coach.client import (
    MODEL_SONNET_4_6,
    CoachAuthError,
    CoachClientUnavailableError,
    CoachRateLimitError,
    CoachUpstreamError,
    chat_sonnet_async,
)
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.blocking import run_blocking
from tokenflow.adapters.web.deps import get_bus, get_repo
from tokenflow.adapters.web.pubsub import EventBus
from tokenflow.adapters.web.rate_limit import better_prompt_limiter
from tokenflow.domain.better_prompt import LLM_SYSTEM_PROMPT, llm_user_prompt, static_suggestion

router = APIRouter(tags=["replay"])


def _publish_api_error(bus: EventBus, *, source: str, status: str) -> None:
    bus.publish({"kind": "api-error", "source": source, "status": status})


@router.get("/sessions")
def list_sessions(
    project: str | None = None,
    has_waste: bool = False,
    q: str | None = None,
    limit: int = 50,
    repo: Repository = Depends(get_repo),
) -> list[dict[str, Any]]:
    return repo.list_sessions(project=project, has_waste=has_waste, q=q, limit=limit)


@router.get("/sessions/{session_id}/replay")
def session_replay(
    session_id: str,
    include_paused: bool = False,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    events = repo.session_replay(session_id, include_paused=include_paused)
    if not events:
        return {"session_id": session_id, "events": [], "summary": {"messages": 0, "tokens": 0, "cost": 0.0}}
    tokens = sum(e["tokens_in"] + e["tokens_out"] for e in events)
    cost = sum(e["cost_usd"] for e in events)
    return {
        "session_id": session_id,
        "events": events,
        "summary": {
            "messages": len(events),
            "tokens": tokens,
            "cost": round(cost, 4),
        },
    }


@router.get("/sessions/{session_id}/export")
def export_session(
    session_id: str,
    include_paused: bool = False,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    replay = session_replay(session_id=session_id, include_paused=include_paused, repo=repo)
    return {
        "schema": "tokenflow.export.v1",
        "session_id": session_id,
        "summary": replay["summary"],
        "events": replay["events"],
    }


@router.post("/sessions/{session_id}/messages/{idx}/better-prompt")
async def better_prompt(
    session_id: str,
    idx: int,
    mode: Literal["static", "llm"] = "static",
    waste_reason: str | None = None,
    repo: Repository = Depends(get_repo),
    bus: EventBus = Depends(get_bus),
) -> dict[str, Any]:
    cached = await run_blocking(repo.get_better_prompt, session_id, idx, mode)
    if cached:
        return cached

    events = await run_blocking(repo.session_replay, session_id)
    if idx < 0 or idx >= len(events):
        raise HTTPException(404, "message index out of range")
    msg = events[idx]

    # LLM mode is billable and can run away under a buggy client — gate it.
    # Static mode is free and deterministic, so it stays unlimited.
    if mode == "llm":
        allowed, retry = better_prompt_limiter.check("better-prompt")
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too Many Requests. Retry in {retry:.1f}s.",
                headers={"Retry-After": str(max(1, int(retry + 0.5)))},
            )

    if mode == "static":
        text, est = static_suggestion(waste_reason, file_path=None)
        await run_blocking(
            repo.cache_better_prompt,
            session_id=session_id,
            msg_index=idx,
            mode=mode,
            suggested_text=text,
            est_save_tokens=est,
        )
        return {"suggested_text": text, "est_save_tokens": est, "mode": "static", "cached": False}

    # LLM mode
    user_prompt = llm_user_prompt(
        query=msg["preview"] or "(no preview)",
        tokens_in=msg["tokens_in"],
        tokens_out=msg["tokens_out"],
        model=msg["model"],
        waste_reason=waste_reason,
    )
    config = await run_blocking(repo.get_config)
    chosen_model = str(config.get("llm_model") or "") or None
    try:
        resp = await chat_sonnet_async(
            system_prompt=LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=200,
            temperature=0.2,
            model=chosen_model,
        )
    except CoachClientUnavailableError as e:
        _publish_api_error(bus, source="Better prompt", status="unavailable")
        raise HTTPException(400, f"LLM mode unavailable: {e}") from e
    except CoachAuthError as e:
        _publish_api_error(bus, source="Better prompt", status="auth rejected")
        raise HTTPException(400, str(e)) from e
    except CoachRateLimitError as e:
        _publish_api_error(bus, source="Better prompt", status="rate limited")
        raise HTTPException(429, str(e), headers={"Retry-After": "30"}) from e
    except CoachUpstreamError as e:
        _publish_api_error(bus, source="Better prompt", status="upstream error")
        raise HTTPException(502, str(e)) from e

    text = resp["text"].strip()
    est = max(0, msg["tokens_in"] // 3)
    await run_blocking(
        repo.cache_better_prompt,
        session_id=session_id,
        msg_index=idx,
        mode=mode,
        suggested_text=text,
        est_save_tokens=est,
    )
    return {"suggested_text": text, "est_save_tokens": est, "mode": "llm", "cached": False, "model": MODEL_SONNET_4_6}
