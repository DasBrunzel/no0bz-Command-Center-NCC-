from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


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


class TelemetryPointRequest(BaseModel):
    sample_id: UUID
    recorded_at: datetime
    metrics: dict[str, object] = Field(max_length=256)

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must include a timezone")
        normalized = value.astimezone(timezone.utc)
        if normalized > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("recorded_at is too far in the future")
        return normalized


class TelemetryBatchRequest(BaseModel):
    points: list[TelemetryPointRequest] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_payload_size(self) -> TelemetryBatchRequest:
        sample_ids = [point.sample_id for point in self.points]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("telemetry batch contains duplicate sample IDs")
        size = len(self.model_dump_json().encode("utf-8"))
        if size > 2 * 1024 * 1024:
            raise ValueError("telemetry batch exceeds 2 MiB")
        return self


class TelemetryBatchResponse(BaseModel):
    accepted: int
    duplicates: int


class FleetTelemetryPoint(BaseModel):
    sample_id: str | None
    recorded_at: datetime
    metrics: dict[str, object]


class FleetNodeResponse(BaseModel):
    node_id: str
    machine_id: str
    display_name: str
    platform: str
    approved: bool
    online: bool
    agent_version: str | None
    metadata: dict[str, object]
    created_at: datetime
    last_seen_at: datetime | None
    latest: FleetTelemetryPoint | None


class FleetSummaryResponse(BaseModel):
    total_nodes: int
    online_nodes: int
    offline_nodes: int
    pending_nodes: int
    telemetry_points: int
    server_time: datetime


class FleetNodeRenameRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized


class AgentInvitationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    expires_hours: int = Field(default=168, ge=0, le=8760)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class AgentInvitationResponse(BaseModel):
    token_id: str
    name: str
    status: Literal["ready", "bound", "expired", "revoked"]
    node_id: str | None
    node_name: str | None
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class AgentInvitationCreatedResponse(AgentInvitationResponse):
    token: str


class AdminCodeCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=128)
    expires_minutes: int = Field(default=15, ge=1, le=60)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("label must not be blank")
        return normalized


class AdminCodeCreatedResponse(BaseModel):
    code: str
    expires_at: datetime


class AdminCodeResponse(BaseModel):
    code_id: str
    label: str
    status: Literal["ready", "used", "expired", "revoked"]
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None


class AdminCodeRedeemRequest(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9]{8}$")


class AgentPairingRegisterRequest(NodeEnrollmentRequest):
    pairing_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    pairing_secret: str = Field(min_length=32, max_length=128)


class AgentPairingClaimRequest(BaseModel):
    pairing_secret: str = Field(min_length=32, max_length=128)


class AgentPairingResponse(BaseModel):
    pairing_id: str
    display_name: str
    platform: str
    status: Literal["waiting", "approved", "claimed", "expired", "cancelled"]
    created_at: datetime
    expires_at: datetime


class AgentPairingClaimResponse(BaseModel):
    token: str
