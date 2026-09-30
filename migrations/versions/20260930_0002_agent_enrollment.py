"""Add persistent agent enrollment and heartbeat state."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0002"
down_revision = "20260930_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nodes", sa.Column("agent_version", sa.String(32)))
    op.add_column("nodes", sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column(
        "nodes",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column("agent_tokens", sa.Column("last_used_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("agent_tokens", "last_used_at")
    op.drop_column("nodes", "updated_at")
    op.drop_column("nodes", "metadata")
    op.drop_column("nodes", "agent_version")
