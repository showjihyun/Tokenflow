from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tokenflow import __version__
from tokenflow.adapters.hook.event_tailer import EventTailer
from tokenflow.adapters.persistence import migrations, paths
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.transcript.tailer import TranscriptTailer
from tokenflow.adapters.web.pubsub import EventBus
from tokenflow.adapters.web.routes import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    paths.ensure_dirs()
    applied = migrations.run_migrations()
    if applied:
        logger.info("Applied migrations: %s", applied)

    repo = Repository()
    bus = EventBus(buffer_size=100)
    app.state.repo = repo
    app.state.bus = bus

    transcript_tailer = TranscriptTailer(repo, publish=bus.publish)
    event_tailer = EventTailer(repo, publish=bus.publish)
    app.state.transcript_tailer = transcript_tailer
    app.state.event_tailer = event_tailer

    event_task = asyncio.create_task(event_tailer.run(), name="event-tailer")
    transcript_task = asyncio.create_task(transcript_tailer.run(), name="transcript-tailer")

    try:
        yield
    finally:
        event_tailer.stop()
        transcript_tailer.stop()
        for t in (event_task, transcript_task):
            t.cancel()
        for t in (event_task, transcript_task):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        repo.close()


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Token Flow", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*", "Last-Event-ID"],
    )

    @app.get("/api/system/health")
    async def health() -> dict[str, object]:
        ndjson = paths.events_ndjson_path()
        return {
            "status": "ok",
            "version": __version__,
            "db": "ok" if paths.db_path().exists() else "missing",
            "hook": "active" if ndjson.exists() and ndjson.stat().st_size > 0 else "not-connected",
            "api_key": "configured" if paths.secret_path().exists() else "not-configured",
            "home": str(paths.tokenflow_dir()),
        }

    app.include_router(api_router)

    if frontend_dist is not None and frontend_dist.is_dir():
        assets = frontend_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            return FileResponse(frontend_dist / "index.html")

    return app
