from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from tokenflow.adapters.persistence import paths

logger = logging.getLogger(__name__)

MODEL_COLOR = {
    "opus": "var(--violet)",
    "sonnet": "var(--amber)",
    "haiku": "var(--blue)",
}


def _model_key(model: str | None) -> str:
    if not model:
        return "sonnet"
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    return "sonnet"


class Repository:
    """Single-connection DuckDB wrapper. DuckDB is not thread-safe for concurrent writes,
    so all writes serialize on self._lock. Reads also hold the lock for simplicity."""

    def __init__(self, db_file: Path | None = None):
        self.db_file = db_file or paths.db_path()
        self._conn = duckdb.connect(str(self.db_file))
        self._lock = threading.RLock()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------- low-level helpers ----------
    def _q(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _exec(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)

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
                   COALESCE(s.total_cache_creation_tokens, 0), COALESCE(s.total_cache_read_tokens, 0),
                   s.context_window_size, s.compacted,
                   (SELECT MAX(ts) FROM tf_messages m WHERE m.session_id = s.session_id) AS last_msg
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
        rows = self._q("SELECT COUNT(*) FROM tf_messages WHERE session_id = ?", (session_id,))
        return int(rows[0][0]) if rows else 0

    def _estimate_context_used(self, session_id: str) -> int:
        """Best-effort: last assistant message's input_tokens (closest to live context size)."""
        rows = self._q(
            """
            SELECT input_tokens + cache_read_tokens + cache_creation_tokens
            FROM tf_messages
            WHERE session_id = ? AND role = 'assistant'
            ORDER BY ts DESC LIMIT 1
            """,
            (session_id,),
        )
        if not rows:
            return 0
        return int(rows[0][0] or 0)

    def _estimate_session_cost(self, session_id: str) -> float:
        rows = self._q(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM tf_messages WHERE session_id = ?",
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
    ) -> bool:
        """Returns True if inserted, False if duplicate."""
        try:
            self._exec(
                """
                INSERT INTO tf_messages (
                  message_id, session_id, ts, role, model,
                  input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                  cost_usd, content_preview
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id, session_id, ts, role, model,
                    input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                    cost_usd, content_preview,
                ),
            )
            return True
        except duckdb.ConstraintException:
            return False

    def update_session_totals_from_messages(self, session_id: str) -> None:
        self._exec(
            """
            UPDATE sessions SET
              total_input_tokens = COALESCE((SELECT SUM(input_tokens) FROM tf_messages WHERE session_id = ?), 0),
              total_output_tokens = COALESCE((SELECT SUM(output_tokens) FROM tf_messages WHERE session_id = ?), 0),
              total_cache_creation_tokens = COALESCE((SELECT SUM(cache_creation_tokens) FROM tf_messages WHERE session_id = ?), 0),
              total_cache_read_tokens = COALESCE((SELECT SUM(cache_read_tokens) FROM tf_messages WHERE session_id = ?), 0)
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
            out.append({"id": eid, "session_id": sid, "type": etype, "ts": ts.isoformat(), "payload": p})
        return out

    # ---------- pricing ----------
    def pricing_for(self, model: str, at: datetime | None = None) -> tuple[float, float, float, float] | None:
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
        # fallback: any matching row
        rows = self._q(
            "SELECT input_per_mtok, output_per_mtok, cache_write_per_mtok, cache_read_per_mtok FROM pricing_rates WHERE model = ? ORDER BY effective_at DESC LIMIT 1",
            (model,),
        )
        if rows:
            return float(rows[0][0]), float(rows[0][1]), float(rows[0][2]), float(rows[0][3])
        return None

    # ---------- KPI / analytics ----------
    def kpi_summary(self) -> dict[str, Any]:
        today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_tokens = self._sum_tokens_since(today_start)
        today_cost = self._sum_cost_since(today_start)
        current_session_tokens = 0
        current = self.get_current_session()
        if current:
            current_session_tokens = current["tokens"]["input"] + current["tokens"]["output"]
        return {
            "currentSession": {"tokens": current_session_tokens, "delta": ""},
            "today": {"tokens": today_tokens, "cost": round(today_cost, 2), "delta": 0.0, "series": []},
            "week": {"tokens": 0, "cost": 0.0, "delta": 0.0, "series": []},
            "efficiency": {"score": 0, "delta": 0, "series": []},
            "waste": {"tokens": 0, "pct": 0.0, "delta": 0.0},
            "window": "today",
        }

    def _sum_tokens_since(self, since: datetime) -> int:
        rows = self._q(
            "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM tf_messages WHERE ts >= ?",
            (since,),
        )
        return int(rows[0][0]) if rows else 0

    def _sum_cost_since(self, since: datetime) -> float:
        rows = self._q(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM tf_messages WHERE ts >= ?",
            (since,),
        )
        return float(rows[0][0]) if rows else 0.0

    def models_today(self) -> list[dict[str, Any]]:
        today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        rows = self._q(
            """
            SELECT model,
                   COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens,
                   COALESCE(SUM(cost_usd), 0) AS cost
            FROM tf_messages
            WHERE ts >= ? AND model IS NOT NULL
            GROUP BY model
            """,
            (today_start,),
        )
        agg: dict[str, dict[str, Any]] = {"opus": {"tokens": 0, "cost": 0.0}, "sonnet": {"tokens": 0, "cost": 0.0}, "haiku": {"tokens": 0, "cost": 0.0}}
        for model, tokens, cost in rows:
            key = _model_key(model)
            agg[key]["tokens"] += int(tokens)
            agg[key]["cost"] += float(cost)
        total = sum(v["tokens"] for v in agg.values()) or 1
        display_names = {"opus": "Opus", "sonnet": "Sonnet", "haiku": "Haiku"}
        return [
            {
                "key": key,
                "name": display_names[key],
                "share": round(agg[key]["tokens"] / total, 4) if total else 0.0,
                "tokens": agg[key]["tokens"],
                "cost": round(agg[key]["cost"], 2),
            }
            for key in ("sonnet", "opus", "haiku")
        ]

    def budget(self) -> dict[str, Any]:
        cfg = self._config_row()
        month_start = datetime.now(tz=UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_cost = self._sum_cost_since(month_start)
        now = datetime.now(tz=UTC)
        days_in_month = 30
        day_of_month = now.day
        daily_avg = month_cost / max(1, day_of_month)
        forecast = daily_avg * days_in_month
        models = self.models_today()
        opus_share = 0.0
        opus = next((m for m in models if m["key"] == "opus"), None)
        total_cost_today = sum(m["cost"] for m in models) or 0.0
        if opus and total_cost_today > 0:
            opus_share = opus["cost"] / total_cost_today
        return {
            "month": float(cfg["monthly_budget_usd"]),
            "spent": round(month_cost, 2),
            "daysLeft": max(0, days_in_month - day_of_month),
            "dailyAvg": round(daily_avg, 2),
            "forecast": round(forecast, 2),
            "opusShare": round(opus_share, 4),
        }

    def _config_row(self) -> dict[str, Any]:
        rows = self._q(
            "SELECT monthly_budget_usd, alert_thresholds_pct, hard_block, better_prompt_mode, "
            "theme, density, chart_style, sidebar_pos, alert_level, lang FROM tf_config WHERE id=1"
        )
        if not rows:
            return {
                "monthly_budget_usd": 150.0,
                "alert_thresholds_pct": "[50,75,90]",
                "hard_block": False,
                "better_prompt_mode": "static",
            }
        keys = ["monthly_budget_usd", "alert_thresholds_pct", "hard_block", "better_prompt_mode",
                "theme", "density", "chart_style", "sidebar_pos", "alert_level", "lang"]
        return dict(zip(keys, rows[0], strict=True))

    def flow_60m(self) -> dict[str, Any]:
        """Token flow grouped into 7 10-minute buckets over the last 60 minutes."""
        now = datetime.now(tz=UTC)
        start = now.timestamp() - 60 * 60
        buckets = 7
        labels = ["60m", "50m", "40m", "30m", "20m", "10m", "now"]
        rows = self._q(
            """
            SELECT ts, model, input_tokens + output_tokens AS toks, cache_read_tokens
            FROM tf_messages
            WHERE ts >= to_timestamp(?)
            """,
            (start,),
        )
        series: dict[str, list[int]] = {
            "opus": [0] * buckets,
            "sonnet": [0] * buckets,
            "haiku": [0] * buckets,
            "cache": [0] * buckets,
        }
        for ts, model, toks, cache in rows:
            sec = ts.timestamp() if isinstance(ts, datetime) else float(ts)
            idx = min(buckets - 1, max(0, int((sec - start) / (60 * 60) * buckets)))
            key = _model_key(model)
            series[key][idx] += int(toks or 0)
            series["cache"][idx] += int(cache or 0)
        return {
            "labels": labels,
            "series": [
                {"key": "opus", "color": "var(--violet)", "data": series["opus"]},
                {"key": "sonnet", "color": "var(--amber)", "data": series["sonnet"]},
                {"key": "haiku", "color": "var(--blue)", "data": series["haiku"]},
                {"key": "cache", "color": "var(--green)", "data": series["cache"]},
            ],
            "window": "60m",
        }

    def projects(self, range_: str = "7d") -> list[dict[str, Any]]:
        days = 30 if range_ == "30d" else 7
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        rows = self._q(
            """
            SELECT s.project_slug,
                   COUNT(DISTINCT s.session_id) AS sess,
                   COALESCE(SUM(m.input_tokens + m.output_tokens), 0) AS toks,
                   COALESCE(SUM(m.cost_usd), 0) AS cost
            FROM sessions s
            LEFT JOIN tf_messages m ON m.session_id = s.session_id
            WHERE s.started_at >= to_timestamp(?)
            GROUP BY s.project_slug
            ORDER BY toks DESC
            """,
            (since,),
        )
        out: list[dict[str, Any]] = []
        for name, sess, toks, cost in rows:
            out.append({
                "name": name,
                "tokens": int(toks),
                "cost": round(float(cost), 2),
                "sessions": int(sess),
                "waste": 0.0,
                "trend": "flat",
                "range": range_,
            })
        return out

    # ---------- transcript offsets ----------
    def get_transcript_offset(self, path: str) -> int:
        rows = self._q("SELECT bytes_read FROM tf_transcript_offsets WHERE transcript_path = ?", (path,))
        return int(rows[0][0]) if rows else 0

    def set_transcript_offset(self, path: str, session_id: str, bytes_read: int) -> None:
        self._exec(
            """
            INSERT INTO tf_transcript_offsets (transcript_path, session_id, bytes_read, last_read_at)
            VALUES (?, ?, ?, now())
            ON CONFLICT (transcript_path) DO UPDATE SET
              bytes_read = EXCLUDED.bytes_read,
              session_id = EXCLUDED.session_id,
              last_read_at = EXCLUDED.last_read_at
            """,
            (path, session_id, bytes_read),
        )

    def get_hook_offset(self) -> int:
        rows = self._q("SELECT bytes_read FROM tf_hook_offset WHERE id = 1")
        return int(rows[0][0]) if rows else 0

    def set_hook_offset(self, bytes_read: int) -> None:
        self._exec("UPDATE tf_hook_offset SET bytes_read = ?, last_read_at = now() WHERE id = 1", (bytes_read,))

    # ---------- Analytics ----------
    def analytics_daily(self, range_: str = "30d") -> dict[str, Any]:
        days = {"24h": 1, "7d": 7, "30d": 30, "90d": 90, "all": 365}.get(range_, 30)
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        rows = self._q(
            """
            SELECT date_trunc('day', ts) AS d, model,
                   COALESCE(SUM(input_tokens + output_tokens), 0) AS toks
            FROM tf_messages
            WHERE ts >= to_timestamp(?) AND model IS NOT NULL
            GROUP BY d, model
            ORDER BY d
            """,
            (since,),
        )
        # bucket by day; pad to full range
        bucket_count = days if days <= 90 else 30
        labels: list[str] = []
        buckets: dict[str, list[int]] = {"opus": [0] * bucket_count, "sonnet": [0] * bucket_count, "haiku": [0] * bucket_count}
        now = datetime.now(tz=UTC)
        for i in range(bucket_count):
            day = now.timestamp() - (bucket_count - 1 - i) * 86400
            labels.append(datetime.fromtimestamp(day, tz=UTC).strftime("%m-%d"))
        for day, model, toks in rows:
            key = _model_key(model)
            day_ts = day.timestamp() if isinstance(day, datetime) else float(day)
            idx = int((day_ts - (now.timestamp() - bucket_count * 86400)) / 86400)
            if 0 <= idx < bucket_count:
                buckets[key][idx] += int(toks)
        return {
            "range": range_,
            "labels": labels,
            "series": [
                {"key": "opus", "color": "var(--violet)", "data": buckets["opus"]},
                {"key": "sonnet", "color": "var(--amber)", "data": buckets["sonnet"]},
                {"key": "haiku", "color": "var(--blue)", "data": buckets["haiku"]},
            ],
        }

    def analytics_heatmap(self, range_: str = "7d") -> list[list[float]]:
        days = {"7d": 7, "30d": 30}.get(range_, 7)
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        rows = self._q(
            """
            SELECT CAST(extract('dow' FROM ts) AS INTEGER) AS dow,
                   CAST(extract('hour' FROM ts) AS INTEGER) AS hr,
                   COALESCE(SUM(input_tokens + output_tokens), 0) AS toks
            FROM tf_messages
            WHERE ts >= to_timestamp(?)
            GROUP BY dow, hr
            """,
            (since,),
        )
        # Return 7x24 matrix. DuckDB dow: 0=Sunday..6=Saturday; map to 0=Mon..6=Sun.
        grid = [[0.0] * 24 for _ in range(7)]
        maxv = 0
        tmp = [[0] * 24 for _ in range(7)]
        for dow, hr, toks in rows:
            row = (int(dow) + 6) % 7  # shift: Mon -> 0
            col = int(hr)
            val = int(toks)
            tmp[row][col] = val
            if val > maxv:
                maxv = val
        if maxv > 0:
            for r in range(7):
                for c in range(24):
                    grid[r][c] = tmp[r][c] / maxv
        return grid

    def analytics_cost_breakdown(self, range_: str = "30d") -> dict[str, Any]:
        days = {"7d": 7, "30d": 30, "90d": 90, "all": 365}.get(range_, 30)
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        rows = self._q(
            """
            SELECT model,
                   COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0),
                   COALESCE(SUM(cache_creation_tokens), 0), COALESCE(SUM(cache_read_tokens), 0)
            FROM tf_messages
            WHERE ts >= to_timestamp(?) AND model IS NOT NULL
            GROUP BY model
            """,
            (since,),
        )
        input_cost = output_cost = cw_cost = cr_cost = 0.0
        for model, inp, out, cw, cr in rows:
            pricing = self.pricing_for(model)
            if not pricing:
                continue
            p_in, p_out, p_cw, p_cr = pricing
            input_cost += (int(inp) / 1e6) * p_in
            output_cost += (int(out) / 1e6) * p_out
            cw_cost += (int(cw) / 1e6) * p_cw
            cr_cost += (int(cr) / 1e6) * p_cr
        total = input_cost + output_cost + cw_cost + cr_cost
        return {
            "range": range_,
            "total": round(total, 2),
            "parts": [
                {"label": "Input", "value": round(input_cost, 2), "color": "var(--blue)"},
                {"label": "Output", "value": round(output_cost, 2), "color": "var(--amber)"},
                {"label": "Cache write", "value": round(cw_cost, 2), "color": "var(--violet)"},
                {"label": "Cache read", "value": round(cr_cost, 2), "color": "var(--green)"},
            ],
        }

    def analytics_kpi(self, range_: str = "7d") -> dict[str, Any]:
        days = {"24h": 1, "7d": 7, "30d": 30, "90d": 90, "all": 365}.get(range_, 7)
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        rows = self._q(
            "SELECT COUNT(*), COALESCE(SUM(input_tokens + output_tokens), 0), COALESCE(SUM(cost_usd), 0) "
            "FROM tf_messages WHERE ts >= to_timestamp(?)",
            (since,),
        )
        msgs, toks, cost = rows[0] if rows else (0, 0, 0.0)
        sess_rows = self._q(
            "SELECT COUNT(*), COALESCE(AVG(EXTRACT('epoch' FROM COALESCE(ended_at, now()) - started_at) / 60.0), 0) "
            "FROM sessions WHERE started_at >= to_timestamp(?)",
            (since,),
        )
        sessions, avg_min = sess_rows[0] if sess_rows else (0, 0.0)
        cost_per_session = float(cost) / max(1, int(sessions))
        return {
            "range": range_,
            "totalTokens": int(toks),
            "totalCost": round(float(cost), 2),
            "avgSessionMinutes": round(float(avg_min), 1),
            "costPerSession": round(cost_per_session, 2),
            "sessions": int(sessions),
            "messages": int(msgs),
        }

    # ---------- Config (budget / tweaks) ----------
    def get_config(self) -> dict[str, Any]:
        return self._config_row()

    def patch_config(self, **fields: Any) -> dict[str, Any]:
        allowed = {
            "monthly_budget_usd", "alert_thresholds_pct", "hard_block", "better_prompt_mode",
            "theme", "density", "chart_style", "sidebar_pos", "alert_level", "lang",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self._config_row()
        # Build a parameterized UPDATE
        sets = ", ".join(f"{k} = ?" for k in updates)
        self._exec(f"UPDATE tf_config SET {sets}, updated_at = now() WHERE id = 1", tuple(updates.values()))
        return self._config_row()

    def mark_onboarded(self) -> None:
        self._exec("UPDATE tf_config SET onboarded_at = COALESCE(onboarded_at, now()) WHERE id = 1")

    def is_onboarded(self) -> bool:
        rows = self._q("SELECT onboarded_at FROM tf_config WHERE id = 1")
        return bool(rows) and rows[0][0] is not None

    # ---------- Waste patterns (Phase E) ----------
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
        filt = "dismissed_at IS NULL AND applied_at IS NULL" if status == "active" else "(dismissed_at IS NOT NULL OR applied_at IS NOT NULL)"
        rows = self._q(
            f"""
            SELECT id, kind, severity, title, meta, body_html,
                   save_tokens, save_usd, sessions, session_id, context,
                   detected_at, dismissed_at, applied_at
            FROM tf_waste_patterns
            WHERE {filt}
            ORDER BY detected_at DESC
            LIMIT 100
            """
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            ctx = r[10]
            try:
                ctx_val = json.loads(ctx) if isinstance(ctx, str) else (ctx or {})
            except (TypeError, json.JSONDecodeError):
                ctx_val = {}
            out.append({
                "id": r[0], "kind": r[1], "severity": r[2], "title": r[3],
                "meta": r[4], "body_html": r[5],
                "save_tokens": int(r[6] or 0), "save_usd": float(r[7] or 0),
                "sessions": int(r[8] or 0), "session_id": r[9], "context": ctx_val,
                "detected_at": r[11].isoformat() if r[11] else None,
                "dismissed_at": r[12].isoformat() if r[12] else None,
                "applied_at": r[13].isoformat() if r[13] else None,
            })
        return out

    def mark_waste_dismissed(self, waste_id: str) -> bool:
        self._exec("UPDATE tf_waste_patterns SET dismissed_at = now() WHERE id = ? AND dismissed_at IS NULL", (waste_id,))
        return True

    def mark_waste_applied(self, waste_id: str, outcome: str) -> bool:
        self._exec(
            "UPDATE tf_waste_patterns SET applied_at = now(), applied_outcome = ? WHERE id = ? AND applied_at IS NULL",
            (outcome, waste_id),
        )
        return True

    def get_waste(self, waste_id: str) -> dict[str, Any] | None:
        results = self.list_wastes(status="active") + self.list_wastes(status="dismissed")
        return next((w for w in results if w["id"] == waste_id), None)

    # ---------- Coach ----------
    def create_coach_thread(self, thread_id: str, title: str | None = None) -> dict[str, Any]:
        self._exec(
            "INSERT INTO tf_coach_threads (id, title, started_at, last_msg_at) VALUES (?, ?, now(), now())",
            (thread_id, title),
        )
        return {"id": thread_id, "title": title, "cost_usd_total": 0.0}

    def list_coach_threads(self) -> list[dict[str, Any]]:
        rows = self._q(
            "SELECT id, title, started_at, last_msg_at, cost_usd_total FROM tf_coach_threads ORDER BY last_msg_at DESC"
        )
        return [
            {
                "id": r[0], "title": r[1],
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
                "id": r[0], "role": r[1], "content": r[2],
                "ts": r[3].isoformat() if r[3] else None,
                "input_tokens": int(r[4] or 0), "output_tokens": int(r[5] or 0),
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
            "UPDATE tf_coach_threads SET last_msg_at = ?, cost_usd_total = cost_usd_total + ? WHERE id = ?",
            (ts, cost_usd, thread_id),
        )

    # ---------- Better prompt cache ----------
    def get_better_prompt(self, session_id: str, msg_index: int, mode: str) -> dict[str, Any] | None:
        rows = self._q(
            "SELECT suggested_text, est_save_tokens FROM tf_better_prompt WHERE session_id=? AND msg_index=? AND mode=?",
            (session_id, msg_index, mode),
        )
        if not rows:
            return None
        return {"suggested_text": rows[0][0], "est_save_tokens": int(rows[0][1] or 0), "mode": mode, "cached": True}

    def cache_better_prompt(
        self, *, session_id: str, msg_index: int, mode: str, suggested_text: str, est_save_tokens: int
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

    # ---------- Session replay ----------
    def list_sessions(
        self, *, project: str | None = None, has_waste: bool = False, q: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        filters = []
        params: list[Any] = []
        if project:
            filters.append("s.project_slug = ?")
            params.append(project)
        if has_waste:
            filters.append("EXISTS (SELECT 1 FROM tf_waste_patterns w WHERE w.session_id = s.session_id)")
        if q:
            filters.append("EXISTS (SELECT 1 FROM tf_messages m WHERE m.session_id = s.session_id AND m.content_preview ILIKE ?)")
            params.append(f"%{q}%")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        rows = self._q(
            f"""
            SELECT s.session_id, s.project_slug, s.started_at, s.ended_at, s.model,
                   COALESCE(SUM(m.input_tokens + m.output_tokens), 0) AS toks,
                   COALESCE(SUM(m.cost_usd), 0) AS cost,
                   COUNT(m.message_id) AS msgs,
                   (SELECT COUNT(*) FROM tf_waste_patterns w WHERE w.session_id = s.session_id) AS wastes
            FROM sessions s
            LEFT JOIN tf_messages m ON m.session_id = s.session_id
            {where}
            GROUP BY s.session_id, s.project_slug, s.started_at, s.ended_at, s.model
            ORDER BY s.started_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [
            {
                "id": r[0], "project": r[1],
                "started_at": r[2].isoformat() if r[2] else None,
                "ended_at": r[3].isoformat() if r[3] else None,
                "model": r[4], "tokens": int(r[5]), "cost": round(float(r[6]), 2),
                "messages": int(r[7]), "wastes": int(r[8]),
            }
            for r in rows
        ]

    def session_replay(self, session_id: str) -> list[dict[str, Any]]:
        rows = self._q(
            """
            SELECT message_id, ts, role, model, input_tokens, output_tokens, cache_read_tokens,
                   cost_usd, content_preview
            FROM tf_messages
            WHERE session_id = ?
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

    # ---------- Routing rules ----------
    def list_routing_rules(self) -> list[dict[str, Any]]:
        rows = self._q(
            "SELECT id, condition_pattern, target_model, enabled, priority FROM tf_routing_rules ORDER BY priority, id"
        )
        return [
            {"id": r[0], "condition_pattern": r[1], "target_model": r[2], "enabled": bool(r[3]), "priority": int(r[4])}
            for r in rows
        ]

    def upsert_routing_rule(
        self, *, rule_id: str, condition_pattern: str, target_model: str, enabled: bool = True, priority: int = 100
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
        rows = self._q("SELECT pref_key, enabled, channel FROM tf_notification_prefs ORDER BY pref_key")
        return [{"key": r[0], "enabled": bool(r[1]), "channel": r[2]} for r in rows]

    def update_notification_pref(self, pref_key: str, *, enabled: bool | None = None, channel: str | None = None) -> None:
        if enabled is not None:
            self._exec(
                "UPDATE tf_notification_prefs SET enabled = ?, updated_at = now() WHERE pref_key = ?",
                (enabled, pref_key),
            )
        if channel is not None:
            self._exec(
                "UPDATE tf_notification_prefs SET channel = ?, updated_at = now() WHERE pref_key = ?",
                (channel, pref_key),
            )

    # ---------- Transcript discovery ----------
    def active_transcript_paths(self) -> list[tuple[str, str]]:
        """Return (transcript_path, session_id) pairs extracted from recent hook events."""
        rows = self._q(
            """
            SELECT DISTINCT payload->>'transcript_path' AS tp, session_id
            FROM events
            WHERE payload->>'transcript_path' IS NOT NULL
              AND session_id IN (SELECT session_id FROM sessions WHERE ended_at IS NULL)
            """
        )
        return [(r[0], r[1]) for r in rows if r[0]]
