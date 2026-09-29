from __future__ import annotations

import json
import platform
from typing import Any, cast

from fastapi import APIRouter, Depends

from ncc import __version__
from ncc.collectors.registry import save_hardware_cache
from ncc.config import ROOT
from ncc.security import require_token

router = APIRouter(prefix="/api")
CACHE_PATH = ROOT / "ncc_system_cache.json"


def static_profile() -> dict[str, Any]:
    return {"platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(), "python": platform.python_version()}


@router.get("/sensors/capabilities")
async def capabilities() -> list[dict[str, Any]]:
    from ncc.app import registry

    return [{"provider": item.provider, "available": item.available, "metrics": item.metrics, "reason": item.reason, "hint": item.hint} for item in registry.capabilities]


@router.get("/system/profile")
async def system_profile() -> dict[str, Any]:
    if CACHE_PATH.exists():
        return cast(dict[str, Any], json.loads(CACHE_PATH.read_text(encoding="utf-8")))
    return {"static": static_profile(), "providers": []}


@router.post("/system/profile/refresh", dependencies=[Depends(require_token)])
async def refresh_profile() -> dict[str, Any]:
    from ncc.app import registry

    save_hardware_cache(registry, static_profile())
    return await system_profile()


@router.get("/auth/check", dependencies=[Depends(require_token)])
async def auth_check() -> dict[str, str | bool]:
    from ncc.app import settings

    return {"authorized": True, "mode": settings.mode, "version": __version__}

