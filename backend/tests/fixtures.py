"""Golden Demo structured fixtures; no extraction or LLM is involved."""

from datetime import UTC, datetime

from backend.app.domain.agent import InvestigationState
from backend.app.domain.evidence import Evidence, EvidenceSource, EvidenceType, SourceType
from backend.app.domain.gaps import evaluate_p0_gaps

CASE_ID = "case_c_serum_001"
CONSUMER_ID = "consumer_001"
NOW = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)


def message_evidence(
    evidence_id: str,
    message_id: str,
    key: str,
    value: object,
    *,
    case_id: str = CASE_ID,
    evidence_type: EvidenceType = EvidenceType.CONSUMER_REPORTED,
    source_type: SourceType = SourceType.CONSUMER_MESSAGE,
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
                "source_id": message_id,
                "source_label": f"Source #{message_id}",
            },
            "observed_at": NOW,
            "created_at": NOW,
            "extraction_confidence": 1.0,
        }
    )


def order_evidence() -> Evidence:
    return Evidence(
        id="ev_order_a1024_first_purchase",
        case_id=CASE_ID,
        key="first_purchase",
        value={"product_id": "c_serum", "product_name": "C Serum", "first_purchase": True},
        evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
        source=EvidenceSource(
            source_type=SourceType.ORDER_SYSTEM,
            source_id="A1024",
            source_label="Order #A1024",
        ),
        observed_at=NOW,
        created_at=NOW,
        extraction_confidence=1.0,
    )


def first_use_evidence() -> Evidence:
    return message_evidence(
        "ev_m102_first_use",
        "M102",
        "actual_first_use_time",
        {
            "product_id": "c_serum",
            "product_name": "C Serum",
            "first_use_at": "2026-09-12",
        },
    )


def d_cream_change_evidence(*, with_date: bool = False) -> Evidence:
    value: dict[str, object] = {
        "product_id": "d_cream",
        "product_name": "D Cream",
        "change_type": "NEW",
    }
    if with_date:
        value["effective_at"] = "2026-09-12"
    return message_evidence(
        "ev_m104_d_cream_dated" if with_date else "ev_m104_d_cream",
        "M105" if with_date else "M104",
        "recent_regimen_changes",
        value,
    )


def feedback_onset_evidence() -> Evidence:
    return message_evidence(
        "ev_m106_onset",
        "M106",
        "feedback_onset_time",
        {"onset_at": "2026-09-13"},
    )


def severity_evidence() -> Evidence:
    return message_evidence(
        "ev_m107_severity",
        "M107",
        "reported_severity",
        "MILD",
    )


def initial_state() -> InvestigationState:
    evidence = [order_evidence()]
    return InvestigationState(
        case_id=CASE_ID,
        consumer_id=CONSUMER_ID,
        current_issue="我刚买的 C 精华用了以后感觉有点不舒服。",
        evidence=evidence,
        evidence_gaps=evaluate_p0_gaps(CASE_ID, evidence),
        created_at=NOW,
        updated_at=NOW,
    )


def fully_resolved_state(*, dated_d_change: bool = True) -> InvestigationState:
    evidence = [
        order_evidence(),
        first_use_evidence(),
        d_cream_change_evidence(with_date=dated_d_change),
        feedback_onset_evidence(),
        severity_evidence(),
    ]
    return InvestigationState(
        case_id=CASE_ID,
        consumer_id=CONSUMER_ID,
        current_issue="我刚买的 C 精华用了以后感觉有点不舒服。",
        evidence=evidence,
        evidence_gaps=evaluate_p0_gaps(CASE_ID, evidence),
        created_at=NOW,
        updated_at=NOW,
    )

