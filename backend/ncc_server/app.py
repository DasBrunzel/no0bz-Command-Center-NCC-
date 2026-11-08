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
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from ncc_server import __version__
from ncc_server.alert_service import evaluate_alerts, get_alert_policy, mark_notified
from ncc_server.api.v1 import router as v1_router
from ncc_server.config import ServerSettings, get_server_settings
from ncc_server.database import Database
from ncc_server.game_metadata import refresh_game_metadata
from ncc_server.hardware_stats import backfill_hardware_rollups
from ncc_server.live_hub import LiveHub, active_app_alerts
from ncc_server.release_feed import sync_release_feed
from ncc_server.telegram import get_telegram_settings, send_telegram_alert, telegram_bot_available
from ncc_server.telegram_bot import alert_recipients, poll_updates, send_weekly_recaps
from ncc_server.unraid_service import collect_unraid

STATIC_DIR = Path(__file__).with_name("static")
logger = logging.getLogger(__name__)


class DashboardGZipMiddleware:
    """Compress the dashboard files only.

    StaticFiles sends JS and CSS uncompressed, which roughly triples the first
    load on a phone. API responses stay uncompressed: some carry one-time
    tokens next to request data, and compressing those invites BREACH-style
    guessing for no real gain on small JSON bodies.
    """

    def __init__(self, app: ASGIApp, minimum_size: int = 1024) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not str(scope.get("path", "")).startswith("/api/"):
            await self.gzip(scope, receive, send)
        else:
            await self.app(scope, receive, send)


def create_app(
    settings: ServerSettings | None = None,
    database: Database | None = None,
) -> FastAPI:
    active_settings = settings or get_server_settings()
    active_database = database or Database(active_settings.database_url)
    live_hub = LiveHub()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if active_settings.database_check_on_start:
            active_database.ping()
        alert_task = asyncio.create_task(_alert_loop(active_database, active_settings, live_hub))
        viewer_task = asyncio.create_task(_viewer_expiry_loop(live_hub))
        unraid_task = asyncio.create_task(_unraid_loop(active_database, active_settings))
        game_task = asyncio.create_task(_game_metadata_loop(active_database, active_settings))
        rollup_task = asyncio.create_task(_rollup_backfill_loop(active_database))
        bot_task = asyncio.create_task(_telegram_bot_loop(active_database, active_settings))
        feed_task = asyncio.create_task(_release_feed_loop(active_database, active_settings))
        try:
            yield
        finally:
            feed_task.cancel()
            with suppress(asyncio.CancelledError):
                await feed_task
            alert_task.cancel()
            viewer_task.cancel()
            with suppress(asyncio.CancelledError):
                await viewer_task
            unraid_task.cancel()
            game_task.cancel()
            rollup_task.cancel()
            bot_task.cancel()
            with suppress(asyncio.CancelledError):
                await bot_task
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
    application.state.live_hub = live_hub

    @application.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        if request.url.path.startswith("/api/v1/fleet"):
            response.headers["Cache-Control"] = "no-store"
        return response

    application.add_middleware(DashboardGZipMiddleware)
    application.include_router(v1_router)
    if (STATIC_DIR / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @application.get("/sw.js", include_in_schema=False)
    async def service_worker() -> Response:
        """The dashboard's service worker; served at the root so its scope is "/"."""
        worker = STATIC_DIR / "sw.js"
        if not worker.is_file():
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(worker, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @application.get("/", include_in_schema=False)
    async def root() -> Response:
        index = STATIC_DIR / "index.html"
        if index.is_file():
            # Always revalidate the page: after an update it names new hashed
            # assets, and a heuristically cached copy would load deleted ones.
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return JSONResponse(
            {"service": "ncc-server", "version": __version__, "api": "/api/v1"}
        )

    return application


app = create_app()


async def _alert_loop(database: Database, settings: ServerSettings, live_hub: LiveHub | None = None) -> None:
    while True:
        try:
            with database.session() as session:
                notifications = evaluate_alerts(session, settings)
                telegram_settings = get_telegram_settings(session)
                if live_hub is not None:
                    # Android apps get alerts independently of Telegram.
                    live_hub.publish_alerts(active_app_alerts(session), get_alert_policy(session).app_alerts_enabled)
            for notification in notifications:
                if not telegram_settings.enabled:
                    continue
                with database.session() as session:
                    chats = alert_recipients(session, settings, notification)
                delivered = False
                for chat_id in chats:
                    delivered = await send_telegram_alert(settings, notification, telegram_settings, chat_id) or delivered
                if delivered:
                    with database.session() as session:
                        mark_notified(session, notification.alert_id, notification.state)
        except Exception as exc:
            logger.warning("Alert loop failed: %s", exc)
        await asyncio.sleep(30)


async def _viewer_expiry_loop(live_hub: LiveHub) -> None:
    """Tell phones when no dashboard is watching them any more."""
    while True:
        live_hub.expire_viewers()
        await asyncio.sleep(5)


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
            await refresh_game_metadata(database, steamgriddb_key=settings.steamgriddb_api_key.get_secret_value())
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


async def _release_feed_loop(database: Database, settings: ServerSettings) -> None:
    """Pick up signed payload releases from GitHub, so nobody registers them."""
    if not settings.release_feed_enabled:
        return
    # Start late so a short-lived process, such as a test, never goes online.
    await asyncio.sleep(30)
    while True:
        try:
            await sync_release_feed(database, settings)
        except Exception as exc:
            logger.warning("Release feed check failed: %s", exc)
        await asyncio.sleep(settings.release_feed_interval_seconds)


async def _telegram_bot_loop(database: Database, settings: ServerSettings) -> None:
    """Answer bot messages (account linking) and send the Monday recap."""
    if not telegram_bot_available(settings):
        return
    await asyncio.sleep(5)
    while True:
        try:
            await send_weekly_recaps(database, settings)
            await poll_updates(database, settings)
        except Exception as exc:
            logger.warning("Telegram bot loop failed: %s", exc)
            await asyncio.sleep(30)
