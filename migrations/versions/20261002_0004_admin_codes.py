"""Add browser admin codes and sessions."""
from alembic import op
import sqlalchemy as sa

revision = "20261002_0004"
down_revision = "20260930_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("admin_codes", sa.Column("id", sa.String(36), primary_key=True), sa.Column("label", sa.String(128), nullable=False), sa.Column("code_hash", sa.String(64), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("used_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_table("dashboard_sessions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("code_id", sa.String(36), sa.ForeignKey("admin_codes.id", ondelete="CASCADE"), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_table("dashboard_sessions")
    op.drop_table("admin_codes")
