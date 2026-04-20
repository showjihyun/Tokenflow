from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["rules-and-notifs"])


class RoutingRulePayload(BaseModel):
    condition_pattern: str = Field(min_length=1, max_length=200)
    target_model: str = Field(min_length=1)
    enabled: bool = True
    priority: int = 100


class NotifPatch(BaseModel):
    enabled: bool | None = None
    channel: Literal["in_app", "system"] | None = None


@router.get("/settings/routing-rules")
async def list_rules(repo: Repository = Depends(get_repo)) -> list[dict[str, Any]]:
    return repo.list_routing_rules()


@router.post("/settings/routing-rules")
async def create_rule(payload: RoutingRulePayload, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    rule_id = uuid.uuid4().hex[:16]
    repo.upsert_routing_rule(
        rule_id=rule_id,
        condition_pattern=payload.condition_pattern,
        target_model=payload.target_model,
        enabled=payload.enabled,
        priority=payload.priority,
    )
    return next((r for r in repo.list_routing_rules() if r["id"] == rule_id), {"id": rule_id})


@router.patch("/settings/routing-rules/{rule_id}")
async def update_rule(
    rule_id: str, payload: RoutingRulePayload, repo: Repository = Depends(get_repo)
) -> dict[str, Any]:
    if not any(r["id"] == rule_id for r in repo.list_routing_rules()):
        raise HTTPException(404)
    repo.upsert_routing_rule(
        rule_id=rule_id,
        condition_pattern=payload.condition_pattern,
        target_model=payload.target_model,
        enabled=payload.enabled,
        priority=payload.priority,
    )
    return next((r for r in repo.list_routing_rules() if r["id"] == rule_id), {"id": rule_id})


@router.delete("/settings/routing-rules/{rule_id}")
async def delete_rule(rule_id: str, repo: Repository = Depends(get_repo)) -> dict[str, bool]:
    repo.delete_routing_rule(rule_id)
    return {"ok": True}


@router.get("/settings/notifications")
async def list_notifs(repo: Repository = Depends(get_repo)) -> list[dict[str, Any]]:
    return repo.list_notification_prefs()


@router.patch("/settings/notifications/{pref_key}")
async def patch_notif(
    pref_key: str, payload: NotifPatch, repo: Repository = Depends(get_repo)
) -> dict[str, Any]:
    repo.update_notification_pref(pref_key, enabled=payload.enabled, channel=payload.channel)
    prefs = repo.list_notification_prefs()
    found = next((p for p in prefs if p["key"] == pref_key), None)
    if not found:
        raise HTTPException(404, f"unknown notification key {pref_key}")
    return found
