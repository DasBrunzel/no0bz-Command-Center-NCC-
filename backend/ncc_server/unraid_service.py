"""Read-only Unraid GraphQL presence collector, executed by the NCC server."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select

from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Node, TelemetryPoint, utc_now

logger = logging.getLogger(__name__)


async def collect_unraid(database: Database, settings: ServerSettings) -> None:
    """Collect read-only Unraid metrics and represent the host as a NCC node."""
    if not settings.unraid_url or not settings.unraid_api_key.get_secret_value():
        logger.warning(
            "Unraid collector disabled: url_configured=%s api_key_configured=%s",
            bool(settings.unraid_url),
            bool(settings.unraid_api_key.get_secret_value()),
        )
        return
    async with httpx.AsyncClient(timeout=15) as client:
        headers = {"x-api-key": settings.unraid_api_key.get_secret_value()}
        # Keep system and storage projections separate. One unsupported array
        # field must not hide CPU/RAM telemetry on older Unraid API schemas.
        payload = await _query_with_fallback(client, settings.unraid_url, headers)
        array_payload = await _query_optional(
            client, settings.unraid_url, headers, _ARRAY_QUERY
        )
        cpu_payload = await _query_optional(
            client, settings.unraid_url, headers, _CPU_DETAILS_QUERY
        )
        vm_payload = await _query_optional(
            client, settings.unraid_url, headers, _VMS_QUERY
        )
        docker_payload = await _query_optional(
            client, settings.unraid_url, headers, _DOCKER_QUERY
        )
    if not isinstance(payload.get("data"), dict):
        raise ValueError("Unraid API returned no GraphQL data")
    data = payload["data"]
    metrics = _dict(data.get("metrics"))
    info = _dict(data.get("info"))
    array = _dict(_dict(array_payload.get("data")).get("array"))
    cpu_details = _dict(_dict(cpu_payload.get("data")).get("info")).get("cpu")
    cpu_details = _dict(cpu_details)
    vms = _dict(_dict(vm_payload.get("data")).get("vms"))
    docker = _dict(_dict(docker_payload.get("data")).get("docker"))
    cpu = _dict(metrics.get("cpu")) or _dict(info.get("cpu"))
    memory = _dict(metrics.get("memory")) or _dict(info.get("memory"))
    network = metrics.get("network")
    network_rows = network if isinstance(network, list) else [network] if isinstance(network, dict) else []
    info_cpu = _dict(info.get("cpu"))
    versions = _dict(info.get("versions"))
    payload_metrics = {
        "cpu": {
            "percent": _number(cpu.get("percentTotal")),
            "model": info_cpu.get("brand") or info_cpu.get("vendor") or "Unraid CPU",
            "logical_cores": info_cpu.get("threads") or info_cpu.get("cores") or 0,
            "temperature_c": _cpu_temperature(cpu_details),
        },
        "memory": {
            "percent": _number(memory.get("percentTotal")),
            "total_gb": _bytes_to_gb(memory.get("total")),
            "used_gb": _bytes_to_gb(memory.get("used")),
            "free_gb": _bytes_to_gb(memory.get("free")),
        },
        "network": {
            "download_mbps": _sum_number(network_rows, "rxSec") * 8 / 1_000_000,
            "upload_mbps": _sum_number(network_rows, "txSec") * 8 / 1_000_000,
            "interface": ", ".join(str(row.get("name")) for row in network_rows if row.get("name")),
        },
        "disks": _disks(array),
        "vms": _vms(vms),
        "containers": _containers(docker),
        "unraid": {
            "api_connected": True,
            "version": versions.get("unraid") or "unknown",
            "array_state": array.get("state"),
        },
    }

    machine_id = f"unraid:{settings.unraid_display_name.casefold()}"
    now = utc_now()
    with database.session() as session:
        node = session.scalar(select(Node).where(Node.machine_id == machine_id))
        if node is None:
            node = Node(
                machine_id=machine_id,
                display_name=settings.unraid_display_name,
                platform="linux",
                approved=True,
                agent_version=str(versions.get("unraid") or "unraid-api"),
                metadata_json={"source": "unraid-api", "endpoint": "tailscale"},
            )
            session.add(node)
            session.flush()
        node.last_seen_at = now
        node.updated_at = now
        node.metadata_json = {"source": "unraid-api", "endpoint": "tailscale"}
        session.add(
            TelemetryPoint(
                node_id=node.id,
                sample_id=str(uuid.uuid4()),
                recorded_at=now,
                payload=payload_metrics,
            )
        )
        session.commit()
    logger.info("Unraid collector succeeded for %s", settings.unraid_display_name)


_QUERY = """
query NccUnraidMetrics {
  metrics {
    cpu { percentTotal }
    memory { total used free available percentTotal }
    network { name rxSec txSec }
  }
  info { cpu { brand vendor threads cores } }
}
"""

_LEGACY_QUERY = """
query NccUnraidLegacyMetrics {
  info { cpu { brand vendor threads cores speed } memory { total used free available active buffcache } }
}
"""

_ARRAY_QUERY = """
query NccUnraidArray {
  array {
    state
    disks {
      id idx name device size status type temp
      fsSize fsUsed fsFree fsType isSpinning
    }
    caches {
      id idx name device size status type temp
      fsSize fsUsed fsFree fsType isSpinning
    }
  }
}
"""

_CPU_DETAILS_QUERY = """
query NccUnraidCpuDetails {
  info { cpu { packages { temp } } }
}
"""

_VMS_QUERY = """
query NccUnraidVms {
  vms { domains { id name state } }
}
"""

_DOCKER_QUERY = """
query NccUnraidDocker {
  docker { containers { id names state status autoStart } }
}
"""


async def _query_with_fallback(
    client: httpx.AsyncClient, url: str, headers: dict[str, str]
) -> dict[str, Any]:
    try:
        return await _query_json(client, url, headers, _QUERY)
    except ValueError:
        return await _query_json(client, url, headers, _LEGACY_QUERY)


async def _query_json(
    client: httpx.AsyncClient, url: str, headers: dict[str, str], query: str
) -> dict[str, Any]:
    response = await client.post(url, headers=headers, json={"query": query})
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Unraid commonly returns GraphQL validation details in a HTTP 400
        # body. Preserve that detail for the fallback and service log without
        # ever including request headers or the API key.
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]
        raise ValueError(f"Unraid HTTP {response.status_code}: {body!s:.500}") from exc
    payload = response.json()
    if isinstance(payload, dict) and payload.get("errors"):
        raise ValueError(f"GraphQL query rejected: {payload['errors']!s:.500}")
    if not isinstance(payload, dict):
        raise ValueError("Unraid API returned an invalid response")
    return payload


async def _query_optional(
    client: httpx.AsyncClient, url: str, headers: dict[str, str], query: str
) -> dict[str, Any]:
    """Run an optional view without letting version differences hide core telemetry."""
    try:
        return await _query_json(client, url, headers, query)
    except (ValueError, httpx.HTTPError) as exc:
        logger.info("Optional Unraid dashboard view unavailable: %s", exc)
        return {}


def _number(value: object) -> float:
    try:
        return float(str(value)) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _bytes_to_gb(value: object) -> float:
    return _number(value) / 1024 / 1024 / 1024


def _kb_to_gb(value: object) -> float:
    """Unraid's array filesystem figures are reported in KiB."""
    return _number(value) / 1024 / 1024


