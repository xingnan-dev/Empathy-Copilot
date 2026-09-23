"""Stable API contracts for the frontend case projection."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class CaseView(BaseModel):
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
