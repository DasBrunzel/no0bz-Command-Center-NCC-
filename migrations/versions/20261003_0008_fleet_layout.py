"""Add persistent fleet groups and node positions."""

import sqlalchemy as sa
from alembic import op

revision = "20261003_0008"
down_revision = "20261002_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fleet_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("fleet_group_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("fleet_position", sa.Integer(), nullable=False, server_default="0"))
        batch.create_foreign_key("fk_nodes_fleet_group", "fleet_groups", ["fleet_group_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.drop_constraint("fk_nodes_fleet_group", type_="foreignkey")
        batch.drop_column("fleet_position")
        batch.drop_column("fleet_group_id")
    op.drop_table("fleet_groups")
