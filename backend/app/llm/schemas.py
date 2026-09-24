"""Typed, non-authoritative model outputs and call telemetry."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CandidateField(StrEnum):
    EXACT_PRODUCT_USED = "EXACT_PRODUCT_USED"
    ACTUAL_FIRST_USE_TIME = "ACTUAL_FIRST_USE_TIME"
    CONSUMER_CAUSALITY_CLAIM = "CONSUMER_CAUSALITY_CLAIM"


class Intent(StrEnum):
    ADVERSE_REACTION = "ADVERSE_REACTION"
    RETURN_REFUND = "RETURN_REFUND"
    LOGISTICS = "LOGISTICS"
    DAMAGED_OR_MISSING = "DAMAGED_OR_MISSING"
    PRODUCT_QUESTION = "PRODUCT_QUESTION"
    OTHER = "OTHER"


class Emotion(StrEnum):
    CALM = "CALM"
    CONCERNED = "CONCERNED"
    FRUSTRATED = "FRUSTRATED"
    ANGRY = "ANGRY"
    DISTRESSED = "DISTRESSED"
    UNKNOWN = "UNKNOWN"


class CandidateFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: CandidateField
    value: Any
    source_text: str = Field(min_length=1)


class UnderstandingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Intent = Intent.OTHER
    emotion: Emotion = Emotion.UNKNOWN
    candidate_facts: list[CandidateFact] = Field(default_factory=list)


class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ModelOutput(BaseModel):
    text: str | None = None
    understanding: UnderstandingResult | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)


class ModelCallRecord(BaseModel):
    operation: str
    provider: str
    model: str
    status: str
    latency_ms: int
    usage: TokenUsage
    error_category: str | None = None
    fallback_used: bool = False


class GeneratedDraft(BaseModel):
    text: str
    kind: str
    fallback_reason: str | None = None
