"""Session lifecycle + messages + hook events + pricing lookups."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, TypedDict

import duckdb

from tokenflow.adapters.persistence._base import _BaseRepo


class MessageInsert(TypedDict):
    message_id: str
    session_id: str
    ts: datetime
    role: str
    model: str | None
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    cost_usd: float
    content_preview: str | None
    paused: bool


class _SessionMixin(_BaseRepo):
    # ---------- sessions ----------
    def upsert_session_started(
        self,
        session_id: str,
        project_slug: str,
        model: str,
        started_at: datetime,
        context_window_size: int = 200_000,
    ) -> None:
        self._exec(
            """
            INSERT INTO sessions (session_id, project_slug, model, started_at, context_window_size)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (session_id, project_slug, model, started_at, context_window_size),
        )

    def mark_session_ended(self, session_id: str, ended_at: datetime) -> None:
        self._exec(
            "UPDATE sessions SET ended_at = COALESCE(ended_at, ?) WHERE session_id = ?",
            (ended_at, session_id),
        )

    def mark_inactive_sessions_ended(self, *, cutoff: datetime) -> int:
        rows = self._q(
            """
            SELECT s.session_id
            FROM sessions s
            WHERE s.ended_at IS NULL
              AND COALESCE(
                (SELECT MAX(m.ts) FROM tf_messages m WHERE m.session_id = s.session_id),
                (SELECT MAX(e.ts) FROM events e WHERE e.session_id = s.session_id),
                s.started_at
              ) < ?
            """,
            (cutoff,),
        )
        ids = [r[0] for r in rows]
        for session_id in ids:
            self.mark_session_ended(session_id, cutoff)
        return len(ids)

    def mark_session_compacted(self, session_id: str, ts: datetime) -> None:
        self._exec(
            "UPDATE sessions SET compacted = TRUE, compacted_at = ? WHERE session_id = ?",
            (ts, session_id),
        )

    def get_current_session(self) -> dict[str, Any] | None:
        rows = self._q(
            """
            SELECT s.session_id, s.project_slug, s.model, s.started_at, s.ended_at,
                   s.total_input_tokens, s.total_output_tokens,
                   COALESCE(s.total_cache_creation_tokens, 0),
                   COALESCE(s.total_cache_read_tokens, 0),
                   s.context_window_size, s.compacted,
                    (SELECT MAX(ts) FROM tf_messages m WHERE m.session_id = s.session_id AND COALESCE(m.paused, FALSE) = FALSE) AS last_msg
            FROM sessions s
            WHERE s.ended_at IS NULL
            ORDER BY s.started_at DESC
            LIMIT 1
            """
        )
        if not rows:
            return None
        (sid, proj, model, started, ended, ti, to, cc, cr, cw, compacted, _last) = rows[0]
        context_used = self._estimate_context_used(sid)
        cost = self._estimate_session_cost(sid)
        return {
            "id": sid,
            "startedAt": started.isoformat() if started else None,
            "project": proj,
            "model": model,
            "tokens": {"input": ti, "output": to, "cacheRead": cr, "cacheWrite": cc},
            "contextWindow": cw,
            "contextUsed": context_used,
            "costUSD": round(cost, 2),
            "messages": self._count_messages(sid),
            "compacted": bool(compacted),
            "ended": ended.isoformat() if ended else None,
        }

    def _count_messages(self, session_id: str) -> int:
        rows = self._q(
            "SELECT COUNT(*) FROM tf_messages WHERE session_id = ? AND COALESCE(paused, FALSE) = FALSE",
            (session_id,),
        )
        return int(rows[0][0]) if rows else 0

    def _estimate_context_used(self, session_id: str) -> int:
        """Best-effort: last assistant message's input_tokens (closest to live context size)."""
        rows = self._q(
            """
            SELECT input_tokens + cache_read_tokens + cache_creation_tokens
            FROM tf_messages
            WHERE session_id = ? AND role = 'assistant' AND COALESCE(paused, FALSE) = FALSE
            ORDER BY ts DESC LIMIT 1
            """,
            (session_id,),
        )
        if not rows:
            return 0
        return int(rows[0][0] or 0)

    def _estimate_session_cost(self, session_id: str) -> float:
        rows = self._q(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM tf_messages WHERE session_id = ? AND COALESCE(paused, FALSE) = FALSE",
            (session_id,),
        )
        return float(rows[0][0]) if rows else 0.0

    # ---------- messages ----------
    def insert_message(
        self,
        message_id: str,
        session_id: str,
        ts: datetime,
        role: str,
        model: str | None,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int,
        cache_read_tokens: int,
        cost_usd: float,
        content_preview: str | None,
        paused: bool = False,
    ) -> bool:
        """Returns True if inserted, False if duplicate."""
        try:
            self._exec(
                """
                INSERT INTO tf_messages (
                  message_id, session_id, ts, role, model,
                  input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                  cost_usd, content_preview, paused
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id, session_id, ts, role, model,
                    input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                    cost_usd, content_preview, paused,
                ),
            )
            return True
        except duckdb.ConstraintException:
            return False

    def insert_messages_batch(self, messages: list[MessageInsert]) -> set[str]:
        """Insert many transcript messages while holding the repository lock once."""
        inserted: set[str] = set()
        if not messages:
            return inserted
        sql = """
            INSERT INTO tf_messages (
              message_id, session_id, ts, role, model,
              input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
              cost_usd, content_preview, paused
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        with self._lock:
            for message in messages:
                try:
                    self._conn.execute(
                        sql,
                        (
                            message["message_id"],
                            message["session_id"],
                            message["ts"],
                            message["role"],
                            message["model"],
                            message["input_tokens"],
                            message["output_tokens"],
                            message["cache_creation_tokens"],
                            message["cache_read_tokens"],
                            message["cost_usd"],
                            message["content_preview"],
                            message["paused"],
                        ),
                    )
                    inserted.add(message["message_id"])
                except duckdb.ConstraintException:
                    continue
        return inserted

    def update_session_totals_from_messages(self, session_id: str) -> None:
        self._exec(
            """
            UPDATE sessions SET
              total_input_tokens = COALESCE((SELECT SUM(input_tokens) FROM tf_messages WHERE session_id = ? AND COALESCE(paused, FALSE) = FALSE), 0),
              total_output_tokens = COALESCE((SELECT SUM(output_tokens) FROM tf_messages WHERE session_id = ? AND COALESCE(paused, FALSE) = FALSE), 0),
              total_cache_creation_tokens = COALESCE((SELECT SUM(cache_creation_tokens) FROM tf_messages WHERE session_id = ? AND COALESCE(paused, FALSE) = FALSE), 0),
              total_cache_read_tokens = COALESCE((SELECT SUM(cache_read_tokens) FROM tf_messages WHERE session_id = ? AND COALESCE(paused, FALSE) = FALSE), 0)
            WHERE session_id = ?
            """,
            (session_id, session_id, session_id, session_id, session_id),
        )

    # ---------- events (hook log) ----------
    def insert_event(
        self,
        event_id: str,
        session_id: str,
        event_type: str,
        ts: datetime,
        payload: dict[str, Any],
        raw_hash: str,
    ) -> bool:
        try:
            self._exec(
                """
                INSERT INTO events (event_id, session_id, event_type, ts, payload, raw_hash)
                VALUES (?, ?, ?, ?, ?::JSON, ?)
                """,
                (event_id, session_id, event_type, ts, json.dumps(payload), raw_hash),
            )
            return True
        except duckdb.ConstraintException:
            return False

    def latest_event_at(self) -> datetime | None:
        """Timestamp of the most recent hook event, or None when nothing has been ingested."""
        rows = self._q("SELECT MAX(ts) FROM events")
        if not rows or rows[0][0] is None:
            return None
        value = rows[0][0]
        if isinstance(value, datetime):
            return value
        return None

    def recent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._q(
            """
            SELECT event_id, session_id, event_type, ts, payload
            FROM events
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        )
        out: list[dict[str, Any]] = []
        for eid, sid, etype, ts, payload in rows:
            try:
                p = json.loads(payload) if isinstance(payload, str) else payload
            except (TypeError, json.JSONDecodeError):
                p = {}
            out.append(
                {"id": eid, "session_id": sid, "type": etype, "ts": ts.isoformat(), "payload": p}
            )
        return out

    # ---------- pricing ----------
    def pricing_for(
        self, model: str, at: datetime | None = None
    ) -> tuple[float, float, float, float] | None:
        at = at or datetime.now(tz=UTC)
        rows = self._q(
            """
            SELECT input_per_mtok, output_per_mtok, cache_write_per_mtok, cache_read_per_mtok
            FROM pricing_rates
            WHERE model = ? AND effective_at <= ?
            ORDER BY effective_at DESC LIMIT 1
            """,
            (model, at),
        )
        if rows:
            return float(rows[0][0]), float(rows[0][1]), float(rows[0][2]), float(rows[0][3])
        rows = self._q(
            "SELECT input_per_mtok, output_per_mtok, cache_write_per_mtok, cache_read_per_mtok "
            "FROM pricing_rates WHERE model = ? ORDER BY effective_at DESC LIMIT 1",
            (model,),
        )
        if rows:
            return float(rows[0][0]), float(rows[0][1]), float(rows[0][2]), float(rows[0][3])
        return None
