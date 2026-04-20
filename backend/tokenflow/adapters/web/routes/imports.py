from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from tokenflow.adapters.persistence.import_ccprophet import import_from_ccprophet
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["import"])

JobState = Literal["queued", "running", "done", "failed"]
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = Lock()


class ImportCcprophetPayload(BaseModel):
    path: str = Field(min_length=1)


def _set_job(job_id: str, **fields: Any) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        job.update(fields)
        job["updated_at"] = datetime.now(tz=UTC).isoformat()


def _run_import(job_id: str, src_path: str, repo: Repository) -> None:
    _set_job(job_id, state="running")
    try:
        counts = import_from_ccprophet(Path(src_path), repo)
    except Exception as e:
        _set_job(job_id, state="failed", errors=[str(e)])
        return
    imported = sum(counts.values())
    _set_job(job_id, state="done", imported=imported, skipped=0, total=imported, counts=counts, errors=[])


@router.post("/import/ccprophet")
async def import_ccprophet(
    payload: ImportCcprophetPayload,
    background_tasks: BackgroundTasks,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    src = Path(payload.path).expanduser().resolve()
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"not found: {src}")
    job_id = f"imp_{uuid4().hex[:12]}"
    now = datetime.now(tz=UTC).isoformat()
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "state": "queued",
            "path": str(src),
            "imported": 0,
            "skipped": 0,
            "errors": [],
            "total": 0,
            "counts": {},
            "created_at": now,
            "updated_at": now,
        }
    background_tasks.add_task(_run_import, job_id, str(src), repo)
    return {"job_id": job_id, "state": "queued"}


@router.get("/import/ccprophet/status/{job_id}")
async def import_ccprophet_status(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"unknown import job: {job_id}")
        return dict(job)
