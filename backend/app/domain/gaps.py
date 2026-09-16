"""Deterministic, evidence-type-aware P0 gap policies."""

from collections.abc import Callable
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

from .evidence import Evidence, EvidenceType, SourceType


class GapType(StrEnum):
    ACTUAL_FIRST_USE_TIME = "ACTUAL_FIRST_USE_TIME"
    FEEDBACK_ONSET_TIME = "FEEDBACK_ONSET_TIME"
    RECENT_REGIMEN_CHANGES = "RECENT_REGIMEN_CHANGES"
    REPORTED_SEVERITY = "REPORTED_SEVERITY"
    USAGE_SEQUENCE = "USAGE_SEQUENCE"
    KNOWN_SENSITIVITY_RECORD = "KNOWN_SENSITIVITY_RECORD"
    VISUAL_EVIDENCE = "VISUAL_EVIDENCE"
    SERVICE_HISTORY = "SERVICE_HISTORY"


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
    return item.key == "actual_first_use_time" and _consumer_message(item) and _valid_payload(
        FIRST_USE_ADAPTER, item.value
    )


def _valid_feedback_onset(item: Evidence) -> bool:
    return item.key == "feedback_onset_time" and _consumer_message(item) and _valid_payload(
        FEEDBACK_ONSET_ADAPTER, item.value
    )


def _valid_regimen_change(item: Evidence) -> bool:
    return item.key == "recent_regimen_changes" and _consumer_message(item) and _valid_payload(
        REGIMEN_CHANGE_ADAPTER, item.value
    )


def _valid_severity(item: Evidence) -> bool:
    return item.key == "reported_severity" and _consumer_message(item) and _valid_payload(
        SEVERITY_ADAPTER, item.value
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
