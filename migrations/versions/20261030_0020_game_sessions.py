"""Track detected games, play sessions and automatic gaming mode."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_0020"
down_revision = "20261029_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("game_tracking", sa.String(16), nullable=False, server_default="titles"))
        batch.add_column(sa.Column("auto_gaming_mode", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("auto_gaming_until", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "games",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(192), nullable=False, unique=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("launcher", sa.String(16), nullable=False),
        sa.Column("steam_app_id", sa.Integer(), nullable=True),
        sa.Column("match_state", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("manual_match", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("store_name", sa.String(256), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("genres", sa.JSON(), nullable=False),
        sa.Column("developers", sa.JSON(), nullable=False),
        sa.Column("release_date", sa.String(64), nullable=True),
        sa.Column("header_image", sa.LargeBinary(), nullable=True),
        sa.Column("header_content_type", sa.String(64), nullable=True),
        sa.Column("metadata_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.String(36), sa.ForeignKey("games.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hardware", sa.JSON(), nullable=False),
    )
    op.create_index("ix_game_sessions_node_ended", "game_sessions", ["node_id", "ended_at"])
    op.create_index("ix_game_sessions_started", "game_sessions", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_game_sessions_started", table_name="game_sessions")
    op.drop_index("ix_game_sessions_node_ended", table_name="game_sessions")
    op.drop_table("game_sessions")
    op.drop_table("games")
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("auto_gaming_until")
        batch.drop_column("auto_gaming_mode")
        batch.drop_column("game_tracking")
