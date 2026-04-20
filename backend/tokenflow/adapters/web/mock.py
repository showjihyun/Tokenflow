"""Mock data for Phase B — returns realistic-looking shapes matching data.js in the design bundle.

Real data sources (hook ingestion + transcript tailer) land in Phase C.
"""
from __future__ import annotations

import random
import time
from datetime import UTC, datetime
from typing import Any


def _sine_series(n: int, base: float, amp: float, noise: float = 0.3) -> list[float]:
    import math

    return [
        round(base + amp * math.sin(i / max(1, n / 6)) + random.random() * noise * amp, 2)
        for i in range(n)
    ]


def kpi_summary(window: str = "today") -> dict[str, Any]:
    return {
        "currentSession": {"tokens": 208160, "delta": "+2,340 last min"},
        "today": {
            "tokens": 1_240_000,
            "cost": 9.84,
            "delta": 0.12,
            "series": [0.3, 0.5, 0.4, 0.8, 1.2, 0.9, 1.4, 1.1, 1.6, 1.3, 1.8, 1.7],
        },
        "week": {
            "tokens": 8_240_000,
            "cost": 62.10,
            "delta": -0.06,
            "series": [1.8, 2.1, 1.9, 2.4, 1.6, 1.3, 1.7],
        },
        "efficiency": {
            "score": 72,
            "delta": 4,
            "series": [62, 64, 61, 65, 68, 70, 72],
            "attribution": {
                "score": 72,
                "totalTokens": 1_240_000,
                "wastedTokens": 184_000,
                "opusMisuseTokens": 82_000,
                "contextBloatTokens": 66_000,
                "wasteRatio": 0.148,
                "opusMisuseRatio": 0.066,
                "contextBloatRatio": 0.053,
                "penalty": {"waste": 5.9, "opusMisuse": 2.0, "contextBloat": 1.6, "total": 9.5},
            },
        },
        "waste": {
            "tokens": 184_000,
            "pct": 14.8,
            "delta": -0.03,
            "byKind": [{"kind": "context-bloat", "findings": 3, "tokens": 66_000, "usd": 0.82}],
        },
        "window": window,
    }


def current_session() -> dict[str, Any]:
    return {
        "id": "sess_8f2a9c",
        "startedAt": "2026-04-18T09:14:02+09:00",
        "project": "commerce-admin",
        "model": "claude-sonnet-4.6",
        "tokens": {"input": 184320, "output": 23840, "cacheRead": 412000, "cacheWrite": 48210},
        "contextWindow": 200000,
        "contextUsed": 142380,
        "costUSD": 2.34,
        "messages": 47,
    }


def flow_60m() -> dict[str, Any]:
    labels = ["60m", "50m", "40m", "30m", "20m", "10m", "now"]
    return {
        "labels": labels,
        "series": [
            {"key": "opus", "color": "var(--violet)", "data": [120, 80, 0, 0, 0, 180, 420]},
            {"key": "sonnet", "color": "var(--amber)", "data": [800, 1100, 1400, 620, 980, 1620, 2240]},
            {"key": "haiku", "color": "var(--blue)", "data": [140, 240, 180, 320, 220, 180, 120]},
            {"key": "cache", "color": "var(--green)", "data": [400, 620, 880, 520, 740, 1100, 1560]},
        ],
    }


def models_distribution() -> list[dict[str, Any]]:
    return [
        {"name": "Sonnet 4.6", "key": "sonnet", "share": 0.62, "tokens": 5_108_800, "cost": 38.41},
        {"name": "Opus 4", "key": "opus", "share": 0.24, "tokens": 1_977_600, "cost": 49.44},
        {"name": "Haiku 4.5", "key": "haiku", "share": 0.14, "tokens": 1_153_600, "cost": 2.31},
    ]


def budget() -> dict[str, Any]:
    return {
        "month": 150,
        "spent": 87.42,
        "daysLeft": 12,
        "dailyAvg": 4.86,
        "forecast": 146.80,
        "opusShare": 0.24,
    }


def projects(range_: str = "7d") -> list[dict[str, Any]]:
    raw = [
        {"name": "commerce-admin", "tokens": 3_420_000, "cost": 38.10, "sessions": 24, "waste": 0.18, "trend": "up"},
        {"name": "design-system", "tokens": 2_108_000, "cost": 24.70, "sessions": 18, "waste": 0.09, "trend": "flat"},
        {"name": "billing-api", "tokens": 1_642_000, "cost": 17.20, "sessions": 12, "waste": 0.22, "trend": "up"},
        {"name": "marketing-site", "tokens": 812_000, "cost": 4.90, "sessions": 9, "waste": 0.11, "trend": "down"},
        {"name": "ops-scripts", "tokens": 258_000, "cost": 2.52, "sessions": 4, "waste": 0.31, "trend": "up"},
    ]
    for p in raw:
        p["range"] = range_
    return raw


def project_trend(name: str, range_: str = "7d") -> dict[str, Any]:
    n = 7 if range_ == "7d" else 30
    return {"name": name, "range": range_, "data": _sine_series(n, base=2.5, amp=1.5)}


_TICKER_TYPES = [
    ("edited", "src/lib/auth.ts", 340),
    ("read", "package.json", 1240),
    ("grep", "pattern: useAuth", 120),
    ("reply", "explained component API", 820),
    ("tool", "bash: npm test", 60),
    ("edited", "components/Button.tsx", 280),
    ("read", "README.md", 420),
]


def next_ticker_event() -> dict[str, Any]:
    t, label, base = random.choice(_TICKER_TYPES)
    tk = base + random.randint(-40, 40)
    return {
        "id": int(time.time() * 1000),
        "t": t,
        "label": label,
        "tk": max(20, tk),
        "time": datetime.now(tz=UTC).astimezone().strftime("%H:%M:%S"),
    }
