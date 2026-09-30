"""Add idempotent agent telemetry sample identifiers."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0003"
down_revision = "20260930_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("telemetry_points", sa.Column("sample_id", sa.String(36)))
    op.create_index(
        "ux_telemetry_node_sample",
        "telemetry_points",
        ["node_id", "sample_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_telemetry_node_sample", table_name="telemetry_points")
    op.drop_column("telemetry_points", "sample_id")
