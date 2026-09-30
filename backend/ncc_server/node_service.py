from __future__ import annotations

import json
from datetime import datetime, timezone

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
    accepted = 0
    duplicates = 0
    for point in points:
        sample_id = str(point.sample_id)
        if sample_id in existing:
            duplicates += 1
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
    return (utc_now() - last_seen).total_seconds() <= offline_after_seconds


def _bound_node(session: Session, token: AgentToken) -> Node:
    if token.node_id is None:
        raise TokenNotEnrolledError
    node = session.get(Node, token.node_id)
    if node is None:
        raise TokenNotEnrolledError
    return node
