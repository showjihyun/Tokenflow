"""Waste patterns + routing rules + notification preferences."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import duckdb

from tokenflow.adapters.persistence._base import _BaseRepo


class _WasteMixin(_BaseRepo):
    _WASTE_COLS = (
        "id, kind, severity, title, meta, body_html, "
        "save_tokens, save_usd, sessions, session_id, context, "
        "detected_at, dismissed_at, applied_at"
    )

    @staticmethod
    def _row_to_waste(r: tuple[Any, ...]) -> dict[str, Any]:
        ctx = r[10]
        try:
            ctx_val = json.loads(ctx) if isinstance(ctx, str) else (ctx or {})
        except (TypeError, json.JSONDecodeError):
            ctx_val = {}
        return {
            "id": r[0], "kind": r[1], "severity": r[2], "title": r[3],
            "meta": r[4], "body_html": r[5],
            "save_tokens": int(r[6] or 0), "save_usd": float(r[7] or 0),
            "sessions": int(r[8] or 0), "session_id": r[9], "context": ctx_val,
            "detected_at": r[11].isoformat() if r[11] else None,
            "dismissed_at": r[12].isoformat() if r[12] else None,
            "applied_at": r[13].isoformat() if r[13] else None,
        }

    def insert_waste_pattern(
        self,
        *,
        id: str,
        kind: str,
        severity: str,
        title: str,
        meta: str,
        body_html: str,
        save_tokens: int,
        save_usd: float,
        sessions: int,
        session_id: str,
        context: str,
        detected_at: datetime,
    ) -> bool:
        try:
            self._exec(
                """
                INSERT INTO tf_waste_patterns (
                    id, kind, severity, title, meta, body_html,
                    save_tokens, save_usd, sessions, session_id, context, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?)
                """,
                (id, kind, severity, title, meta, body_html,
                 save_tokens, save_usd, sessions, session_id, context, detected_at),
            )
            return True
        except duckdb.ConstraintException:
            return False

    def list_wastes(self, *, status: str = "active") -> list[dict[str, Any]]:
        filt = (
            "dismissed_at IS NULL AND applied_at IS NULL"
            if status == "active"
            else "(dismissed_at IS NOT NULL OR applied_at IS NOT NULL)"
        )
        rows = self._q(
            f"SELECT {self._WASTE_COLS} FROM tf_waste_patterns "
            f"WHERE {filt} ORDER BY detected_at DESC LIMIT 100"
        )
        return [self._row_to_waste(r) for r in rows]

    def top_wastes(
        self, *, range_: str = "30d", limit: int = 4, project: str | None = None
    ) -> list[dict[str, Any]]:
        days = {"24h": 1, "7d": 7, "30d": 30, "90d": 90, "all": 365}.get(range_, 30)
        since = datetime.now(tz=UTC) - timedelta(days=days)
        safe_limit = max(1, min(int(limit), 50))
        params: list[Any] = [since]
        join = ""
        project_filter = ""
        if project:
            join = "JOIN sessions s ON s.session_id = w.session_id"
            project_filter = "AND s.project_slug = ?"
            params.append(project)
        params.append(safe_limit)
        rows = self._q(
            f"""
            SELECT
              kind,
              MAX(CASE severity WHEN 'high' THEN 3 WHEN 'med' THEN 2 WHEN 'low' THEN 1 ELSE 0 END) AS severity_rank,
              COUNT(*) AS findings,
              COALESCE(SUM(save_tokens), 0) AS total_save_tokens,
              COALESCE(SUM(save_usd), 0) AS total_save_usd,
              COALESCE(SUM(sessions), 0) AS total_sessions,
              MAX(detected_at) AS latest_detected_at
            FROM tf_waste_patterns w
            {join}
            WHERE detected_at >= ? {project_filter}
            GROUP BY kind
            ORDER BY
              severity_rank DESC,
              total_save_usd DESC,
              total_save_tokens DESC,
              latest_detected_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        severity_by_rank = {3: "high", 2: "med", 1: "low"}
        out: list[dict[str, Any]] = []
        for kind, severity_rank, findings, save_tokens, save_usd, sessions, latest in rows:
            count = int(findings or 0)
            latest_iso = latest.isoformat() if latest else None
            out.append({
                "id": f"top:{kind}",
                "kind": kind,
                "severity": severity_by_rank.get(int(severity_rank or 0), "low"),
                "title": str(kind).replace("-", " ").title(),
                "meta": f"{count} finding{'s' if count != 1 else ''}",
                "body_html": "",
                "save_tokens": int(save_tokens or 0),
                "save_usd": float(save_usd or 0),
                "sessions": int(sessions or 0),
                "session_id": None,
                "context": {"count": count, "latest_detected_at": latest_iso},
                "detected_at": latest_iso,
                "dismissed_at": None,
                "applied_at": None,
            })
        return out

    def mark_waste_dismissed(self, waste_id: str) -> bool:
        self._exec(
            "UPDATE tf_waste_patterns SET dismissed_at = now() "
            "WHERE id = ? AND dismissed_at IS NULL",
            (waste_id,),
        )
        return True

    def mark_waste_applied(self, waste_id: str, outcome: str) -> bool:
        self._exec(
            "UPDATE tf_waste_patterns SET applied_at = now(), applied_outcome = ? "
            "WHERE id = ? AND applied_at IS NULL",
            (outcome, waste_id),
        )
        return True

    def get_waste(self, waste_id: str) -> dict[str, Any] | None:
        rows = self._q(
            f"SELECT {self._WASTE_COLS} FROM tf_waste_patterns WHERE id = ?",
            (waste_id,),
        )
        return self._row_to_waste(rows[0]) if rows else None

    # ---------- Routing rules ----------
    def list_routing_rules(self) -> list[dict[str, Any]]:
        rows = self._q(
            "SELECT id, condition_pattern, target_model, enabled, priority "
            "FROM tf_routing_rules ORDER BY priority, id"
        )
        return [
            {
                "id": r[0],
                "condition_pattern": r[1],
                "target_model": r[2],
                "enabled": bool(r[3]),
                "priority": int(r[4]),
            }
            for r in rows
        ]

    def upsert_routing_rule(
        self,
        *,
        rule_id: str,
        condition_pattern: str,
        target_model: str,
        enabled: bool = True,
        priority: int = 100,
    ) -> None:
        self._exec(
            """
            INSERT INTO tf_routing_rules (id, condition_pattern, target_model, enabled, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, now(), now())
            ON CONFLICT (id) DO UPDATE SET
              condition_pattern = EXCLUDED.condition_pattern,
              target_model = EXCLUDED.target_model,
              enabled = EXCLUDED.enabled,
              priority = EXCLUDED.priority,
              updated_at = now()
            """,
            (rule_id, condition_pattern, target_model, enabled, priority),
        )

    def delete_routing_rule(self, rule_id: str) -> None:
        self._exec("DELETE FROM tf_routing_rules WHERE id = ?", (rule_id,))

    # ---------- Notification prefs ----------
    def list_notification_prefs(self) -> list[dict[str, Any]]:
        rows = self._q(
            "SELECT pref_key, enabled, channel FROM tf_notification_prefs ORDER BY pref_key"
        )
        return [{"key": r[0], "enabled": bool(r[1]), "channel": r[2]} for r in rows]

    def update_notification_pref(
        self, pref_key: str, *, enabled: bool | None = None, channel: str | None = None
    ) -> None:
        if enabled is not None:
            self._exec(
                "UPDATE tf_notification_prefs SET enabled = ?, updated_at = now() "
                "WHERE pref_key = ?",
                (enabled, pref_key),
            )
        if channel is not None:
            self._exec(
                "UPDATE tf_notification_prefs SET channel = ?, updated_at = now() "
                "WHERE pref_key = ?",
                (channel, pref_key),
            )

    # ---------- Notification events ----------
    def list_notifications(self, *, limit: int = 10) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 50))
        rows = self._q(
            """
            SELECT id, pref_key, title, body, created_at, read_at
            FROM tf_notifications
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        )
        return [
            {
                "id": r[0],
                "prefKey": r[1],
                "title": r[2],
                "body": r[3],
                "createdAt": r[4].isoformat() if r[4] else None,
                "readAt": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]

    def unread_notification_count(self) -> int:
        rows = self._q("SELECT COUNT(*) FROM tf_notifications WHERE read_at IS NULL")
        return int(rows[0][0]) if rows else 0

    def insert_notification(
        self,
        *,
        id: str,
        pref_key: str,
        title: str,
        body: str,
        created_at: datetime,
    ) -> bool:
        try:
            self._exec(
                """
                INSERT INTO tf_notifications (id, pref_key, title, body, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (id, pref_key, title, body, created_at),
            )
            return True
        except duckdb.ConstraintException:
            return False

    def clear_notifications(self) -> int:
        rows = self._q("SELECT COUNT(*) FROM tf_notifications")
        count = int(rows[0][0]) if rows else 0
        self._exec("DELETE FROM tf_notifications")
        return count

    def mark_notification_read(self, notification_id: str, *, read_at: datetime) -> dict[str, Any] | None:
        self._exec(
            """
            UPDATE tf_notifications
            SET read_at = COALESCE(read_at, ?)
            WHERE id = ?
            """,
            (read_at, notification_id),
        )
        rows = self._q(
            """
            SELECT id, pref_key, title, body, created_at, read_at
            FROM tf_notifications
            WHERE id = ?
            """,
            (notification_id,),
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "id": r[0],
            "prefKey": r[1],
            "title": r[2],
            "body": r[3],
            "createdAt": r[4].isoformat() if r[4] else None,
            "readAt": r[5].isoformat() if r[5] else None,
        }

    def mark_all_notifications_read(self, *, read_at: datetime) -> int:
        rows = self._q("SELECT COUNT(*) FROM tf_notifications WHERE read_at IS NULL")
        count = int(rows[0][0]) if rows else 0
        self._exec(
            "UPDATE tf_notifications SET read_at = COALESCE(read_at, ?) WHERE read_at IS NULL",
            (read_at,),
        )
        return count
