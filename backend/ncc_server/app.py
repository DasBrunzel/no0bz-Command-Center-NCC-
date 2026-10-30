from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from ncc.security import SECURITY_HEADERS

from ncc_server import __version__
from ncc_server.alert_service import evaluate_alerts, mark_notified
from ncc_server.api.v1 import router as v1_router
from ncc_server.config import ServerSettings, get_server_settings
from ncc_server.database import Database
from ncc_server.game_metadata import refresh_game_metadata
from ncc_server.hardware_stats import backfill_hardware_rollups
from ncc_server.telegram import get_telegram_settings, send_telegram_alert
from ncc_server.unraid_service import collect_unraid

STATIC_DIR = Path(__file__).with_name("static")
logger = logging.getLogger(__name__)


def create_app(
    settings: ServerSettings | None = None,
    database: Database | None = None,
) -> FastAPI:
    active_settings = settings or get_server_settings()
    active_database = database or Database(active_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if active_settings.database_check_on_start:
            active_database.ping()
        alert_task = asyncio.create_task(_alert_loop(active_database, active_settings))
        unraid_task = asyncio.create_task(_unraid_loop(active_database, active_settings))
        game_task = asyncio.create_task(_game_metadata_loop(active_database, active_settings))
        rollup_task = asyncio.create_task(_rollup_backfill_loop(active_database))
        try:
            yield
        finally:
            alert_task.cancel()
            unraid_task.cancel()
            game_task.cancel()
            rollup_task.cancel()
            with suppress(asyncio.CancelledError):
                await game_task
            with suppress(asyncio.CancelledError):
                await rollup_task
            with suppress(asyncio.CancelledError):
                await alert_task
            with suppress(asyncio.CancelledError):
                await unraid_task
            active_database.dispose()

    application = FastAPI(
        title="no0bz Command Center Server",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    application.state.database = active_database
    application.state.server_settings = active_settings

    @application.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        if request.url.path.startswith("/api/v1/fleet"):
            response.headers["Cache-Control"] = "no-store"
        return response

    application.include_router(v1_router)
    if (STATIC_DIR / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @application.get("/", include_in_schema=False)
    async def root() -> Response:
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {"service": "ncc-server", "version": __version__, "api": "/api/v1"}
        )

    return application


app = create_app()


async def _alert_loop(database: Database, settings: ServerSettings) -> None:
    while True:
        try:
            with database.session() as session:
                notifications = evaluate_alerts(session, settings)
                telegram_settings = get_telegram_settings(session)
            for notification in notifications:
                if telegram_settings.enabled and await send_telegram_alert(settings, notification, telegram_settings):
                    with database.session() as session:
                        mark_notified(session, notification.alert_id, notification.state)
        except Exception as exc:
            logger.warning("Alert loop failed: %s", exc)
        await asyncio.sleep(30)


async def _unraid_loop(database: Database, settings: ServerSettings) -> None:
    while True:
        try:
            await collect_unraid(database, settings)
        except Exception as exc:
            logger.warning("Unraid collector failed: %s", exc)
        await asyncio.sleep(30)


async def _game_metadata_loop(database: Database, settings: ServerSettings) -> None:
    if not settings.game_metadata_enabled:
        return
    while True:
        # Start late so a short-lived process, such as a test, never goes online.
        await asyncio.sleep(20)
        try:
            await refresh_game_metadata(database)
        except Exception as exc:
            logger.warning("Game metadata refresh failed: %s", exc)
        await asyncio.sleep(40)


async def _rollup_backfill_loop(database: Database) -> None:
    """Add stored telemetry to the hourly statistics, a batch at a time."""
    while True:
        await asyncio.sleep(15)
        try:
            # The database work is synchronous; keep the event loop free.
            added = await asyncio.to_thread(backfill_hardware_rollups, database)
        except Exception as exc:
            logger.warning("Hardware statistics backfill failed: %s", exc)
            added = 0
        if not added:
            await asyncio.sleep(285)
