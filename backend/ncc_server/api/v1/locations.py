"""Opt-in GPS history (heatmap) of app nodes, for the dashboard and for the app itself."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server import __version__
from ncc_server.access import manageable_node, visible_node
from ncc_server.api.v1.node_chat import chat_node
from ncc_server.auth import DashboardIdentity, database_session, require_dashboard_identity
from ncc_server.config import ServerSettings
from ncc_server.location_service import (
    delete_locations,
    location_gpx,
    location_heatmap,
    set_location_tracking,
)
from ncc_server.models import Node
from ncc_server.schemas import LocationHeatmapResponse, LocationTrackingRequest

dashboard_router = APIRouter(prefix="/fleet/nodes", tags=["locations"])
node_router = APIRouter(prefix="/nodes", tags=["agents"], dependencies=[Depends(limited("v1-node-location", 30))])
map_router = APIRouter(prefix="/map", tags=["locations"])

TILE_MAX_AGE_SECONDS = 30 * 24 * 3600
TILE_MAX_ZOOM = 19


@dashboard_router.get("/{node_id}/locations", response_model=LocationHeatmapResponse)
async def heatmap(
    node_id: str,
    days: int = Query(default=30, ge=1, le=3660),
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> LocationHeatmapResponse:
    visible_node(session, identity, node_id)
    return location_heatmap(session, node_id, days)


@dashboard_router.get("/{node_id}/locations.gpx")
async def gpx(
    node_id: str,
    days: int = Query(default=30, ge=1, le=3660),
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> Response:
    node = visible_node(session, identity, node_id)
    filename = f"ncc-{node_id[:8]}-{days}d.gpx"
    return Response(
        location_gpx(session, node, days),
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@dashboard_router.put("/{node_id}/location-tracking", response_model=LocationTrackingRequest)
async def dashboard_tracking(
    node_id: str,
    payload: LocationTrackingRequest,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> LocationTrackingRequest:
    node = manageable_node(session, identity, node_id)
    set_location_tracking(session, node, payload.enabled)
    # A connected phone switches immediately instead of at its next heartbeat.
    request.app.state.live_hub.send_config(node_id, {"location_tracking": payload.enabled})
    return payload


@dashboard_router.delete("/{node_id}/locations")
async def dashboard_delete(
    node_id: str,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> dict[str, int]:
    manageable_node(session, identity, node_id)
    return {"deleted": delete_locations(session, node_id)}


@node_router.put("/location-tracking", response_model=LocationTrackingRequest)
async def app_tracking(
    payload: LocationTrackingRequest,
    node: Node = Depends(chat_node),
    session: Session = Depends(database_session),
) -> LocationTrackingRequest:
    set_location_tracking(session, node, payload.enabled)
    return payload


@node_router.delete("/locations")
async def app_delete(node: Node = Depends(chat_node), session: Session = Depends(database_session)) -> dict[str, int]:
    return {"deleted": delete_locations(session, node.id)}


@map_router.get("/tiles/{z}/{x}/{y}.png", dependencies=[Depends(require_dashboard_identity)])
async def tile(z: int, x: int, y: int, request: Request) -> Response:
    """OpenStreetMap tile through the server, cached on disk for 30 days."""
    if not 0 <= z <= TILE_MAX_ZOOM or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise HTTPException(status_code=404, detail="tile out of range")
    settings: ServerSettings = request.app.state.server_settings
    path = Path(settings.map_tile_cache_dir) / str(z) / str(x) / f"{y}.png"
    headers = {"Cache-Control": "private, max-age=86400"}
    if path.is_file() and time.time() - path.stat().st_mtime < TILE_MAX_AGE_SECONDS:
        return Response(path.read_bytes(), media_type="image/png", headers=headers)
    url = settings.map_tile_url.format(z=z, x=x, y=y)
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": f"no0bz-Command-Center/{__version__} (self-hosted)"}) as client:
            upstream = await client.get(url)
    except httpx.HTTPError as exc:
        if path.is_file():  # stale is better than nothing
            return Response(path.read_bytes(), media_type="image/png", headers=headers)
        raise HTTPException(status_code=502, detail="map tile unavailable") from exc
    if upstream.status_code != 200 or not upstream.headers.get("content-type", "").startswith("image/"):
        raise HTTPException(status_code=502, detail="map tile unavailable")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(upstream.content)
    temporary.replace(path)
    return Response(upstream.content, media_type="image/png", headers=headers)
