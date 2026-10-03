from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ncc_server.config import ServerSettings
from ncc_server.models import (
    AlertState,
    AuditEvent,
    FleetGroup,
    Node,
    TelemetryPoint,
    TrafficStatisticsSettings,
    utc_now,
)
from ncc_server.node_service import is_online
from ncc_server.schemas import (
    FleetAlertResponse,
    FleetGroupResponse,
    FleetLayoutPlacement,
    FleetNodeResponse,
    FleetSummaryResponse,
    FleetTelemetryPoint,
    NetworkUsageSummary,
)

DEFAULT_FLEET_GROUPS = (
    ("default-pcs-laptops", "PCS & LAPTOPS", 0),
    ("default-servers", "SERVER", 1),
    ("default-mobile", "MOBILE", 2),
    ("default-friends", "FRIENDS", 3),
)


def list_fleet_groups(session: Session) -> list[FleetGroupResponse]:
    _ensure_default_fleet_groups(session)
    groups = session.scalars(select(FleetGroup).order_by(FleetGroup.position, FleetGroup.name)).all()
    return [FleetGroupResponse(group_id=group.id, name=group.name, position=group.position) for group in groups]


def create_fleet_group(session: Session, name: str) -> FleetGroupResponse:
    _ensure_default_fleet_groups(session)
    highest = session.scalar(select(func.max(FleetGroup.position)))
    group = FleetGroup(name=name, position=(highest or 0) + 1)
    session.add(group)
    session.commit()
    return FleetGroupResponse(group_id=group.id, name=group.name, position=group.position)


def update_fleet_layout(session: Session, placements: list[FleetLayoutPlacement]) -> bool:
    _ensure_default_fleet_groups(session)
    group_ids = {placement.group_id for placement in placements}
    valid_groups = set(session.scalars(select(FleetGroup.id).where(FleetGroup.id.in_(group_ids))).all())
    node_ids = {placement.node_id for placement in placements}
    nodes = {node.id: node for node in session.scalars(select(Node).where(Node.id.in_(node_ids))).all()}
    if group_ids != valid_groups or node_ids != set(nodes):
        return False
    for placement in placements:
        node = nodes[placement.node_id]
        node.fleet_group_id = placement.group_id
        node.fleet_position = placement.position
        node.updated_at = utc_now()
    session.commit()
    return True


def _ensure_default_fleet_groups(session: Session) -> None:
    existing = set(session.scalars(select(FleetGroup.id)).all())
    missing = [FleetGroup(id=group_id, name=name, position=position) for group_id, name, position in DEFAULT_FLEET_GROUPS if group_id not in existing]
    if missing:
        session.add_all(missing)
        session.commit()


def list_fleet_alerts(session: Session, limit: int) -> list[FleetAlertResponse]:
    rows = session.execute(
        select(AlertState, Node.display_name)
        .join(Node, Node.id == AlertState.node_id)
        .order_by(AlertState.active.desc(), AlertState.updated_at.desc())
        .limit(limit)
    ).all()
    return [
        FleetAlertResponse(
            alert_id=alert.id,
            node_id=alert.node_id,
            display_name=display_name,
            kind=alert.kind,
            severity=alert.severity,  # type: ignore[arg-type]
            active=alert.active,
            message=alert.message,
            opened_at=alert.opened_at,
            updated_at=alert.updated_at,
            resolved_at=alert.resolved_at,
        )
        for alert, display_name in rows
    ]


def list_fleet_nodes(session: Session, settings: ServerSettings) -> list[FleetNodeResponse]:
    nodes = session.scalars(select(Node).order_by(Node.display_name, Node.id)).all()
    responses = [_node_response(session, node, settings) for node in nodes]
    return sorted(responses, key=lambda item: (not item.online, item.display_name.casefold()))


