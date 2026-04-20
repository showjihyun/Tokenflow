from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tokenflow.adapters.web.app import create_app


def test_analytics_empty_shapes() -> None:
    with TestClient(create_app()) as c:
        kpi = c.get("/api/analytics/kpi?range=7d").json()
        assert kpi["totalTokens"] == 0
        daily = c.get("/api/analytics/daily?range=30d").json()
        assert len(daily["series"]) == 3
        heatmap = c.get("/api/analytics/heatmap?range=7d").json()
        assert len(heatmap["grid"]) == 7
        assert all(len(row) == 24 for row in heatmap["grid"])
        cost = c.get("/api/analytics/cost-breakdown?range=30d").json()
        assert cost["total"] == 0.0
        assert len(cost["parts"]) == 4
        assert c.get("/api/analytics/top-wastes").json() == []


def test_analytics_top_wastes_returns_ranked_range_results() -> None:
    from datetime import UTC, datetime, timedelta

    from tokenflow.adapters.persistence.repository import Repository

    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        for waste_id, kind, severity, save_usd, save_tokens, detected_at in [
            ("old", "tool-loop", "high", 99.0, 99_000, now - timedelta(days=10)),
            ("low", "repeat-question", "low", 10.0, 10_000, now - timedelta(days=1)),
            ("med", "wrong-model", "med", 1.0, 1_000, now - timedelta(hours=2)),
            ("high", "context-bloat", "high", 0.5, 500, now - timedelta(hours=1)),
            ("high-2", "context-bloat", "med", 0.25, 250, now - timedelta(minutes=30)),
        ]:
            repo.insert_waste_pattern(
                id=waste_id,
                kind=kind,
                severity=severity,
                title=waste_id,
                meta="m",
                body_html="b",
                save_tokens=save_tokens,
                save_usd=save_usd,
                sessions=1,
                session_id="s1",
                context="{}",
                detected_at=detected_at,
            )

        r = c.get("/api/analytics/top-wastes?range=7d&limit=2")
        assert r.status_code == 200
        body = r.json()
        assert [w["kind"] for w in body] == ["context-bloat", "wrong-model"]
        assert body[0]["id"] == "top:context-bloat"
        assert body[0]["context"]["count"] == 2
        assert body[0]["save_tokens"] == 750
        assert all(w["kind"] != "tool-loop" for w in body)


def test_analytics_project_filter_and_efficiency_score() -> None:
    from datetime import UTC, datetime, timedelta

    from tokenflow.adapters.persistence.repository import Repository

    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started("pa", "alpha", "claude-sonnet-4-6", now - timedelta(minutes=10))
        repo.upsert_session_started("pb", "beta", "claude-opus-4-7", now - timedelta(minutes=8))
        repo.insert_message("ma", "pa", now, "assistant", "claude-sonnet-4-6", 1000, 1000, 0, 0, 0.01, "alpha", False)
        repo.insert_message("mb", "pb", now, "assistant", "claude-opus-4-7", 3000, 1000, 0, 0, 0.04, "beta", False)
        repo.insert_waste_pattern(
            id="w-alpha",
            kind="context-bloat",
            severity="high",
            title="alpha waste",
            meta="m",
            body_html="b",
            save_tokens=1000,
            save_usd=0.01,
            sessions=1,
            session_id="pa",
            context="{}",
            detected_at=now,
        )

        all_kpi = c.get("/api/analytics/kpi?range=7d").json()
        alpha_kpi = c.get("/api/analytics/kpi?range=7d&project=alpha").json()
        assert all_kpi["totalTokens"] == 6000
        assert alpha_kpi["totalTokens"] == 2000

        top = c.get("/api/analytics/top-wastes?range=7d&project=beta").json()
        assert top == []

        live = c.get("/api/kpi/summary?window=7d").json()
        assert live["efficiency"]["score"] < 100
        assert live["waste"]["tokens"] == 1000


