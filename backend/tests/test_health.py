from __future__ import annotations

from fastapi.testclient import TestClient

from tokenflow.adapters.web.app import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    r = client.get("/api/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
