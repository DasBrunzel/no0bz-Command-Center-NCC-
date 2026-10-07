from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    machine_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_role: Mapped[str] = mapped_column(String(32), nullable=False, default="commander")
    agent_version: Mapped[str | None] = mapped_column(String(32))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Availability is accumulated by the server's health loop.  It deliberately
    # lives independently of raw telemetry retention so the fleet ranking stays
    # meaningful over the lifetime of a node.
    availability_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    availability_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    availability_online_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    availability_current_streak_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    availability_record_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    gaming_mode_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fleet_group_id: Mapped[str | None] = mapped_column(ForeignKey("fleet_groups.id", ondelete="SET NULL"))
    fleet_position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fleet_group: Mapped[FleetGroup | None] = relationship(back_populates="nodes")
    telemetry: Mapped[list[TelemetryPoint]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )
    tokens: Mapped[list[AgentToken]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


class FleetGroup(Base):
    __tablename__ = "fleet_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    nodes: Mapped[list[Node]] = relationship(back_populates="fleet_group")


class TelemetryPoint(Base):
    __tablename__ = "telemetry_points"
    __table_args__ = (
        Index("ix_telemetry_node_recorded", "node_id", "recorded_at"),
        Index("ux_telemetry_node_sample", "node_id", "sample_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    sample_id: Mapped[str | None] = mapped_column(String(36))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    node: Mapped[Node] = relationship(back_populates="telemetry")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AgentToken(Base):
    __tablename__ = "agent_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id: Mapped[str | None] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    access_role: Mapped[str] = mapped_column(String(32), nullable=False, default="commander")
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    node: Mapped[Node | None] = relationship(back_populates="tokens")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)


class AdminCode(Base):
    __tablename__ = "admin_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    access_role: Mapped[str] = mapped_column(String(32), nullable=False, default="commander")
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DashboardSession(Base):
    __tablename__ = "dashboard_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code_id: Mapped[str] = mapped_column(ForeignKey("admin_codes.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentPairing(Base):
    __tablename__ = "agent_pairings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    access_role: Mapped[str] = mapped_column(String(32), nullable=False, default="commander")
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AlertState(Base):
    __tablename__ = "alert_states"
    __table_args__ = (UniqueConstraint("node_id", "kind", name="ux_alert_state_node_kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_notified_state: Mapped[str | None] = mapped_column(String(16))


class AlertPolicy(Base):
    __tablename__ = "alert_policy"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default="default")
    cpu_threshold: Mapped[int] = mapped_column(nullable=False, default=90)
    memory_threshold: Mapped[int] = mapped_column(nullable=False, default=90)
    gpu_threshold: Mapped[int] = mapped_column(nullable=False, default=90)
    disk_threshold: Mapped[int] = mapped_column(nullable=False, default=90)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class TelegramNotificationSettings(Base):
    """Dashboard-editable presentation preferences; credentials stay in server.env."""

    __tablename__ = "telegram_notification_settings"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    warning_title: Mapped[str] = mapped_column(String(128), nullable=False, default="NCC WARNUNG")
    critical_title: Mapped[str] = mapped_column(String(128), nullable=False, default="NCC KRITISCHE WARNUNG")
    resolved_title: Mapped[str] = mapped_column(String(128), nullable=False, default="NCC ENTWARNUNG")
    footer: Mapped[str] = mapped_column(String(256), nullable=False, default="NCC {version}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class TrafficStatisticsSettings(Base):
    """The manual start marker for the visible fleet traffic period."""

    __tablename__ = "traffic_statistics_settings"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default="default")
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FleetChatMessage(Base):
    """A durable Fleet-wide conversation entry, optionally with one attachment."""

    __tablename__ = "fleet_chat_messages"
    __table_args__ = (Index("ix_fleet_chat_messages_created", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_node_id: Mapped[str | None] = mapped_column(ForeignKey("nodes.id", ondelete="SET NULL"))
    sender_name: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_format: Mapped[str] = mapped_column(String(16), nullable=False, default="plain")
    attachment_name: Mapped[str | None] = mapped_column(String(255))
    attachment_path: Mapped[str | None] = mapped_column(String(255))
    attachment_type: Mapped[str | None] = mapped_column(String(128))
    attachment_size: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
