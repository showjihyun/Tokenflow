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


# ---- package / dev-checkout layout helpers ----
# paths.py location: <prefix>/tokenflow/adapters/persistence/paths.py
#   parents[0] persistence/
#   parents[1] adapters/
#   parents[2] tokenflow/        <- the Python package root
#   parents[3] <prefix>          <- `backend/` in dev, `site-packages/` in wheel install
#   parents[4] <prefix>/..       <- repo root in dev (has `frontend/`), or env root in wheel

def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _dev_backend_root_or_none() -> Path | None:
    """Backend dir in a dev checkout (contains `migrations/`). None when installed from wheel."""
    candidate = Path(__file__).resolve().parents[3]
    if (candidate / "migrations").is_dir():
        return candidate
    return None


def _dev_repo_root_or_none() -> Path | None:
    """Repo root in a dev checkout (contains `frontend/`)."""
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / "frontend").is_dir():
        return candidate
    return None


def migrations_dir() -> Path:
    """Wheel: tokenflow/_migrations. Dev: backend/migrations."""
    packaged = _package_root() / "_migrations"
    if packaged.is_dir():
        return packaged
    dev = _dev_backend_root_or_none()
    if dev is not None:
        return dev / "migrations"
    raise FileNotFoundError(
        "no migrations directory — wheel missing _migrations or not in a dev checkout"
    )


def frontend_dist_dir() -> Path | None:
    """Wheel: tokenflow/_static. Dev: <repo>/frontend/dist. None if neither built."""
    packaged = _package_root() / "_static"
    if packaged.is_dir() and (packaged / "index.html").exists():
        return packaged
    repo = _dev_repo_root_or_none()
    if repo is not None:
        dev = repo / "frontend" / "dist"
        if dev.is_dir() and (dev / "index.html").exists():
            return dev
    return None
