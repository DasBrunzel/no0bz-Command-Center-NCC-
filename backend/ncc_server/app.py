from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from ncc.security import SECURITY_HEADERS

from ncc_server import __version__
from ncc_server.api.v1 import router as v1_router
from ncc_server.config import ServerSettings, get_server_settings
from ncc_server.database import Database

STATIC_DIR = Path(__file__).with_name("static")


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
        try:
            yield
        finally:
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