def fleet_node(
    session: Session, node_id: str, settings: ServerSettings
) -> FleetNodeResponse | None:
    node = session.get(Node, node_id)
    return _node_response(session, node, settings) if node is not None else None


def node_telemetry(
    session: Session, node_id: str, limit: int
) -> list[FleetTelemetryPoint] | None:
    if session.get(Node, node_id) is None:
        return None
    points = session.scalars(
        select(TelemetryPoint)
        .where(TelemetryPoint.node_id == node_id)
        .order_by(TelemetryPoint.recorded_at.desc())
        .limit(limit)
    ).all()
    return [_telemetry_response(point) for point in reversed(points)]


def node_monthly_network_usage(
    session: Session, node_id: str, now: datetime | None = None
) -> NetworkUsageSummary | None:
    """Calculate monthly traffic from counter deltas without deleting raw data.

    Agents report the operating system's cumulative byte counters.  A counter
    reset (for example after a reboot) starts a new counter generation; its
    current value is therefore counted instead of treating the delta as
    negative.
    """
    if session.get(Node, node_id) is None:
        return None
    current = now or utc_now()
    local_now = current.astimezone()
    period_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_start_utc = period_start.astimezone(timezone.utc)
    traffic_settings = session.get(TrafficStatisticsSettings, "default")
    manual_reset = traffic_settings.reset_at if traffic_settings is not None else None
    if manual_reset is not None and manual_reset.tzinfo is None:
        # SQLite returns naive values for timezone-aware columns in tests. The
        # persisted value is UTC, just like PostgreSQL's server-side value.
        manual_reset = manual_reset.replace(tzinfo=timezone.utc)
    effective_start = max(period_start_utc, manual_reset) if manual_reset is not None else period_start_utc
    previous = session.scalar(
        select(TelemetryPoint)
        .where(TelemetryPoint.node_id == node_id, TelemetryPoint.recorded_at < effective_start)
        .order_by(TelemetryPoint.recorded_at.desc())
        .limit(1)
    )
    points = session.scalars(
        select(TelemetryPoint)
        .where(TelemetryPoint.node_id == node_id, TelemetryPoint.recorded_at >= effective_start)
        .order_by(TelemetryPoint.recorded_at)
    ).all()
    previous_pair = _network_counters(previous.payload) if previous is not None else None
    received = sent = 0
    samples = 0
    for point in points:
        current_pair = _network_counters(point.payload)
        if current_pair is None:
            continue
        samples += 1
        if previous_pair is not None:
            received += _counter_delta(previous_pair[0], current_pair[0])
            sent += _counter_delta(previous_pair[1], current_pair[1])
        previous_pair = current_pair
    return NetworkUsageSummary(
        period_start=effective_start,
        received_bytes=received,
        sent_bytes=sent,
        samples=samples,
        available=samples > 0,
    )


def reset_network_statistics(session: Session) -> None:
    """Reset displayed traffic without deleting any raw telemetry."""
    reset_at = utc_now()
    settings = session.get(TrafficStatisticsSettings, "default")
    if settings is None:
        settings = TrafficStatisticsSettings(id="default", reset_at=reset_at)
        session.add(settings)
    else:
        settings.reset_at = reset_at
    session.add(
        AuditEvent(
            actor_type="dashboard",
            actor_id=None,
            action="traffic.statistics.reset",
            details=json.dumps({"reset_at": reset_at.isoformat()}, separators=(",", ":")),
        )
    )
    session.commit()


def _network_counters(payload: dict[str, object]) -> tuple[int, int] | None:
    network = payload.get("network")
    if not isinstance(network, dict):
        return None
    received = _number(network.get("bytes_recv"))
    sent = _number(network.get("bytes_sent"))
    if received is None:
        received_gb = _number(network.get("total_recv_gb"))
        received = int(received_gb * 1024**3) if received_gb is not None else None
    if sent is None:
        sent_gb = _number(network.get("total_sent_gb"))
        sent = int(sent_gb * 1024**3) if sent_gb is not None else None
    if received is None or sent is None:
        return None
    return max(0, int(received)), max(0, int(sent))


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _counter_delta(previous: int, current: int) -> int:
    return current - previous if current >= previous else current


