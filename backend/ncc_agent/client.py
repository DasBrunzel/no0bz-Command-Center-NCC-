from __future__ import annotations

import hashlib
import platform
import socket
import subprocess
from pathlib import Path
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
        agent_version: str = __version__,
    ) -> None:
        self.settings = settings
        self.machine_id = machine_id
        self.buffer = buffer
        self.agent_version = agent_version
        self.server_url = settings.validated_server_url()
        self._headers: dict[str, str] = {}
        self.set_token(settings.token.get_secret_value())
        self._client = httpx.Client(
            timeout=settings.request_timeout_seconds,
            verify=settings.verify_tls,
            transport=transport,
        )

    @property
    def has_token(self) -> bool:
        return bool(self._headers)

    def set_token(self, token: str) -> None:
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    def register_pairing(self) -> None:
        pairing_id = self.settings.pairing_id
        pairing_secret = self.settings.pairing_secret.get_secret_value()
        if not pairing_id or not pairing_secret:
            raise ValueError("NCC agent pairing is not configured")
        self._request_public(
            "POST",
            "/api/v1/agent-pairings/register",
            json={
                "pairing_id": pairing_id,
                "pairing_secret": pairing_secret,
                "machine_id": self.machine_id,
                "display_name": (self.settings.display_name or socket.gethostname())[:128],
                "platform": _platform_name(),
                "agent_version": self.agent_version,
                "metadata": _host_metadata(),
            },
        )

    def claim_pairing(self) -> str | None:
        response = self._request_public(
            "POST",
            f"/api/v1/agent-pairings/{self.settings.pairing_id}/claim",
            json={"pairing_secret": self.settings.pairing_secret.get_secret_value()},
            pending_ok=True,
        )
        return None if response.status_code == 409 else str(response.json()["token"])

    def enroll(self) -> int:
        response = self._request(
            "POST",
            "/api/v1/nodes/enroll",
            json={
                "machine_id": self.machine_id,
                "display_name": (self.settings.display_name or socket.gethostname())[:128],
                "platform": _platform_name(),
                "agent_version": self.agent_version,
                "metadata": _host_metadata(),
            },
        )
        return int(response.json()["heartbeat_interval_seconds"])

    def heartbeat(self) -> None:
        self._request(
            "POST",
            "/api/v1/nodes/heartbeat",
            json={"agent_version": self.agent_version, "metadata": _host_metadata()},
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

    def _request_public(self, method: str, path: str, *, pending_ok: bool = False, **kwargs: Any) -> httpx.Response:
        response = self._client.request(method, f"{self.server_url}{path}", **kwargs)
        if pending_ok and response.status_code == 409:
            return response
        if response.status_code in {400, 401, 403, 410, 422}:
            raise AgentRejectedError(f"server rejected agent pairing ({response.status_code})")
        response.raise_for_status()
        return response


def _platform_name() -> str:
    name = platform.system().lower()
    return "darwin" if name == "darwin" else name


def _host_metadata() -> dict[str, str]:
    metadata = {
        "architecture": platform.machine() or "unknown",
        "os_release": platform.release() or "unknown",
    }
    fingerprint = _hardware_fingerprint()
    if fingerprint:
        # Send only a one-way identifier, never the DMI UUID / Windows UUID.
        metadata["hardware_fingerprint"] = fingerprint
    return metadata


def _hardware_fingerprint() -> str | None:
    try:
        if platform.system().lower() == "windows":
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
                text=True, stderr=subprocess.DEVNULL, timeout=3,
            ).strip()
        else:
            raw = Path("/sys/class/dmi/id/product_uuid").read_text(encoding="utf-8").strip()
    except (OSError, subprocess.SubprocessError):
        return None
    normalized = raw.lower().replace("-", "").strip()
    if not normalized or set(normalized) == {"0"}:
        return None
    return hashlib.sha256(normalized.encode("ascii", "ignore")).hexdigest()
