"""Read-only Unraid GraphQL presence collector, executed by the NCC server."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from sqlalchemy import select

from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Node, TelemetryPoint, utc_now


async def collect_unraid(database: Database, settings: ServerSettings) -> None:
    """Collect read-only Unraid metrics and represent the host as a NCC node."""
    if not settings.unraid_url or not settings.unraid_api_key.get_secret_value():
        return
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            settings.unraid_url,
            headers={"x-api-key": settings.unraid_api_key.get_secret_value()},
            json={"query": _QUERY},
        )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("errors"):
        errors = payload["errors"]
        raise ValueError(f"GraphQL query rejected: {errors!s:.500}")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("Unraid API returned no GraphQL data")
    data = payload["data"]
    metrics = _dict(data.get("metrics"))
    info = _dict(data.get("info"))
    array = _dict(data.get("array"))
    cpu = _dict(metrics.get("cpu"))
    memory = _dict(metrics.get("memory"))
    network = metrics.get("network")
    network_rows = network if isinstance(network, list) else [network] if isinstance(network, dict) else []
    info_cpu = _dict(info.get("cpu"))
    versions = _dict(info.get("versions"))
    payload_metrics = {
        "cpu": {
            "percent": _number(cpu.get("percentTotal")),
            "model": info_cpu.get("brand") or info_cpu.get("vendor") or "Unraid CPU",
            "logical_cores": info_cpu.get("threads") or info_cpu.get("cores") or 0,
        },
        "memory": {
            "percent": _number(memory.get("percentTotal")),
            "total_gb": _kb_to_gb(memory.get("total")),
            "used_gb": _kb_to_gb(memory.get("used")),
            "free_gb": _kb_to_gb(memory.get("free")),
        },
        "network": {
            "download_mbps": _sum_number(network_rows, "rxSec") * 8 / 1_000_000,
            "upload_mbps": _sum_number(network_rows, "txSec") * 8 / 1_000_000,
            "interface": ", ".join(str(row.get("name")) for row in network_rows if row.get("name")),
        },
        "disks": _disks(array),
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


_QUERY = """
query NccUnraidMetrics {
  metrics {
    cpu { id percentTotal cpus { percentTotal percentUser percentSystem percentNice percentIdle percentIrq percentGuest percentSteal } }
    memory { id total used free available active buffcache percentTotal swapTotal swapUsed swapFree percentSwapTotal }
    network { id name operstate bytesReceived bytesSent packetsReceived packetsSent receiveErrors transmitErrors receiveDropped transmitDropped rxSec txSec utilizationPercent lastUpdated }
  }
  info { cpu { brand vendor threads cores } versions { unraid } }
  array { state capacity { kilobytes { total used free } } parityCheckStatus { status progress speed errors running } disks { id name device status temp size fsSize fsUsed type numReads numWrites numErrors isSpinning fsType } caches { id name device status temp size fsSize fsUsed type numReads numWrites numErrors isSpinning fsType } }
}
"""


def _number(value: object) -> float:
    try:
        return float(str(value)) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _kb_to_gb(value: object) -> float:
    return _number(value) / 1024 / 1024


def _sum_number(rows: list[object], key: str) -> float:
    return sum(_number(row.get(key)) for row in rows if isinstance(row, dict))


def _disks(array: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in ("disks", "caches"):
        entries = array.get(group)
        if not isinstance(entries, list):
            continue
        for disk in entries:
            if not isinstance(disk, dict):
                continue
            rows.append(
                {
                    "name": disk.get("name") or disk.get("device") or "disk",
                    "mount": disk.get("device") or "",
                    "percent": _disk_percent(disk),
                    "total_gb": _kb_to_gb(disk.get("size")),
                    "used_gb": _kb_to_gb(disk.get("fsUsed")),
                    "temperature_c": disk.get("temp"),
                    "status": disk.get("status"),
                    "fstype": disk.get("fsType"),
                }
            )
    return rows


def _disk_percent(disk: dict[str, object]) -> float:
    total = _number(disk.get("fsSize"))
    used = _number(disk.get("fsUsed"))
    return used / total * 100 if total > 0 else 0.0
