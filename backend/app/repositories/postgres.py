"""PostgreSQL implementations of the Phase 3 business repository protocols."""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain.business import ConsumerRecord, OrderRecord, ServiceRecord
from backend.app.persistence.models import ConsumerRow, OrderRow, ServiceRecordRow

SessionFactory = Callable[[], Session]


class PostgresConsumerRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def get(self, consumer_id: str) -> ConsumerRecord | None:
        with self._sessions() as session:
            row = session.get(ConsumerRow, consumer_id)
            if row is None:
                return None
            return ConsumerRecord(
                consumer_id=row.consumer_id,
                explicit_preferences=list(row.explicit_preferences),
            )


class PostgresOrderRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def list_for_consumer(self, consumer_id: str) -> list[OrderRecord]:
        with self._sessions() as session:
            rows = session.scalars(
                select(OrderRow)
                .where(OrderRow.consumer_id == consumer_id)
                .order_by(OrderRow.ordered_at)
            ).all()
            return [
                OrderRecord(
                    order_id=row.order_id,
                    consumer_id=row.consumer_id,
                    product_id=row.product_id,
                    product_name=row.product_name,
                    ordered_at=row.ordered_at,
                    quantity=row.quantity,
                    first_purchase=row.first_purchase,
                )
                for row in rows
            ]


class PostgresServiceHistoryRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def list_for_consumer(self, consumer_id: str) -> list[ServiceRecord]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ServiceRecordRow)
                .where(ServiceRecordRow.consumer_id == consumer_id)
                .order_by(ServiceRecordRow.contact_time)
            ).all()
            return [
                ServiceRecord(
                    service_record_id=row.service_record_id,
                    consumer_id=row.consumer_id,
                    case_id=row.case_id,
                    issue_type=row.issue_type,
                    contact_time=row.contact_time,
                    resolution_status=row.resolution_status,
                    summary=row.summary,
                )
                for row in rows
            ]


class PostgresRepositoryBundle:
    def __init__(self, sessions: SessionFactory) -> None:
        self.consumers = PostgresConsumerRepository(sessions)
        self.orders = PostgresOrderRepository(sessions)
        self.service_history = PostgresServiceHistoryRepository(sessions)
