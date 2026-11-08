from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.agent_tokens import find_valid_agent_token
from ncc_server.alert_service import get_alert_policy
from ncc_server.auth import database_session, require_agent_token
from ncc_server.config import ServerSettings
from ncc_server.live_hub import LiveHub, active_app_alerts
from ncc_server.models import AgentToken, Node, utc_now
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
        node, now, update_check_requested = record_heartbeat(session, token, payload)
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
        update_check_requested=update_check_requested,
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


LIVE_MESSAGE_MAX_BYTES = 64 * 1024
STREAM_PING_SECONDS = 25


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    """Live channel for app nodes: live telemetry up, alerts and viewer signals down."""
    token = _bearer(websocket.headers.get("authorization")) or websocket.headers.get("x-ncc-agent-token") or ""
    hub: LiveHub = websocket.app.state.live_hub
    with websocket.app.state.database.session() as session:
        record = find_valid_agent_token(session, token)
        node = session.get(Node, record.node_id) if record is not None and record.node_id else None
        if record is None or node is None or not node.approved:
            # Closing before accept rejects the handshake (HTTP 403).
            await websocket.close(code=4401)
            return
        node_id = node.id
        commander = record.access_role == "commander"
        owner_user_id = record.owner_user_id
        snapshot = active_app_alerts(session) if get_alert_policy(session).app_alerts_enabled else None
        record.last_used_at = utc_now()
        session.commit()

    await websocket.accept()
    subscriber = hub.subscribe(node_id, commander=commander, owner_user_id=owner_user_id, snapshot=snapshot)

    async def send_loop() -> None:
        while True:
            await websocket.send_json(await subscriber.queue.get())

    async def ping_loop() -> None:
        while True:
            await asyncio.sleep(STREAM_PING_SECONDS)
            subscriber.put({"type": "ping"})

    tasks = [asyncio.create_task(send_loop()), asyncio.create_task(ping_loop())]
    try:
        while True:
            text = await websocket.receive_text()
            if len(text) > LIVE_MESSAGE_MAX_BYTES:
                continue
            try:
                message = json.loads(text)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("type") == "telemetry.live" and isinstance(message.get("metrics"), dict):
                recorded_at = message.get("recorded_at")
                if not isinstance(recorded_at, str):
                    recorded_at = datetime.now(timezone.utc).isoformat()
                hub.store_live(node_id, recorded_at, message["metrics"])
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
        hub.unsubscribe(subscriber)


def _bearer(header: str | None) -> str | None:
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def _node_response(node: Node, settings: ServerSettings) -> NodeResponse:
    return NodeResponse(
        node_id=node.id,
        machine_id=node.machine_id,
        display_name=node.display_name,
        platform=node.platform,
        approved=node.approved,
        access_role=node.access_role,  # type: ignore[arg-type]
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
