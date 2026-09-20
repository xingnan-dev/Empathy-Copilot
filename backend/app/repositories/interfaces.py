"""Lightweight repository protocols replaceable by Phase 4 adapters."""

from typing import Protocol

from backend.app.domain.business import ConsumerRecord, OrderRecord, ServiceRecord


class ConsumerRepository(Protocol):
    def get(self, consumer_id: str) -> ConsumerRecord | None: ...


class OrderRepository(Protocol):
    def list_for_consumer(self, consumer_id: str) -> list[OrderRecord]: ...


class ServiceHistoryRepository(Protocol):
    def list_for_consumer(self, consumer_id: str) -> list[ServiceRecord]: ...


class BusinessRepositoryBundle(Protocol):
    @property
    def consumers(self) -> ConsumerRepository: ...

    @property
    def orders(self) -> OrderRepository: ...

    @property
    def service_history(self) -> ServiceHistoryRepository: ...
