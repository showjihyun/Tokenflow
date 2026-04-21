"""Coach threads/messages, better-prompt cache, session replay + session list."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from tokenflow.adapters.persistence._base import _BaseRepo


class _CoachReplayMixin(_BaseRepo):
    # ---------- Coach ----------
    def create_coach_thread(self, thread_id: str, title: str | None = None) -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        self._exec(
            "INSERT INTO tf_coach_threads (id, title, started_at, last_msg_at) "
            "VALUES (?, ?, ?, ?)",
            (thread_id, title, now, now),
        )
        return {
            "id": thread_id,
            "title": title,
            "started_at": now.isoformat(),
            "last_msg_at": now.isoformat(),
            "cost_usd_total": 0.0,
        }

    def list_coach_threads(self) -> list[dict[str, Any]]:
        rows = self._q(
            "SELECT id, title, started_at, last_msg_at, cost_usd_total "
            "FROM tf_coach_threads ORDER BY last_msg_at DESC"
        )
        return [
            {
                "id": r[0],
                "title": r[1],
                "started_at": r[2].isoformat() if r[2] else None,
                "last_msg_at": r[3].isoformat() if r[3] else None,
                "cost_usd_total": float(r[4] or 0),
            }
            for r in rows
        ]

    def list_coach_messages(self, thread_id: str) -> list[dict[str, Any]]:
        rows = self._q(
            """
            SELECT id, role, content, ts, input_tokens, output_tokens, cost_usd
            FROM tf_coach_messages WHERE thread_id = ? ORDER BY ts
            """,
            (thread_id,),
        )
        return [
            {
                "id": r[0],
                "role": r[1],
                "content": r[2],
                "ts": r[3].isoformat() if r[3] else None,
                "input_tokens": int(r[4] or 0),
                "output_tokens": int(r[5] or 0),
                "cost_usd": float(r[6] or 0),
            }
            for r in rows
        ]

    def insert_coach_message(
        self,
        *,
        message_id: str,
        thread_id: str,
        role: str,
        content: str,
        ts: datetime,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        context_snapshot: dict[str, Any] | None = None,
    ) -> None:
        self._exec(
            """
            INSERT INTO tf_coach_messages (
                id, thread_id, role, content, ts, context_snapshot_json,
                input_tokens, output_tokens, cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?::JSON, ?, ?, ?)
            """,
            (
                message_id, thread_id, role, content, ts,
                json.dumps(context_snapshot or {}),
                input_tokens, output_tokens, cost_usd,
            ),
        )
        self._exec(
            "UPDATE tf_coach_threads SET last_msg_at = ?, cost_usd_total = cost_usd_total + ? "
            "WHERE id = ?",
            (ts, cost_usd, thread_id),
        )

    # ---------- Better prompt cache ----------
    def get_better_prompt(
        self, session_id: str, msg_index: int, mode: str
    ) -> dict[str, Any] | None:
        rows = self._q(
            "SELECT suggested_text, est_save_tokens FROM tf_better_prompt "
            "WHERE session_id=? AND msg_index=? AND mode=?",
            (session_id, msg_index, mode),
        )
        if not rows:
            return None
        return {
            "suggested_text": rows[0][0],
            "est_save_tokens": int(rows[0][1] or 0),
            "mode": mode,
            "cached": True,
        }

    def cache_better_prompt(
        self,
        *,
        session_id: str,
        msg_index: int,
        mode: str,
        suggested_text: str,
        est_save_tokens: int,
    ) -> None:
        key = f"{session_id}:{msg_index}:{mode}"
        self._exec(
            """
            INSERT INTO tf_better_prompt (cache_key, session_id, msg_index, mode, suggested_text, est_save_tokens, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (cache_key) DO UPDATE SET
              suggested_text = EXCLUDED.suggested_text,
              est_save_tokens = EXCLUDED.est_save_tokens,
              cached_at = EXCLUDED.cached_at
            """,
            (key, session_id, msg_index, mode, suggested_text, est_save_tokens),
        )

    # ---------- Session replay / picker ----------
    def list_sessions(
        self,
        *,
        project: str | None = None,
        has_waste: bool = False,
        q: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        filters = []
        params: list[Any] = []
        if project:
            filters.append("s.project_slug = ?")
            params.append(project)
        if has_waste:
            filters.append(
                "EXISTS (SELECT 1 FROM tf_waste_patterns w WHERE w.session_id = s.session_id)"
            )
        if q:
            filters.append(
                "EXISTS (SELECT 1 FROM tf_messages m "
                "WHERE m.session_id = s.session_id "
                "AND COALESCE(m.paused, FALSE) = FALSE "
                "AND m.content_preview ILIKE ?)"
            )
            params.append(f"%{q}%")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        rows = self._q(
            f"""
            SELECT s.session_id, s.project_slug, s.started_at, s.ended_at, s.model,
                   COALESCE(SUM(m.input_tokens + m.output_tokens), 0) AS toks,
                   COALESCE(SUM(m.cost_usd), 0) AS cost,
                   COUNT(m.message_id) AS msgs,
                   COALESCE(w.wastes, 0) AS wastes
            FROM sessions s
            LEFT JOIN tf_messages m ON m.session_id = s.session_id AND COALESCE(m.paused, FALSE) = FALSE
            LEFT JOIN (
                SELECT session_id, COUNT(*) AS wastes
                FROM tf_waste_patterns
                GROUP BY session_id
            ) w ON w.session_id = s.session_id
            {where}
            GROUP BY s.session_id, s.project_slug, s.started_at, s.ended_at, s.model, w.wastes
            ORDER BY s.started_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [
            {
                "id": r[0],
                "project": r[1],
                "started_at": r[2].isoformat() if r[2] else None,
                "ended_at": r[3].isoformat() if r[3] else None,
                "model": r[4],
                "tokens": int(r[5]),
                "cost": round(float(r[6]), 2),
                "messages": int(r[7]),
                "wastes": int(r[8]),
            }
            for r in rows
        ]

    def session_replay(self, session_id: str, *, include_paused: bool = False) -> list[dict[str, Any]]:
        paused_filter = "" if include_paused else "AND COALESCE(paused, FALSE) = FALSE"
        rows = self._q(
            f"""
            SELECT message_id, ts, role, model, input_tokens, output_tokens, cache_read_tokens,
                   cost_usd, content_preview
            FROM tf_messages
            WHERE session_id = ? {paused_filter}
            ORDER BY ts
            """,
            (session_id,),
        )
        out: list[dict[str, Any]] = []
        for idx, r in enumerate(rows):
            out.append({
                "idx": idx,
                "id": r[0],
                "t": r[1].strftime("%H:%M:%S") if r[1] else "",
                "ts": r[1].isoformat() if r[1] else None,
                "role": r[2],
                "model": r[3],
                "tokens_in": int(r[4] or 0),
                "tokens_out": int(r[5] or 0),
                "cache_read": int(r[6] or 0),
                "cost_usd": round(float(r[7] or 0), 4),
                "preview": r[8] or "",
            })
        return out
