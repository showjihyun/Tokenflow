from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.app import create_app


def test_health_ok() -> None:
    with TestClient(create_app()) as c:
        r = c.get("/api/system/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        # Fresh DB = no events ingested = hook status "disconnected" per system.py taxonomy.
        assert body["hook"] == "disconnected"


def test_empty_db_returns_empty_shapes() -> None:
    with TestClient(create_app()) as c:
        s = c.get("/api/sessions/current").json()
        assert s["active"] is False
        assert s["tokens"] == {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}

        k = c.get("/api/kpi/summary").json()
        for key in ("currentSession", "today", "week", "efficiency", "waste"):
            assert key in k
        assert k["today"]["tokens"] == 0

        m = c.get("/api/kpi/models").json()
        assert {row["key"] for row in m} == {"opus", "sonnet", "haiku"}
        assert all(row["tokens"] == 0 for row in m)

        b = c.get("/api/kpi/budget").json()
        assert b["month"] == 150.0
        assert b["spent"] == 0.0

        assert c.get("/api/projects").json() == []

        flow = c.get("/api/sessions/current/flow").json()
        assert len(flow["series"]) == 4


def test_synthetic_data_populates_routes() -> None:
    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started(
            "sess_test_1",
            project_slug="commerce-admin",
            model="claude-sonnet-4-6",
            started_at=now - timedelta(minutes=5),
        )
        repo.insert_message(
            message_id="m1",
            session_id="sess_test_1",
            ts=now - timedelta(minutes=4),
            role="user",
            model=None,
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            cost_usd=0.0,
            content_preview="hello",
        )
        repo.insert_message(
            message_id="m2",
            session_id="sess_test_1",
            ts=now - timedelta(minutes=3),
            role="assistant",
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=1200,
            cache_creation_tokens=0,
            cache_read_tokens=3000,
            cost_usd=0.021,
            content_preview="sure, let me help",
        )
        repo.update_session_totals_from_messages("sess_test_1")

        s = c.get("/api/sessions/current").json()
        assert s["active"] is True
        assert s["id"] == "sess_test_1"
        assert s["project"] == "commerce-admin"
        assert s["tokens"]["output"] == 1200

        models = c.get("/api/kpi/models").json()
        sonnet = next(m for m in models if m["key"] == "sonnet")
        assert sonnet["tokens"] == 1700

        projects = c.get("/api/projects").json()
        assert projects[0]["name"] == "commerce-admin"
        assert projects[0]["sessions"] == 1


def test_migrations_idempotent() -> None:
    with TestClient(create_app()) as _c:
        pass
    with TestClient(create_app()) as c:
        r = c.get("/api/system/health")
        assert r.status_code == 200


def test_analytics_range_rejects_invalid_value() -> None:
    """Pydantic Literal validation: unsupported range strings should 422, not silently default."""
    with TestClient(create_app()) as c:
        for path in (
            "/api/analytics/kpi",
            "/api/analytics/daily",
            "/api/analytics/heatmap",
            "/api/analytics/cost-breakdown",
            "/api/analytics/top-wastes",
        ):
            r = c.get(f"{path}?range=banana")
            assert r.status_code == 422, f"{path} accepted invalid range"


def test_analytics_top_wastes_rejects_out_of_range_limit() -> None:
    with TestClient(create_app()) as c:
        assert c.get("/api/analytics/top-wastes?limit=0").status_code == 422
        assert c.get("/api/analytics/top-wastes?limit=51").status_code == 422
        assert c.get("/api/analytics/top-wastes?limit=50").status_code == 200


