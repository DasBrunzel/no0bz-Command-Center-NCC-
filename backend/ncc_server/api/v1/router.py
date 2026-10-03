from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from ncc_server import __version__
from ncc_server.api.v1.admin_codes import router as admin_codes_router
from ncc_server.api.v1.agent_pairings import router as agent_pairings_router
from ncc_server.api.v1.chat import router as chat_router
from ncc_server.api.v1.fleet import router as fleet_router
from ncc_server.api.v1.invitations import router as invitations_router
from ncc_server.api.v1.nodes import router as nodes_router

router = APIRouter(prefix="/api/v1")
router.include_router(nodes_router)
router.include_router(fleet_router)
router.include_router(chat_router)
router.include_router(invitations_router)
router.include_router(admin_codes_router)
router.include_router(agent_pairings_router)


@router.get("/status/live", tags=["status"])
async def live() -> dict[str, str]:
    return {"status": "ok", "service": "ncc-server", "version": __version__}


@router.get("/status/ready", tags=["status"])
async def ready(request: Request) -> dict[str, str]:
    try:
        request.app.state.database.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return {"status": "ready", "database": "available"}


@router.get("/version", tags=["status"])
async def version() -> dict[str, str]:
    return {"version": __version__, "api": "v1"}
