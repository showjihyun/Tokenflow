from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime
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


# Cached head version — module-level so repeated create_app() calls in tests
# don't re-glob the migrations dir on every run.
_MIGRATIONS_HEAD_CACHE: dict[Path, int] = {}


def _migrations_head(migrations_dir: Path) -> int:
    cached = _MIGRATIONS_HEAD_CACHE.get(migrations_dir)
    if cached is not None:
        return cached
    versions = [v for v, _ in _list_migrations(migrations_dir)]
    head = max(versions) if versions else 0
    _MIGRATIONS_HEAD_CACHE[migrations_dir] = head
    return head


def _applied_versions(conn: duckdb.DuckDBPyConnection) -> set[int]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL, description VARCHAR NOT NULL)"
    )
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {int(r[0]) for r in rows}


def run_migrations(db_file: Path | None = None, migrations_dir: Path | None = None) -> list[int]:
    """Apply pending migrations in version order. Returns list of newly applied versions.

    Fast path: when every migration file version is already applied (the common case on
    subsequent boots), skip the file glob + read entirely. Big win in test suites that
    call create_app() many times.
    """
    paths.ensure_dirs()
    db_file = db_file or paths.db_path()
    migrations_dir = migrations_dir or paths.migrations_dir()

    conn = duckdb.connect(str(db_file))
    try:
        applied = _applied_versions(conn)
        head = _migrations_head(migrations_dir)
        if applied and max(applied) >= head:
            return []
        pending = [(v, p) for v, p in _list_migrations(migrations_dir) if v not in applied]
    finally:
        conn.close()

    # Backup on file copy requires the DB not be open (Windows holds an exclusive lock).
    if pending and db_file.exists() and db_file.stat().st_size > 0 and applied:
        paths.backups_dir().mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = paths.backups_dir() / f"events_{stamp}.duckdb"
        suffix = 1
        while backup.exists():
            backup = paths.backups_dir() / f"events_{stamp}_{suffix}.duckdb"
            suffix += 1
        shutil.copy2(db_file, backup)
        logger.info("backed up database before migrations: %s", backup)

    if not pending:
        return []

    conn = duckdb.connect(str(db_file))
    try:
        newly: list[int] = []
        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            logger.info("applying migration V%d (%s)", version, path.name)
            conn.execute(sql)
            newly.append(version)
        return newly
    finally:
        conn.close()
