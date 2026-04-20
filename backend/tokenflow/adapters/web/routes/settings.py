from __future__ import annotations

import contextlib
import json
import os
import stat
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tokenflow.adapters.persistence import paths
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
    """Report presence + parseability so the UI can recover from a corrupt secret.json."""
    secret = paths.secret_path()
    if not secret.exists():
        return {"configured": False, "valid": False}
    try:
        payload = json.loads(secret.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"configured": True, "valid": False, "error": f"cannot read secret.json: {e}"}
    if not isinstance(payload, dict):
        return {"configured": True, "valid": False, "error": "secret.json is not a JSON object"}
    key = payload.get("anthropic_api_key")
    if not isinstance(key, str) or not key.strip():
        return {"configured": True, "valid": False, "error": "anthropic_api_key missing or empty"}
    return {"configured": True, "valid": True}


@router.post("/settings/api-key")
async def set_api_key(payload: ApiKeyPayload) -> dict[str, bool]:
    if not payload.key.strip():
        raise HTTPException(status_code=400, detail="empty key")
    secret = paths.secret_path()
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text(json.dumps({"anthropic_api_key": payload.key.strip()}), encoding="utf-8")
    # Tighten perms on POSIX (best-effort on Windows)
    with contextlib.suppress(OSError):
        os.chmod(secret, stat.S_IRUSR | stat.S_IWUSR)
    return {"configured": True}


@router.delete("/settings/api-key")
async def delete_api_key() -> dict[str, bool]:
    secret = paths.secret_path()
    if secret.exists():
        secret.unlink()
    return {"configured": False}