def _sum_number(rows: list[object], key: str) -> float:
    return sum(_number(row.get(key)) for row in rows if isinstance(row, dict))


def _disks(array: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in ("caches", "disks"):
        entries = array.get(group)
        if not isinstance(entries, list):
            continue
        for disk in entries:
            if not isinstance(disk, dict):
                continue
            rows.append(
                {
                    "name": _disk_name(disk, group),
                    "mount": disk.get("device") or "",
                    "percent": _disk_percent(disk),
                    "total_gb": _kb_to_gb(disk.get("fsSize") or disk.get("size")),
                    "used_gb": _kb_to_gb(disk.get("fsUsed")),
                    "temperature_c": _disk_temperature(disk),
                    "status": disk.get("status"),
                    "spinning": disk.get("isSpinning"),
                    "fstype": disk.get("fsType"),
                }
            )
    return rows


def _disk_percent(disk: dict[str, object]) -> float:
    total = _number(disk.get("fsSize"))
    used = _number(disk.get("fsUsed"))
    return used / total * 100 if total > 0 else 0.0


def _disk_name(disk: dict[str, object], group: str) -> str:
    if group == "caches":
        name = str(disk.get("name") or "")
        return "Cache" if not name or name.casefold() == "cache" else name
    index = disk.get("idx")
    return f"Disk {index}" if index not in (None, "") else str(
        disk.get("name") or disk.get("device") or "Disk"
    )


def _disk_temperature(disk: dict[str, object]) -> float | None:
    if disk.get("isSpinning") is False:
        return None
    temperature = _number(disk.get("temp") or disk.get("temperature"))
    return temperature if temperature > 0 else None


def _cpu_temperature(cpu: dict[str, object]) -> float | None:
    packages = cpu.get("packages")
    rows = packages if isinstance(packages, list) else [packages]
    temperatures = [
        _number(row.get("temp")) for row in rows if isinstance(row, dict)
    ]
    valid = [temperature for temperature in temperatures if temperature > 0]
    return max(valid) if valid else None


def _vms(vms: dict[str, Any]) -> list[dict[str, object]]:
    domains = vms.get("domains")
    if not isinstance(domains, list):
        return []
    return [
        {"name": domain.get("name") or "Unbenannte VM", "state": domain.get("state") or "unknown"}
        for domain in domains
        if isinstance(domain, dict)
    ]


def _containers(docker: dict[str, Any]) -> list[dict[str, object]]:
    containers = docker.get("containers")
    if not isinstance(containers, list):
        return []
    result: list[dict[str, object]] = []
    for container in containers:
        if not isinstance(container, dict):
            continue
        names = container.get("names")
        name = names[0] if isinstance(names, list) and names else container.get("id")
        result.append(
            {
                "name": str(name or "Unbenannter Container").lstrip("/"),
                "state": container.get("state") or "unknown",
                "status": container.get("status") or "",
                "auto_start": bool(container.get("autoStart")),
            }
        )
    return result
