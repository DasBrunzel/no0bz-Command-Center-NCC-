from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ncc_server.auth import (
    database_session,
    require_agent_token,
    require_commander_access,
    require_dashboard_access,
)
from ncc_server.models import AgentToken
from ncc_server.node_service import bound_node
from ncc_server.release_service import (
    ReleaseManifestError,
    assign_release,
    list_releases,
    pending_release,
    register_release,
    update_node_channel,
)
from ncc_server.schemas import (
    AgentReleaseManifestCreateRequest,
    AgentReleaseResponse,
    FleetNodeReleaseAssignmentRequest,
    FleetNodeUpdateChannelRequest,
)

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("", response_model=list[AgentReleaseResponse], dependencies=[Depends(require_dashboard_access)])
async def releases(session: Session = Depends(database_session)) -> list[AgentReleaseResponse]:
    return list_releases(session)


@router.post("", response_model=AgentReleaseResponse, status_code=201, dependencies=[Depends(require_commander_access)])
async def create_release(payload: AgentReleaseManifestCreateRequest, session: Session = Depends(database_session)) -> AgentReleaseResponse:
    try:
        return register_release(session, payload.manifest)
    except ReleaseManifestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/nodes/{node_id}", status_code=204, dependencies=[Depends(require_commander_access)])
async def set_node_release(node_id: str, payload: FleetNodeReleaseAssignmentRequest, session: Session = Depends(database_session)) -> None:
    if not assign_release(session, node_id, payload.release_id):
        raise HTTPException(status_code=404, detail="node or compatible release not found")


@router.put("/nodes/{node_id}/channel", status_code=204, dependencies=[Depends(require_commander_access)])
async def set_node_channel(node_id: str, payload: FleetNodeUpdateChannelRequest, session: Session = Depends(database_session)) -> None:
    if not update_node_channel(session, node_id, payload.channel):
        raise HTTPException(status_code=404, detail="node not found")


@router.get("/pending", response_model=AgentReleaseResponse | None)
async def agent_pending_release(
    token: AgentToken = Depends(require_agent_token), session: Session = Depends(database_session)
) -> AgentReleaseResponse | None:
    node = bound_node(session, token)
    return pending_release(session, node.id)
