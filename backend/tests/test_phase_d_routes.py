from __future__ import annotations

import json
from pathlib import Path

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
    with TestClient(create_app()) as c:
        empty = c.get("/api/settings/api-key/status").json()
        assert empty["configured"] is False
        assert empty["valid"] is False

        r = c.post("/api/settings/api-key", json={"key": "sk-ant-test-1234567890"})
        assert r.status_code == 200
        live = c.get("/api/settings/api-key/status").json()
        assert live["configured"] is True
        assert live["valid"] is True

        r = c.delete("/api/settings/api-key")
        assert r.status_code == 200
        gone = c.get("/api/settings/api-key/status").json()
        assert gone["configured"] is False
        assert gone["valid"] is False


def test_api_key_corrupt_file_reports_invalid(tmp_path: Path) -> None:
    from tokenflow.adapters.persistence import paths as paths_mod

    with TestClient(create_app()) as c:
        secret = paths_mod.secret_path()
        secret.parent.mkdir(parents=True, exist_ok=True)
        secret.write_text("not-json-at-all", encoding="utf-8")

        body = c.get("/api/settings/api-key/status").json()
        assert body["configured"] is True
        assert body["valid"] is False
        assert "cannot read" in body["error"] or "JSON" in body["error"]


def test_onboarding_status_and_complete(tmp_path: Path, monkeypatch) -> None:
    # Point the hook installer at a throwaway settings.json so we never touch real Claude settings.
    fake_settings = tmp_path / "fake_claude_settings.json"
    monkeypatch.setattr(
        "tokenflow.adapters.hook.installer.claude_settings_path",
        lambda: fake_settings,
    )
    with TestClient(create_app()) as c:
        s = c.get("/api/onboarding/status").json()
        assert s["onboarded"] is False
        assert s["hook"]["status"] == "not_installed"
        assert s["api_key_configured"] is False

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
