from __future__ import annotations

import uvicorn

from ncc_server.config import get_server_settings


def main() -> None:
    settings = get_server_settings()
    uvicorn.run("ncc_server.app:app", host=settings.host, port=settings.port, reload=False)
