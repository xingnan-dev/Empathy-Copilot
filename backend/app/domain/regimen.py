"""Evidence-backed beauty regimen changes."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .evidence import Evidence, EvidenceType, SourceType
from .gaps import FIRST_USE_ADAPTER, REGIMEN_CHANGE_ADAPTER


class ChangeType(StrEnum):
    NEW = "NEW"
    REPLACED = "REPLACED"
    STOPPED = "STOPPED"
    STABLE = "STABLE"


class RegimenChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    change_type: ChangeType
    effective_at: date | datetime | None = None
    source_evidence_ids: list[str] = Field(min_length=1)


def build_regimen_changes(case_id: str, evidence: list[Evidence]) -> list[RegimenChange]:
    """Build changes only from explicit, same-case consumer usage reports."""

    changes: list[RegimenChange] = []
    for item in evidence:
        if (
            item.case_id != case_id
            or item.evidence_type is not EvidenceType.CONSUMER_REPORTED
            or item.source.source_type is not SourceType.CONSUMER_MESSAGE
        ):
            continue
        try:
            if item.key == "actual_first_use_time":
                first_use = FIRST_USE_ADAPTER.validate_python(item.value)
                changes.append(
                    RegimenChange(
                        product_id=first_use.product_id,
                        product_name=first_use.product_name,
                        change_type=ChangeType.NEW,
                        effective_at=first_use.first_use_at,
                        source_evidence_ids=[item.id],
                    )
                )
            elif item.key == "recent_regimen_changes":
                regimen_change = REGIMEN_CHANGE_ADAPTER.validate_python(item.value)
                changes.append(
                    RegimenChange(
                        product_id=regimen_change.product_id,
                        product_name=regimen_change.product_name,
                        change_type=ChangeType(regimen_change.change_type),
                        effective_at=regimen_change.effective_at,
                        source_evidence_ids=[item.id],
                    )
                )
        except ValidationError:
            continue
    return changes
