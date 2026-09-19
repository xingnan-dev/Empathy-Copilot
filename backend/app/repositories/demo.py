"""JSON-backed deterministic demo repositories."""

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from backend.app.domain.business import ConsumerRecord, OrderRecord, ServiceRecord

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "demo"


def _load_json(filename: str) -> Any:
    with (DATA_DIR / filename).open(encoding="utf-8") as handle:
        return json.load(handle)


class DemoConsumerRepository:
    def __init__(self) -> None:
        records = TypeAdapter(list[ConsumerRecord]).validate_python(_load_json("consumers.json"))
        self._records = {record.consumer_id: record for record in records}

    def get(self, consumer_id: str) -> ConsumerRecord | None:
        return self._records.get(consumer_id)


class DemoOrderRepository:
    def __init__(self) -> None:
        self._records = TypeAdapter(list[OrderRecord]).validate_python(_load_json("orders.json"))

    def list_for_consumer(self, consumer_id: str) -> list[OrderRecord]:
        return [record for record in self._records if record.consumer_id == consumer_id]


class DemoServiceHistoryRepository:
    def __init__(self) -> None:
        self._records = TypeAdapter(list[ServiceRecord]).validate_python(
            _load_json("service_records.json")
        )

    def list_for_consumer(self, consumer_id: str) -> list[ServiceRecord]:
        return [record for record in self._records if record.consumer_id == consumer_id]


class DemoRepositoryBundle:
    def __init__(self) -> None:
        self.consumers = DemoConsumerRepository()
        self.orders = DemoOrderRepository()
        self.service_history = DemoServiceHistoryRepository()

