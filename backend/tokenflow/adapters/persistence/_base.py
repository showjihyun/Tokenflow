"""Base repository: DuckDB connection + threading lock + low-level _q/_exec.

Mixins in sibling files (_sessions, _wastes, _coach_replay, _analytics) inherit
from _BaseRepo so `self._q(...)` is typed correctly in each concern's methods.
The public Repository class composes all mixins; see repository.py.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import duckdb

from tokenflow.adapters.persistence import paths

logger = logging.getLogger(__name__)


MODEL_COLOR = {
    "opus": "var(--violet)",
    "sonnet": "var(--amber)",
    "haiku": "var(--blue)",
}


def _model_key(model: str | None) -> str:
    if not model:
        return "sonnet"
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    return "sonnet"


class _BaseRepo:
    """DuckDB single-connection wrapper. Writes + reads serialize on ``self._lock``."""

    def __init__(self, db_file: Path | None = None):
        self.db_file = db_file or paths.db_path()
        self._conn = duckdb.connect(str(self.db_file))
        self._lock = threading.RLock()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _q(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _exec(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
