"""Persist normalized official conversation sessions and messages."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260924_0002"
down_revision: str | None = "20260920_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_id", sa.String(length=128), nullable=False),
        sa.Column("shop", sa.String(length=255), nullable=False),
        sa.Column("scene_major", sa.String(length=128), nullable=False),
        sa.Column("scene_minor", sa.String(length=128), nullable=False),
        sa.Column("scenario", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("order_ids", postgresql.JSONB(), nullable=False),
        sa.Column("ticket_ids", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["consumer_id"], ["consumers.consumer_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        "ix_conversation_sessions_consumer_id", "conversation_sessions", ["consumer_id"]
    )
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumer_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("sender", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("image_path", sa.String(length=512), nullable=True),
        sa.Column("order_id", sa.String(length=128), nullable=True),
        sa.Column("ticket_id", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["consumer_id"], ["consumers.consumer_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.session_id"]),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index("ix_messages_consumer_id", "messages", ["consumer_id"])
    op.create_index("ix_messages_session_id", "messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_index("ix_messages_consumer_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversation_sessions_consumer_id", table_name="conversation_sessions")
    op.drop_table("conversation_sessions")
