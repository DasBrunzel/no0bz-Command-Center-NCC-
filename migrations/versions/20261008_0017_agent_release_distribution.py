"""Add signed agent release distribution and explicit per-node approval."""

import sqlalchemy as sa
from alembic import op

revision = "20261008_0017"
down_revision = "20261008_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_releases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payload_version", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("architecture", sa.String(length=32), nullable=False),
        sa.Column("artifact_url", sa.String(length=2048), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("signature_key_id", sa.String(length=64), nullable=False),
        sa.Column("signature_value", sa.Text(), nullable=False),
        sa.Column("minimum_core_version", sa.String(length=64), nullable=True),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payload_version", "channel", "platform", "architecture", name="ux_agent_release_target"),
    )
    op.add_column("nodes", sa.Column("update_channel", sa.String(length=16), server_default="beta", nullable=False))
    op.add_column("nodes", sa.Column("pending_release_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_nodes_pending_release", "nodes", "agent_releases", ["pending_release_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_nodes_pending_release", "nodes", type_="foreignkey")
    op.drop_column("nodes", "pending_release_id")
    op.drop_column("nodes", "update_channel")
    op.drop_table("agent_releases")
