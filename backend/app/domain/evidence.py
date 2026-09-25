"""Evidence and provenance models with deterministic consistency validation."""

from datetime import datetime
from enum import StrEnum
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class EvidenceType(StrEnum):
    VERIFIED_BUSINESS_FACT = "VERIFIED_BUSINESS_FACT"
    CONSUMER_REPORTED = "CONSUMER_REPORTED"
    AI_OBSERVATION = "AI_OBSERVATION"
    AI_INFERENCE = "AI_INFERENCE"
    UNKNOWN = "UNKNOWN"


class SourceType(StrEnum):
    ORDER_SYSTEM = "ORDER_SYSTEM"
    SERVICE_SYSTEM = "SERVICE_SYSTEM"
    CONSUMER_MESSAGE = "CONSUMER_MESSAGE"
    UPLOADED_IMAGE = "UPLOADED_IMAGE"
    PRODUCT_DATABASE = "PRODUCT_DATABASE"
    POLICY_DATABASE = "POLICY_DATABASE"
    AI_REASONING = "AI_REASONING"


ALLOWED_SOURCE_TYPES: dict[EvidenceType, frozenset[SourceType]] = {
    EvidenceType.VERIFIED_BUSINESS_FACT: frozenset(
        {
            SourceType.ORDER_SYSTEM,
            SourceType.SERVICE_SYSTEM,
            SourceType.PRODUCT_DATABASE,
            SourceType.POLICY_DATABASE,
        }
    ),
    EvidenceType.CONSUMER_REPORTED: frozenset(
        {SourceType.CONSUMER_MESSAGE, SourceType.SERVICE_SYSTEM}
    ),
    EvidenceType.AI_OBSERVATION: frozenset({SourceType.UPLOADED_IMAGE}),
    EvidenceType.AI_INFERENCE: frozenset({SourceType.AI_REASONING}),
    EvidenceType.UNKNOWN: frozenset(
        {
            SourceType.ORDER_SYSTEM,
            SourceType.SERVICE_SYSTEM,
            SourceType.CONSUMER_MESSAGE,
            SourceType.PRODUCT_DATABASE,
            SourceType.POLICY_DATABASE,
        }
    ),
}


class EvidenceSource(BaseModel):
    """Structured provenance identifying the exact system record or user artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: SourceType
    source_id: str = Field(min_length=1)
    source_label: str = Field(min_length=1)


class Evidence(BaseModel):
    """A sourced JSON-safe fact, report, observation, inference, or explicit unknown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    key: str = Field(min_length=1)
    value: JsonValue
    evidence_type: EvidenceType
    source: EvidenceSource
    observed_at: datetime
    created_at: datetime
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence_provenance(self) -> "Evidence":
        allowed = ALLOWED_SOURCE_TYPES[self.evidence_type]
        if self.source.source_type not in allowed:
            raise ValueError(
                f"{self.evidence_type.value} cannot use {self.source.source_type.value} provenance"
            )
        if not isfinite(self.extraction_confidence):
            raise ValueError("extraction_confidence must be finite")
        return self
