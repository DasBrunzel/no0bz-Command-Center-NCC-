from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.alert_service import AlertNotification, get_alert_policy, update_alert_policy
from ncc_server.auth import database_session, require_commander_access, require_dashboard_access
from ncc_server.fleet_service import (
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
    node_telemetry,
    rename_fleet_node,
    reset_network_statistics,
    set_fleet_gaming_mode,
    update_fleet_layout,
    update_fleet_node_role,
)
from ncc_server.schemas import (
    AlertPolicyResponse,
    AlertPolicyUpdateRequest,
    FleetAlertResponse,
    FleetGamingModeRequest,
    FleetGroupCreateRequest,
    FleetGroupResponse,
    FleetLayoutUpdateRequest,
    FleetNodeRenameRequest,
    FleetNodeResponse,
    FleetNodeRoleUpdateRequest,
    FleetSummaryResponse,
    FleetTelemetryPoint,
    NetworkUsageSummary,
    PhysicalDeviceCreateRequest,
    PhysicalDeviceResponse,
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


def _physical_device_response(device) -> PhysicalDeviceResponse:  # type: ignore[no-untyped-def]
    return PhysicalDeviceResponse(
        device_id=device.id, display_name=device.display_name, node_ids=[node.id for node in device.nodes]
    )


@router.get("/physical-devices", response_model=list[PhysicalDeviceResponse])
async def physical_devices(session: Session = Depends(database_session)) -> list[PhysicalDeviceResponse]:
    return [_physical_device_response(device) for device in list_physical_devices(session)]


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


@router.post("/alerts/clear", dependencies=[Depends(require_commander_access)])
async def clear_alerts(session: Session = Depends(database_session)) -> dict[str, int]:
    return {"cleared": clear_active_alerts(session)}


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


def _telegram_response(settings, preferences) -> TelegramSettingsResponse:  # type: ignore[no-untyped-def]
    return TelegramSettingsResponse(
        configured=telegram_is_configured(settings),
        enabled=preferences.enabled,
        warning_title=preferences.warning_title,
        critical_title=preferences.critical_title,
        resolved_title=preferences.resolved_title,
        footer=preferences.footer,
    )


@router.get("/telegram", response_model=TelegramSettingsResponse)
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


@router.put(
    "/nodes/{node_id}/gaming-mode",
    response_model=FleetNodeResponse,
    dependencies=[Depends(require_commander_access)],
)
async def set_gaming_mode(
    node_id: str, payload: FleetGamingModeRequest, request: Request, session: Session = Depends(database_session)
) -> FleetNodeResponse:
    result = set_fleet_gaming_mode(session, node_id, payload.minutes)
    if result is None:
        raise HTTPException(status_code=404, detail="node not found")
    response = fleet_node(session, result.id, request.app.state.server_settings)
    if response is None:  # pragma: no cover
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


@router.post(
    "/network/reset",
    status_code=204,
    dependencies=[Depends(require_commander_access)],
)
async def reset_network(session: Session = Depends(database_session)) -> None:
    reset_network_statistics(session)