def fleet_summary(session: Session, settings: ServerSettings) -> FleetSummaryResponse:
    nodes = session.scalars(select(Node)).all()
    online = sum(is_online(node, settings.node_offline_after_seconds) for node in nodes)
    pending = sum(not node.approved for node in nodes)
    points = session.scalar(select(func.count()).select_from(TelemetryPoint)) or 0
    return FleetSummaryResponse(
        total_nodes=len(nodes),
        online_nodes=online,
        offline_nodes=len(nodes) - online,
        pending_nodes=pending,
        telemetry_points=points,
        server_time=utc_now(),
    )


def forget_fleet_node(session: Session, node_id: str) -> bool:
    """Remove a node and its bound credentials after an explicit dashboard action."""
    node = session.get(Node, node_id)
    if node is None:
        return False
    session.add(
        AuditEvent(
            actor_type="dashboard",
            actor_id=node.id,
            action="node.forgotten",
            details=json.dumps(
                {"machine_id": node.machine_id, "display_name": node.display_name},
                separators=(",", ":"),
            ),
        )
    )
    session.delete(node)
    session.commit()
    return True


def rename_fleet_node(session: Session, node_id: str, display_name: str) -> Node | None:
    node = session.get(Node, node_id)
    if node is None:
        return None
    node.display_name = display_name
    node.updated_at = utc_now()
    session.add(
        AuditEvent(
            actor_type="dashboard",
            actor_id=node.id,
            action="node.renamed",
            details=json.dumps({"display_name": display_name}, separators=(",", ":")),
        )
    )
    session.commit()
    session.refresh(node)
    return node


def update_fleet_node_role(
    session: Session, node_id: str, access_role: str
) -> Node | None:
    node = session.get(Node, node_id)
    if node is None:
        return None
    node.access_role = access_role
    node.updated_at = utc_now()
    session.add(
        AuditEvent(
            actor_type="dashboard",
            actor_id=node.id,
            action="node.access-role.updated",
            details=json.dumps({"access_role": access_role}, separators=(",", ":")),
        )
    )
    session.commit()
    session.refresh(node)
    return node


def _node_response(
    session: Session, node: Node, settings: ServerSettings
) -> FleetNodeResponse:
    latest = session.scalar(
        select(TelemetryPoint)
        .where(TelemetryPoint.node_id == node.id)
        .order_by(TelemetryPoint.recorded_at.desc())
        .limit(1)
    )
    return FleetNodeResponse(
        node_id=node.id,
        machine_id=node.machine_id,
        display_name=node.display_name,
        platform=node.platform,
        approved=node.approved,
        access_role=node.access_role,  # type: ignore[arg-type]
        online=is_online(node, settings.node_offline_after_seconds),
        agent_version=node.agent_version,
        metadata=node.metadata_json,
        created_at=node.created_at,
        last_seen_at=node.last_seen_at,
        fleet_group_id=node.fleet_group_id or _default_group_for(node),
        fleet_position=node.fleet_position,
        latest=_telemetry_response(latest) if latest is not None else None,
    )


def _default_group_for(node: Node) -> str:
    identity = f"{node.display_name} {node.machine_id}".lower()
    if node.metadata_json.get("source") == "unraid-api" or "server" in identity or "tower" in identity:
        return "default-servers"
    if any(word in identity for word in ("android", "ios", "pixel", "phone")):
        return "default-mobile"
    return "default-pcs-laptops"


def _telemetry_response(point: TelemetryPoint) -> FleetTelemetryPoint:
    return FleetTelemetryPoint(
        sample_id=point.sample_id,
        recorded_at=point.recorded_at,
        metrics=point.payload,
    )
