"""Idempotently seed PostgreSQL from the deterministic Phase 3 demo dataset."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.repositories.demo import (
    load_demo_consumers,
    load_demo_orders,
    load_demo_service_records,
)

from .models import ConsumerRow, OrderRow, ServiceRecordRow


def seed_demo_data(session: Session) -> None:
    consumers = load_demo_consumers()
    orders = load_demo_orders()
    service_records = load_demo_service_records()

    for consumer in consumers:
        statement = insert(ConsumerRow).values(**consumer.model_dump(mode="json"))
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[ConsumerRow.consumer_id],
                set_={"explicit_preferences": statement.excluded.explicit_preferences},
            )
        )
    for order in orders:
        values = order.model_dump()
        statement = insert(OrderRow).values(**values)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[OrderRow.order_id],
                set_={
                    "consumer_id": statement.excluded.consumer_id,
                    "product_id": statement.excluded.product_id,
                    "product_name": statement.excluded.product_name,
                    "ordered_at": statement.excluded.ordered_at,
                    "quantity": statement.excluded.quantity,
                    "first_purchase": statement.excluded.first_purchase,
                },
            )
        )
    for service_record in service_records:
        values = service_record.model_dump()
        statement = insert(ServiceRecordRow).values(**values)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[ServiceRecordRow.service_record_id],
                set_={
                    "consumer_id": statement.excluded.consumer_id,
                    "case_id": statement.excluded.case_id,
                    "issue_type": statement.excluded.issue_type,
                    "contact_time": statement.excluded.contact_time,
                    "resolution_status": statement.excluded.resolution_status,
                    "summary": statement.excluded.summary,
                },
            )
        )


def seed_demo_data_transactionally(session: Session) -> None:
    with session.begin():
        seed_demo_data(session)
