"""Create Phase 4 business and investigation persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260920_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consumers",
        sa.Column("consumer_id", sa.String(length=128), nullable=False),
        sa.Column("explicit_preferences", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("consumer_id"),
    )
    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_id", sa.String(length=128), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("first_purchase", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["consumer_id"], ["consumers.consumer_id"]),
        sa.PrimaryKeyConstraint("order_id"),
    )
    op.create_index("ix_orders_consumer_id", "orders", ["consumer_id"])
    op.create_table(
        "service_records",
        sa.Column("service_record_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("issue_type", sa.String(length=128), nullable=False),
        sa.Column("contact_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution_status", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["consumer_id"], ["consumers.consumer_id"]),
        sa.PrimaryKeyConstraint("service_record_id"),
    )
    op.create_index("ix_service_records_case_id", "service_records", ["case_id"])
    op.create_index(
        "ix_service_records_consumer_id", "service_records", ["consumer_id"]
    )
    op.create_table(
        "investigation_checkpoints",
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_id", sa.String(length=128), nullable=False),
        sa.Column("state_schema_version", sa.Integer(), nullable=False),
        sa.Column("state_revision", sa.Integer(), nullable=False),
        sa.Column("state_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("case_id"),
    )
    op.create_index(
        "ix_investigation_checkpoints_consumer_id",
        "investigation_checkpoints",
        ["consumer_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investigation_checkpoints_consumer_id",
        table_name="investigation_checkpoints",
    )
    op.drop_table("investigation_checkpoints")
    op.drop_index("ix_service_records_consumer_id", table_name="service_records")
    op.drop_index("ix_service_records_case_id", table_name="service_records")
    op.drop_table("service_records")
    op.drop_index("ix_orders_consumer_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("consumers")
