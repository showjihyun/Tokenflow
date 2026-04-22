"""SPA catch-all must serve index.html for unknown client-side routes while
leaving /api/* (and the docs/openapi/redoc/assets paths) as real 404s.

Regression guard for PR 1 URL-routing migration: if the catch-all ever
re-captures /api/*, every unknown API path would silently return HTML and
mask real 404s.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tokenflow.adapters.web.app import create_app


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>tf</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("/* empty */", encoding="utf-8")
    return dist


def test_spa_fallback_serves_index_for_unknown_client_routes(tmp_path: Path) -> None:
    with TestClient(create_app(frontend_dist=_make_dist(tmp_path))) as c:
        # Client-side routes exist in React Router, not on the server.
        for path in ("/live", "/analytics", "/waste", "/coach", "/replay", "/settings", "/totally-unknown"):
            r = c.get(path)
            assert r.status_code == 200, f"{path} did not serve SPA fallback"
            assert r.headers["content-type"].startswith("text/html"), path
            assert "<title>tf</title>" in r.text, path


def test_spa_fallback_does_not_hijack_api_404s(tmp_path: Path) -> None:
    with TestClient(create_app(frontend_dist=_make_dist(tmp_path))) as c:
        # Existing API keeps returning JSON.
        health = c.get("/api/system/health")
        assert health.status_code == 200
        assert health.headers["content-type"].startswith("application/json")

        # Unknown /api/* paths must 404 — not HTML. This is the critical invariant
        # from plan-eng-review: SPA catch-all after the /api router would otherwise
        # swallow real 404s and return index.html for every bad API request.
        for bad in ("/api/does-not-exist", "/api/sessions/nope", "/api/kpi/unknown"):
            r = c.get(bad)
            assert r.status_code == 404, f"{bad} was hijacked by SPA fallback"
            assert not r.headers["content-type"].startswith("text/html"), bad


def test_spa_fallback_does_not_hijack_docs_or_assets(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path)
    with TestClient(create_app(frontend_dist=dist)) as c:
        # Real asset served by the StaticFiles mount.
        r = c.get("/assets/app.js")
        assert r.status_code == 200
        assert "empty" in r.text

        # Missing asset returns 404 JSON (FastAPI default) — not SPA HTML.
        r = c.get("/assets/ghost.js")
        assert r.status_code == 404
        assert not r.headers["content-type"].startswith("text/html")

        # FastAPI docs/openapi should not be rewritten to HTML either.
        docs = c.get("/docs")
        assert docs.status_code == 200
        assert "swagger" in docs.text.lower()

        openapi = c.get("/openapi.json")
        assert openapi.status_code == 200
        assert openapi.headers["content-type"].startswith("application/json")
