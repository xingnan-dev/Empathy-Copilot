"""Deterministic recovery eligibility for current and legacy pause reasons."""

from backend.app.domain.agent import HumanReviewBlock, InvestigationState, ToolCallRecord
from backend.app.domain.safety import SafetyGate, SafetyGateService


def safety_blocks(state: InvestigationState) -> set[HumanReviewBlock]:
    result: set[HumanReviewBlock] = set()
    if SafetyGateService().assess(state).gate is SafetyGate.SAFETY:
        result.add(HumanReviewBlock.SAFETY)
    if any(e.key == "human_review_required" and e.value is True for e in state.evidence):
        result.add(HumanReviewBlock.BUSINESS_REVIEW)
    return result


def recovery_blocks(state: InvestigationState, target: ToolCallRecord) -> set[HumanReviewBlock]:
    result = safety_blocks(state)
    if state.human_review_blocks is not None:
        return result | set(state.human_review_blocks)
    reason = state.next_action_reason
    allowed = {
        f"Business tool {target.tool_name} failed; manual recovery is required.",
        f"Tool invocation {target.invocation_id or target.id} "
        "requires manual recovery before another execution.",
    }
    if (
        state.transition_events
        and state.transition_events[-1].reason == reason
        and reason in allowed
    ):
        return result | {HumanReviewBlock.TOOL_RECOVERY}
    return result | {HumanReviewBlock.OTHER}
