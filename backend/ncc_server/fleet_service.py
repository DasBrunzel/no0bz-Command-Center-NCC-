from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ncc_server.config import ServerSettings
from ncc_server.models import AuditEvent, Node, TelemetryPoint, utc_now
from ncc_server.node_service import is_online
from ncc_server.schemas import FleetNodeResponse, FleetSummaryResponse, FleetTelemetryPoint


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
        online=is_online(node, settings.node_offline_after_seconds),
        agent_version=node.agent_version,
        metadata=node.metadata_json,
        created_at=node.created_at,
        last_seen_at=node.last_seen_at,
        latest=_telemetry_response(latest) if latest is not None else None,
    )


def _telemetry_response(point: TelemetryPoint) -> FleetTelemetryPoint:
    return FleetTelemetryPoint(
        sample_id=point.sample_id,
        recorded_at=point.recorded_at,
        metrics=point.payload,
    )
