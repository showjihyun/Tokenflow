from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tokenflow.adapters.coach.client import DEFAULT_MODEL, SUPPORTED_MODELS
from tokenflow.adapters.persistence import secret_store
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["settings"])


class BudgetPayload(BaseModel):
    monthly_budget_usd: float = Field(ge=0)
    alert_thresholds_pct: list[int] = Field(default_factory=lambda: [50, 75, 90])
    hard_block: bool = False


class TweaksPayload(BaseModel):
    theme: Literal["dark", "light"] | None = None
    density: Literal["compact", "normal", "roomy"] | None = None
    chart_style: Literal["bold", "minimal", "outlined"] | None = None
    sidebar_pos: Literal["left", "right"] | None = None
    alert_level: Literal["quiet", "balanced", "loud"] | None = None
    lang: Literal["ko", "en"] | None = None
    better_prompt_mode: Literal["static", "llm"] | None = None
    # LLM model for AI Coach + better-prompt LLM mode. Clamped server-side to SUPPORTED_MODELS.
    llm_model: Literal["claude-sonnet-4-6", "claude-opus-4-7"] | None = None


class ApiKeyPayload(BaseModel):
    key: str = Field(min_length=8)


def _serialize_config(cfg: dict[str, Any]) -> dict[str, Any]:
    thresholds_raw = cfg.get("alert_thresholds_pct", "[50,75,90]")
    try:
        thresholds = json.loads(thresholds_raw) if isinstance(thresholds_raw, str) else thresholds_raw
    except (TypeError, json.JSONDecodeError):
        thresholds = [50, 75, 90]
    return {
        "budget": {
            "monthly_budget_usd": cfg.get("monthly_budget_usd", 150.0),
            "alert_thresholds_pct": thresholds,
            "hard_block": bool(cfg.get("hard_block", False)),
        },
        "tweaks": {
            "theme": cfg.get("theme", "dark"),
            "density": cfg.get("density", "normal"),
            "chart_style": cfg.get("chart_style", "bold"),
            "sidebar_pos": cfg.get("sidebar_pos", "left"),
            "alert_level": cfg.get("alert_level", "balanced"),
            "lang": cfg.get("lang", "ko"),
            "better_prompt_mode": cfg.get("better_prompt_mode", "static"),
            "llm_model": cfg.get("llm_model") or DEFAULT_MODEL,
        },
        "llm": {
            "model": cfg.get("llm_model") or DEFAULT_MODEL,
            "supported": list(SUPPORTED_MODELS),
        },
    }


@router.get("/settings")
async def get_settings(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    return _serialize_config(repo.get_config())


@router.put("/settings/budget")
async def put_budget(payload: BudgetPayload, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    repo.patch_config(
        monthly_budget_usd=payload.monthly_budget_usd,
        alert_thresholds_pct=json.dumps(payload.alert_thresholds_pct),
        hard_block=payload.hard_block,
    )
    return _serialize_config(repo.get_config())


@router.patch("/settings/tweaks")
async def patch_tweaks(payload: TweaksPayload, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    repo.patch_config(**updates)
    return _serialize_config(repo.get_config())


@router.get("/settings/api-key/status")
async def api_key_status() -> dict[str, Any]:
    """Report presence + backend (keyring vs file) so the UI can surface it."""
    return secret_store.status()


@router.post("/settings/api-key")
async def set_api_key(payload: ApiKeyPayload) -> dict[str, Any]:
    try:
        backend = secret_store.set_api_key(payload.key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"configured": True, "backend": backend}


@router.delete("/settings/api-key")
async def delete_api_key() -> dict[str, bool]:
    secret_store.delete_api_key()
    return {"configured": False}
