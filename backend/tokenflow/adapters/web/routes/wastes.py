from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_bus, get_repo
from tokenflow.adapters.web.pubsub import EventBus
from tokenflow.use_cases.detect_waste import run_detectors, run_hourly_sweep

router = APIRouter(tags=["wastes"])


def _claude_md_preview(waste: dict[str, Any]) -> dict[str, Any] | None:
    kind = str(waste.get("kind") or "")
    title = str(waste.get("title") or kind)
    meta = str(waste.get("meta") or "")
    snippets = {
        "big-file-load": [
            "## Token Flow: Large file reads",
            "- Before reading large files, prefer grep/glob to locate the exact symbol or section.",
            "- If full-file context is required, summarize why and read the smallest relevant range first.",
        ],
        "repeat-question": [
            "## Token Flow: Repeated questions",
            f"- Reuse the saved answer for: {title}.",
            "- Add durable project facts here after resolving repeated questions.",
        ],
        "tool-loop": [
            "## Token Flow: Tool loop recovery",
            f"- If this pattern repeats ({meta or title}), stop and inspect the prior command/error before retrying.",
            "- Prefer one diagnostic command, then update the command or ask for missing context.",
        ],
    }
    lines = snippets.get(kind)
    if not lines:
        return None
    return {
        "path": "CLAUDE.md",
        "title": f"Append {kind} guidance",
        "diff": "\n".join(["--- CLAUDE.md", "+++ CLAUDE.md", "@@", *[f"+{line}" for line in lines]]),
    }


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
    preview = _claude_md_preview(waste)
    if kind == "wrong-model":
        repo.upsert_routing_rule(
            rule_id=f"auto-{waste_id[:8]}",
            condition_pattern="Simple edits (auto from waste)",
            target_model="claude-haiku-4-5",
            enabled=True,
            priority=10,
        )
        outcome = "routing-rule-added"
        preview = {
            "path": "settings/routing-rules",
            "title": "Add auto-routing rule",
            "diff": (
                "+ condition: Simple edits (auto from waste)\n"
                "+ target_model: claude-haiku-4-5\n"
                "+ priority: 10"
            ),
        }
    elif kind == "big-file-load":
        outcome = "claude-md-snippet-proposed"
    elif kind == "repeat-question":
        outcome = "claude-md-faq-proposed"
    elif kind == "context-bloat":
        outcome = "user-action-required"
    else:
        outcome = "claude-md-snippet-proposed"
    repo.mark_waste_applied(waste_id, outcome)
    return {"ok": True, "outcome": outcome, "preview": preview}


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
