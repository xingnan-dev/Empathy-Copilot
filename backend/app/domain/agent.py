"""Agent actions, lifecycle records, and checkpoint-safe investigation state."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from .business import ConsumerMemorySnapshot
from .evidence import Evidence
from .gaps import EvidenceGap, GapType
from .scenarios import InvestigationScenario


class AgentAction(StrEnum):
    ASK_USER = "ASK_USER"
    CALL_TOOL = "CALL_TOOL"
    RETRIEVE_POLICY = "RETRIEVE_POLICY"
    ESCALATE = "ESCALATE"
    CONCLUDE = "CONCLUDE"
    WAIT_FOR_HUMAN = "WAIT_FOR_HUMAN"


class AgentStatus(StrEnum):
    INVESTIGATING = "INVESTIGATING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    READY_FOR_ACTION = "READY_FOR_ACTION"
    ESCALATED = "ESCALATED"
    CONCLUDED = "CONCLUDED"
    TERMINATED = "TERMINATED"


class QuestionStatus(StrEnum):
    PENDING = "PENDING"
    ASKED = "ASKED"
    ANSWERED = "ANSWERED"


class AskedQuestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    gap_type: GapType
    text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    status: QuestionStatus
    asked_at: datetime | None = None
    answered_by_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "AskedQuestion":
        if self.status is QuestionStatus.PENDING and self.asked_at is not None:
            raise ValueError("PENDING question cannot have asked_at")
        if self.status in {QuestionStatus.ASKED, QuestionStatus.ANSWERED} and self.asked_at is None:
            raise ValueError("sent question requires asked_at")
        if self.status is QuestionStatus.ANSWERED and not self.answered_by_evidence_ids:
            raise ValueError("ANSWERED question requires answering evidence")
        if self.status is not QuestionStatus.ANSWERED and self.answered_by_evidence_ids:
            raise ValueError("only ANSWERED questions can link answering evidence")
        return self


class ToolCallStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ToolFailureKind(StrEnum):
    RETRYABLE = "RETRYABLE"
    NON_RETRYABLE = "NON_RETRYABLE"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"


class ContinuationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SETTLED = "SETTLED"
    INTERRUPTED = "INTERRUPTED"


class HumanReviewBlock(StrEnum):
    TOOL_RECOVERY = "TOOL_RECOVERY"
    SAFETY = "SAFETY"
    BUSINESS_REVIEW = "BUSINESS_REVIEW"
    QUESTION_LIMIT = "QUESTION_LIMIT"
    OTHER = "OTHER"


class ToolRecoveryRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: UUID
    target_attempt_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0, strict=True)
    operator_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=1000)
    previous_process_exited: bool = Field(strict=True)

    @field_validator("target_attempt_id", "operator_id", "reason")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank recovery fields are not allowed")
        return value


class ToolRecoveryRecord(ToolRecoveryRequest):
    new_attempt_id: str = Field(min_length=1)
    logical_call_id: str = Field(min_length=1)
    accepted_at: AwareDatetime
    interrupted_status: ToolCallStatus | None
    continuation: ContinuationStatus = ContinuationStatus.PENDING

    @model_validator(mode="after")
    def accepted_record(self) -> "ToolRecoveryRecord":
        if not self.previous_process_exited or self.accepted_at.utcoffset() != timedelta(0):
            raise ValueError("accepted recovery requires exit declaration and UTC time")
        if self.interrupted_status not in {None, ToolCallStatus.PENDING, ToolCallStatus.RUNNING}:
            raise ValueError("invalid interrupted status")
        return self


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    status: ToolCallStatus
    created_at: datetime
    completed_at: datetime | None = None
    result_evidence_ids: list[str] = Field(default_factory=list)
    invocation_id: str | None = None
    attempt_count: int = Field(default=0, ge=0)
    failure_kind: ToolFailureKind | None = None
    error_summary: str | None = None
    attempt_sequence: int | None = Field(default=None, ge=1)
    previous_attempt_id: str | None = Field(default=None, min_length=1)
    recovery_request_id: UUID | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "ToolCallRecord":
        finished = self.status in {ToolCallStatus.COMPLETED, ToolCallStatus.FAILED}
        if finished != (self.completed_at is not None):
            raise ValueError("completed_at must be present exactly when a tool call is finished")
        if self.status is not ToolCallStatus.COMPLETED and self.result_evidence_ids:
            raise ValueError("only COMPLETED tool calls can link result evidence")
        if self.status is ToolCallStatus.FAILED:
            if self.failure_kind is None or not self.error_summary:
                raise ValueError("FAILED tool calls require safe failure details")
        elif self.failure_kind is not None or self.error_summary is not None:
            raise ValueError("only FAILED tool calls can contain failure details")
        return self


class AttributionDecision(StrEnum):
    SUPPORTED = "SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ATTRIBUTION_AMBIGUOUS = "ATTRIBUTION_AMBIGUOUS"


class InvestigationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attribution_decision: AttributionDecision
    reason: str = Field(min_length=1)


class TransitionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    from_status: AgentStatus
    to_status: AgentStatus
    action: AgentAction | None
    reason: str = Field(min_length=1)
    state_revision: int = Field(ge=1)
    timestamp: datetime


class InvestigationState(BaseModel):
    """Serializable state suitable for a future LangGraph checkpoint adapter."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    case_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    current_issue: str = Field(min_length=1)
    scenario: InvestigationScenario | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    asked_questions: list[AskedQuestion] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    tool_recoveries: list[ToolRecoveryRecord] = Field(default_factory=list)
    human_review_blocks: list[HumanReviewBlock] | None = None
    transition_events: list[TransitionEvent] = Field(default_factory=list)
    investigation_result: InvestigationResult | None = None
    consumer_memory: ConsumerMemorySnapshot | None = None
    question_count: int = Field(default=0, ge=0)
    step_count: int = Field(default=0, ge=0)
    max_steps: int = Field(default=30, gt=0)
    max_questions: int = Field(default=6, gt=0)
    current_action: AgentAction | None = None
    status: AgentStatus = AgentStatus.INVESTIGATING
    next_question: str | None = None
    next_action_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state_schema_version: int = Field(default=1, ge=1)
    state_revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_state(self) -> "InvestigationState":
        from .tool_history import validate_tool_history

        validate_tool_history(self)
        evidence_ids = {item.id for item in self.evidence}
        if any(item.case_id != self.case_id for item in self.evidence):
            raise ValueError("all evidence must belong to the State case")
        if any(
            isinstance(item.value, dict)
            and item.value.get("consumer_id") not in {None, self.consumer_id}
            for item in self.evidence
        ):
            raise ValueError("business evidence must belong to the State consumer")
        for question in self.asked_questions:
            if not set(question.answered_by_evidence_ids) <= evidence_ids:
                raise ValueError("question evidence ids must reference State evidence")
        for call in self.tool_calls:
            if not set(call.result_evidence_ids) <= evidence_ids:
                raise ValueError("tool result_evidence_ids must reference State evidence")
        if self.consumer_memory is not None:
            if self.consumer_memory.consumer_id != self.consumer_id:
                raise ValueError("consumer memory must belong to the State consumer")
            memory_facts = (
                self.consumer_memory.repeat_purchase_products
                + self.consumer_memory.recent_orders
                + self.consumer_memory.previous_service_contacts
                + self.consumer_memory.explicit_preferences
            )
            if any(not set(fact.evidence_ids) <= evidence_ids for fact in memory_facts):
                raise ValueError("consumer memory facts must reference State evidence")
        sent_ids = {
            question.id
            for question in self.asked_questions
            if question.status in {QuestionStatus.ASKED, QuestionStatus.ANSWERED}
        }
        if self.question_count != len(sent_ids):
            raise ValueError("question_count must equal unique ASKED + ANSWERED question ids")
        if (
            self.status
            in {
                AgentStatus.CONCLUDED,
                AgentStatus.TERMINATED,
                AgentStatus.ESCALATED,
            }
            and self.current_action is not None
        ):
            raise ValueError(f"{self.status.value} state cannot have a current action")
        if (
            self.status is AgentStatus.WAITING_FOR_HUMAN
            and self.current_action is AgentAction.ASK_USER
        ):
            raise ValueError("WAITING_FOR_HUMAN cannot ASK_USER")
        if self.status is AgentStatus.WAITING_FOR_USER:
            waiting = {QuestionStatus.PENDING, QuestionStatus.ASKED}
            if not any(question.status in waiting for question in self.asked_questions):
                raise ValueError("WAITING_FOR_USER requires a pending or asked question")
            if self.current_action not in {None, AgentAction.ASK_USER}:
                raise ValueError("WAITING_FOR_USER cannot perform a non-question action")
        return self
