from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from tokenflow.adapters.web.deps import get_bus
from tokenflow.adapters.web.pubsub import EventBus

router = APIRouter(tags=["events"])


def _as_int(value: object) -> int:
    """Tolerant coercion — SSE payloads come from arbitrary sources."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _as_ticker(payload: dict[str, object]) -> dict[str, object] | None:
    """Shape a bus event into the ticker-event contract the frontend expects."""
    now_hhmmss = datetime.now(tz=UTC).astimezone().strftime("%H:%M:%S")
    now_id = int(datetime.now(tz=UTC).timestamp() * 1000)

    if payload.get("kind") == "message":
        tokens = _as_int(payload.get("tokens_in")) + _as_int(payload.get("tokens_out"))
        role = str(payload.get("role") or "assistant")
        model = str(payload.get("model") or "")
        label = f"{role} · {model}".strip(" ·")
        return {"id": now_id, "t": "reply", "label": label or role, "tk": tokens, "time": now_hhmmss}

    if payload.get("kind") == "waste-detected":
        severity = str(payload.get("severity") or "waste")
        waste_kind = str(payload.get("waste_kind") or "waste")
        return {"id": now_id, "t": "waste", "label": f"{severity} {waste_kind}", "tk": 0, "time": now_hhmmss}

    if payload.get("kind") == "budget-threshold":
        threshold = payload.get("threshold_pct") or "budget"
        spent = payload.get("spent")
        budget = payload.get("budget")
        return {"id": now_id, "t": "budget", "label": f"Budget {threshold}% reached · ${spent} / ${budget}", "tk": 0, "time": now_hhmmss}

    if payload.get("kind") == "context-saturation":
        pct = int(float(payload.get("pct") or 0) * 100)
        return {"id": now_id, "t": "context", "label": f"Context saturation {pct}%", "tk": 0, "time": now_hhmmss}

    if payload.get("kind") == "opus-overuse":
        pct = int(float(payload.get("share") or 0) * 100)
        return {"id": now_id, "t": "opus", "label": f"Opus usage {pct}% of spend", "tk": 0, "time": now_hhmmss}

    if payload.get("kind") == "api-error":
        source = str(payload.get("source") or "API")
        status = str(payload.get("status") or "error")
        return {"id": now_id, "t": "api_error", "label": f"{source} {status}", "tk": 0, "time": now_hhmmss}

    hook_event = payload.get("hook_event_name")
    if not isinstance(hook_event, str):
        return None
    tool = payload.get("tool_name")
    if hook_event == "PostToolUse" and isinstance(tool, str):
        kind = {
            "Bash": "bash",
            "Edit": "edited",
            "Write": "edited",
            "Read": "read",
            "Grep": "grep",
            "Glob": "grep",
        }.get(tool, "tool")
        label = tool
    else:
        kind = "tool"
        label = hook_event
    return {"id": now_id, "t": kind, "label": label, "tk": 0, "time": now_hhmmss}


async def _generator(
    request: Request, bus: EventBus, last_event_id: int
) -> AsyncIterator[str]:
    yield ": connected\n\n"
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
            ticker = _as_ticker(payload)
            if ticker is None:
                continue
            yield f"id: {eid}\nevent: ticker\ndata: {json.dumps(ticker)}\n\n"
    finally:
        await bus.unsubscribe(q)


@router.get("/events/stream")
async def events_stream(
    request: Request,
    bus: EventBus = Depends(get_bus),
) -> StreamingResponse:
    last_id_header = request.headers.get("last-event-id") or "0"
    try:
        last_id = int(last_id_header)
    except ValueError:
        last_id = 0
    return StreamingResponse(
        _generator(request, bus, last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
