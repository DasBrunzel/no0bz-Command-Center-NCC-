from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MetricValue(BaseModel):
    value: float | int | str | bool | None
    unit: str | None = None
    source: str


class Snapshot(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    node_id: str
    metrics: dict[str, Any]


class Profile(BaseModel):
    alias: str = Field(min_length=1, max_length=48)
    pc_name: str = Field(min_length=1, max_length=128)
    avatar: str = Field(default="circuit", max_length=32)
    role: str = Field(default="operator", max_length=48)
    bio: str = Field(default="", max_length=500)


class KillRequest(BaseModel):
    pid: int = Field(gt=0)


class ChatMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    sender: str = Field(min_length=1, max_length=128)
    kind: str = Field(default="text", pattern="^(text|code|note)$")


class NodeRegistration(BaseModel):
    node_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    profile: Profile | None = None


class NodeTelemetry(BaseModel):
    node_id: str = Field(min_length=1, max_length=128)
    snapshot: Snapshot

