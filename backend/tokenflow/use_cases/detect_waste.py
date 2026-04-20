"""Use case: run all waste detectors against a session (or recent window) and persist new patterns."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.domain.waste import (
    EventRow,
    MessageRow,
    WasteCandidate,
    detect_big_file_load,
    detect_context_bloat,
    detect_repeat_question,
    detect_tool_loop,
    detect_wrong_model,
)

logger = logging.getLogger(__name__)


def _load_messages(repo: Repository, since: datetime | None = None, session_id: str | None = None) -> list[MessageRow]:
    params: list[Any] = []
    filters = []
    if since is not None:
        filters.append("ts >= ?")
        params.append(since)
    if session_id is not None:
        filters.append("session_id = ?")
        params.append(session_id)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = repo._q(
        f"""
        SELECT session_id, ts, role, model, input_tokens, output_tokens, cache_read_tokens, content_preview
        FROM tf_messages {where}
        ORDER BY ts
        """,
        tuple(params),
    )
    return [MessageRow(*r) for r in rows]


def _load_events(repo: Repository, since: datetime | None = None, session_id: str | None = None) -> list[EventRow]:
    params: list[Any] = []
    filters = []
    if since is not None:
        filters.append("ts >= ?")
        params.append(since)
    if session_id is not None:
        filters.append("session_id = ?")
        params.append(session_id)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = repo._q(
        f"""
        SELECT session_id, ts, event_type,
               payload->>'tool_name'     AS tool_name,
               payload->'tool_input'->>'file_path' AS file_path,
               NULL AS error_hash
        FROM events {where}
        ORDER BY ts
        """,
        tuple(params),
    )
    return [
        EventRow(
            session_id=r[0],
            ts=r[1],
            event_type=r[2],
            tool_name=r[3],
            file_path=r[4],
            error_hash=r[5],
        )
        for r in rows
    ]


def run_detectors(
    repo: Repository,
    *,
    session_id: str | None = None,
    since: datetime | None = None,
    publish: Callable[[dict[str, Any]], None] | None = None,
) -> list[str]:
    """Run all five detectors. Persist any newly detected patterns. Return list of new pattern IDs."""
    msgs = _load_messages(repo, since=since, session_id=session_id)
    evts = _load_events(repo, since=since, session_id=session_id)

    candidates: list[WasteCandidate] = []
    candidates.extend(detect_big_file_load(evts))
    candidates.extend(detect_repeat_question(msgs))
    candidates.extend(detect_wrong_model(msgs))
    candidates.extend(detect_context_bloat(msgs))
    candidates.extend(detect_tool_loop(evts))

    new_ids: list[str] = []
    now = datetime.now(tz=UTC)
    for c in candidates:
        inserted = repo.insert_waste_pattern(
            id=c.dedup_key,
            kind=c.kind,
            severity=c.severity,
            title=c.title,
            meta=c.meta,
            body_html=c.body_html,
            save_tokens=c.save_tokens,
            save_usd=c.save_usd,
            sessions=c.sessions,
            session_id=c.session_id,
            context=json.dumps(c.context),
            detected_at=now,
        )
        if inserted:
            new_ids.append(c.dedup_key)
            if publish:
                publish({"kind": "waste-detected", "waste_kind": c.kind, "severity": c.severity, "id": c.dedup_key})

    logger.info("run_detectors: %d candidates, %d new", len(candidates), len(new_ids))
    return new_ids


def run_hourly_sweep(repo: Repository, publish: Callable[[dict[str, Any]], None] | None = None) -> list[str]:
    """Recent-hour sweep across all sessions — catches cross-session patterns like repeat-question."""
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    return run_detectors(repo, since=since, publish=publish)
