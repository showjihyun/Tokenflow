from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["kpi"])


@router.get("/kpi/summary")
def kpi_summary(
    window: Literal["today", "7d", "30d"] = "today",
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    return repo.kpi_summary(window)


@router.get("/kpi/models")
def kpi_models(repo: Repository = Depends(get_repo)) -> list[dict[str, Any]]:
    return repo.models_today()


@router.get("/kpi/budget")
def kpi_budget(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    return repo.budget()
