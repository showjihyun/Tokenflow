from fastapi import APIRouter

from . import (
    analytics,
    coach,
    events,
    kpi,
    onboarding,
    projects,
    replay,
    rules_and_notifs,
    sessions,
    settings,
    wastes,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(kpi.router)
api_router.include_router(sessions.router)
api_router.include_router(projects.router)
api_router.include_router(events.router)
api_router.include_router(analytics.router)
api_router.include_router(settings.router)
api_router.include_router(onboarding.router)
api_router.include_router(wastes.router)
api_router.include_router(coach.router)
api_router.include_router(replay.router)
api_router.include_router(rules_and_notifs.router)

__all__ = ["api_router"]
