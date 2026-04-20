from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from tokenflow.adapters.persistence import migrations
from tokenflow.adapters.persistence.import_ccprophet import import_from_ccprophet
from tokenflow.adapters.persistence.repository import Repository


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
