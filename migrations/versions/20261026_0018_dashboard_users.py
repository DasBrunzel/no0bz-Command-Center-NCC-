"""Link browser sessions and Fleet chat to personal dashboard users."""

import sqlalchemy as sa
from alembic import op

revision = "20261026_0018"
down_revision = "20261008_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("dashboard_sessions") as batch:
        batch.alter_column("code_id", existing_type=sa.String(length=36), nullable=True)
        batch.add_column(sa.Column("user_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_dashboard_sessions_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE")
    with op.batch_alter_table("fleet_chat_messages") as batch:
        batch.add_column(sa.Column("sender_user_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_fleet_chat_messages_user_id", "users", ["sender_user_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("fleet_chat_messages") as batch:
        batch.drop_constraint("fk_fleet_chat_messages_user_id", type_="foreignkey")
        batch.drop_column("sender_user_id")
    op.execute("DELETE FROM dashboard_sessions WHERE code_id IS NULL")
    with op.batch_alter_table("dashboard_sessions") as batch:
        batch.drop_constraint("fk_dashboard_sessions_user_id", type_="foreignkey")
        batch.drop_column("user_id")
        batch.alter_column("code_id", existing_type=sa.String(length=36), nullable=False)
