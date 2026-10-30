"""Friend accounts: device owners, invite codes and statistics access."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_0023"
down_revision = "20261030_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("full_statistics", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("owner_user_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_nodes_owner_user", "users", ["owner_user_id"], ["id"], ondelete="SET NULL")
    with op.batch_alter_table("agent_tokens") as batch:
        batch.add_column(sa.Column("owner_user_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_agent_tokens_owner_user", "users", ["owner_user_id"], ["id"], ondelete="SET NULL")
    with op.batch_alter_table("agent_pairings") as batch:
        batch.add_column(sa.Column("owner_user_id", sa.String(36), nullable=True))
    op.create_table(
        "account_invites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("account_invites")
    with op.batch_alter_table("agent_pairings") as batch:
        batch.drop_column("owner_user_id")
    with op.batch_alter_table("agent_tokens") as batch:
        batch.drop_constraint("fk_agent_tokens_owner_user", type_="foreignkey")
        batch.drop_column("owner_user_id")
    with op.batch_alter_table("nodes") as batch:
        batch.drop_constraint("fk_nodes_owner_user", type_="foreignkey")
        batch.drop_column("owner_user_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("full_statistics")
