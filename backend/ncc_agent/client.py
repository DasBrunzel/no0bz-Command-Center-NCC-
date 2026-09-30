from __future__ import annotations

import platform
import socket
from typing import Any

import httpx

from ncc_agent import __version__
from ncc_agent.buffer import TelemetryBuffer
from ncc_agent.config import AgentSettings


class AgentRejectedError(RuntimeError):
    pass


class AgentClient:
    def __init__(
        self,
        settings: AgentSettings,
        machine_id: str,
        buffer: TelemetryBuffer,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.machine_id = machine_id
        self.buffer = buffer
        self.server_url = settings.validated_server_url()
        token = settings.token.get_secret_value()
        if not token:
            raise ValueError("NCC_AGENT_TOKEN is required")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.Client(
            timeout=settings.request_timeout_seconds,
            verify=settings.verify_tls,
            transport=transport,
        )

    def enroll(self) -> int:
        response = self._request(
            "POST",
            "/api/v1/nodes/enroll",
            json={
                "machine_id": self.machine_id,
                "display_name": (self.settings.display_name or socket.gethostname())[:128],
                "platform": _platform_name(),
                "agent_version": __version__,
                "metadata": _host_metadata(),
            },
        )
        return int(response.json()["heartbeat_interval_seconds"])

    def heartbeat(self) -> None:
        self._request(
            "POST",
            "/api/v1/nodes/heartbeat",
            json={"agent_version": __version__, "metadata": _host_metadata()},
        )

    def flush(self, max_batches: int = 10) -> int:
        sent = 0
        for _ in range(max_batches):
            batch = self.buffer.peek(self.settings.batch_size)
            if not batch:
                break
            self._request(
                "POST",
                "/api/v1/nodes/telemetry",
                json={
                    "points": [
                        {
                            "sample_id": point.sample_id,
                            "recorded_at": point.recorded_at,
                            "metrics": point.metrics,
                        }
                        for point in batch
                    ]
                },
            )
            self.buffer.acknowledge([point.row_id for point in batch])
            sent += len(batch)
        return sent

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self._client.request(
            method,
            f"{self.server_url}{path}",
            headers=self._headers,
            **kwargs,
        )
        if response.status_code in {400, 401, 403, 409, 422}:
            raise AgentRejectedError(f"server rejected agent request ({response.status_code})")
        response.raise_for_status()
        return response


def _platform_name() -> str:
    name = platform.system().lower()
    return "darwin" if name == "darwin" else name


def _host_metadata() -> dict[str, str]:
    return {
        "architecture": platform.machine() or "unknown",
        "os_release": platform.release() or "unknown",
    }
