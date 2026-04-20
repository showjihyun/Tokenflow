from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["analytics"])
Range = Literal["24h", "7d", "30d", "90d", "all"]


@router.get("/analytics/kpi")
async def kpi(
    range: Range = "7d",
    project: str | None = None,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    return repo.analytics_kpi(range, project=project)


@router.get("/analytics/daily")
async def daily(
    range: Range = "30d",
    project: str | None = None,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    return repo.analytics_daily(range, project=project)


@router.get("/analytics/heatmap")
async def heatmap(
    range: Range = "7d",
    project: str | None = None,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    grid = repo.analytics_heatmap(range, project=project)
    return {"range": range, "grid": grid}


@router.get("/analytics/cost-breakdown")
async def cost_breakdown(
    range: Range = "30d",
    project: str | None = None,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    return repo.analytics_cost_breakdown(range, project=project)


@router.get("/analytics/top-wastes")
async def top_wastes(
    range: Range = "30d",
    limit: int = Query(default=4, ge=1, le=50),
    project: str | None = None,
    repo: Repository = Depends(get_repo),
) -> list[dict[str, Any]]:
    return repo.top_wastes(range_=range, limit=limit, project=project)
