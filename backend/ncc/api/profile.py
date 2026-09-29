from __future__ import annotations

import json
import socket
from typing import Any, cast

from fastapi import APIRouter, Depends

from ncc.config import ROOT
from ncc.models import Profile
from ncc.multipc.server import nodes
from ncc.security import require_token

router = APIRouter(prefix="/api")
PROFILE_PATH = ROOT / "ncc_profile.json"


def load_profile() -> dict[str, Any]:
    if PROFILE_PATH.exists():
        return cast(dict[str, Any], json.loads(PROFILE_PATH.read_text(encoding="utf-8")))
    return Profile(alias=socket.gethostname(), pc_name=socket.gethostname()).model_dump()


@router.post("/profile", dependencies=[Depends(require_token)])
async def save_profile(profile: Profile) -> dict[str, Any]:
    payload = profile.model_dump()
    PROFILE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    nodes.register(socket.gethostname(), profile.pc_name, payload)
    return payload

