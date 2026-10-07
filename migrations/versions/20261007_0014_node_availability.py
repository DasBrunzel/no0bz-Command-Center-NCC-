"""Persist observed availability and uptime records for fleet nodes."""

import sqlalchemy as sa
from alembic import op


revision = "20261007_0014"
down_revision = "20261004_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("availability_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("availability_last_checked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("availability_online_seconds", sa.Float(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("availability_current_streak_seconds", sa.Float(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("availability_record_seconds", sa.Float(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("availability_record_seconds")
        batch.drop_column("availability_current_streak_seconds")
        batch.drop_column("availability_online_seconds")
        batch.drop_column("availability_last_checked_at")
        batch.drop_column("availability_started_at")
