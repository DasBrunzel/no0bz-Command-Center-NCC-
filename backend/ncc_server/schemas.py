from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NodeEnrollmentRequest(BaseModel):
    machine_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    display_name: str = Field(min_length=1, max_length=128)
    platform: Literal["windows", "linux", "darwin"]
    agent_version: str = Field(min_length=1, max_length=32)
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, max_length=64
    )


class NodeHeartbeatRequest(BaseModel):
    agent_version: str = Field(min_length=1, max_length=32)
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, max_length=64
    )


class NodeResponse(BaseModel):
    node_id: str
    machine_id: str
    display_name: str
    platform: str
    approved: bool
    online: bool
    agent_version: str | None
    last_seen_at: datetime | None
    heartbeat_interval_seconds: int


class HeartbeatResponse(BaseModel):
    accepted: bool
    node_id: str
    server_time: datetime
    next_heartbeat_seconds: int
