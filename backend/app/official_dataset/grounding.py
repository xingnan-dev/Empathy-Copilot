"""Ground normalized official records without leaking Excel columns into the domain."""

import re
from datetime import UTC, datetime
from typing import Any

from backend.app.domain.evidence import Evidence, EvidenceType, SourceType
from backend.app.domain.scenarios import InvestigationScenario

from .models import MessageRecord, OfficialDataset, OfficialOrderRecord, OfficialServiceRecord

EXPLICIT_USE_PATTERN = re.compile(r"(?:使用了?|用了|用过|涂了|擦了)")
USE_CLAUSE_END_PATTERN = re.compile(
    r"[，,。！!？?；;]|之后|以后|后|整张|全脸|脸上|面部|眼周|出现|开始|感觉|觉得|发红|红肿|刺痛|肿|痒|不适"
)
BEAUTY_PRODUCT_LABELS = (
    "护发精油",
    "粉底液",
    "洁面乳",
    "洗面奶",
    "爽肤水",
    "精华液",
    "防晒霜",
    "面霜",
    "眼霜",
    "乳液",
    "面膜",
    "精华",
    "唇釉",
    "口红",
)


class OfficialEvidenceGroundingService:
    def ground_case(
        self,
        dataset: OfficialDataset,
        session_id: str,
        *,
        message_sequence_cutoff: int | None = None,
    ) -> list[Evidence]:
        session = dataset.session(session_id)
        session_messages = sorted(
            (item for item in dataset.messages if item.session_id == session_id),
            key=lambda item: item.sequence,
        )
        if message_sequence_cutoff is not None:
            if message_sequence_cutoff < 1:
                raise ValueError("message_sequence_cutoff must be positive")
            messages = [
                item for item in session_messages if item.sequence <= message_sequence_cutoff
            ]
            if not messages:
                raise ValueError(
                    f"message_sequence_cutoff precedes all messages for session {session_id}"
                )
            as_of = messages[-1].sent_at
        else:
            messages = session_messages
            as_of = None
        orders = [
            item
            for item in dataset.orders
            if item.session_id == session_id and (as_of is None or item.ordered_at <= as_of)
        ]
        records = [
            item
            for item in dataset.service_records
            if item.session_id == session_id and self._available_as_of(item, as_of)
        ]
        evidence: list[Evidence | list[Evidence]] = [
            self._order_match(item, session_id) for item in orders
        ]
        evidence.extend(
            self._message(item, session.scenario) for item in messages if item.role == "买家"
        )
        evidence.extend(self._image_metadata(item) for item in messages if item.image_path)
        evidence.extend(self._service(item, session.scenario) for item in records)
        previous = [
            item
            for item in dataset.service_records
            if item.consumer_id == session.consumer_id and item.session_id != session_id
            and self._available_as_of(item, as_of)
        ]
        evidence.extend(self._previous_service(item, session_id) for item in previous)
        grounded = [
            item for group in evidence for item in (group if isinstance(group, list) else [group])
        ]
        if message_sequence_cutoff is None:
            return grounded
        assert as_of is not None
        return [
            item.model_copy(
                update={
                    "metadata": {
                        **item.metadata,
                        "official_message_sequence_cutoff": message_sequence_cutoff,
                        "official_as_of": as_of.isoformat(),
                    }
                }
            )
            for item in grounded
        ]

    @staticmethod
    def _available_as_of(record: OfficialServiceRecord, as_of: datetime | None) -> bool:
        if as_of is None:
            return True
        return record.created_at <= as_of and (
            record.completed_at is None or record.completed_at <= as_of
        )

    @staticmethod
    def _base(
        *,
        evidence_id: str,
        case_id: str,
        key: str,
        value: Any,
        evidence_type: EvidenceType,
        source_type: SourceType,
        source_id: str,
        source_label: str,
        observed_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> Evidence:
        return Evidence.model_validate(
            {
                "id": evidence_id,
                "case_id": case_id,
                "key": key,
                "value": value,
                "evidence_type": evidence_type,
                "source": {
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_label": source_label,
                },
                "observed_at": observed_at,
                "created_at": datetime.now(UTC),
                "extraction_confidence": 1.0,
                "metadata": {
                    "grounding_method": "OFFICIAL_DATASET_DETERMINISTIC",
                    "official_data": True,
                    **(metadata or {}),
                },
            }
        )

    def _order_match(self, record: OfficialOrderRecord, case_id: str) -> list[Evidence]:
        common = {
            "order_id": record.order_id,
            "consumer_id": record.consumer_id,
            "product_id": record.product_id,
            "product_name": record.product_name,
            "quantity": record.quantity,
            "order_status": record.order_status,
            "ordered_at": record.ordered_at.isoformat(),
            "tracking_number": record.tracking_number,
        }
        source: dict[str, Any] = dict(
            evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
            source_type=SourceType.ORDER_SYSTEM,
            source_id=record.order_id,
            source_label=f"Official order {record.order_id}",
            observed_at=record.ordered_at,
        )
        return [
            self._base(
                evidence_id=f"official-order-match-{record.order_id}",
                case_id=case_id,
                key="order_match",
                value=common,
                **source,
            ),
            self._base(
                evidence_id=f"official-purchase-{record.order_id}",
                case_id=case_id,
                key="first_purchase",
                value={**common, "first_purchase": True},
                **source,
            ),
        ]

    def _message(
        self, record: MessageRecord, scenario: InvestigationScenario | None
    ) -> list[Evidence]:
        base: dict[str, Any] = dict(
            case_id=record.session_id,
            evidence_type=EvidenceType.CONSUMER_REPORTED,
            source_type=SourceType.CONSUMER_MESSAGE,
            source_id=record.message_id,
            source_label=f"Official consumer message {record.message_id}",
            observed_at=record.sent_at,
            metadata={"supporting_excerpt": record.text},
        )
        items = [
            self._base(
                evidence_id=f"official-message-{record.message_id}",
                key="consumer_message",
                value=record.text,
                **base,
            )
        ]
        text = record.text
        if scenario is InvestigationScenario.ADVERSE_REACTION:
            for index, product_label in enumerate(self._explicitly_used_products(text), start=1):
                usage_base = dict(base)
                usage_base["metadata"] = {
                    "supporting_excerpt": record.text,
                    "extracted_label": product_label,
                }
                items.append(
                    self._base(
                        evidence_id=f"official-product-used-{record.message_id}-{index}",
                        key="exact_product_used",
                        value=product_label,
                        **usage_base,
                    )
                )
            if any(term in text for term in ("肿", "红肿", "刺痛", "不适")):
                items.append(
                    self._base(
                        evidence_id=f"official-severity-{record.message_id}",
                        key="reported_severity",
                        value="SEVERE",
                        **base,
                    )
                )
            if any(term in text for term in ("医院", "就医", "皮肤科")):
                items.append(
                    self._base(
                        evidence_id=f"official-medical-{record.message_id}",
                        key="reported_medical_attention",
                        value=True,
                        **base,
                    )
                )
        elif scenario is InvestigationScenario.PRODUCT_DAMAGE:
            if any(term in text for term in ("坏", "破损", "按不出来")):
                items.append(
                    self._base(
                        evidence_id=f"official-damage-{record.message_id}",
                        key="damage_description",
                        value=text,
                        **base,
                    )
                )
                items.append(
                    self._base(
                        evidence_id=f"official-item-{record.message_id}",
                        key="affected_item",
                        value="粉底液泵头",
                        **base,
                    )
                )
        elif scenario is InvestigationScenario.LOGISTICS_EXCEPTION:
            if "没收到" in text:
                items.append(
                    self._base(
                        evidence_id=f"official-receipt-no-{record.message_id}",
                        key="consumer_receipt_status",
                        value="NOT_RECEIVED",
                        **base,
                    )
                )
            if "收到了" in text:
                items.append(
                    self._base(
                        evidence_id=f"official-receipt-yes-{record.message_id}",
                        key="consumer_receipt_status",
                        value="RECEIVED",
                        **base,
                    )
                )
        elif scenario is InvestigationScenario.AFTER_SALES:
            if any(term in text for term in ("退款", "报销", "退货")):
                items.append(
                    self._base(
                        evidence_id=f"official-request-{record.message_id}",
                        key="after_sales_request_type",
                        value=text,
                        **base,
                    )
                )
        return items

    @staticmethod
    def _explicitly_used_products(text: str) -> list[str]:
        """Return only beauty product labels inside an explicit consumer usage clause."""

        match = EXPLICIT_USE_PATTERN.search(text)
        if match is None:
            return []
        usage_clause = text[match.end() :]
        clause_end = USE_CLAUSE_END_PATTERN.search(usage_clause)
        if clause_end is not None:
            usage_clause = usage_clause[: clause_end.start()]
        matches = [label for label in BEAUTY_PRODUCT_LABELS if label in usage_clause]
        return [
            label
            for label in matches
            if not any(label != other and label in other for other in matches)
        ]

    def _image_metadata(self, record: MessageRecord) -> Evidence:
        return self._base(
            evidence_id=f"official-image-{record.message_id}",
            case_id=record.session_id,
            key="image_reference",
            value={
                "reference_exists": True,
                "asset_available": False,
                "path": record.image_path,
            },
            evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
            source_type=SourceType.SERVICE_SYSTEM,
            source_id=record.message_id,
            source_label=f"Official message metadata {record.message_id}",
            observed_at=record.sent_at,
            metadata={"supporting_field": "image_path", "vision_analyzed": False},
        )

    def _service(
        self, record: OfficialServiceRecord, scenario: InvestigationScenario | None
    ) -> list[Evidence]:
        base: dict[str, Any] = dict(
            case_id=record.session_id,
            evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
            source_type=SourceType.SERVICE_SYSTEM,
            source_id=record.service_record_id,
            source_label=f"Official service record {record.service_record_id}",
            observed_at=record.created_at,
            metadata={"source_kind": record.source_kind},
        )
        items = [
            self._base(
                evidence_id=f"official-service-status-{record.service_record_id}",
                key="resolution_status",
                value=record.status,
                **base,
            )
        ]
        if scenario is InvestigationScenario.ADVERSE_REACTION:
            reported: dict[str, Any] = dict(base)
            reported["evidence_type"] = EvidenceType.CONSUMER_REPORTED
            if record.details.get("症状描述"):
                items.append(
                    self._base(
                        evidence_id=f"official-reported-symptom-{record.service_record_id}",
                        key="reported_symptom",
                        value=record.details["症状描述"],
                        metadata={
                            "source_kind": record.source_kind,
                            "supporting_field": "症状描述",
                        },
                        **{key: value for key, value in reported.items() if key != "metadata"},
                    )
                )
            if record.details.get("是否就医"):
                items.append(
                    self._base(
                        evidence_id=f"official-reported-medical-{record.service_record_id}",
                        key="reported_medical_attention",
                        value=record.details["是否就医"] == "是",
                        metadata={
                            "source_kind": record.source_kind,
                            "supporting_field": "是否就医",
                        },
                        **{key: value for key, value in reported.items() if key != "metadata"},
                    )
                )
        elif scenario is InvestigationScenario.PRODUCT_DAMAGE:
            items.append(
                self._base(
                    evidence_id=f"official-replacement-{record.service_record_id}",
                    key="replacement_eligibility",
                    value={"eligible": True, "status": record.status},
                    **base,
                )
            )
        elif scenario is InvestigationScenario.LOGISTICS_EXCEPTION:
            items.extend(
                [
                    self._base(
                        evidence_id=f"official-logistics-{record.service_record_id}",
                        key="logistics_status",
                        value="SYSTEM_MARKED_DELIVERED",
                        **base,
                    ),
                    self._base(
                        evidence_id=f"official-investigation-{record.service_record_id}",
                        key="logistics_investigation_result",
                        value=record.details.get("处理方案") or record.issue_type,
                        **base,
                    ),
                    self._base(
                        evidence_id=f"official-delivery-{record.service_record_id}",
                        key="delivery_evidence",
                        value={"ticket_status": record.status},
                        **base,
                    ),
                ]
            )
        elif scenario is InvestigationScenario.AFTER_SALES:
            items.extend(
                [
                    self._base(
                        evidence_id=f"official-after-status-{record.service_record_id}",
                        key="after_sales_status",
                        value=record.status,
                        **base,
                    ),
                    self._base(
                        evidence_id=f"official-eligibility-{record.service_record_id}",
                        key="after_sales_eligibility",
                        value={"recorded": True},
                        **base,
                    ),
                    self._base(
                        evidence_id=f"official-required-{record.service_record_id}",
                        key="required_evidence",
                        value={"ticket_id": record.service_record_id},
                        **base,
                    ),
                    self._base(
                        evidence_id=f"official-path-{record.service_record_id}",
                        key="resolution_path",
                        value=record.issue_type,
                        **base,
                    ),
                ]
            )
        return items

    def _previous_service(self, record: OfficialServiceRecord, case_id: str) -> Evidence:
        return self._base(
            evidence_id=f"official-history-{case_id}-{record.service_record_id}",
            case_id=case_id,
            key="previous_service_contact",
            value={
                "service_record_id": record.service_record_id,
                "consumer_id": record.consumer_id,
                "historical_case_id": record.session_id,
                "issue_type": record.issue_type,
                "resolution_status": record.status,
                "contact_time": record.created_at.isoformat(),
            },
            evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
            source_type=SourceType.SERVICE_SYSTEM,
            source_id=record.service_record_id,
            source_label=f"Previous official service {record.service_record_id}",
            observed_at=record.created_at,
        )
