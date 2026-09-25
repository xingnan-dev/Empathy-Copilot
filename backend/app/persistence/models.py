"""Minimal relational business schema plus versioned investigation snapshots."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConsumerRow(Base):
    __tablename__ = "consumers"

    consumer_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    explicit_preferences: Mapped[list[str]] = mapped_column(JSONB, default=list)


class OrderRow(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    consumer_id: Mapped[str] = mapped_column(ForeignKey("consumers.consumer_id"), index=True)
    product_id: Mapped[str] = mapped_column(String(128))
    product_name: Mapped[str] = mapped_column(String(255))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quantity: Mapped[int] = mapped_column(Integer)
    first_purchase: Mapped[bool] = mapped_column(Boolean)


class ServiceRecordRow(Base):
    __tablename__ = "service_records"

    service_record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    consumer_id: Mapped[str] = mapped_column(ForeignKey("consumers.consumer_id"), index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    issue_type: Mapped[str] = mapped_column(String(128))
    contact_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolution_status: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(Text)


class InvestigationCheckpointRow(Base):
    __tablename__ = "investigation_checkpoints"

    case_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    consumer_id: Mapped[str] = mapped_column(String(128), index=True)
    state_schema_version: Mapped[int] = mapped_column(Integer)
    state_revision: Mapped[int] = mapped_column(Integer)
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationSessionRow(Base):
    __tablename__ = "conversation_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    consumer_id: Mapped[str] = mapped_column(ForeignKey("consumers.consumer_id"), index=True)
    shop: Mapped[str] = mapped_column(String(255))
    scene_major: Mapped[str] = mapped_column(String(128))
    scene_minor: Mapped[str] = mapped_column(String(128))
    scenario: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    order_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    ticket_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)


class MessageRow(Base):
    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_sessions.session_id"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumer_id: Mapped[str] = mapped_column(ForeignKey("consumers.consumer_id"), index=True)
    role: Mapped[str] = mapped_column(String(64))
    sender: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(64))
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ticket_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
