"""Add browser-approved agent pairings."""

from alembic import op
import sqlalchemy as sa

revision = "20261002_0005"
down_revision = "20261002_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_pairings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("machine_id", sa.String(128), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("agent_version", sa.String(32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("agent_pairings")
