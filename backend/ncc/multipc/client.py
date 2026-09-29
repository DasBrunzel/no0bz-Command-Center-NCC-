from __future__ import annotations

import asyncio
import logging
import socket
from contextlib import suppress
from typing import Any

import httpx

from ncc.config import Settings

MAX_BACKOFF_SECONDS = 60.0
logger = logging.getLogger(__name__)


class NodeClient:
    def __init__(self, settings: Settings, snapshot_getter: Any) -> None:
        self.settings = settings
        self.snapshot_getter = snapshot_getter
        self.node_id = socket.gethostname()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self.settings.mode == "client" and self.settings.server_url:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        backoff = 1.0
        headers = {"X-NCC-Token": self.settings.token}
        server_url = self.settings.server_url.rstrip("/")
        async with httpx.AsyncClient(timeout=10) as client:
            while True:
                try:
                    response = await client.post(f"{server_url}/api/nodes/register", headers=headers, json={"node_id": self.node_id, "name": socket.gethostname()})
                    response.raise_for_status()
                    logger.info("NCC-Client ist mit %s verbunden.", server_url)
                    while True:
                        snapshot = self.snapshot_getter()
                        response = await client.post(f"{server_url}/api/nodes/telemetry", headers=headers, json={"node_id": self.node_id, "snapshot": snapshot})
                        response.raise_for_status()
                        backoff = 1.0
                        await asyncio.sleep(self.settings.interval)
                except (httpx.HTTPError, OSError) as error:
                    logger.warning("NCC-Server %s nicht erreichbar: %s; neuer Versuch in %.0fs", server_url, error, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)

