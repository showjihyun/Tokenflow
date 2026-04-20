"""Import a ccprophet DuckDB into Token Flow.

Schema V1-V5 is shared, so we copy core rows with ON CONFLICT skip. Dedup key is primary key.
"""
from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from tokenflow.adapters.persistence.repository import Repository

logger = logging.getLogger(__name__)

# Tables copied as-is (schema V1-V5 matches between ccprophet and Token Flow)
_SHARED_TABLES: tuple[str, ...] = (
    "sessions",
    "events",
    "tool_calls",
    "tool_defs_loaded",
    "file_reads",
    "phases",
    "subagents",
    "outcome_labels",
    "session_summary",
)


def import_from_ccprophet(src_db: Path, dst_repo: Repository) -> dict[str, int]:
    """Import shared V1-V5 tables from ``src_db`` into the Token Flow repo.

    Returns per-table insert counts. Uses DuckDB's ATTACH so the copy is transactional
    and skips PK conflicts row-by-row.
    """
    src_db = src_db.expanduser().resolve()
    if not src_db.exists():
        raise FileNotFoundError(f"not found: {src_db}")

    # DuckDB ATTACH does not accept bind parameters — quote the path defensively.
    src_literal = str(src_db).replace("'", "''")
    counts: dict[str, int] = {}
    with dst_repo._lock:
        dst_repo._conn.execute(f"ATTACH '{src_literal}' AS src (READ_ONLY)")
        try:
            for table in _SHARED_TABLES:
                try:
                    before_row = dst_repo._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    before = int(before_row[0]) if before_row else 0
                    dst_repo._conn.execute(f"INSERT INTO {table} SELECT * FROM src.{table} ON CONFLICT DO NOTHING")
                    after_row = dst_repo._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    after = int(after_row[0]) if after_row else 0
                    counts[table] = after - before
                except duckdb.CatalogException:
                    counts[table] = 0
                except duckdb.BinderException as e:
                    logger.warning("Skipping %s: %s", table, e)
                    counts[table] = 0
        finally:
            dst_repo._conn.execute("DETACH src")
    return counts
