from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_bus, get_repo
from tokenflow.adapters.web.pubsub import EventBus

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


async def _flow_generator(
    request: Request,
    repo: Repository,
    bus: EventBus,
    last_event_id: int,
) -> AsyncIterator[str]:
    yield f"event: flow\ndata: {json.dumps(repo.flow_60m())}\n\n"
    q = await bus.subscribe(last_event_id=last_event_id)
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                eid, payload = await asyncio.wait_for(q.get(), timeout=15.0)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            if payload.get("kind") != "message":
                continue
            yield f"id: {eid}\nevent: flow\ndata: {json.dumps(repo.flow_60m())}\n\n"
    finally:
        await bus.unsubscribe(q)


@router.get("/sessions/current/flow/stream")
async def get_current_session_flow_stream(
    request: Request,
    window: str = "60m",
    repo: Repository = Depends(get_repo),
    bus: EventBus = Depends(get_bus),
) -> StreamingResponse:
    if window != "60m":
        raise HTTPException(status_code=400, detail="Only 60m window is supported")
    try:
        last_id = int(request.headers.get("last-event-id") or "0")
    except ValueError:
        last_id = 0
    return StreamingResponse(
        _flow_generator(request, repo, bus, last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
