"""Stable API contracts for the frontend case projection."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.service_strategy import ServiceStrategy


class EvidenceView(BaseModel):
    id: str
    fact: str
    type: str
    source: str
    provenance: str
    timestamp: datetime


class GapView(BaseModel):
    id: str
    label: str
    why: str
    resolve: str
    status: str


class ActivityView(BaseModel):
    id: str
    label: str
    status: str
    technical: str


class HumanCheckpointView(BaseModel):
    state: Literal["REQUIRED", "APPROVED", "NOT_REQUIRED"]
    can_approve: bool


class ResponseContextView(BaseModel):
    evidence_used_ids: list[str]
    next_best_question: str | None = None
    question_resolves_gap: str | None = None


class ResponseDraftView(BaseModel):
    text: str
    kind: Literal["GENERATED", "FALLBACK"]
    fallback_reason: str | None = None


class ConsumerMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    message_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message is blank")
        return value

    @field_validator("message_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("invalid message id")
        return value


class MessageView(BaseModel):
    id: str
    case_id: str
    role: Literal["CONSUMER", "AGENT", "UNKNOWN"]
    text: str
    received_at: datetime | None = None
    sent_at: datetime | None = None
    sequence: int
    origin: Literal["LIVE", "OFFICIAL", "DEMO_FIXTURE"]
    content_type: Literal["TEXT", "IMAGE", "UNKNOWN"]
    evidence_ids: list[str] = Field(default_factory=list)


class MessageHistoryView(BaseModel):
    historical_source: Literal["OFFICIAL", "DEMO_FIXTURE", "UNAVAILABLE"] = "UNAVAILABLE"
    historical_complete: bool = False


class MessageReceipt(BaseModel):
    message_id: str
    sequence: int
    received_at: datetime
    accepted_revision: int
    evidence_ids: list[str]
    replayed: bool


class ResponseDraftRequest(BaseModel):
    expected_revision: int = Field(ge=0)


class CaseView(BaseModel):
    messages: list[MessageView] = Field(default_factory=list)
    message_history: MessageHistoryView = Field(default_factory=MessageHistoryView)
    message_receipt: MessageReceipt | None = None
    case_id: str
    consumer: str
    lifecycle: str
    current_action: str
    safety_path: str
    attribution_status: str
    evidence: list[EvidenceView]
    gaps: list[GapView]
    questions: list[dict[str, Any]]
    tool_activity: list[ActivityView]
    context_passport: dict[str, Any]
    human_checkpoint: HumanCheckpointView
    response_context: ResponseContextView
    updated_at: datetime
    revision: int
    scenario: str | None = None
    official_data: bool = False
    restored_context: bool = False
    previous_service_history: list[dict[str, Any]] = Field(default_factory=list)
    evidence_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    visual_observations: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_context: list[dict[str, Any]] = Field(default_factory=list)
    safety_gate: str = "NORMAL"
    ingredient_context: list[dict[str, Any]] = Field(default_factory=list)
    why_sources: list[dict[str, Any]] = Field(default_factory=list)
    service_strategy: ServiceStrategy


class HumanApprovalRequest(BaseModel):
    expected_revision: int = Field(ge=0)


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    gap: Literal[
        "ACTUAL_FIRST_USE_TIME",
        "FEEDBACK_ONSET_TIME",
        "RECENT_REGIMEN_CHANGES",
        "REPORTED_SEVERITY",
    ]
    value: Any
    source_id: str = Field(min_length=1)


class ErrorView(BaseModel):
    code: str
    message: str
