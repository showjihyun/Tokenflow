from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
from fastapi.testclient import TestClient

from tokenflow.adapters.persistence import migrations
from tokenflow.adapters.persistence.import_ccprophet import import_from_ccprophet
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.app import create_app


def _build_ccprophet_db(path: Path) -> None:
    """Create a minimal ccprophet-shaped DB (V1..V5) for import testing."""
    migrations.run_migrations(db_file=path)


def test_import_empty_ccprophet_creates_no_rows(tmp_path: Path) -> None:
    src = tmp_path / "ccprophet.duckdb"
    _build_ccprophet_db(src)

    migrations.run_migrations()
    repo = Repository()
    counts = import_from_ccprophet(src, repo)
    assert all(v == 0 for v in counts.values())
    repo.close()


def test_import_copies_sessions(tmp_path: Path) -> None:
    # Build source DB with one session
    src = tmp_path / "ccprophet.duckdb"
    _build_ccprophet_db(src)
    conn = duckdb.connect(str(src))
    now = datetime.now(tz=UTC)
    conn.execute(
        "INSERT INTO sessions (session_id, project_slug, model, started_at, total_input_tokens, total_output_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("imported_s1", "old-project", "claude-sonnet-4-5", now, 1000, 500),
    )
    conn.close()

    migrations.run_migrations()
    repo = Repository()
    counts = import_from_ccprophet(src, repo)
    assert counts["sessions"] == 1

    # Second import is idempotent
    counts2 = import_from_ccprophet(src, repo)
    assert counts2["sessions"] == 0
    repo.close()


def test_import_ccprophet_rest_job(tmp_path: Path) -> None:
    src = tmp_path / "ccprophet.duckdb"
    _build_ccprophet_db(src)

    with TestClient(create_app()) as c:
        r = c.post("/api/import/ccprophet", json={"path": str(src)})
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        status = c.get(f"/api/import/ccprophet/status/{job_id}")
        assert status.status_code == 200
        body = status.json()
        assert body["state"] in ("done", "running", "queued")
        if body["state"] == "done":
            assert "counts" in body
