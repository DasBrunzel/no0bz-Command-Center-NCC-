"""Opt-in GPS history for the Android app's heatmap."""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0028"
down_revision = "20261108_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("location_tracking", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "location_points",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("node_id", sa.String(length=36), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
    )
    op.create_index("ux_location_node_recorded", "location_points", ["node_id", "recorded_at"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_location_node_recorded", table_name="location_points")
    op.drop_table("location_points")
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("location_tracking")
