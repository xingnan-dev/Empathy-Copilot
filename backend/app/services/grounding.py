"""The sole conversion boundary from raw business results to Evidence."""

from datetime import UTC, datetime

from backend.app.domain.business import (
    ConsumerMemoryToolResult,
    ConsumerRecord,
    LogisticsStatusToolResult,
    OrderHistoryToolResult,
    OrderRecord,
    PolicyToolResult,
    ServiceHistoryToolResult,
    ServiceRecord,
)
from backend.app.domain.evidence import Evidence, EvidenceSource, EvidenceType, SourceType


class EvidenceGroundingService:
    """Ground typed raw records without inferring usage, regimen, or causality."""

    def ground_order_history(self, result: OrderHistoryToolResult, case_id: str) -> list[Evidence]:
        return [self._ground_order(record, case_id) for record in result.records]

    def ground_service_history(
        self, result: ServiceHistoryToolResult, case_id: str
    ) -> list[Evidence]:
        return [self._ground_service_record(record, case_id) for record in result.records]

    def ground_consumer_memory(
        self, result: ConsumerMemoryToolResult, case_id: str
    ) -> list[Evidence]:
        evidence: list[Evidence] = []
        if result.consumer is not None:
            evidence.extend(self._ground_consumer(result.consumer, case_id))
        evidence.extend(self._ground_order(record, case_id) for record in result.recent_orders)
        evidence.extend(
            self._ground_service_record(record, case_id)
            for record in result.previous_service_contacts
        )
        return evidence

    def ground_policy(self, result: PolicyToolResult, case_id: str) -> list[Evidence]:
        """Ground the retained Phase 2 policy stub through the same conversion boundary."""
        now = datetime.now(UTC)
        return [
            Evidence(
                id=f"ev-tool-policy-{case_id}-{result.policy_id}",
                case_id=case_id,
                key="policy_retrieved",
                value={"policy_id": result.policy_id},
                evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
                source=EvidenceSource(
                    source_type=SourceType.POLICY_DATABASE,
                    source_id=result.policy_id,
                    source_label="Stub service policy",
                ),
                observed_at=now,
                created_at=now,
                extraction_confidence=1.0,
            )
        ]

    def ground_logistics_status(
        self, result: LogisticsStatusToolResult, case_id: str
    ) -> list[Evidence]:
        record = result.record
        if record is None:
            return []
        source = EvidenceSource(
            source_type=SourceType.SERVICE_SYSTEM,
            source_id=record.service_record_id,
            source_label=f"Logistics record {record.service_record_id}",
        )

        def evidence(evidence_id: str, key: str, value: str) -> Evidence:
            return Evidence(
                id=evidence_id,
                case_id=case_id,
                key=key,
                value=value,
                evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
                source=source,
                observed_at=record.observed_at,
                created_at=datetime.now(UTC),
                extraction_confidence=1.0,
                metadata={"grounding_method": "BUSINESS_TOOL"},
            )

        grounded = [
            evidence(
                f"ev-logistics-status-{record.service_record_id}",
                "logistics_status",
                record.delivery_status,
            )
        ]
        if record.investigation_result is not None:
            grounded.extend(
                [
                    evidence(
                        f"ev-logistics-result-{record.service_record_id}",
                        "logistics_investigation_result",
                        record.investigation_result,
                    ),
                    evidence(
                        f"ev-logistics-resolution-{record.service_record_id}",
                        "resolution_status",
                        record.resolution_status,
                    ),
                ]
            )
        return grounded

    @staticmethod
    def _ground_order(record: OrderRecord, case_id: str) -> Evidence:
        purchase_key = "first_purchase" if record.first_purchase else "repeat_purchase"
        return Evidence(
            id=f"ev-order-{record.order_id}-{purchase_key}",
            case_id=case_id,
            key=purchase_key,
            value={
                "order_id": record.order_id,
                "consumer_id": record.consumer_id,
                "product_id": record.product_id,
                "product_name": record.product_name,
                "ordered_at": record.ordered_at.isoformat(),
                "quantity": record.quantity,
                "first_purchase": record.first_purchase,
            },
            evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
            source=EvidenceSource(
                source_type=SourceType.ORDER_SYSTEM,
                source_id=record.order_id,
                source_label=f"Order {record.order_id}",
            ),
            observed_at=record.ordered_at,
            created_at=datetime.now(UTC),
            extraction_confidence=1.0,
        )

    @staticmethod
    def _ground_service_record(record: ServiceRecord, case_id: str) -> Evidence:
        return Evidence(
            id=f"ev-service-{record.service_record_id}",
            case_id=case_id,
            key="previous_service_contact",
            value={
                "service_record_id": record.service_record_id,
                "consumer_id": record.consumer_id,
                "historical_case_id": record.case_id,
                "issue_type": record.issue_type,
                "contact_time": record.contact_time.isoformat(),
                "resolution_status": record.resolution_status,
                "summary": record.summary,
            },
            evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
            source=EvidenceSource(
                source_type=SourceType.SERVICE_SYSTEM,
                source_id=record.service_record_id,
                source_label=f"Service record {record.service_record_id}",
            ),
            observed_at=record.contact_time,
            created_at=datetime.now(UTC),
            extraction_confidence=1.0,
        )

    @staticmethod
    def _ground_consumer(record: ConsumerRecord, case_id: str) -> list[Evidence]:
        if not record.explicit_preferences:
            return []
        now = datetime.now(UTC)
        return [
            Evidence(
                id=f"ev-consumer-{record.consumer_id}-explicit-preferences",
                case_id=case_id,
                key="explicit_preferences",
                value=list(record.explicit_preferences),
                evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
                source=EvidenceSource(
                    source_type=SourceType.SERVICE_SYSTEM,
                    source_id=record.consumer_id,
                    source_label=f"Consumer record {record.consumer_id}",
                ),
                observed_at=now,
                created_at=now,
                extraction_confidence=1.0,
            )
        ]
