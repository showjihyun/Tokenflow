from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from tokenflow.adapters.coach.client import (
    MODEL_SONNET_4_6,
    CoachClientUnavailableError,
    chat_sonnet,
)
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo
from tokenflow.domain.better_prompt import LLM_SYSTEM_PROMPT, llm_user_prompt, static_suggestion

router = APIRouter(tags=["replay"])


@router.get("/sessions")
async def list_sessions(
    project: str | None = None,
    has_waste: bool = False,
    q: str | None = None,
    limit: int = 50,
    repo: Repository = Depends(get_repo),
) -> list[dict[str, Any]]:
    return repo.list_sessions(project=project, has_waste=has_waste, q=q, limit=limit)


@router.get("/sessions/{session_id}/replay")
async def session_replay(session_id: str, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    events = repo.session_replay(session_id)
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


@router.post("/sessions/{session_id}/messages/{idx}/better-prompt")
async def better_prompt(
    session_id: str,
    idx: int,
    mode: Literal["static", "llm"] = "static",
    waste_reason: str | None = None,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    cached = repo.get_better_prompt(session_id, idx, mode)
    if cached:
        return cached

    events = repo.session_replay(session_id)
    if idx < 0 or idx >= len(events):
        raise HTTPException(404, "message index out of range")
    msg = events[idx]

    if mode == "static":
        text, est = static_suggestion(waste_reason, file_path=None)
        repo.cache_better_prompt(session_id=session_id, msg_index=idx, mode=mode,
                                 suggested_text=text, est_save_tokens=est)
        return {"suggested_text": text, "est_save_tokens": est, "mode": "static", "cached": False}

    # LLM mode
    user_prompt = llm_user_prompt(
        query=msg["preview"] or "(no preview)",
        tokens_in=msg["tokens_in"],
        tokens_out=msg["tokens_out"],
        model=msg["model"],
        waste_reason=waste_reason,
    )
    try:
        resp = chat_sonnet(
            system_prompt=LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=200,
            temperature=0.2,
        )
    except CoachClientUnavailableError as e:
        raise HTTPException(400, f"LLM mode unavailable: {e}") from e
    except Exception as e:
        raise HTTPException(502, f"Claude API error: {e}") from e

    text = resp["text"].strip()
    est = max(0, msg["tokens_in"] // 3)
    repo.cache_better_prompt(session_id=session_id, msg_index=idx, mode=mode,
                             suggested_text=text, est_save_tokens=est)
    return {"suggested_text": text, "est_save_tokens": est, "mode": "llm", "cached": False, "model": MODEL_SONNET_4_6}
