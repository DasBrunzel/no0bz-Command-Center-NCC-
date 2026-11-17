"""NCC Android app: private APK updates and remote settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.access import manageable_node
from ncc_server.android_release import apk_path, current_release, store_release
from ncc_server.api.v1.node_chat import chat_node
from ncc_server.auth import (
    DashboardIdentity,
    database_session,
    require_commander_access,
    require_dashboard_identity,
)
from ncc_server.models import Node
from ncc_server.schemas import AndroidAppConfigRequest, AndroidReleaseResponse

dashboard_router = APIRouter(prefix="/android", tags=["android app"])
node_router = APIRouter(prefix="/nodes", tags=["agents"], dependencies=[Depends(limited("v1-node-app-release", 30))])
fleet_router = APIRouter(prefix="/fleet/nodes", tags=["android app"])


@dashboard_router.get("/release", response_model=AndroidReleaseResponse | None, dependencies=[Depends(require_dashboard_identity)])
async def release(request: Request) -> AndroidReleaseResponse | None:
    return current_release(request.app.state.server_settings.android_release_dir)


@dashboard_router.post(
    "/release",
    response_model=AndroidReleaseResponse,
    status_code=201,
    dependencies=[Depends(require_commander_access), Depends(limited("android-release-upload", 10))],
)
async def upload_release(
    request: Request,
    file: UploadFile = File(...),
    version_code: int = Form(...),
    version_name: str = Form(..., max_length=32),
    notes: str = Form(default="", max_length=2000),
) -> AndroidReleaseResponse:
    stored = store_release(request.app.state.server_settings.android_release_dir, file, version_code, version_name, notes)
    # Connected phones learn about it at once instead of at their next check.
    request.app.state.live_hub.publish_app_update(stored.model_dump(mode="json"))
    return stored


@node_router.get("/app-release", response_model=AndroidReleaseResponse | None)
async def app_release(request: Request, _: Node = Depends(chat_node)) -> AndroidReleaseResponse | None:
    return current_release(request.app.state.server_settings.android_release_dir)


@node_router.get("/app-release/apk")
async def app_release_apk(request: Request, _: Node = Depends(chat_node)) -> FileResponse:
    directory = request.app.state.server_settings.android_release_dir
    release = current_release(directory)
    if release is None:
        raise HTTPException(status_code=404, detail="no app release available")
    return FileResponse(
        apk_path(directory),
        media_type="application/vnd.android.package-archive",
        filename=f"ncc-android-{release.version_name}.apk",
    )


@fleet_router.put("/{node_id}/app-config", status_code=204)
async def app_config(
    node_id: str,
    payload: AndroidAppConfigRequest,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> Response:
    node = manageable_node(session, identity, node_id)
    if node.platform != "android":
        raise HTTPException(status_code=422, detail="only Android app nodes have remote settings")
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="nothing to change")
    hub = request.app.state.live_hub
    if not hub.connected(node_id):
        # Settings travel over the live channel; an offline phone cannot take them.
        raise HTTPException(status_code=409, detail="the phone is not connected")
    hub.send_config(node_id, changes)
    return Response(status_code=204)
