from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["analytics"])


@router.get("/analytics/kpi")
async def kpi(range: str = "7d", repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    return repo.analytics_kpi(range)


@router.get("/analytics/daily")
async def daily(range: str = "30d", repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    return repo.analytics_daily(range)


@router.get("/analytics/heatmap")
async def heatmap(range: str = "7d", repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    grid = repo.analytics_heatmap(range)
    return {"range": range, "grid": grid}


@router.get("/analytics/cost-breakdown")
async def cost_breakdown(range: str = "30d", repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    return repo.analytics_cost_breakdown(range)


@router.get("/analytics/top-wastes")
async def top_wastes(range: str = "30d", limit: int = 4) -> list[dict[str, Any]]:
    # Phase E stub: real waste detection comes later. Return empty so UI shows empty state.
    return []
