from __future__ import annotations

import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ncc.api.changelog import router as changelog_router
from ncc.api.chat import router as chat_router
from ncc.api.metrics import router as metrics_router
from ncc.api.nodes import router as nodes_router
from ncc.api.processes import router as processes_router
from ncc.api.profile import router as profile_router
from ncc.api.system import router as system_router
from ncc.collectors.registry import ProviderRegistry, SnapshotCollector, save_hardware_cache
from ncc.config import ROOT, get_settings
from ncc.multipc.client import NodeClient
from ncc.security import SECURITY_HEADERS
from ncc.storage.db import MetricsStore, TelemetryRecorder

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    collector.start()
    recorder.start()
    node_client.start()
    if not (ROOT / "ncc_system_cache.json").exists():
        from ncc.api.system import static_profile

        save_hardware_cache(registry, static_profile())
    try:
        yield
    finally:
        await node_client.stop()
        recorder.stop()
        collector.stop()


app = FastAPI(title="no0bz Command Center", version="0.1.0", lifespan=lifespan)
settings = get_settings()
registry = ProviderRegistry(settings)

collector = SnapshotCollector(registry, settings.interval, socket.gethostname())
store = MetricsStore(settings.retention_hours)
recorder = TelemetryRecorder(store, collector.snapshot, settings.interval)
node_client = NodeClient(settings, collector.snapshot)
allowed_hosts = ["127.0.0.1", "localhost", "[::1]"]
if settings.host not in {"127.0.0.1", "::1", "localhost"}:
    allowed_hosts.append(settings.host)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.middleware("http")
async def secure_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    origin = request.headers.get("origin")
    if origin and not _allowed_origin(origin):
        return HTMLResponse("Origin not allowed", status_code=403)
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


def _allowed_origin(origin: str) -> bool:
    configured = {f"http://{settings.host}:{settings.port}", f"https://{settings.host}:{settings.port}"}
    loopback = {f"http://127.0.0.1:{settings.port}", f"http://localhost:{settings.port}"}
    return origin in configured | loopback


app.include_router(system_router)
app.include_router(metrics_router)
app.include_router(nodes_router)
app.include_router(processes_router)
app.include_router(chat_router)
app.include_router(profile_router)
app.include_router(changelog_router)


if STATIC_DIR.joinpath("index.html").exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
else:
    @app.get("/", response_class=HTMLResponse)
    async def missing_frontend() -> str:
        return """<!doctype html><meta charset='utf-8'><title>NCC</title>
        <style>body{font:16px system-ui;background:#071018;color:#d7f9ff;padding:3rem}</style>
        <h1>no0bz Command Center</h1><p>Das Frontend wurde noch nicht gebaut.</p>
        <pre>cd frontend\nnpm install\nnpm run build\npython ../scripts/build_frontend.py</pre>"""

