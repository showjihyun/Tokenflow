from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_bus, get_repo
from tokenflow.adapters.web.pubsub import EventBus
from tokenflow.use_cases.detect_waste import run_detectors, run_hourly_sweep

router = APIRouter(tags=["wastes"])


@router.get("/wastes")
async def list_wastes(
    status: Literal["active", "dismissed"] = "active",
    repo: Repository = Depends(get_repo),
) -> list[dict[str, Any]]:
    return repo.list_wastes(status=status)


@router.post("/wastes/{waste_id}/dismiss")
async def dismiss(waste_id: str, repo: Repository = Depends(get_repo)) -> dict[str, bool]:
    ok = repo.mark_waste_dismissed(waste_id)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@router.post("/wastes/{waste_id}/apply")
async def apply(waste_id: str, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    waste = repo.get_waste(waste_id)
    if not waste:
        raise HTTPException(404)
    kind = waste["kind"]
    if kind == "wrong-model":
        repo.upsert_routing_rule(
            rule_id=f"auto-{waste_id[:8]}",
            condition_pattern="Simple edits (auto from waste)",
            target_model="claude-haiku-4-5",
            enabled=True,
            priority=10,
        )
        outcome = "routing-rule-added"
    elif kind == "big-file-load":
        outcome = "claude-md-snippet-proposed"
    elif kind == "repeat-question":
        outcome = "claude-md-faq-proposed"
    elif kind == "context-bloat":
        outcome = "user-action-required"
    else:
        outcome = "claude-md-snippet-proposed"
    repo.mark_waste_applied(waste_id, outcome)
    return {"ok": True, "outcome": outcome}


@router.post("/wastes/scan")
async def scan(
    session_id: str | None = None,
    repo: Repository = Depends(get_repo),
    bus: EventBus = Depends(get_bus),
) -> dict[str, Any]:
    """Run the detectors on demand (helpful from the UI / E2E tests)."""
    since = datetime.now(tz=UTC) - timedelta(hours=24) if session_id is None else None
    new_ids = run_detectors(repo, session_id=session_id, since=since, publish=bus.publish)
    return {"new": new_ids}


@router.post("/wastes/sweep")
async def sweep(
    repo: Repository = Depends(get_repo),
    bus: EventBus = Depends(get_bus),
) -> dict[str, Any]:
    new_ids = run_hourly_sweep(repo, publish=bus.publish)
    return {"new": new_ids}
