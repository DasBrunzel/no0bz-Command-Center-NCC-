from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.auth import database_session, require_dashboard_access
from ncc_server.fleet_service import (
    fleet_node,
    fleet_summary,
    forget_fleet_node,
    list_fleet_nodes,
    node_telemetry,
    rename_fleet_node,
)
from ncc_server.schemas import (
    FleetNodeRenameRequest,
    FleetNodeResponse,
    FleetSummaryResponse,
    FleetTelemetryPoint,
)

router = APIRouter(
    prefix="/fleet",
    tags=["fleet"],
    dependencies=[Depends(require_dashboard_access), Depends(limited("v1-fleet-read", 300))],
)


@router.get("/summary", response_model=FleetSummaryResponse)
async def summary(
    request: Request, session: Session = Depends(database_session)
) -> FleetSummaryResponse:
    return fleet_summary(session, request.app.state.server_settings)


@router.get("/nodes", response_model=list[FleetNodeResponse])
async def nodes(
    request: Request, session: Session = Depends(database_session)
) -> list[FleetNodeResponse]:
    return list_fleet_nodes(session, request.app.state.server_settings)


@router.get("/nodes/{node_id}", response_model=FleetNodeResponse)
async def node(
    node_id: str, request: Request, session: Session = Depends(database_session)
) -> FleetNodeResponse:
    result = fleet_node(session, node_id, request.app.state.server_settings)
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    return result


@router.delete("/nodes/{node_id}", status_code=204)
async def forget_node(
    node_id: str, session: Session = Depends(database_session)
) -> None:
    if not forget_fleet_node(session, node_id):
        raise HTTPException(status_code=404, detail="node not found")


@router.patch("/nodes/{node_id}", response_model=FleetNodeResponse)
async def rename_node(
    node_id: str,
    payload: FleetNodeRenameRequest,
    request: Request,
    session: Session = Depends(database_session),
) -> FleetNodeResponse:
    result = rename_fleet_node(session, node_id, payload.display_name)
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    response = fleet_node(session, result.id, request.app.state.server_settings)
    if response is None:  # pragma: no cover - result was loaded above
        raise HTTPException(status_code=404, detail="node not found")
    return response


@router.get("/nodes/{node_id}/telemetry", response_model=list[FleetTelemetryPoint])
async def telemetry(
    node_id: str,
    limit: int = Query(default=120, ge=1, le=1000),
    session: Session = Depends(database_session),
) -> list[FleetTelemetryPoint]:
    result = node_telemetry(session, node_id, limit)
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    return result
