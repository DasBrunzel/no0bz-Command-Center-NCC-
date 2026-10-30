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
    access_role: Literal["commander", "beta_tester"]
    online: bool
    agent_version: str | None
    last_seen_at: datetime | None
    heartbeat_interval_seconds: int


class HeartbeatResponse(BaseModel):
    accepted: bool
    node_id: str
    server_time: datetime
    next_heartbeat_seconds: int
    # 0.5 agents ignore unknown fields; 0.6 payloads hand it to the service host.
    update_check_requested: bool = False


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
    point_id: str
    sample_id: str | None
    recorded_at: datetime
    metrics: dict[str, object]


class NetworkUsageSummary(BaseModel):
    """Traffic derived from raw telemetry for the current calendar month."""

    period_start: datetime
    received_bytes: int
    sent_bytes: int
    samples: int
    available: bool


class NetworkHistorySample(BaseModel):
    recorded_at: datetime
    network: dict[str, object] | None


SensorRole = Literal["cpu", "case", "gpu", "pump", "radiator"]


class SensorLabel(BaseModel):
    name: str | None = Field(default=None, max_length=48)
    role: SensorRole | None = None


class SensorLabelUpdateRequest(BaseModel):
    key: str = Field(min_length=3, max_length=96, pattern=r"^(fan|temp):[^\x00-\x1f]+$")
    # An empty name and no role remove the label again.
    name: str | None = Field(default=None, max_length=48)
    role: SensorRole | None = None


class NowPlayingResponse(BaseModel):
    session_id: str
    game_id: str | None
    title: str | None
    launcher: str | None
    started_at: datetime
    has_artwork: bool
    genres: list[str]


class FleetNodeResponse(BaseModel):
    node_id: str
    machine_id: str
    display_name: str
    platform: str
    approved: bool
    access_role: Literal["commander", "beta_tester"]
    online: bool
    agent_version: str | None
    metadata: dict[str, object]
    created_at: datetime
    last_seen_at: datetime | None
    availability_percent: float
    availability_started_at: datetime | None
    uptime_record_seconds: int
    gaming_mode_until: datetime | None
    auto_gaming_until: datetime | None = None
    game_tracking: Literal["off", "presence", "titles"] = "titles"
    auto_gaming_mode: bool = True
    now_playing: NowPlayingResponse | None = None
    sensor_labels: dict[str, SensorLabel] = Field(default_factory=dict)
    owner_user_id: str | None = None
    owner_name: str | None = None
    update_check_requested_at: datetime | None
    physical_device_id: str | None
    physical_device_name: str | None
    fleet_group_id: str
    fleet_position: int
    update_channel: Literal["beta", "stable"]
    pending_release_id: str | None
    latest: FleetTelemetryPoint | None


class FleetGroupResponse(BaseModel):
    group_id: str
    name: str
    position: int


class PhysicalDeviceCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)
    node_ids: list[str] = Field(min_length=1, max_length=16)


class PhysicalDeviceResponse(BaseModel):
    device_id: str
    display_name: str
    node_ids: list[str]


class FleetGroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class FleetLayoutPlacement(BaseModel):
    node_id: str = Field(min_length=1, max_length=36)
    group_id: str = Field(min_length=1, max_length=36)
    position: int = Field(ge=0, le=10000)


class FleetLayoutUpdateRequest(BaseModel):
    placements: list[FleetLayoutPlacement] = Field(min_length=1, max_length=500)


class FleetSummaryResponse(BaseModel):
    total_nodes: int
    online_nodes: int
    offline_nodes: int
    pending_nodes: int
    telemetry_points: int
    server_time: datetime


class FleetAlertResponse(BaseModel):
    alert_id: str
    node_id: str
    display_name: str
    kind: str
    severity: Literal["warning", "critical"]
    active: bool
    message: str
    opened_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class AlertPolicyResponse(BaseModel):
    cpu_threshold: int
    memory_threshold: int
    gpu_threshold: int
    disk_threshold: int
    cpu_temperature_threshold: int = 90
    gpu_temperature_threshold: int = 85
    drive_temperature_threshold: int = 65


class AlertPolicyUpdateRequest(AlertPolicyResponse):
    @field_validator("cpu_threshold", "memory_threshold", "gpu_threshold", "disk_threshold")
    @classmethod
    def validate_threshold(cls, value: int) -> int:
        if not 50 <= value <= 100:
            raise ValueError("Grenzwerte müssen zwischen 50 und 100 liegen")
        return value

    @field_validator("cpu_temperature_threshold", "gpu_temperature_threshold", "drive_temperature_threshold")
    @classmethod
    def validate_temperature(cls, value: int) -> int:
        if not 40 <= value <= 110:
            raise ValueError("Temperatur-Grenzwerte müssen zwischen 40 und 110 °C liegen")
        return value


class TelegramAccountResponse(BaseModel):
    available: bool
    linked: bool
    telegram_name: str | None = None
    weekly_recap: bool = True
    bot_username: str | None = None


class TelegramLinkCodeResponse(BaseModel):
    code: str
    expires_at: datetime
    deep_link: str | None = None


class TelegramAccountUpdateRequest(BaseModel):
    weekly_recap: bool


