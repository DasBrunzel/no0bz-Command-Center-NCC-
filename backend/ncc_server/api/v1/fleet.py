from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.access import manageable_node, visible_node, visible_node_ids
from ncc_server.alert_service import AlertNotification, get_alert_policy, update_alert_policy
from ncc_server.auth import (
    DashboardIdentity,
    database_session,
    require_commander_access,
    require_dashboard_access,
    require_dashboard_identity,
    require_staff_access,
)
from ncc_server.fleet_service import (
    attach_physical_device_node,
    clear_active_alerts,
    create_fleet_group,
    create_physical_device,
    detach_physical_device_node,
    fleet_node,
    fleet_summary,
    forget_fleet_node,
    list_fleet_alerts,
    list_fleet_groups,
    list_fleet_nodes,
    list_physical_devices,
    node_monthly_network_usage,
    node_network_history,
    node_telemetry,
    rename_fleet_node,
    request_fleet_update_check,
    reset_network_statistics,
    set_fleet_gaming_mode,
    set_node_owner,
    update_fleet_layout,
    update_fleet_node_role,
    update_sensor_label,
)
from ncc_server.release_service import assign_release, update_node_channel
from ncc_server.schemas import (
    AlertPolicyResponse,
    AlertPolicyUpdateRequest,
    FleetAlertResponse,
    FleetGamingModeRequest,
    FleetGroupCreateRequest,
    FleetGroupResponse,
    FleetLayoutUpdateRequest,
    FleetNodeReleaseAssignmentRequest,
    FleetNodeRenameRequest,
    FleetNodeResponse,
    FleetNodeRoleUpdateRequest,
    FleetNodeUpdateChannelRequest,
    FleetSummaryResponse,
    FleetTelemetryPoint,
    NetworkHistorySample,
    NetworkUsageSummary,
    NodeOwnerUpdateRequest,
    PhysicalDeviceCreateRequest,
    PhysicalDeviceResponse,
    SensorLabelUpdateRequest,
    TelegramSettingsResponse,
    TelegramSettingsUpdateRequest,
)
from ncc_server.telegram import (
    get_telegram_settings,
    send_telegram_alert,
    telegram_is_configured,
    update_telegram_settings,
)

router = APIRouter(
    prefix="/fleet",
    tags=["fleet"],
    dependencies=[Depends(require_dashboard_access), Depends(limited("v1-fleet-read", 300))],
)


