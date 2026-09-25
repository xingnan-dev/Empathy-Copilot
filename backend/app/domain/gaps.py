"""Deterministic, evidence-type-aware P0 gap policies."""

from collections.abc import Callable
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

from .evidence import Evidence, EvidenceType, SourceType
from .scenarios import InvestigationScenario


class GapType(StrEnum):
    EXACT_PRODUCT_USED = "EXACT_PRODUCT_USED"
    ACTUAL_FIRST_USE_TIME = "ACTUAL_FIRST_USE_TIME"
    FEEDBACK_ONSET_TIME = "FEEDBACK_ONSET_TIME"
    RECENT_REGIMEN_CHANGES = "RECENT_REGIMEN_CHANGES"
    REPORTED_SEVERITY = "REPORTED_SEVERITY"
    USAGE_SEQUENCE = "USAGE_SEQUENCE"
    KNOWN_SENSITIVITY_RECORD = "KNOWN_SENSITIVITY_RECORD"
    VISUAL_EVIDENCE = "VISUAL_EVIDENCE"
    SERVICE_HISTORY = "SERVICE_HISTORY"
    CURRENT_SYMPTOM_STATUS = "CURRENT_SYMPTOM_STATUS"
    MEDICAL_ATTENTION_STATUS = "MEDICAL_ATTENTION_STATUS"
    AFFECTED_ITEM = "AFFECTED_ITEM"
    DAMAGE_DESCRIPTION = "DAMAGE_DESCRIPTION"
    ORDER_MATCH = "ORDER_MATCH"
    REPLACEMENT_ELIGIBILITY = "REPLACEMENT_ELIGIBILITY"
    LOGISTICS_STATUS = "LOGISTICS_STATUS"
    CONSUMER_RECEIPT_STATUS = "CONSUMER_RECEIPT_STATUS"
    DELIVERY_EVIDENCE = "DELIVERY_EVIDENCE"
    INVESTIGATION_RESULT = "INVESTIGATION_RESULT"
    RESOLUTION_STATUS = "RESOLUTION_STATUS"
    REQUEST_TYPE = "REQUEST_TYPE"
    AFTER_SALES_STATUS = "AFTER_SALES_STATUS"
    ELIGIBILITY = "ELIGIBILITY"
    REQUIRED_EVIDENCE = "REQUIRED_EVIDENCE"
    RESOLUTION_PATH = "RESOLUTION_PATH"


class GapStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReportedSeverity(StrEnum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    UNKNOWN = "UNKNOWN"


class EvidenceGap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gap_type: GapType
    status: GapStatus
    required: bool = True
    resolved_by_evidence_ids: list[str] = Field(default_factory=list)


class FirstUseValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    first_use_at: date | datetime


class FeedbackOnsetValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onset_at: date | datetime


class RegimenChangeValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    change_type: str = Field(pattern="^(NEW|REPLACED|STOPPED)$")
    effective_at: date | datetime | None = None


FIRST_USE_ADAPTER = TypeAdapter(FirstUseValue)
FEEDBACK_ONSET_ADAPTER = TypeAdapter(FeedbackOnsetValue)
REGIMEN_CHANGE_ADAPTER = TypeAdapter(RegimenChangeValue)
SEVERITY_ADAPTER = TypeAdapter(ReportedSeverity)


def _valid_payload(adapter: TypeAdapter[Any], value: JsonValue) -> bool:
    try:
        adapter.validate_python(value)
    except ValidationError:
        return False
    return True


def _consumer_message(item: Evidence) -> bool:
    return (
        item.evidence_type is EvidenceType.CONSUMER_REPORTED
        and item.source.source_type is SourceType.CONSUMER_MESSAGE
    )


def _valid_first_use(item: Evidence) -> bool:
    return (
        item.key == "actual_first_use_time"
        and _consumer_message(item)
        and _valid_payload(FIRST_USE_ADAPTER, item.value)
    )


def _valid_feedback_onset(item: Evidence) -> bool:
    return (
        item.key == "feedback_onset_time"
        and _consumer_message(item)
        and _valid_payload(FEEDBACK_ONSET_ADAPTER, item.value)
    )


def _valid_regimen_change(item: Evidence) -> bool:
    return (
        item.key == "recent_regimen_changes"
        and _consumer_message(item)
        and _valid_payload(REGIMEN_CHANGE_ADAPTER, item.value)
    )


def _valid_severity(item: Evidence) -> bool:
    return (
        item.key == "reported_severity"
        and _consumer_message(item)
        and _valid_payload(SEVERITY_ADAPTER, item.value)
    )


P0_RESOLUTION_POLICIES: dict[GapType, Callable[[Evidence], bool]] = {
    GapType.ACTUAL_FIRST_USE_TIME: _valid_first_use,
    GapType.FEEDBACK_ONSET_TIME: _valid_feedback_onset,
    GapType.RECENT_REGIMEN_CHANGES: _valid_regimen_change,
    GapType.REPORTED_SEVERITY: _valid_severity,
}


def evaluate_p0_gaps(case_id: str, evidence: list[Evidence]) -> list[EvidenceGap]:
    """Evaluate all P0 gaps from valid, same-case evidence using fixed policies."""

    gaps: list[EvidenceGap] = []
    for gap_type, policy in P0_RESOLUTION_POLICIES.items():
        matches = [item.id for item in evidence if item.case_id == case_id and policy(item)]
        gaps.append(
            EvidenceGap(
                gap_type=gap_type,
                status=GapStatus.RESOLVED if matches else GapStatus.OPEN,
                resolved_by_evidence_ids=matches,
            )
        )
    return gaps


SCENARIO_GAPS: dict[InvestigationScenario, tuple[GapType, ...]] = {
    InvestigationScenario.ADVERSE_REACTION: (
        GapType.EXACT_PRODUCT_USED,
        GapType.ACTUAL_FIRST_USE_TIME,
        GapType.FEEDBACK_ONSET_TIME,
        GapType.RECENT_REGIMEN_CHANGES,
        GapType.REPORTED_SEVERITY,
        GapType.CURRENT_SYMPTOM_STATUS,
        GapType.MEDICAL_ATTENTION_STATUS,
    ),
    InvestigationScenario.PRODUCT_DAMAGE: (
        GapType.AFFECTED_ITEM,
        GapType.DAMAGE_DESCRIPTION,
        GapType.VISUAL_EVIDENCE,
        GapType.ORDER_MATCH,
        GapType.REPLACEMENT_ELIGIBILITY,
    ),
    InvestigationScenario.LOGISTICS_EXCEPTION: (
        GapType.ORDER_MATCH,
        GapType.LOGISTICS_STATUS,
        GapType.CONSUMER_RECEIPT_STATUS,
        GapType.DELIVERY_EVIDENCE,
        GapType.INVESTIGATION_RESULT,
        GapType.RESOLUTION_STATUS,
    ),
    InvestigationScenario.AFTER_SALES: (
        GapType.ORDER_MATCH,
        GapType.REQUEST_TYPE,
        GapType.AFTER_SALES_STATUS,
        GapType.ELIGIBILITY,
        GapType.REQUIRED_EVIDENCE,
        GapType.RESOLUTION_PATH,
    ),
}


GAP_EVIDENCE_KEYS: dict[GapType, frozenset[str]] = {
    GapType.EXACT_PRODUCT_USED: frozenset({"exact_product_used"}),
    GapType.ACTUAL_FIRST_USE_TIME: frozenset({"actual_first_use_time"}),
    GapType.FEEDBACK_ONSET_TIME: frozenset({"feedback_onset_time"}),
    GapType.RECENT_REGIMEN_CHANGES: frozenset({"recent_regimen_changes"}),
    GapType.REPORTED_SEVERITY: frozenset({"reported_severity"}),
    GapType.CURRENT_SYMPTOM_STATUS: frozenset({"current_symptom_status"}),
    GapType.MEDICAL_ATTENTION_STATUS: frozenset({"reported_medical_attention"}),
    GapType.AFFECTED_ITEM: frozenset({"affected_item"}),
    GapType.DAMAGE_DESCRIPTION: frozenset({"damage_description"}),
    GapType.VISUAL_EVIDENCE: frozenset({"image_evidence_available"}),
    GapType.ORDER_MATCH: frozenset({"order_match"}),
    GapType.REPLACEMENT_ELIGIBILITY: frozenset({"replacement_eligibility"}),
    GapType.LOGISTICS_STATUS: frozenset({"logistics_status"}),
    GapType.CONSUMER_RECEIPT_STATUS: frozenset({"consumer_receipt_status"}),
    GapType.DELIVERY_EVIDENCE: frozenset({"delivery_evidence"}),
    GapType.INVESTIGATION_RESULT: frozenset({"logistics_investigation_result"}),
    GapType.RESOLUTION_STATUS: frozenset({"resolution_status"}),
    GapType.REQUEST_TYPE: frozenset({"after_sales_request_type"}),
    GapType.AFTER_SALES_STATUS: frozenset({"after_sales_status"}),
    GapType.ELIGIBILITY: frozenset({"after_sales_eligibility"}),
    GapType.REQUIRED_EVIDENCE: frozenset({"required_evidence"}),
    GapType.RESOLUTION_PATH: frozenset({"resolution_path"}),
}


def evaluate_scenario_gaps(
    case_id: str,
    scenario: InvestigationScenario,
    evidence: list[Evidence],
) -> list[EvidenceGap]:
    """Resolve only the required gaps for a structured scenario from grounded Evidence."""

    gaps = []
    for gap_type in SCENARIO_GAPS[scenario]:
        if gap_type in P0_RESOLUTION_POLICIES:
            policy = P0_RESOLUTION_POLICIES[gap_type]
            matches = [item.id for item in evidence if item.case_id == case_id and policy(item)]
        else:
            keys = GAP_EVIDENCE_KEYS[gap_type]
            matches = [
                item.id
                for item in evidence
                if item.case_id == case_id
                and item.key in keys
                and item.evidence_type is not EvidenceType.UNKNOWN
            ]
        gaps.append(
            EvidenceGap(
                gap_type=gap_type,
                status=GapStatus.RESOLVED if matches else GapStatus.OPEN,
                resolved_by_evidence_ids=matches,
            )
        )
    return gaps
