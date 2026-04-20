from __future__ import annotations

from fastapi.testclient import TestClient

from tokenflow.adapters.web.app import create_app


def test_health_returns_ok() -> None:
    # Must use the context-manager form so lifespan runs and app.state is populated.
    with TestClient(create_app()) as c:
        r = c.get("/api/system/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body
