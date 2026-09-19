"""Deterministic Context Passport projection for continuity and handoff."""

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    AskedQuestion,
    InvestigationState,
    ToolCallStatus,
)
from backend.app.domain.business import EvidenceBackedFact
from backend.app.domain.evidence import EvidenceType
from backend.app.domain.gaps import GapStatus, GapType


class ContextPassport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    consumer_id: str
    confirmed_facts: list[EvidenceBackedFact] = Field(default_factory=list)
    open_gaps: list[GapType] = Field(default_factory=list)
    asked_questions: list[AskedQuestion] = Field(default_factory=list)
    completed_tools: list[str] = Field(default_factory=list)
    service_history_summary: list[EvidenceBackedFact] = Field(default_factory=list)
    current_status: AgentStatus
    next_action: AgentAction | None = None


class ContextPassportService:
    def build(self, state: InvestigationState) -> ContextPassport:
        confirmed = [
            EvidenceBackedFact(key=item.key, value=item.value, evidence_ids=[item.id])
            for item in state.evidence
            if item.evidence_type
            not in {EvidenceType.AI_INFERENCE, EvidenceType.UNKNOWN}
        ]
        return ContextPassport(
            case_id=state.case_id,
            consumer_id=state.consumer_id,
            confirmed_facts=confirmed,
            open_gaps=[
                gap.gap_type for gap in state.evidence_gaps if gap.status is GapStatus.OPEN
            ],
            asked_questions=list(state.asked_questions),
            completed_tools=[
                call.tool_name
                for call in state.tool_calls
                if call.status is ToolCallStatus.COMPLETED
            ],
            service_history_summary=[
                fact for fact in confirmed if fact.key == "previous_service_contact"
            ],
            current_status=state.status,
            next_action=state.current_action,
        )
