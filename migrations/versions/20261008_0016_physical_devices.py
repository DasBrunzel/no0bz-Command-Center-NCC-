"""Add physical devices for multi-OS agents."""

import sqlalchemy as sa
from alembic import op

revision = "20261008_0016"
down_revision = "20261007_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "physical_devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("hardware_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hardware_fingerprint"),
    )
    op.add_column("nodes", sa.Column("physical_device_id", sa.String(length=36), nullable=True))
    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot ALTER an existing table to add a foreign key. Alembic
        # recreates the table atomically in batch mode for development/tests.
        with op.batch_alter_table("nodes") as batch:
            batch.create_foreign_key(
                "fk_nodes_physical_device", "physical_devices", ["physical_device_id"], ["id"], ondelete="SET NULL"
            )
    else:
        op.create_foreign_key("fk_nodes_physical_device", "nodes", "physical_devices", ["physical_device_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("nodes") as batch:
            batch.drop_constraint("fk_nodes_physical_device", type_="foreignkey")
    else:
        op.drop_constraint("fk_nodes_physical_device", "nodes", type_="foreignkey")
    op.drop_column("nodes", "physical_device_id")
    op.drop_table("physical_devices")
