from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.alert_service import get_alert_policy, update_alert_policy
from ncc_server.auth import database_session, require_commander_access, require_dashboard_access
from ncc_server.fleet_service import (
    create_fleet_group,
    fleet_node,
    fleet_summary,
    forget_fleet_node,
    list_fleet_alerts,
    list_fleet_groups,
    list_fleet_nodes,
    node_monthly_network_usage,
    node_telemetry,
    rename_fleet_node,
    update_fleet_layout,
    update_fleet_node_role,
)
from ncc_server.schemas import (
    AlertPolicyResponse,
    AlertPolicyUpdateRequest,
    FleetAlertResponse,
    FleetGroupCreateRequest,
    FleetGroupResponse,
    FleetLayoutUpdateRequest,
    FleetNodeRenameRequest,
    FleetNodeResponse,
    FleetNodeRoleUpdateRequest,
    FleetSummaryResponse,
    FleetTelemetryPoint,
    NetworkUsageSummary,
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


@router.get("/groups", response_model=list[FleetGroupResponse])
async def groups(session: Session = Depends(database_session)) -> list[FleetGroupResponse]:
    return list_fleet_groups(session)


@router.post("/groups", response_model=FleetGroupResponse, status_code=201)
async def create_group(
    payload: FleetGroupCreateRequest, session: Session = Depends(database_session)
) -> FleetGroupResponse:
    return create_fleet_group(session, payload.name)


@router.put("/layout", status_code=204)
async def set_layout(
    payload: FleetLayoutUpdateRequest, session: Session = Depends(database_session)
) -> None:
    if not update_fleet_layout(session, payload.placements):
        raise HTTPException(status_code=404, detail="node or group not found")


@router.get("/alerts", response_model=list[FleetAlertResponse])
async def alerts(
    limit: int = Query(default=100, ge=1, le=500), session: Session = Depends(database_session)
) -> list[FleetAlertResponse]:
    return list_fleet_alerts(session, limit)


@router.get("/alert-policy", response_model=AlertPolicyResponse)
async def alert_policy(session: Session = Depends(database_session)) -> AlertPolicyResponse:
    policy = get_alert_policy(session)
    return AlertPolicyResponse.model_validate(policy, from_attributes=True)


@router.put("/alert-policy", response_model=AlertPolicyResponse)
async def set_alert_policy(
    payload: AlertPolicyUpdateRequest, session: Session = Depends(database_session)
) -> AlertPolicyResponse:
    policy = update_alert_policy(session, payload.model_dump())
    return AlertPolicyResponse.model_validate(policy, from_attributes=True)


@router.get("/nodes/{node_id}", response_model=FleetNodeResponse)
async def node(
    node_id: str, request: Request, session: Session = Depends(database_session)
) -> FleetNodeResponse:
    result = fleet_node(session, node_id, request.app.state.server_settings)
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    return result


@router.delete("/nodes/{node_id}", status_code=204, dependencies=[Depends(require_commander_access)])
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


@router.patch(
    "/nodes/{node_id}/role",
    response_model=FleetNodeResponse,
    dependencies=[Depends(require_commander_access)],
)
async def update_node_role(
    node_id: str,
    payload: FleetNodeRoleUpdateRequest,
    request: Request,
    session: Session = Depends(database_session),
) -> FleetNodeResponse:
    result = update_fleet_node_role(session, node_id, payload.access_role)
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


@router.get("/nodes/{node_id}/network/month", response_model=NetworkUsageSummary)
async def monthly_network_usage(
    node_id: str, session: Session = Depends(database_session)
) -> NetworkUsageSummary:
    result = node_monthly_network_usage(session, node_id)
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    return result
