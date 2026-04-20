"""Dependency injection helpers used by FastAPI routes.

The app lifespan sets ``app.state.repo`` / ``app.state.bus``; these getters read from there.
"""
from __future__ import annotations

from fastapi import Request

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.pubsub import EventBus


def get_repo(request: Request) -> Repository:
    return request.app.state.repo  # type: ignore[no-any-return]


def get_bus(request: Request) -> EventBus:
    return request.app.state.bus  # type: ignore[no-any-return]
