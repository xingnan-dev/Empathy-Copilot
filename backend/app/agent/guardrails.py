"""Deterministic safety gates; no language-model judgment lives here."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict

from backend.app.domain.agent import (
    AgentStatus,
    InvestigationState,
)
from backend.app.domain.agent import (
    AttributionDecision as AttributionDecision,
)
from backend.app.domain.gaps import P0_RESOLUTION_POLICIES, GapStatus
from backend.app.domain.regimen import ChangeType, RegimenChange


class AttributionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: AttributionDecision
    reason: str


def normalize_question(question: str) -> str:
    normalized = unicodedata.normalize("NFKC", question).casefold().strip()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def can_ask_question(state: InvestigationState, question: str) -> bool:
    if state.status in {
        AgentStatus.TERMINATED,
        AgentStatus.CONCLUDED,
        AgentStatus.ESCALATED,
        AgentStatus.WAITING_FOR_HUMAN,
    }:
        return False
    if state.question_count >= state.max_questions:
        return False
    candidate = normalize_question(question)
    return bool(candidate) and all(
        record.normalized_text != candidate for record in state.asked_questions
    )


def apply_step_limit(state: InvestigationState) -> InvestigationState:
    """Terminate after max_steps completed transitions; max-1 may still continue."""

    if state.step_count < state.max_steps:
        return state
    data = state.model_dump()
    data.update(
        {
            "status": AgentStatus.TERMINATED,
            "current_action": None,
            "next_question": None,
            "next_action_reason": "Maximum investigation steps reached.",
            "state_revision": state.state_revision + 1,
        }
    )
    return InvestigationState.model_validate(data)


def assess_attribution(
    state: InvestigationState,
    candidate_product_id: str,
    regimen_changes: list[RegimenChange],
) -> AttributionResult:
    """Gate causal claims; Phase 1.1 intentionally has no SUPPORTED return path."""

    gaps_by_type = {gap.gap_type: gap for gap in state.evidence_gaps}
    required_types = set(P0_RESOLUTION_POLICIES)
    if set(gaps_by_type) != required_types or any(
        gaps_by_type[gap_type].status is not GapStatus.RESOLVED for gap_type in required_types
    ):
        return AttributionResult(
            decision=AttributionDecision.INSUFFICIENT_EVIDENCE,
            reason="All required P0 evidence gaps must be present and resolved.",
        )

    relevant = [
        change
        for change in regimen_changes
        if change.change_type in {ChangeType.NEW, ChangeType.REPLACED}
        and change.effective_at is not None
    ]
    candidate_changes = [
        change for change in relevant if change.product_id == candidate_product_id
    ]
    if candidate_changes:
        candidate_times = {change.effective_at for change in candidate_changes}
        competing = {
            change.product_id
            for change in relevant
            if change.product_id != candidate_product_id
            and change.effective_at in candidate_times
        }
        if competing:
            return AttributionResult(
                decision=AttributionDecision.ATTRIBUTION_AMBIGUOUS,
                reason="Multiple explicitly reported product changes share an effective date.",
            )
    return AttributionResult(
        decision=AttributionDecision.INSUFFICIENT_EVIDENCE,
        reason="Temporal or usage evidence alone does not establish causality.",
    )
