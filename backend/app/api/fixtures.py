"""Backend-owned Phase 5 integration fixture for the accepted S00154 scenario."""

from datetime import UTC, datetime

from backend.app.domain.agent import AgentAction, AgentStatus, InvestigationState
from backend.app.domain.evidence import Evidence, EvidenceType, SourceType
from backend.app.domain.gaps import evaluate_p0_gaps
from backend.app.services.transitions import StateTransitionService

NOW = datetime(2026, 5, 11, 16, 49, tzinfo=UTC)


def _evidence(
    evidence_id: str,
    key: str,
    value: object,
    evidence_type: EvidenceType,
    source_type: SourceType,
    source_id: str,
    label: str,
    observed_at: datetime = NOW,
) -> Evidence:
    return Evidence.model_validate(
        {
            "id": evidence_id,
            "case_id": "S00154",
            "key": key,
            "value": value,
            "evidence_type": evidence_type,
            "source": {
                "source_type": source_type,
                "source_id": source_id,
                "source_label": label,
            },
            "observed_at": observed_at,
            "created_at": observed_at,
            "extraction_confidence": 1.0,
        }
    )


def s00154_waiting_for_human() -> InvestigationState:
    report_time = datetime(2026, 5, 11, 16, 20, tzinfo=UTC)
    evidence = [
        _evidence(
            "consumer-swelling",
            "reported_facial_swelling",
            "Consumer reports facial swelling after cream use",
            EvidenceType.CONSUMER_REPORTED,
            SourceType.CONSUMER_MESSAGE,
            "94422222481506.PNM",
            "Consumer message · S00154",
            report_time,
        ),
        _evidence(
            "consumer-medical-attention",
            "reported_medical_attention",
            "Consumer reports medical attention",
            EvidenceType.CONSUMER_REPORTED,
            SourceType.CONSUMER_MESSAGE,
            "94422222481506.PNM",
            "Consumer message · S00154",
            report_time,
        ),
        _evidence(
            "order-purchase",
            "first_purchase",
            {
                "consumer_id": "蒋a**",
                "order_id": "6920073444593979097",
                "product_id": "firming_gift_set",
                "product_name": "Firming Gift Set",
                "paid": "¥1,398",
                "first_purchase": True,
            },
            EvidenceType.VERIFIED_BUSINESS_FACT,
            SourceType.ORDER_SYSTEM,
            "6920073444593979097",
            "Order system",
            datetime(2026, 4, 27, 7, 24, tzinfo=UTC),
        ),
        _evidence(
            "service-ticket",
            "previous_service_contact",
            {
                "consumer_id": "蒋a**",
                "ticket_id": "BLFY27898314",
                "summary": "Adverse-reaction service case exists",
            },
            EvidenceType.VERIFIED_BUSINESS_FACT,
            SourceType.SERVICE_SYSTEM,
            "BLFY27898314",
            "Service record",
        ),
        _evidence(
            "uploaded-material",
            "uploaded_medical_material",
            "Medical material uploaded; contents not medically verified",
            EvidenceType.AI_OBSERVATION,
            SourceType.UPLOADED_IMAGE,
            "25581855302692.PNM",
            "Uploaded image",
            datetime(2026, 5, 11, 16, 21, tzinfo=UTC),
        ),
        _evidence(
            "human-review-required",
            "human_review_required",
            True,
            EvidenceType.VERIFIED_BUSINESS_FACT,
            SourceType.SERVICE_SYSTEM,
            "adverse-reaction-policy",
            "Adverse-reaction policy",
        ),
    ]
    initial = InvestigationState(
        case_id="S00154",
        consumer_id="蒋a**",
        current_issue="Consumer reports facial swelling and medical attention.",
        evidence=evidence,
        evidence_gaps=evaluate_p0_gaps("S00154", evidence),
        created_at=NOW,
        updated_at=NOW,
    )
    return StateTransitionService().transition(
        initial,
        to_status=AgentStatus.WAITING_FOR_HUMAN,
        action=AgentAction.WAIT_FOR_HUMAN,
        reason="Reported facial swelling and medical attention require human-reviewed escalation.",
    )
