from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
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


def _added_lines_from_diff(diff: str) -> list[str]:
    lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return lines


def _session_cwd(repo: Repository, session_id: str | None) -> Path | None:
    if not session_id:
        return None
    rows = repo._q(
        """
        SELECT json_extract_string(payload, '$.cwd')
        FROM events
        WHERE session_id = ?
          AND json_extract_string(payload, '$.cwd') IS NOT NULL
        ORDER BY ts ASC
        LIMIT 1
        """,
        (session_id,),
    )
    if not rows or not rows[0][0]:
        return None
    try:
        path = Path(str(rows[0][0])).expanduser().resolve()
    except OSError:
        return None
    return path if path.exists() and path.is_dir() else None


@router.get("/wastes")
def list_wastes(
    status: Literal["active", "dismissed"] = "active",
    repo: Repository = Depends(get_repo),
) -> list[dict[str, Any]]:
    return repo.list_wastes(status=status)


@router.post("/wastes/{waste_id}/dismiss")
def dismiss(waste_id: str, repo: Repository = Depends(get_repo)) -> dict[str, bool]:
    ok = repo.mark_waste_dismissed(waste_id)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@router.post("/wastes/{waste_id}/apply")
def apply(waste_id: str, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
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


@router.post("/wastes/{waste_id}/apply-confirm")
def apply_confirm(waste_id: str, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    waste = repo.get_waste(waste_id)
    if not waste:
        raise HTTPException(404)
    preview = _claude_md_preview(waste)
    if not preview:
        return {"ok": True, "applied": False, "reason": "no-file-preview"}
    cwd = _session_cwd(repo, waste.get("session_id"))
    if cwd is None:
        raise HTTPException(409, "session cwd is unavailable")
    target = (cwd / "CLAUDE.md").resolve()
    if cwd not in target.parents and target != cwd:
        raise HTTPException(400, "target path escaped project")
    lines = _added_lines_from_diff(str(preview["diff"]))
    if not lines:
        raise HTTPException(400, "empty preview")
    block = "\n".join(lines).strip()
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if block in existing:
        return {"ok": True, "applied": False, "path": str(target), "reason": "already-present"}
    prefix = "\n\n" if existing.strip() else ""
    target.write_text(existing.rstrip() + prefix + block + "\n", encoding="utf-8")
    return {"ok": True, "applied": True, "path": str(target)}


@router.post("/wastes/scan")
def scan(
    session_id: str | None = None,
    repo: Repository = Depends(get_repo),
    bus: EventBus = Depends(get_bus),
) -> dict[str, Any]:
    """Run the detectors on demand (helpful from the UI / E2E tests)."""
    since = datetime.now(tz=UTC) - timedelta(hours=24) if session_id is None else None
    new_ids = run_detectors(repo, session_id=session_id, since=since, publish=bus.publish)
    return {"new": new_ids}


@router.post("/wastes/sweep")
def sweep(
    repo: Repository = Depends(get_repo),
    bus: EventBus = Depends(get_bus),
) -> dict[str, Any]:
    new_ids = run_hourly_sweep(repo, publish=bus.publish)
    return {"new": new_ids}