class TelegramSettingsResponse(BaseModel):
    configured: bool
    enabled: bool
    warning_title: str
    critical_title: str
    resolved_title: str
    footer: str


class TelegramSettingsUpdateRequest(BaseModel):
    enabled: bool
    warning_title: str = Field(min_length=1, max_length=128)
    critical_title: str = Field(min_length=1, max_length=128)
    resolved_title: str = Field(min_length=1, max_length=128)
    footer: str = Field(min_length=1, max_length=256)

    @field_validator("warning_title", "critical_title", "resolved_title", "footer")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Text darf nicht leer sein")
        return normalized


class FleetNodeRenameRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized


class FleetNodeRoleUpdateRequest(BaseModel):
    access_role: Literal["commander", "beta_tester"]


class FleetGamingModeRequest(BaseModel):
    minutes: int = Field(ge=0, le=480)


class FleetGameSettingsRequest(BaseModel):
    game_tracking: Literal["off", "presence", "titles"]
    auto_gaming_mode: bool


class GameMatchUpdateRequest(BaseModel):
    # A Steam app id, or null when the game is not on Steam.
    steam_app_id: int | None = Field(default=None, ge=1, le=99_999_999)


class GameResponse(BaseModel):
    game_id: str
    title: str
    launcher: str
    steam_app_id: int | None
    match_state: str
    manual_match: bool
    store_name: str | None
    description: str | None
    genres: list[str]
    developers: list[str]
    release_date: str | None
    has_artwork: bool


class AgentReleaseManifestCreateRequest(BaseModel):
    """Manifest produced by build_ncc_payload.ps1; the binary stays at HTTPS URL."""

    manifest: dict[str, object]


class AgentReleaseResponse(BaseModel):
    release_id: str
    payload_version: str
    channel: Literal["beta", "stable"]
    platform: Literal["windows", "linux"]
    architecture: str
    artifact_url: str
    sha256: str
    size_bytes: int
    signature_key_id: str
    signature_value: str
    minimum_core_version: str | None
    released_at: datetime
    assigned_nodes: int = 0


class FleetNodeReleaseAssignmentRequest(BaseModel):
    release_id: str | None = Field(default=None, min_length=1, max_length=36)


class FleetNodeUpdateChannelRequest(BaseModel):
    channel: Literal["beta", "stable"]


class FleetChatMessageCreateRequest(BaseModel):
    body: str = Field(default="", max_length=20_000)
    body_format: Literal["plain", "markdown"] = "plain"

    @field_validator("body")
    @classmethod
    def require_text_when_present(cls, value: str) -> str:
        return value.rstrip()


class FleetChatAttachmentResponse(BaseModel):
    name: str
    content_type: str
    size: int
    url: str


class FleetChatMessageResponse(BaseModel):
    message_id: str
    sender_node_id: str | None
    sender_user_id: str | None
    sender_name: str
    body: str
    body_format: Literal["plain", "markdown"]
    attachment: FleetChatAttachmentResponse | None
    created_at: datetime


class FleetChatParticipantResponse(BaseModel):
    user_id: str | None
    display_name: str
    role: Literal["commander", "beta_tester", "friend"]


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
    beta_tester: bool = False

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
    access_role: Literal["commander", "beta_tester"]


class AdminCodeResponse(BaseModel):
    code_id: str
    label: str
    status: Literal["ready", "used", "expired", "revoked"]
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
    access_role: Literal["commander", "beta_tester"]


class DashboardAccessResponse(BaseModel):
    access_role: Literal["commander", "beta_tester"]


class DashboardUserResponse(BaseModel):
    user_id: str | None
    username: str
    role: Literal["commander", "beta_tester", "friend"]
    active: bool
    managed: bool
    created_at: datetime | None = None
    full_statistics: bool = False
    device_count: int = 0


class DashboardUserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: Literal["commander", "beta_tester", "friend"] = "beta_tester"


class DashboardUserUpdateRequest(BaseModel):
    role: Literal["commander", "beta_tester", "friend"] | None = None
    active: bool | None = None
    full_statistics: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> DashboardUserUpdateRequest:
        if self.role is None and self.active is None and self.full_statistics is None:
            raise ValueError("role, active or full_statistics must be supplied")
        return self


class AccountInviteCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=128)
    expires_days: int = Field(default=7, ge=1, le=60)


class AccountInviteResponse(BaseModel):
    invite_id: str
    label: str
    created_at: datetime
    expires_at: datetime
    status: Literal["open", "used", "expired", "revoked"]
    used_by: str | None = None


class AccountInviteCreatedResponse(AccountInviteResponse):
    # Shown exactly once; only its hash is stored.
    code: str


class AccountRegisterRequest(BaseModel):
    code: str = Field(min_length=8, max_length=64)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)


class NodeOwnerUpdateRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=36)


class DashboardUserLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class DashboardUserPasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


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
    access_role: Literal["commander", "beta_tester"]
    status: Literal["waiting", "approved", "claimed", "expired", "cancelled"]
    created_at: datetime
    expires_at: datetime


class AgentPairingClaimResponse(BaseModel):
    token: str
