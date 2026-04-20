"""KPI, budget, flow chart, projects, analytics endpoints,
config (budget + tweaks), tailer offsets, active transcript discovery."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tokenflow.adapters.persistence._base import _BaseRepo, _model_key


class _AnalyticsMixin(_BaseRepo):
    # ---------- KPI ----------
    def kpi_summary(self, window: str = "today") -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since = {
            "today": today_start,
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
        }.get(window, today_start)
        prev_since = since - (now - since)
        today_tokens = self._sum_tokens_since(today_start)
        today_cost = self._sum_cost_since(today_start)
        attribution = self._efficiency_attribution(since, now)
        prev_attribution = self._efficiency_attribution(prev_since, since)
        score = int(attribution["score"])
        prev_score = int(prev_attribution["score"])
        waste_pct = round(float(attribution["wasteRatio"]) * 100, 1)
        prev_waste_pct = round(float(prev_attribution["wasteRatio"]) * 100, 1)
        current_session_tokens = 0
        current = self.get_current_session()  # type: ignore[attr-defined]
        if current:
            current_session_tokens = current["tokens"]["input"] + current["tokens"]["output"]
        return {
            "currentSession": {"tokens": current_session_tokens, "delta": ""},
            "today": {"tokens": today_tokens, "cost": round(today_cost, 2), "delta": 0.0, "series": []},
            "week": {"tokens": 0, "cost": 0.0, "delta": 0.0, "series": []},
            "efficiency": {
                "score": score,
                "delta": score - prev_score,
                "series": self._efficiency_series(days=7),
                "attribution": attribution,
            },
            "waste": {
                "tokens": attribution["wastedTokens"],
                "pct": waste_pct,
                "delta": round(waste_pct - prev_waste_pct, 4),
                "byKind": attribution["byKind"],
            },
            "window": window,
        }

    def _tokens_between(self, start: datetime, end: datetime) -> int:
        rows = self._q(
            """
            SELECT COALESCE(SUM(input_tokens + output_tokens), 0)
            FROM tf_messages
            WHERE ts >= ? AND ts < ? AND COALESCE(paused, FALSE) = FALSE
            """,
            (start, end),
        )
        return int(rows[0][0]) if rows else 0

    def _waste_tokens_between(
        self, start: datetime, end: datetime, kind: str | None = None
    ) -> int:
        params: list[Any] = [start, end]
        kind_filter = ""
        if kind:
            kind_filter = "AND kind = ?"
            params.append(kind)
        rows = self._q(
            f"""
            SELECT COALESCE(SUM(save_tokens), 0)
            FROM tf_waste_patterns
            WHERE detected_at >= ? AND detected_at < ? {kind_filter}
              AND dismissed_at IS NULL
            """,
            tuple(params),
        )
        return int(rows[0][0]) if rows else 0

    def _waste_rollup_between(self, start: datetime, end: datetime) -> dict[str, Any]:
        rows = self._q(
            """
            SELECT kind,
                   COUNT(*) AS findings,
                   COALESCE(SUM(save_tokens), 0) AS tokens,
                   COALESCE(SUM(save_usd), 0) AS usd
            FROM tf_waste_patterns
            WHERE detected_at >= ? AND detected_at < ?
              AND dismissed_at IS NULL
            GROUP BY kind
            ORDER BY tokens DESC, usd DESC
            """,
            (start, end),
        )
        by_kind = [
            {
                "kind": r[0],
                "findings": int(r[1] or 0),
                "tokens": int(r[2] or 0),
                "usd": round(float(r[3] or 0), 4),
            }
            for r in rows
        ]
        totals = {str(item["kind"]): int(item["tokens"]) for item in by_kind}
        return {
            "total": sum(totals.values()),
            "wrong-model": totals.get("wrong-model", 0),
            "context-bloat": totals.get("context-bloat", 0),
            "byKind": by_kind,
        }

    def _efficiency_score(self, start: datetime, end: datetime) -> int:
        attribution = self._efficiency_attribution(start, end)
        return int(attribution["score"])

    def _efficiency_attribution(self, start: datetime, end: datetime) -> dict[str, Any]:
        total = self._tokens_between(start, end)
        waste_rollup = self._waste_rollup_between(start, end)
        if total <= 0:
            return {
                "score": 100,
                "totalTokens": 0,
                "wastedTokens": 0,
                "opusMisuseTokens": 0,
                "contextBloatTokens": 0,
                "wasteRatio": 0.0,
                "opusMisuseRatio": 0.0,
                "contextBloatRatio": 0.0,
                "penalty": {"waste": 0.0, "opusMisuse": 0.0, "contextBloat": 0.0, "total": 0.0},
                "byKind": waste_rollup["byKind"],
            }
        wasted = min(total, int(waste_rollup["total"]))
        opus_misuse = min(total, int(waste_rollup["wrong-model"]))
        context_bloat = min(total, int(waste_rollup["context-bloat"]))
        waste_penalty = (wasted / total) * 40
        opus_penalty = (opus_misuse / total) * 30
        context_penalty = (context_bloat / total) * 30
        total_penalty = waste_penalty + opus_penalty + context_penalty
        score = max(0, min(100, round(100 - total_penalty)))
        return {
            "score": score,
            "totalTokens": total,
            "wastedTokens": wasted,
            "opusMisuseTokens": opus_misuse,
            "contextBloatTokens": context_bloat,
            "wasteRatio": round(wasted / total, 4),
            "opusMisuseRatio": round(opus_misuse / total, 4),
            "contextBloatRatio": round(context_bloat / total, 4),
            "penalty": {
                "waste": round(waste_penalty, 1),
                "opusMisuse": round(opus_penalty, 1),
                "contextBloat": round(context_penalty, 1),
                "total": round(total_penalty, 1),
            },
            "byKind": waste_rollup["byKind"],
        }

    def _waste_summary(self, start: datetime, end: datetime) -> dict[str, Any]:
        total = self._tokens_between(start, end)
        tokens = self._waste_tokens_between(start, end)
        pct = (tokens / total) if total > 0 else 0.0
        return {"tokens": tokens, "pct": round(pct * 100, 1)}

    def _waste_breakdown_by_kind(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return list(self._waste_rollup_between(start, end)["byKind"])

    def _efficiency_series(self, *, days: int) -> list[int]:
        now = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        start = now - timedelta(days=days - 1)
        token_rows = self._q(
            """
            SELECT CAST(date_trunc('day', ts) AS DATE) AS d,
                   COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens
            FROM tf_messages
            WHERE ts >= ? AND ts < ? AND COALESCE(paused, FALSE) = FALSE
            GROUP BY d
            """,
            (start, now + timedelta(days=1)),
        )
        waste_rows = self._q(
            """
            SELECT CAST(date_trunc('day', detected_at) AS DATE) AS d,
                   kind,
                   COALESCE(SUM(save_tokens), 0) AS tokens
            FROM tf_waste_patterns
            WHERE detected_at >= ? AND detected_at < ?
              AND dismissed_at IS NULL
            GROUP BY d, kind
            """,
            (start, now + timedelta(days=1)),
        )
        tokens_by_day = {
            r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]): int(r[1] or 0)
            for r in token_rows
        }
        waste_by_day: dict[str, dict[str, int]] = {}
        for day, kind, tokens in waste_rows:
            key = day.isoformat() if hasattr(day, "isoformat") else str(day)
            waste_by_day.setdefault(key, {})[str(kind)] = int(tokens or 0)

        out: list[int] = []
        for offset in range(days - 1, -1, -1):
            day = (now - timedelta(days=offset)).date().isoformat()
            total = tokens_by_day.get(day, 0)
            if total <= 0:
                out.append(100)
                continue
            wastes = waste_by_day.get(day, {})
            wasted = min(total, sum(wastes.values()))
            opus_misuse = min(total, wastes.get("wrong-model", 0))
            context_bloat = min(total, wastes.get("context-bloat", 0))
            penalty = (
                (wasted / total) * 40
                + (opus_misuse / total) * 30
                + (context_bloat / total) * 30
            )
            out.append(max(0, min(100, round(100 - penalty))))
        return out

    def _sum_tokens_since(self, since: datetime) -> int:
        rows = self._q(
            "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM tf_messages WHERE ts >= ? AND COALESCE(paused, FALSE) = FALSE",
            (since,),
        )
        return int(rows[0][0]) if rows else 0

    def _sum_cost_since(self, since: datetime) -> float:
        rows = self._q(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM tf_messages WHERE ts >= ? AND COALESCE(paused, FALSE) = FALSE",
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
            WHERE ts >= ? AND model IS NOT NULL AND COALESCE(paused, FALSE) = FALSE
            GROUP BY model
            """,
            (today_start,),
        )
        agg: dict[str, dict[str, Any]] = {
            "opus": {"tokens": 0, "cost": 0.0},
            "sonnet": {"tokens": 0, "cost": 0.0},
            "haiku": {"tokens": 0, "cost": 0.0},
        }
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
        month_start = datetime.now(tz=UTC).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
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
            "theme, density, chart_style, sidebar_pos, alert_level, lang, llm_model "
            "FROM tf_config WHERE id=1"
        )
        if not rows:
            return {
                "monthly_budget_usd": 150.0,
                "alert_thresholds_pct": "[50,75,90]",
                "hard_block": False,
                "better_prompt_mode": "static",
                "llm_model": "claude-sonnet-4-6",
            }
        keys = [
            "monthly_budget_usd", "alert_thresholds_pct", "hard_block", "better_prompt_mode",
            "theme", "density", "chart_style", "sidebar_pos", "alert_level", "lang", "llm_model",
        ]
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
            WHERE ts >= to_timestamp(?) AND COALESCE(paused, FALSE) = FALSE
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
        summary_rows = self._q(
            """
            SELECT s.project_slug,
                   COUNT(DISTINCT s.session_id) AS sess,
                   COALESCE(SUM(m.input_tokens + m.output_tokens), 0) AS toks,
                   COALESCE(SUM(m.cost_usd), 0) AS cost
            FROM sessions s
            LEFT JOIN tf_messages m ON m.session_id = s.session_id AND COALESCE(m.paused, FALSE) = FALSE
            WHERE s.started_at >= to_timestamp(?)
            GROUP BY s.project_slug
            ORDER BY toks DESC
            """,
            (since,),
        )
        trend_map = self._project_trends(range_)
        out: list[dict[str, Any]] = []
        for name, sess, toks, cost in summary_rows:
            trend_data = trend_map.get(str(name), [0] * days)
            midpoint = max(1, len(trend_data) // 2)
            earlier = sum(trend_data[:midpoint])
            later = sum(trend_data[midpoint:])
            trend = "flat"
            if later > earlier * 1.1:
                trend = "up"
            elif earlier > later * 1.1:
                trend = "down"
            out.append({
                "name": name,
                "tokens": int(toks),
                "cost": round(float(cost), 2),
                "sessions": int(sess),
                "waste": 0.0,
                "trend": trend,
                "trendData": trend_data,
                "range": range_,
            })
        return out

    def project_trend(self, name: str, range_: str = "7d") -> dict[str, Any]:
        days = 30 if range_ == "30d" else 7
        return {"name": name, "range": range_, "data": self._project_trends(range_, project=name).get(name, [0] * days)}

    def project_exists(self, name: str) -> bool:
        rows = self._q("SELECT 1 FROM sessions WHERE project_slug = ? LIMIT 1", (name,))
        return bool(rows)

    def _project_trends(self, range_: str = "7d", project: str | None = None) -> dict[str, list[int]]:
        days = 30 if range_ == "30d" else 7
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        params: list[Any] = [since]
        project_filter = ""
        if project:
            project_filter = "AND s.project_slug = ?"
            params.append(project)
        rows = self._q(
            f"""
            SELECT s.project_slug,
                   date_trunc('day', m.ts) AS d,
                   COALESCE(SUM(m.input_tokens + m.output_tokens), 0) AS toks
            FROM tf_messages m
            JOIN sessions s ON s.session_id = m.session_id
            WHERE m.ts >= to_timestamp(?)
              AND COALESCE(m.paused, FALSE) = FALSE
              {project_filter}
            GROUP BY s.project_slug, d
            ORDER BY s.project_slug, d
            """,
            tuple(params),
        )
        now = datetime.now(tz=UTC)
        start = now.timestamp() - days * 86400
        out: dict[str, list[int]] = {}
        for project, day, toks in rows:
            buckets = out.setdefault(str(project), [0] * days)
            day_ts = day.timestamp() if isinstance(day, datetime) else float(day)
            idx = int((day_ts - start) / 86400)
            if 0 <= idx < days:
                buckets[idx] += int(toks or 0)
        return out

    # ---------- Analytics page ----------
    def analytics_daily(self, range_: str = "30d", project: str | None = None) -> dict[str, Any]:
        days = {"24h": 1, "7d": 7, "30d": 30, "90d": 90, "all": 365}.get(range_, 30)
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        params: list[Any] = [since]
        join = ""
        project_filter = ""
        if project:
            join = "JOIN sessions s ON s.session_id = m.session_id"
            project_filter = "AND s.project_slug = ?"
            params.append(project)
        rows = self._q(
            f"""
            SELECT date_trunc('day', m.ts) AS d, m.model,
                   COALESCE(SUM(input_tokens + output_tokens), 0) AS toks
            FROM tf_messages m
            {join}
            WHERE m.ts >= to_timestamp(?) AND m.model IS NOT NULL AND COALESCE(paused, FALSE) = FALSE {project_filter}
            GROUP BY d, m.model
            ORDER BY d
            """,
            tuple(params),
        )
        bucket_count = days if days <= 90 else 30
        labels: list[str] = []
        buckets: dict[str, list[int]] = {
            "opus": [0] * bucket_count,
            "sonnet": [0] * bucket_count,
            "haiku": [0] * bucket_count,
        }
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

    def analytics_heatmap(self, range_: str = "7d", project: str | None = None) -> list[list[float]]:
        days = {"7d": 7, "30d": 30}.get(range_, 7)
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        params: list[Any] = [since]
        join = ""
        project_filter = ""
        if project:
            join = "JOIN sessions s ON s.session_id = m.session_id"
            project_filter = "AND s.project_slug = ?"
            params.append(project)
        rows = self._q(
            f"""
            SELECT CAST(extract('dow' FROM m.ts) AS INTEGER) AS dow,
                   CAST(extract('hour' FROM m.ts) AS INTEGER) AS hr,
                   COALESCE(SUM(input_tokens + output_tokens), 0) AS toks
            FROM tf_messages m
            {join}
            WHERE m.ts >= to_timestamp(?) AND COALESCE(paused, FALSE) = FALSE {project_filter}
            GROUP BY dow, hr
            """,
            tuple(params),
        )
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

    def analytics_cost_breakdown(self, range_: str = "30d", project: str | None = None) -> dict[str, Any]:
        days = {"7d": 7, "30d": 30, "90d": 90, "all": 365}.get(range_, 30)
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        params: list[Any] = [since]
        join = ""
        project_filter = ""
        if project:
            join = "JOIN sessions s ON s.session_id = m.session_id"
            project_filter = "AND s.project_slug = ?"
            params.append(project)
        rows = self._q(
            f"""
            SELECT m.model,
                   COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0),
                   COALESCE(SUM(cache_creation_tokens), 0), COALESCE(SUM(cache_read_tokens), 0)
            FROM tf_messages m
            {join}
            WHERE m.ts >= to_timestamp(?) AND m.model IS NOT NULL AND COALESCE(paused, FALSE) = FALSE {project_filter}
            GROUP BY m.model
            """,
            tuple(params),
        )
        input_cost = output_cost = cw_cost = cr_cost = 0.0
        for model, inp, out, cw, cr in rows:
            pricing = self.pricing_for(model)  # type: ignore[attr-defined]
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

    def analytics_kpi(self, range_: str = "7d", project: str | None = None) -> dict[str, Any]:
        days = {"24h": 1, "7d": 7, "30d": 30, "90d": 90, "all": 365}.get(range_, 7)
        since = datetime.now(tz=UTC).timestamp() - days * 86400
        params: list[Any] = [since]
        join = ""
        project_filter = ""
        if project:
            join = "JOIN sessions s ON s.session_id = m.session_id"
            project_filter = "AND s.project_slug = ?"
            params.append(project)
        rows = self._q(
            f"""
            SELECT COUNT(*), COALESCE(SUM(input_tokens + output_tokens), 0),
                   COALESCE(SUM(cost_usd), 0)
            FROM tf_messages m
            {join}
            WHERE m.ts >= to_timestamp(?) AND COALESCE(paused, FALSE) = FALSE {project_filter}
            """,
            tuple(params),
        )
        msgs, toks, cost = rows[0] if rows else (0, 0, 0.0)
        sess_params: list[Any] = [since]
        sess_filter = ""
        if project:
            sess_filter = "AND project_slug = ?"
            sess_params.append(project)
        sess_rows = self._q(
            "SELECT COUNT(*), COALESCE("
            "AVG(EXTRACT('epoch' FROM COALESCE(ended_at, now()) - started_at) / 60.0), 0) "
            f"FROM sessions WHERE started_at >= to_timestamp(?) {sess_filter}",
            tuple(sess_params),
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
            "theme", "density", "chart_style", "sidebar_pos", "alert_level", "lang", "llm_model",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self._config_row()
        sets = ", ".join(f"{k} = ?" for k in updates)
        self._exec(
            f"UPDATE tf_config SET {sets}, updated_at = now() WHERE id = 1",
            tuple(updates.values()),
        )
        return self._config_row()

    def mark_onboarded(self) -> None:
        self._exec(
            "UPDATE tf_config SET onboarded_at = COALESCE(onboarded_at, now()) WHERE id = 1"
        )

    def is_onboarded(self) -> bool:
        rows = self._q("SELECT onboarded_at FROM tf_config WHERE id = 1")
        return bool(rows) and rows[0][0] is not None

    # ---------- Transcript / hook tailer offsets ----------
    def get_transcript_offset(self, path: str) -> int:
        rows = self._q(
            "SELECT bytes_read FROM tf_transcript_offsets WHERE transcript_path = ?",
            (path,),
        )
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
        self._exec(
            "UPDATE tf_hook_offset SET bytes_read = ?, last_read_at = now() WHERE id = 1",
            (bytes_read,),
        )

    def active_transcript_paths(self) -> list[tuple[str, str]]:
        """Return (transcript_path, session_id) pairs from recent hook events for live sessions."""
        rows = self._q(
            """
            SELECT DISTINCT payload->>'transcript_path' AS tp, session_id
            FROM events
            WHERE payload->>'transcript_path' IS NOT NULL
              AND session_id IN (SELECT session_id FROM sessions WHERE ended_at IS NULL)
            """
        )
        return [(r[0], r[1]) for r in rows if r[0]]

    # ---------- Retention / rollup ----------
    def rollup_daily_before(self, cutoff: datetime) -> int:
        self._exec(
            """
            INSERT INTO daily_aggregate (
                day, project_slug, model_key, input_tokens, output_tokens,
                cache_creation_tokens, cache_read_tokens, cost_usd, messages, updated_at
            )
            SELECT
                CAST(date_trunc('day', m.ts) AS DATE) AS day,
                COALESCE(s.project_slug, 'unknown') AS project_slug,
                CASE
                    WHEN lower(COALESCE(m.model, '')) LIKE '%opus%' THEN 'opus'
                    WHEN lower(COALESCE(m.model, '')) LIKE '%haiku%' THEN 'haiku'
                    ELSE 'sonnet'
                END AS model_key,
                COALESCE(SUM(m.input_tokens), 0),
                COALESCE(SUM(m.output_tokens), 0),
                COALESCE(SUM(m.cache_creation_tokens), 0),
                COALESCE(SUM(m.cache_read_tokens), 0),
                COALESCE(SUM(m.cost_usd), 0),
                COUNT(*),
                now()
            FROM tf_messages m
            LEFT JOIN sessions s ON s.session_id = m.session_id
            WHERE m.ts < ? AND COALESCE(m.paused, FALSE) = FALSE
            GROUP BY day, project_slug, model_key
            ON CONFLICT (day, project_slug, model_key) DO UPDATE SET
                input_tokens = EXCLUDED.input_tokens,
                output_tokens = EXCLUDED.output_tokens,
                cache_creation_tokens = EXCLUDED.cache_creation_tokens,
                cache_read_tokens = EXCLUDED.cache_read_tokens,
                cost_usd = EXCLUDED.cost_usd,
                messages = EXCLUDED.messages,
                updated_at = EXCLUDED.updated_at
            """,
            (cutoff,),
        )
        rows = self._q(
            "SELECT COUNT(*) FROM tf_messages WHERE ts < ? AND COALESCE(paused, FALSE) = FALSE",
            (cutoff,),
        )
        return int(rows[0][0]) if rows else 0

    def apply_retention(self, *, days: int = 180) -> dict[str, int]:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        rolled = self.rollup_daily_before(cutoff)
        self._exec("DELETE FROM tf_messages WHERE ts < ?", (cutoff,))
        self._exec("DELETE FROM events WHERE ts < ?", (cutoff,))
        return {"rolled_messages": rolled, "retention_days": days}
