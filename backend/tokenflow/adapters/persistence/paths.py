from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def tokenflow_dir() -> Path:
    """Root directory for Token Flow's local state. Override with TOKENFLOW_HOME env."""
    override = os.environ.get("TOKENFLOW_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".tokenflow").resolve()


def db_path() -> Path:
    return tokenflow_dir() / "events.duckdb"


def events_ndjson_path() -> Path:
    return tokenflow_dir() / "events.ndjson"


def secret_path() -> Path:
    return tokenflow_dir() / "secret.json"


def logs_dir() -> Path:
    return tokenflow_dir() / "logs"


def backups_dir() -> Path:
    return tokenflow_dir() / "backups"


def ensure_dirs() -> None:
    for p in (tokenflow_dir(), logs_dir(), backups_dir()):
        p.mkdir(parents=True, exist_ok=True)


def migrations_dir() -> Path:
    """Package-bundled migrations directory."""
    here = Path(__file__).resolve()
    backend_root = here.parents[3]
    return backend_root / "migrations"
