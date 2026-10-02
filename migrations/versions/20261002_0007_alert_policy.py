"""Add configurable alert thresholds."""

from alembic import op
import sqlalchemy as sa

revision = "20261002_0007"
down_revision = "20261002_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_policy",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("cpu_threshold", sa.Integer(), nullable=False),
        sa.Column("memory_threshold", sa.Integer(), nullable=False),
        sa.Column("gpu_threshold", sa.Integer(), nullable=False),
        sa.Column("disk_threshold", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alert_policy")
