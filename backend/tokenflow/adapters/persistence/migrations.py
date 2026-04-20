from __future__ import annotations

import logging
import re
from pathlib import Path

import duckdb

from tokenflow.adapters.persistence import paths

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"^V(\d+)__")


def _parse_version(fn: str) -> int:
    m = _VERSION_RE.match(fn)
    if not m:
        raise ValueError(f"migration filename must be 'V<n>__<desc>.sql', got {fn}")
    return int(m.group(1))


def _list_migrations(migrations_dir: Path) -> list[tuple[int, Path]]:
    files = sorted(migrations_dir.glob("V*.sql"), key=lambda p: _parse_version(p.name))
    return [(_parse_version(p.name), p) for p in files]


def _applied_versions(conn: duckdb.DuckDBPyConnection) -> set[int]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, description VARCHAR NOT NULL)"
    )
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {int(r[0]) for r in rows}


def run_migrations(db_file: Path | None = None, migrations_dir: Path | None = None) -> list[int]:
    """Apply pending migrations in version order. Returns list of newly applied versions."""
    paths.ensure_dirs()
    db_file = db_file or paths.db_path()
    migrations_dir = migrations_dir or paths.migrations_dir()

    conn = duckdb.connect(str(db_file))
    try:
        applied = _applied_versions(conn)
        pending = [(v, p) for v, p in _list_migrations(migrations_dir) if v not in applied]
        newly: list[int] = []
        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            logger.info("applying migration V%d (%s)", version, path.name)
            conn.execute(sql)
            newly.append(version)
        return newly
    finally:
        conn.close()
