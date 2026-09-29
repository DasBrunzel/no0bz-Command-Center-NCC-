from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ncc.config import get_settings
from ncc.security import websocket_authorized

router = APIRouter()


@router.get("/api/metrics")
async def metrics() -> dict[str, Any]:
    from ncc.app import collector

    return collector.snapshot()


@router.get("/api/history")
async def history(minutes: int = Query(default=60, ge=1, le=10080)) -> dict[str, Any]:
    from ncc.app import store

    return {"minutes": minutes, "backend": store.backend, "points": store.history(minutes)}


@router.websocket("/ws/live")
async def live(websocket: WebSocket) -> None:
    from ncc.app import collector

    settings = get_settings()
    origin = websocket.headers.get("origin")
    allowed = {f"http://127.0.0.1:{settings.port}", f"http://localhost:{settings.port}", f"http://{settings.host}:{settings.port}"}
    if origin and origin not in allowed:
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    if not websocket_authorized(websocket, settings):
        await websocket.close(code=1008, reason="Missing or invalid NCC token")
        return
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(collector.snapshot())
            await asyncio.sleep(settings.interval)
    except (WebSocketDisconnect, RuntimeError):
        return