def test_settings_crud_persists() -> None:
    with TestClient(create_app()) as c:
        initial = c.get("/api/settings").json()
        assert initial["budget"]["monthly_budget_usd"] == 150.0
        assert initial["tweaks"]["theme"] == "dark"

        r = c.put("/api/settings/budget", json={
            "monthly_budget_usd": 200.0,
            "alert_thresholds_pct": [60, 80, 95],
            "hard_block": True,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["budget"]["monthly_budget_usd"] == 200.0
        assert body["budget"]["alert_thresholds_pct"] == [60, 80, 95]
        assert body["budget"]["hard_block"] is True

        r = c.patch("/api/settings/tweaks", json={"theme": "light", "better_prompt_mode": "llm"})
        assert r.status_code == 200
        body = r.json()
        assert body["tweaks"]["theme"] == "light"
        assert body["tweaks"]["better_prompt_mode"] == "llm"


def test_api_key_roundtrip(tmp_path: Path) -> None:
    unique = f"sk-ant-test-{tmp_path.name[:8]}"
    with TestClient(create_app()) as c:
        # Start empty — clean out any key left behind by a previous test run on this machine.
        c.delete("/api/settings/api-key")
        empty = c.get("/api/settings/api-key/status").json()
        assert empty["configured"] is False
        assert empty["valid"] is False
        assert empty["backend"] in ("keyring", "file")

        r = c.post("/api/settings/api-key", json={"key": unique})
        assert r.status_code == 200
        live = c.get("/api/settings/api-key/status").json()
        assert live["configured"] is True
        assert live["valid"] is True

        r = c.delete("/api/settings/api-key")
        assert r.status_code == 200
        gone = c.get("/api/settings/api-key/status").json()
        assert gone["configured"] is False
        assert gone["valid"] is False


def test_api_key_fallback_file_reports_invalid_when_no_keyring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Force the no-keyring fallback path and verify corrupt secret.json reports as not-configured."""
    from tokenflow.adapters.persistence import paths as paths_mod
    from tokenflow.adapters.persistence import secret_store

    monkeypatch.setattr(secret_store, "_keyring_available", lambda: False)
    secret = paths_mod.secret_path()
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("not-json-at-all", encoding="utf-8")

    with TestClient(create_app()) as c:
        body = c.get("/api/settings/api-key/status").json()
        assert body["configured"] is False
        assert body["valid"] is False
        assert body["backend"] == "file"


def test_onboarding_status_and_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point the hook installer at a throwaway settings.json so we never touch real Claude settings.
    fake_settings = tmp_path / "fake_claude_settings.json"
    monkeypatch.setattr(
        "tokenflow.adapters.hook.installer.claude_settings_path",
        lambda: fake_settings,
    )
    with TestClient(create_app()) as c:
        c.delete("/api/settings/api-key")
        s = c.get("/api/onboarding/status").json()
        assert s["onboarded"] is False
        assert s["hook"]["status"] == "not_installed"
        assert s["api_key_configured"] is False
        assert s["api_key"]["configured"] is False

        r = c.post("/api/onboarding/install-hook?dry_run=true")
        assert r.status_code == 200
        assert r.json()["dry_run"] is True

        r = c.post("/api/onboarding/install-hook")
        assert r.status_code == 200
        assert fake_settings.exists()
        written = json.loads(fake_settings.read_text(encoding="utf-8"))
        assert "SessionStart" in written["hooks"]

        s2 = c.get("/api/onboarding/status").json()
        assert s2["hook"]["status"] == "installed"

        r = c.post("/api/onboarding/complete")
        assert r.json()["onboarded"] is True
        assert c.get("/api/onboarding/status").json()["onboarded"] is True


def test_system_pause_backups_and_vacuum() -> None:
    with TestClient(create_app()) as c:
        health = c.get("/api/system/health").json()
        assert health["hook"] == "disconnected"
        assert health["api_key_detail"]["configured"] is False

        r = c.post("/api/system/ingestion-pause", json={"paused": True})
        assert r.status_code == 200
        assert r.json()["paused"] is True
        assert c.get("/api/system/health").json()["ingestion_paused"] is True

        r = c.post("/api/system/vacuum")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "retention" in body
        assert c.get("/api/system/backups").status_code == 200


def test_query_quality_endpoint() -> None:
    with TestClient(create_app()) as c:
        r = c.post(
            "/api/coach/query-quality",
            json={
                "query": "Fix the failing pytest in backend/tests/test_routes.py and return a concise patch summary",
                "context": {"file": "test_routes.py"},
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["grade"] in ("A", "B", "C", "D")
        assert body["score"] >= 0
        assert set(body["signals"]) == {"specificity", "has_context", "model_match", "scope_bounded"}


def test_paused_messages_excluded_from_kpi() -> None:
    from datetime import UTC, datetime

    from tokenflow.adapters.persistence.repository import Repository

    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started("paused_s1", "proj", "claude-sonnet-4-6", now)
        repo.insert_message(
            "paused_msg",
            "paused_s1",
            now,
            "assistant",
            "claude-sonnet-4-6",
            1000,
            500,
            0,
            0,
            0.01,
            "paused",
            True,
        )
        repo.update_session_totals_from_messages("paused_s1")
        kpi = c.get("/api/kpi/summary").json()
        assert kpi["today"]["tokens"] == 0
        current = c.get("/api/sessions/current").json()
        assert current["tokens"]["input"] == 0
