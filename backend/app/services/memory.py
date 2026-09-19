"""Deterministic evidence-backed consumer memory projection."""

from backend.app.domain.business import ConsumerMemorySnapshot, EvidenceBackedFact
from backend.app.domain.evidence import Evidence


class ConsumerMemoryService:
    def build(self, consumer_id: str, evidence: list[Evidence]) -> ConsumerMemorySnapshot:
        consumer_evidence = [item for item in evidence if self._belongs_to(item, consumer_id)]
        recent_orders = [
            self._fact(item)
            for item in consumer_evidence
            if item.key in {"first_purchase", "repeat_purchase"}
        ]
        repeat_products = [
            self._fact(item) for item in consumer_evidence if item.key == "repeat_purchase"
        ]
        service_contacts = [
            self._fact(item)
            for item in consumer_evidence
            if item.key == "previous_service_contact"
        ]
        preferences = [
            self._fact(item)
            for item in consumer_evidence
            if item.key == "explicit_preferences"
        ]
        return ConsumerMemorySnapshot(
            consumer_id=consumer_id,
            repeat_purchase_products=repeat_products,
            recent_orders=recent_orders,
            previous_service_contacts=service_contacts,
            explicit_preferences=preferences,
        )

    @staticmethod
    def _belongs_to(item: Evidence, consumer_id: str) -> bool:
        if item.key == "explicit_preferences":
            return item.source.source_id == consumer_id
        if isinstance(item.value, dict):
            value_consumer_id = item.value.get("consumer_id")
            return value_consumer_id is None or value_consumer_id == consumer_id
        return True

    @staticmethod
    def _fact(item: Evidence) -> EvidenceBackedFact:
        return EvidenceBackedFact(key=item.key, value=item.value, evidence_ids=[item.id])

