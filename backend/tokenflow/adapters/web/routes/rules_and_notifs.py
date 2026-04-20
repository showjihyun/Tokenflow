from __future__ import annotations

import uuid
from datetime import UTC, datetime
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


class NotificationCreate(BaseModel):
    # camelCase fields match the frontend notification store payload shape.
    id: str = Field(min_length=1, max_length=120)
    prefKey: str = Field(min_length=1, max_length=80)  # noqa: N815
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=500)
    createdAt: datetime | None = None  # noqa: N815


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


@router.get("/notifications")
async def list_notification_events(
    limit: int = 10,
    repo: Repository = Depends(get_repo),
) -> list[dict[str, Any]]:
    return repo.list_notifications(limit=limit)


@router.get("/notifications/unread-count")
async def unread_notification_count(repo: Repository = Depends(get_repo)) -> dict[str, int]:
    return {"count": repo.unread_notification_count()}


@router.post("/notifications")
async def create_notification_event(
    payload: NotificationCreate,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    prefs = repo.list_notification_prefs()
    pref = next((p for p in prefs if p["key"] == payload.prefKey), None)
    if not pref:
        raise HTTPException(404, f"unknown notification key {payload.prefKey}")
    if not pref["enabled"] or pref["channel"] != "in_app":
        return {"ok": False, "stored": False}
    created_at = payload.createdAt or datetime.now(tz=UTC)
    stored = repo.insert_notification(
        id=payload.id,
        pref_key=payload.prefKey,
        title=payload.title,
        body=payload.body,
        created_at=created_at,
    )
    return {"ok": True, "stored": stored}


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    notification = repo.mark_notification_read(notification_id, read_at=datetime.now(tz=UTC))
    if not notification:
        raise HTTPException(404, f"unknown notification {notification_id}")
    return notification


@router.post("/notifications/read-all")
async def mark_all_notification_events_read(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    updated = repo.mark_all_notifications_read(read_at=datetime.now(tz=UTC))
    return {"ok": True, "updated": updated}


@router.delete("/notifications")
async def clear_notification_events(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    deleted = repo.clear_notifications()
    return {"ok": True, "deleted": deleted}
