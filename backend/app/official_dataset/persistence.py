"""Idempotent PostgreSQL import and reconstruction for normalized official records."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from backend.app.persistence.models import (
    ConsumerRow,
    ConversationSessionRow,
    MessageRow,
    OrderRow,
    ServiceRecordRow,
)

from .models import ConversationSession, MessageRecord, OfficialDataset


class OfficialDatasetImporter:
    def import_dataset(self, dataset: OfficialDataset, sessions: sessionmaker[Session]) -> None:
        first_orders = {
            consumer.consumer_id: min(
                (order for order in dataset.orders if order.consumer_id == consumer.consumer_id),
                key=lambda order: order.ordered_at,
            ).order_id
            for consumer in dataset.consumers
            if any(order.consumer_id == consumer.consumer_id for order in dataset.orders)
        }
        with sessions.begin() as session:
            for consumer in dataset.consumers:
                statement = insert(ConsumerRow).values(
                    consumer_id=consumer.consumer_id, explicit_preferences=[]
                )
                session.execute(
                    statement.on_conflict_do_nothing(index_elements=[ConsumerRow.consumer_id])
                )
            for conversation in dataset.sessions:
                values = conversation.model_dump()
                values["scenario"] = conversation.scenario.value if conversation.scenario else None
                statement = insert(ConversationSessionRow).values(**values)
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[ConversationSessionRow.session_id],
                        set_={
                            key: getattr(statement.excluded, key)
                            for key in values
                            if key != "session_id"
                        },
                    )
                )
            for message in dataset.messages:
                values = message.model_dump()
                statement = insert(MessageRow).values(**values)
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[MessageRow.message_id],
                        set_={
                            key: getattr(statement.excluded, key)
                            for key in values
                            if key != "message_id"
                        },
                    )
                )
            for order in dataset.orders:
                values = {
                    "order_id": order.order_id,
                    "consumer_id": order.consumer_id,
                    "product_id": order.product_id,
                    "product_name": order.product_name,
                    "ordered_at": order.ordered_at,
                    "quantity": order.quantity,
                    "first_purchase": first_orders[order.consumer_id] == order.order_id,
                }
                statement = insert(OrderRow).values(**values)
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[OrderRow.order_id],
                        set_={
                            key: getattr(statement.excluded, key)
                            for key in values
                            if key != "order_id"
                        },
                    )
                )
            for service_record in dataset.service_records:
                values = {
                    "service_record_id": service_record.service_record_id,
                    "consumer_id": service_record.consumer_id,
                    "case_id": service_record.session_id,
                    "issue_type": service_record.issue_type,
                    "contact_time": service_record.created_at,
                    "resolution_status": service_record.status,
                    "summary": (
                        f"{service_record.source_kind}: {service_record.issue_type} "
                        f"({service_record.status})"
                    ),
                }
                statement = insert(ServiceRecordRow).values(**values)
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[ServiceRecordRow.service_record_id],
                        set_={
                            key: getattr(statement.excluded, key)
                            for key in values
                            if key != "service_record_id"
                        },
                    )
                )


class OfficialConversationRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get_session(self, session_id: str) -> ConversationSession | None:
        with self._sessions() as session:
            row = session.get(ConversationSessionRow, session_id)
            if row is None:
                return None
            return ConversationSession.model_validate(
                {
                    column.name: getattr(row, column.name)
                    for column in ConversationSessionRow.__table__.columns
                }
            )

    def list_messages(self, session_id: str) -> list[MessageRecord]:
        with self._sessions() as session:
            rows = session.scalars(
                select(MessageRow)
                .where(MessageRow.session_id == session_id)
                .order_by(MessageRow.sequence)
            ).all()
            return [
                MessageRecord.model_validate(
                    {
                        column.name: getattr(row, column.name)
                        for column in MessageRow.__table__.columns
                    }
                )
                for row in rows
            ]
