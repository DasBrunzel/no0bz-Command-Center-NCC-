from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from ncc.config import get_settings
from ncc.models import NodeRegistration, NodeTelemetry
from ncc.multipc.server import nodes
from ncc.security import limited, require_token

router = APIRouter(prefix="/api")


@router.get("/multipc/mode")
async def mode() -> dict[str, str]:
    return {"mode": get_settings().mode}


@router.get("/nodes")
async def list_nodes() -> list[dict[str, Any]]:
    from ncc.app import collector

    return nodes.list(collector.snapshot())


@router.post("/nodes/register", dependencies=[Depends(require_token), Depends(limited("node-register", 20))])
async def register(payload: NodeRegistration, request: Request) -> dict[str, Any]:
    return nodes.register(payload.node_id, payload.name, payload.profile.model_dump() if payload.profile else None)


@router.post("/nodes/telemetry", dependencies=[Depends(require_token), Depends(limited("node-telemetry", 180))])
async def telemetry(payload: NodeTelemetry) -> dict[str, bool]:
    from ncc.app import store

    snapshot = payload.snapshot.model_dump(mode="json")
    nodes.telemetry(payload.node_id, snapshot)
    store.enqueue(snapshot)
    return {"accepted": True}

