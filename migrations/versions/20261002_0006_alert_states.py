"""Add persistent NCC alert state."""

from alembic import op
import sqlalchemy as sa

revision = "20261002_0006"
down_revision = "20261002_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("message", sa.String(512), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("last_notified_state", sa.String(16)),
        sa.UniqueConstraint("node_id", "kind", name="ux_alert_state_node_kind"),
    )


def downgrade() -> None:
    op.drop_table("alert_states")
