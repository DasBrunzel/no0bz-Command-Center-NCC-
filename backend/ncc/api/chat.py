from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ncc.config import get_settings
from ncc.hub.chat import add_message, list_messages
from ncc.hub.uploads import save_upload
from ncc.models import ChatMessageRequest
from ncc.security import limited, require_token, validate_basename

router = APIRouter(prefix="/api/chat")


@router.get("/messages")
async def messages() -> list[dict[str, Any]]:
    return list_messages()


@router.post("/send", dependencies=[Depends(require_token), Depends(limited("chat", 60))])
async def send(payload: ChatMessageRequest) -> dict[str, Any]:
    return add_message(payload.sender, payload.text, payload.kind)


@router.post("/upload", dependencies=[Depends(require_token), Depends(limited("upload", 20))])
async def upload(files: list[UploadFile] = File(...)) -> dict[str, list[dict[str, Any]]]:
    settings = get_settings()
    saved = []
    for item in files:
        if not item.filename:
            raise HTTPException(status_code=400, detail="Every upload needs a filename")
        path = save_upload(item.file, item.filename, settings)
        saved.append({"name": path.name, "size": path.stat().st_size, "url": f"/api/chat/files/{path.name}"})
    return {"files": saved}


@router.get("/files")
async def files() -> list[dict[str, Any]]:
    directory = get_settings().uploads_dir
    return [{"name": path.name, "size": path.stat().st_size, "url": f"/api/chat/files/{path.name}"} for path in sorted(directory.iterdir()) if path.is_file()]


@router.get("/files/{filename}")
async def download(filename: str) -> FileResponse:
    clean_name = validate_basename(filename)
    path = get_settings().uploads_dir / clean_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=clean_name, media_type="application/octet-stream", headers={"X-Content-Type-Options": "nosniff"})

