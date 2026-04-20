from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from tokenflow import __version__
from tokenflow.adapters.persistence import paths, secret_store
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["system"])


class IngestionPausePayload(BaseModel):
    paused: bool


def _backup_db(reason: str, repo: Repository | None = None) -> dict[str, Any] | None:
    db = paths.db_path()
    if not db.exists() or db.stat().st_size == 0:
        return None
    paths.backups_dir().mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    backup = paths.backups_dir() / f"events_{stamp}_{reason}.duckdb"
    suffix = 1
    while backup.exists():
        backup = paths.backups_dir() / f"events_{stamp}_{reason}_{suffix}.duckdb"
        suffix += 1
    if repo is None:
        shutil.copy2(db, backup)
    else:
        backup_literal = str(backup).replace("'", "''")
        with repo._lock:
            repo._conn.execute(f"ATTACH '{backup_literal}' AS backup_db")
            try:
                repo._conn.execute("COPY FROM DATABASE events TO backup_db")
            finally:
                repo._conn.execute("DETACH backup_db")
    return {"name": backup.name, "path": str(backup), "bytes": backup.stat().st_size}


def _hook_status(repo: Repository) -> dict[str, Any]:
    latest = repo.latest_event_at()
    if latest is None:
        return {"status": "disconnected", "last_event_at": None, "age_seconds": None}
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=UTC)
    age = datetime.now(tz=UTC) - latest.astimezone(UTC)
    status = "stale" if age > timedelta(minutes=10) else "ok"
    return {
        "status": status,
        "last_event_at": latest.isoformat(),
        "age_seconds": int(age.total_seconds()),
    }


@router.get("/system/health")
async def health(request: Request, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    key = secret_store.status()
    hook = _hook_status(repo)
    return {
        "status": "ok",
        "version": __version__,
        "db": "ok" if paths.db_path().exists() else "missing",
        "hook": hook["status"],
        "hook_detail": hook,
        "api_key": "configured" if key["configured"] else "not-configured",
        "api_key_detail": key,
        "ingestion_paused": bool(getattr(request.app.state, "ingestion_paused", False)),
        "home": str(paths.tokenflow_dir()),
    }


@router.post("/system/ingestion-pause")
async def ingestion_pause(payload: IngestionPausePayload, request: Request) -> dict[str, bool]:
    request.app.state.ingestion_paused = payload.paused
    return {"paused": bool(request.app.state.ingestion_paused)}


@router.get("/system/backups")
async def backups() -> list[dict[str, Any]]:
    paths.backups_dir().mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for p in sorted(paths.backups_dir().glob("*.duckdb"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        out.append({
            "name": p.name,
            "path": str(p),
            "bytes": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
        })
    return out


@router.post("/system/vacuum")
async def vacuum(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    before = paths.db_path().stat().st_size if paths.db_path().exists() else 0
    backup = _backup_db("vacuum", repo)
    retention = repo.apply_retention(days=180)
    try:
        repo._exec("VACUUM")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"vacuum failed: {e}") from e
    after = paths.db_path().stat().st_size if paths.db_path().exists() else 0
    return {"ok": True, "before_bytes": before, "after_bytes": after, "backup": backup, "retention": retention}
