"""Create the NCC 0.5 server foundation tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("machine_id", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "agent_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("nodes.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "telemetry_points",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_telemetry_node_recorded", "telemetry_points", ["node_id", "recorded_at"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(128)),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("details", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_index("ix_telemetry_node_recorded", table_name="telemetry_points")
    op.drop_table("telemetry_points")
    op.drop_table("agent_tokens")
    op.drop_table("users")
    op.drop_table("nodes")
