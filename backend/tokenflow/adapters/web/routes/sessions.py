from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["sessions"])

_EMPTY_SESSION: dict[str, Any] = {
    "id": None,
    "startedAt": None,
    "project": None,
    "model": None,
    "tokens": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
    "contextWindow": 200000,
    "contextUsed": 0,
    "costUSD": 0.0,
    "messages": 0,
    "compacted": False,
    "ended": None,
    "active": False,
}


@router.get("/sessions/current")
async def get_current_session(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    session = repo.get_current_session()
    if session is None:
        return _EMPTY_SESSION
    session["active"] = True
    return session


@router.get("/sessions/current/flow")
async def get_current_session_flow(
    window: str = "60m",
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    if window != "60m":
        raise HTTPException(status_code=400, detail="Only 60m window is supported in Phase C")
    return repo.flow_60m()
