from __future__ import annotations

import json
import os
from typing import Any

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request

from ncc.config import ROOT
from ncc.models import KillRequest, utc_now
from ncc.security import PROTECTED_PROCESS_NAMES, limited, require_token

router = APIRouter(prefix="/api")
AUDIT_PATH = ROOT / "ncc_audit.log"


def kill_process(pid: int, client: str) -> dict[str, Any]:
    result: dict[str, Any] = {"timestamp": utc_now().isoformat(), "client": client, "pid": pid}
    try:
        process = psutil.Process(pid)
        name = process.name().lower()
        result["name"] = name
        if pid in {0, 1, os.getpid()} or name in PROTECTED_PROCESS_NAMES:
            raise HTTPException(status_code=403, detail=f"Protected process cannot be terminated: {name}")
        process.terminate()
        result.update({"success": True, "result": "terminate requested"})
        return result
    except psutil.NoSuchProcess as error:
        result.update({"success": False, "result": "process not found"})
        raise HTTPException(status_code=404, detail="Process not found") from error
    except psutil.AccessDenied as error:
        result.update({"success": False, "result": "access denied"})
        raise HTTPException(status_code=403, detail="Permission denied while terminating process") from error
    finally:
        with AUDIT_PATH.open("a", encoding="utf-8") as audit:
            audit.write(json.dumps(result) + "\n")


@router.post("/kill", dependencies=[Depends(require_token), Depends(limited("kill", 10))])
async def kill(payload: KillRequest, request: Request) -> dict[str, Any]:
    client = request.client.host if request.client else "unknown"
    return kill_process(payload.pid, client)

