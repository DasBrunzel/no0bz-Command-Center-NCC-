from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.auth import database_session, require_agent_token
from ncc_server.config import ServerSettings
from ncc_server.models import AgentToken, Node
from ncc_server.node_service import (
    EnrollmentConflictError,
    NodeNotApprovedError,
    TokenNotEnrolledError,
    bound_node,
    enroll_node,
    is_online,
    record_heartbeat,
    store_telemetry,
)
from ncc_server.schemas import (
    HeartbeatResponse,
    NodeEnrollmentRequest,
    NodeHeartbeatRequest,
    NodeResponse,
    TelemetryBatchRequest,
    TelemetryBatchResponse,
)

router = APIRouter(prefix="/nodes", tags=["agents"])


@router.post(
    "/enroll",
    response_model=NodeResponse,
    dependencies=[Depends(limited("v1-node-enroll", 20))],
)
async def enroll(
    payload: NodeEnrollmentRequest,
    request: Request,
    token: AgentToken = Depends(require_agent_token),
    session: Session = Depends(database_session),
) -> NodeResponse:
    try:
        node = enroll_node(session, token, payload)
    except EnrollmentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="token or machine identity is already assigned",
        ) from exc
    return _node_response(node, request.app.state.server_settings)


@router.post(
    "/heartbeat",
    response_model=HeartbeatResponse,
    dependencies=[Depends(limited("v1-node-heartbeat", 180))],
)
async def heartbeat(
    payload: NodeHeartbeatRequest,
    request: Request,
    token: AgentToken = Depends(require_agent_token),
    session: Session = Depends(database_session),
) -> HeartbeatResponse:
    try:
        node, now = record_heartbeat(session, token, payload)
    except TokenNotEnrolledError as exc:
        raise HTTPException(status_code=409, detail="agent token is not enrolled") from exc
    except NodeNotApprovedError as exc:
        raise HTTPException(status_code=403, detail="node is not approved") from exc
    settings: ServerSettings = request.app.state.server_settings
    return HeartbeatResponse(
        accepted=True,
        node_id=node.id,
        server_time=now,
        next_heartbeat_seconds=settings.heartbeat_interval_seconds,
    )


@router.get("/me", response_model=NodeResponse)
async def me(
    request: Request,
    token: AgentToken = Depends(require_agent_token),
    session: Session = Depends(database_session),
) -> NodeResponse:
    try:
        node = bound_node(session, token)
    except TokenNotEnrolledError as exc:
        raise HTTPException(status_code=409, detail="agent token is not enrolled") from exc
    return _node_response(node, request.app.state.server_settings)


def _node_response(node: Node, settings: ServerSettings) -> NodeResponse:
    return NodeResponse(
        node_id=node.id,
        machine_id=node.machine_id,
        display_name=node.display_name,
        platform=node.platform,
        approved=node.approved,
        online=is_online(node, settings.node_offline_after_seconds),
        agent_version=node.agent_version,
        last_seen_at=node.last_seen_at,
        heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
    )


@router.post(
    "/telemetry",
    response_model=TelemetryBatchResponse,
    dependencies=[Depends(limited("v1-node-telemetry", 120))],
)
async def telemetry(
    payload: TelemetryBatchRequest,
    token: AgentToken = Depends(require_agent_token),
    session: Session = Depends(database_session),
) -> TelemetryBatchResponse:
    try:
        accepted, duplicates = store_telemetry(session, token, payload.points)
    except TokenNotEnrolledError as exc:
        raise HTTPException(status_code=409, detail="agent token is not enrolled") from exc
    except NodeNotApprovedError as exc:
        raise HTTPException(status_code=403, detail="node is not approved") from exc
    return TelemetryBatchResponse(accepted=accepted, duplicates=duplicates)
