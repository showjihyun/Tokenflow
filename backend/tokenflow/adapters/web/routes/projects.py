from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["projects"])


@router.get("/projects")
async def list_projects(
    range: str = "7d",
    repo: Repository = Depends(get_repo),
) -> list[dict[str, Any]]:
    return repo.projects(range)


@router.get("/projects/{name}/trend")
async def project_trend(
    name: str,
    range: str = "7d",
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    if not repo.project_exists(name):
        raise HTTPException(status_code=404, detail=f"unknown project: {name}")
    return repo.project_trend(name, range)
