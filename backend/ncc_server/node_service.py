from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ncc_server.models import AgentToken, AuditEvent, Node, TelemetryPoint, utc_now
from ncc_server.schemas import (
    NodeEnrollmentRequest,
    NodeHeartbeatRequest,
    TelemetryPointRequest,
)


class EnrollmentConflictError(Exception):
    pass


class TokenNotEnrolledError(Exception):
    pass


class NodeNotApprovedError(Exception):
    pass


TELEMETRY_DUPLICATE_WINDOW = timedelta(seconds=1)


def enroll_node(
    session: Session,
    token: AgentToken,
    payload: NodeEnrollmentRequest,
) -> Node:
    now = utc_now()
    if token.node_id is not None:
        node = session.get(Node, token.node_id)
        if node is None or node.machine_id != payload.machine_id:
            raise EnrollmentConflictError
    else:
        existing = session.scalar(select(Node).where(Node.machine_id == payload.machine_id))
        if existing is not None:
            raise EnrollmentConflictError
        node = Node(
            machine_id=payload.machine_id,
            display_name=payload.display_name,
            platform=payload.platform,
            approved=True,
            access_role=token.access_role,
        )
        session.add(node)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise EnrollmentConflictError from exc
        token.node_id = node.id
        session.add(
            AuditEvent(
                actor_type="agent",
                actor_id=node.id,
                action="node.enrolled",
                details=json.dumps(
                    {"machine_id": payload.machine_id, "token_id": token.id},
                    separators=(",", ":"),
                ),
            )
        )
    node.display_name = payload.display_name
    node.platform = payload.platform
    node.access_role = token.access_role
    node.agent_version = payload.agent_version
    node.metadata_json = dict(payload.metadata)
    node.last_seen_at = now
    node.updated_at = now
    token.last_used_at = now
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise EnrollmentConflictError from exc
    session.refresh(node)
    return node


def record_heartbeat(
    session: Session,
    token: AgentToken,
    payload: NodeHeartbeatRequest,
) -> tuple[Node, datetime]:
    node = _bound_node(session, token)
    if not node.approved:
        raise NodeNotApprovedError
    now = utc_now()
    node.agent_version = payload.agent_version
    node.metadata_json = dict(payload.metadata)
    node.last_seen_at = now
    node.updated_at = now
    token.last_used_at = now
    session.commit()
    session.refresh(node)
    return node, now


def bound_node(session: Session, token: AgentToken) -> Node:
    return _bound_node(session, token)


def store_telemetry(
    session: Session,
    token: AgentToken,
    points: list[TelemetryPointRequest],
) -> tuple[int, int]:
    node = _bound_node(session, token)
    if not node.approved:
        raise NodeNotApprovedError
    sample_ids = [str(point.sample_id) for point in points]
    existing = set(
        session.scalars(
            select(TelemetryPoint.sample_id).where(
                TelemetryPoint.node_id == node.id,
                TelemetryPoint.sample_id.in_(sample_ids),
            )
        ).all()
    )
    latest = session.scalar(
        select(TelemetryPoint)
        .where(TelemetryPoint.node_id == node.id)
        .order_by(TelemetryPoint.recorded_at.desc())
        .limit(1)
    )
    latest_recorded_at = latest.recorded_at if latest is not None else None
    accepted = 0
    duplicates = 0
    for point in points:
        sample_id = str(point.sample_id)
        if sample_id in existing:
            duplicates += 1
            continue
        if latest_recorded_at is not None and _same_telemetry_window(
            latest_recorded_at, point.recorded_at
        ):
            # Two independently running local agents can have different sample
            # IDs but emit the same host snapshot milliseconds apart. Keep the
            # first point so counter-based statistics cannot double-count it.
            duplicates += 1
            _record_duplicate_telemetry(session, node, point.recorded_at)
            continue
        try:
            with session.begin_nested():
                session.add(
                    TelemetryPoint(
                        node_id=node.id,
                        sample_id=sample_id,
                        recorded_at=point.recorded_at,
                        payload=point.metrics,
                    )
                )
                session.flush()
        except IntegrityError:
            duplicates += 1
        else:
            existing.add(sample_id)
            latest_recorded_at = point.recorded_at
            accepted += 1
    now = utc_now()
    node.last_seen_at = now
    node.updated_at = now
    token.last_used_at = now
    session.commit()
    return accepted, duplicates


def is_online(node: Node, offline_after_seconds: int) -> bool:
    if node.last_seen_at is None:
        return False
    last_seen = node.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (utc_now() - last_seen).total_seconds() <= _offline_timeout(node, offline_after_seconds)


def _offline_timeout(node: Node, default_seconds: int) -> int:
    """Return a source-appropriate grace period for a node health check."""
    metadata = node.metadata_json if isinstance(node.metadata_json, dict) else {}
    # Unraid is polled by NCC, rather than sending its own heartbeat. Its
    # 30-second polling cadence needs room for a slow API response and a
    # database write, otherwise it briefly oscillates between online/offline.
    if metadata.get("source") == "unraid-api":
        return max(default_seconds, 90)
    return default_seconds


def _same_telemetry_window(left: datetime, right: datetime) -> bool:
    if left.tzinfo is None:
        left = left.replace(tzinfo=timezone.utc)
    if right.tzinfo is None:
        right = right.replace(tzinfo=timezone.utc)
    return abs(left - right) <= TELEMETRY_DUPLICATE_WINDOW


def _record_duplicate_telemetry(session: Session, node: Node, recorded_at: datetime) -> None:
    """Keep a rate-limited audit signal for agent-health evaluation."""
    now = utc_now()
    recent = session.scalar(
        select(AuditEvent.id)
        .where(
            AuditEvent.actor_id == node.id,
            AuditEvent.action == "agent.telemetry.duplicate",
            AuditEvent.occurred_at >= now - timedelta(minutes=1),
        )
        .limit(1)
    )
    if recent is None:
        session.add(
            AuditEvent(
                actor_type="server",
                actor_id=node.id,
                action="agent.telemetry.duplicate",
                details=json.dumps(
                    {"recorded_at": recorded_at.isoformat()}, separators=(",", ":")
                ),
            )
        )


def _bound_node(session: Session, token: AgentToken) -> Node:
    if token.node_id is None:
        raise TokenNotEnrolledError
    node = session.get(Node, token.node_id)
    if node is None:
        raise TokenNotEnrolledError
    return node
