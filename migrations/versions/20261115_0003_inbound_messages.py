"""Add an isolated ledger for accepted inbound messages."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261115_0003"
down_revision = "20260924_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_inbound_messages",
        sa.Column(
            "case_id",
            sa.String(128),
            sa.ForeignKey("investigation_checkpoints.case_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("message_id", sa.String(128), primary_key=True),
        sa.Column("consumer_id", sa.String(128), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("request_revision", sa.BigInteger(), nullable=False),
        sa.Column("accepted_revision", sa.BigInteger(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.UniqueConstraint("case_id", "sequence"),
        sa.CheckConstraint("role = 'CONSUMER'"),
        sa.CheckConstraint("sequence > 0 AND request_revision >= 0"),
        sa.CheckConstraint("accepted_revision > request_revision"),
        sa.CheckConstraint("length(message_id) BETWEEN 1 AND 128"),
        sa.CheckConstraint("length(text) BETWEEN 1 AND 4000 AND length(btrim(text)) > 0"),
        sa.CheckConstraint("jsonb_typeof(evidence_ids) = 'array'"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM case_inbound_messages")):
        raise RuntimeError("Refusing downgrade with accepted messages; preserve a database backup.")
    op.drop_table("case_inbound_messages")