@router.get("/summary", response_model=FleetSummaryResponse)
async def summary(
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> FleetSummaryResponse:
    return fleet_summary(session, request.app.state.server_settings, visible_node_ids(session, identity))


@router.get("/nodes", response_model=list[FleetNodeResponse])
async def nodes(
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> list[FleetNodeResponse]:
    return list_fleet_nodes(session, request.app.state.server_settings, visible_node_ids(session, identity))


@router.get("/groups", response_model=list[FleetGroupResponse])
async def groups(session: Session = Depends(database_session)) -> list[FleetGroupResponse]:
    return list_fleet_groups(session)


def _physical_device_response(device, node_ids: set[str] | None = None) -> PhysicalDeviceResponse:  # type: ignore[no-untyped-def]
    return PhysicalDeviceResponse(
        device_id=device.id, display_name=device.display_name,
        node_ids=[node.id for node in device.nodes if node_ids is None or node.id in node_ids],
    )


@router.get("/physical-devices", response_model=list[PhysicalDeviceResponse])
async def physical_devices(
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> list[PhysicalDeviceResponse]:
    allowed = visible_node_ids(session, identity)
    return [
        _physical_device_response(device, allowed) for device in list_physical_devices(session)
        if allowed is None or any(node.id in allowed for node in device.nodes)
    ]


@router.post("/physical-devices", response_model=PhysicalDeviceResponse, status_code=201,
             dependencies=[Depends(require_commander_access)])
async def create_device(
    payload: PhysicalDeviceCreateRequest, session: Session = Depends(database_session)
) -> PhysicalDeviceResponse:
    device = create_physical_device(session, payload.display_name, payload.node_ids)
    if device is None:
        raise HTTPException(status_code=404, detail="node not found")
    return _physical_device_response(device)


@router.delete("/physical-devices/{device_id}/nodes/{node_id}", status_code=204,
               dependencies=[Depends(require_commander_access)])
async def detach_device_node(device_id: str, node_id: str, session: Session = Depends(database_session)) -> None:
    if not detach_physical_device_node(session, device_id, node_id):
        raise HTTPException(status_code=404, detail="physical device or node not found")


@router.post("/physical-devices/{device_id}/nodes/{node_id}", response_model=PhysicalDeviceResponse,
             dependencies=[Depends(require_commander_access)])
async def attach_device_node(device_id: str, node_id: str, session: Session = Depends(database_session)) -> PhysicalDeviceResponse:
    try:
        device = attach_physical_device_node(session, device_id, node_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if device is None:
        raise HTTPException(status_code=404, detail="physical device or node not found")
    session.expire(device, ["nodes"])
    return _physical_device_response(device)


@router.post("/groups", response_model=FleetGroupResponse, status_code=201, dependencies=[Depends(require_commander_access)])
async def create_group(
    payload: FleetGroupCreateRequest, session: Session = Depends(database_session)
) -> FleetGroupResponse:
    return create_fleet_group(session, payload.name)


@router.put("/layout", status_code=204, dependencies=[Depends(require_commander_access)])
async def set_layout(
    payload: FleetLayoutUpdateRequest, session: Session = Depends(database_session)
) -> None:
    if not update_fleet_layout(session, payload.placements):
        raise HTTPException(status_code=404, detail="node or group not found")


@router.get("/alerts", response_model=list[FleetAlertResponse])
async def alerts(
    limit: int = Query(default=100, ge=1, le=500),
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> list[FleetAlertResponse]:
    return list_fleet_alerts(session, limit, visible_node_ids(session, identity))


@router.post("/alerts/clear", dependencies=[Depends(require_commander_access)])
async def clear_alerts(session: Session = Depends(database_session)) -> dict[str, int]:
    return {"cleared": clear_active_alerts(session)}


@router.get("/alert-policy", response_model=AlertPolicyResponse)
async def alert_policy(session: Session = Depends(database_session)) -> AlertPolicyResponse:
    policy = get_alert_policy(session)
    return AlertPolicyResponse.model_validate(policy, from_attributes=True)


@router.put("/alert-policy", response_model=AlertPolicyResponse, dependencies=[Depends(require_commander_access)])
async def set_alert_policy(
    payload: AlertPolicyUpdateRequest, session: Session = Depends(database_session)
) -> AlertPolicyResponse:
    policy = update_alert_policy(session, payload.model_dump())
    return AlertPolicyResponse.model_validate(policy, from_attributes=True)


def _telegram_response(settings, preferences) -> TelegramSettingsResponse:  # type: ignore[no-untyped-def]
    return TelegramSettingsResponse(
        configured=telegram_is_configured(settings),
        enabled=preferences.enabled,
        warning_title=preferences.warning_title,
        critical_title=preferences.critical_title,
        resolved_title=preferences.resolved_title,
        footer=preferences.footer,
    )


@router.get("/telegram", response_model=TelegramSettingsResponse, dependencies=[Depends(require_staff_access)])
async def telegram_settings(
    request: Request, session: Session = Depends(database_session)
) -> TelegramSettingsResponse:
    return _telegram_response(request.app.state.server_settings, get_telegram_settings(session))


@router.put(
    "/telegram",
    response_model=TelegramSettingsResponse,
    dependencies=[Depends(require_commander_access)],
)
async def set_telegram_settings(
    payload: TelegramSettingsUpdateRequest,
    request: Request,
    session: Session = Depends(database_session),
) -> TelegramSettingsResponse:
    preferences = update_telegram_settings(session, payload.model_dump())
    return _telegram_response(request.app.state.server_settings, preferences)


@router.post("/telegram/test", dependencies=[Depends(require_commander_access)])
async def test_telegram(
    request: Request, session: Session = Depends(database_session)
) -> dict[str, bool]:
    settings = request.app.state.server_settings
    preferences = get_telegram_settings(session)
    if not telegram_is_configured(settings):
        raise HTTPException(status_code=503, detail="Telegram ist auf dem Server nicht konfiguriert")
    sent = await send_telegram_alert(
        settings,
        AlertNotification(
            "telegram-test", "active", "warning", "NCC Dashboard", "telegram-test",
            "Dies ist eine Testnachricht aus den NCC-Einstellungen.",
        ),
        preferences,
    )
    if not sent:
        raise HTTPException(status_code=502, detail="Telegram-Test konnte nicht zugestellt werden")
    return {"sent": True}


def _node_or_404(session: Session, node_id: str, request: Request) -> FleetNodeResponse:
    response = fleet_node(session, node_id, request.app.state.server_settings)
    if response is None:  # pragma: no cover - callers load the node first
        raise HTTPException(status_code=404, detail="node not found")
    return response


@router.get("/nodes/{node_id}", response_model=FleetNodeResponse)
async def node(
    node_id: str,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> FleetNodeResponse:
    visible_node(session, identity, node_id)
    return _node_or_404(session, node_id, request)


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
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> FleetNodeResponse:
    manageable_node(session, identity, node_id)
    if rename_fleet_node(session, node_id, payload.display_name) is None:
        raise HTTPException(status_code=404, detail="node not found")
    return _node_or_404(session, node_id, request)


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
    if update_fleet_node_role(session, node_id, payload.access_role) is None:
        raise HTTPException(status_code=404, detail="node not found")
    return _node_or_404(session, node_id, request)


@router.put("/nodes/{node_id}/owner", response_model=FleetNodeResponse, dependencies=[Depends(require_commander_access)])
async def update_node_owner(
    node_id: str, payload: NodeOwnerUpdateRequest, request: Request, session: Session = Depends(database_session)
) -> FleetNodeResponse:
    try:
        result = set_node_owner(session, node_id, payload.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    return _node_or_404(session, node_id, request)


@router.put("/nodes/{node_id}/gaming-mode", response_model=FleetNodeResponse)
async def set_gaming_mode(
    node_id: str,
    payload: FleetGamingModeRequest,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> FleetNodeResponse:
    manageable_node(session, identity, node_id)
    set_fleet_gaming_mode(session, node_id, payload.minutes)
    return _node_or_404(session, node_id, request)


@router.put("/nodes/{node_id}/sensor-labels", response_model=FleetNodeResponse)
async def set_sensor_label(
    node_id: str,
    payload: SensorLabelUpdateRequest,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> FleetNodeResponse:
    manageable_node(session, identity, node_id)
    update_sensor_label(session, node_id, payload.key, payload.name, payload.role)
    return _node_or_404(session, node_id, request)


@router.post("/nodes/{node_id}/update-check", response_model=FleetNodeResponse)
async def request_update_check(
    node_id: str,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> FleetNodeResponse:
    manageable_node(session, identity, node_id)
    request_fleet_update_check(session, node_id)
    return _node_or_404(session, node_id, request)


@router.put("/nodes/{node_id}/release", status_code=204, dependencies=[Depends(require_commander_access)])
async def set_release_for_node(
    node_id: str, payload: FleetNodeReleaseAssignmentRequest, session: Session = Depends(database_session)
) -> None:
    if not assign_release(session, node_id, payload.release_id, payload.allow_downgrade):
        raise HTTPException(status_code=404, detail="node or compatible release not found")


@router.put("/nodes/{node_id}/update-channel", status_code=204, dependencies=[Depends(require_commander_access)])
async def set_update_channel_for_node(
    node_id: str, payload: FleetNodeUpdateChannelRequest, session: Session = Depends(database_session)
) -> None:
    if not update_node_channel(session, node_id, payload.channel):
        raise HTTPException(status_code=404, detail="node not found")


@router.get("/nodes/{node_id}/telemetry", response_model=list[FleetTelemetryPoint])
async def telemetry(
    node_id: str,
    limit: int = Query(default=120, ge=1, le=1000),
    after: str | None = None,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> list[FleetTelemetryPoint]:
    visible_node(session, identity, node_id)
    try:
        result = node_telemetry(session, node_id, limit, after=after)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="telemetry cursor not found") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    return result


@router.get("/nodes/{node_id}/network/history", response_model=list[NetworkHistorySample])
async def network_history(
    node_id: str,
    limit: int = Query(default=48, ge=1, le=1000),
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> list[NetworkHistorySample]:
    visible_node(session, identity, node_id)
    result = node_network_history(session, node_id, limit)
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    return result


@router.get("/nodes/{node_id}/network/month", response_model=NetworkUsageSummary)
async def monthly_network_usage(
    node_id: str,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> NetworkUsageSummary:
    visible_node(session, identity, node_id)
    result = node_monthly_network_usage(session, node_id)
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    return result


@router.post(
    "/network/reset",
    status_code=204,
    dependencies=[Depends(require_commander_access)],
)
async def reset_network(session: Session = Depends(database_session)) -> None:
    reset_network_statistics(session)
