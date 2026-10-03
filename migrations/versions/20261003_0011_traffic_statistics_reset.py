"""Add a persistent manual reset marker for displayed traffic statistics."""

import sqlalchemy as sa
from alembic import op

revision = "20261003_0011"
down_revision = "20261003_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "traffic_statistics_settings",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("traffic_statistics_settings")
