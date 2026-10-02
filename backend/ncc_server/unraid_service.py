"""Read-only Unraid GraphQL presence collector, executed by the NCC server."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select

from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Node, TelemetryPoint, utc_now


async def collect_unraid(database: Database, settings: ServerSettings) -> None:
    """Confirm the API connection and represent the external Unraid host as a NCC node."""
    if not settings.unraid_url or not settings.unraid_api_key.get_secret_value():
        return
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            settings.unraid_url,
            headers={"x-api-key": settings.unraid_api_key.get_secret_value()},
            json={"query": "query NccConnectionCheck { __typename }"},
        )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("Unraid API returned no GraphQL data")

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
                agent_version="unraid-api-4.37.4",
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
                payload={"unraid": {"api_connected": True, "version": "4.37.4"}},
            )
        )
        session.commit()
