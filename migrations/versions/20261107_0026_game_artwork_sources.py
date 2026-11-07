"""Remember where a game banner came from so uploads are kept."""

import sqlalchemy as sa
from alembic import op

revision = "20261107_0026"
down_revision = "20261030_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("games") as batch:
        batch.add_column(sa.Column("artwork_source", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("artwork_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE games SET artwork_source = 'steam' WHERE header_content_type IS NOT NULL"))


def downgrade() -> None:
    with op.batch_alter_table("games") as batch:
        batch.drop_column("artwork_checked_at")
        batch.drop_column("artwork_source")
