from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tokenflow import __version__
from tokenflow.adapters.hook.event_tailer import EventTailer
from tokenflow.adapters.persistence import migrations, paths
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.transcript.tailer import TranscriptTailer
from tokenflow.adapters.web.blocking import run_blocking
from tokenflow.adapters.web.middleware.request_id import RequestIdMiddleware
from tokenflow.adapters.web.pubsub import EventBus
from tokenflow.adapters.web.routes import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await run_blocking(paths.ensure_dirs)
    applied = await run_blocking(migrations.run_migrations)
    if applied:
        logger.info("Applied migrations: %s", applied)

    repo = Repository()
    bus = EventBus(buffer_size=100)
    app.state.repo = repo
    app.state.bus = bus
    app.state.ingestion_paused = False

    await run_blocking(repo.apply_retention, days=180)

    transcript_tailer = TranscriptTailer(repo, publish=bus.publish, is_paused=lambda: bool(app.state.ingestion_paused))
    event_tailer = EventTailer(repo, publish=bus.publish, is_paused=lambda: bool(app.state.ingestion_paused))
    app.state.transcript_tailer = transcript_tailer
    app.state.event_tailer = event_tailer

    event_thread = threading.Thread(target=event_tailer.run, name="event-tailer", daemon=True)
    transcript_thread = threading.Thread(target=transcript_tailer.run, name="transcript-tailer", daemon=True)
    event_thread.start()
    transcript_thread.start()

    try:
        yield
    finally:
        event_tailer.stop()
        transcript_tailer.stop()
        for t in (event_thread, transcript_thread):
            with contextlib.suppress(Exception):
                await asyncio.to_thread(t.join, 5.0)
        await run_blocking(repo.close)


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Token Flow", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*", "Last-Event-ID", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    # Starlette runs middleware in LIFO order, so adding RequestID after CORS
    # means it runs FIRST on the request path and LAST on the response — that
    # way CORS preflights still carry the request_id we assign, and the echoed
    # X-Request-ID header survives CORS header filtering.
    app.add_middleware(RequestIdMiddleware)

    app.include_router(api_router)

    if frontend_dist is not None and frontend_dist.is_dir():
        assets = frontend_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            # SPA routes (client-side) get index.html — React Router then
            # picks the matching <Route>. API/doc/asset paths must never
            # be rewritten to HTML: an unknown /api/* is a real 404, not
            # a frontend view. The /assets/* mount above catches real
            # asset 404s before we get here, but guard anyway.
            if full_path.startswith(("api/", "api", "assets/", "docs", "openapi", "redoc")):
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(frontend_dist / "index.html")

    return app
