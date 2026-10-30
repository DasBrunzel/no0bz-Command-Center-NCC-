"""Keep hourly hardware statistics per node."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_0022"
down_revision = "20261030_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("rollup_live_since", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("rollup_backfilled_before", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("rollup_backfill_done", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "hardware_hourly",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hour", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("energy_wh", sa.Float(), nullable=False, server_default="0"),
        sa.Column("first_point_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_point_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ux_hardware_hourly_node_hour", "hardware_hourly", ["node_id", "hour"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_hardware_hourly_node_hour", table_name="hardware_hourly")
    op.drop_table("hardware_hourly")
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("rollup_backfill_done")
        batch.drop_column("rollup_backfilled_before")
        batch.drop_column("rollup_live_since")
