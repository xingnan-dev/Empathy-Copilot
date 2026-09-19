"""Deterministic next-action policy, separate from execution."""

from pydantic import BaseModel, ConfigDict

from backend.app.agent.guardrails import can_ask_question
from backend.app.agent.questions import QuestionTemplateRegistry
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    InvestigationState,
    ToolCallStatus,
)
from backend.app.domain.gaps import EvidenceGap, GapStatus, GapType


class NextActionDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: AgentAction | None
    reason: str
    target_gap: GapType | None = None
    tool_name: str | None = None
    question_intent: str | None = None
    terminate: bool = False


class DeterministicDecisionPolicy:
    GAP_PRIORITY = (
        GapType.ACTUAL_FIRST_USE_TIME,
        GapType.FEEDBACK_ONSET_TIME,
        GapType.RECENT_REGIMEN_CHANGES,
        GapType.REPORTED_SEVERITY,
    )

    def __init__(self, questions: QuestionTemplateRegistry) -> None:
        self.questions = questions

    def decide(self, state: InvestigationState) -> NextActionDecision:
        if state.status in {
            AgentStatus.ESCALATED,
            AgentStatus.CONCLUDED,
            AgentStatus.TERMINATED,
        }:
            return NextActionDecision(action=None, reason="State is terminal.")
        if state.step_count >= state.max_steps:
            return NextActionDecision(
                action=None,
                reason="Maximum completed transitions reached.",
                terminate=True,
            )
        if self._is_severe(state):
            return NextActionDecision(
                action=AgentAction.ESCALATE,
                reason="Consumer explicitly reported SEVERE impact; human service is required.",
            )
        if self._boolean_evidence(state, "human_review_required"):
            return NextActionDecision(
                action=AgentAction.WAIT_FOR_HUMAN,
                reason="A deterministic case flag requires human review.",
            )
        if not self._has_order_fact(state) and not self._completed_tool(state, "get_order_history"):
            if state.max_steps - state.step_count < 3:
                return NextActionDecision(
                    action=None,
                    reason="Not enough transition budget remains for the stub tool lifecycle.",
                    terminate=True,
                )
            return NextActionDecision(
                action=AgentAction.CALL_TOOL,
                reason="Order history has not been retrieved.",
                tool_name="get_order_history",
            )
        actual_first_use = self._gap(state, GapType.ACTUAL_FIRST_USE_TIME)
        if actual_first_use is None or actual_first_use.status is GapStatus.OPEN:
            return self._question_or_human(state, GapType.ACTUAL_FIRST_USE_TIME)
        if not self._has_service_history(state) and not self._completed_tool(
            state, "get_service_history"
        ):
            return self._tool_or_terminate(
                state,
                tool_name="get_service_history",
                reason="Service history context has not been retrieved.",
            )
        if state.consumer_memory is None and not self._completed_tool(
            state, "get_consumer_memory"
        ):
            return self._tool_or_terminate(
                state,
                tool_name="get_consumer_memory",
                reason="Evidence-backed consumer memory has not been assembled.",
            )
        if self._boolean_evidence(state, "policy_required") and not any(
            item.key == "policy_retrieved" for item in state.evidence
        ):
            if state.max_steps - state.step_count < 3:
                return NextActionDecision(
                    action=None,
                    reason="Not enough transition budget remains for policy retrieval.",
                    terminate=True,
                )
            return NextActionDecision(
                action=AgentAction.RETRIEVE_POLICY,
                reason="The case explicitly requires policy context.",
                tool_name="retrieve_service_policy",
            )

        gaps = {gap.gap_type: gap for gap in state.evidence_gaps}
        for gap_type in self.GAP_PRIORITY:
            if gap_type is GapType.ACTUAL_FIRST_USE_TIME:
                continue
            gap = gaps.get(gap_type)
            if gap is None or gap.status is GapStatus.OPEN:
                return self._question_or_human(state, gap_type)
        if self._has_undated_regimen_change(state):
            gap_type = GapType.RECENT_REGIMEN_CHANGES
            candidate = self.questions.create(
                state, gap_type, intent="REGIMEN_CHANGE_EFFECTIVE_AT"
            )
            if can_ask_question(state, candidate.text):
                return NextActionDecision(
                    action=AgentAction.ASK_USER,
                    reason="A reported regimen change has no effective date.",
                    target_gap=gap_type,
                    question_intent="REGIMEN_CHANGE_EFFECTIVE_AT",
                )
            return NextActionDecision(
                action=AgentAction.WAIT_FOR_HUMAN,
                reason="The undated regimen change cannot be clarified within question guards.",
                target_gap=gap_type,
            )
        return NextActionDecision(
            action=AgentAction.CONCLUDE,
            reason="All required P0 evidence gaps are resolved.",
        )

    @staticmethod
    def _has_order_fact(state: InvestigationState) -> bool:
        return any(
            item.key in {"first_purchase", "repeat_purchase"} for item in state.evidence
        )

    @staticmethod
    def _has_service_history(state: InvestigationState) -> bool:
        return any(item.key == "previous_service_contact" for item in state.evidence)

    @staticmethod
    def _completed_tool(state: InvestigationState, tool_name: str) -> bool:
        return any(
            call.tool_name == tool_name and call.status is ToolCallStatus.COMPLETED
            for call in state.tool_calls
        )

    @staticmethod
    def _boolean_evidence(state: InvestigationState, key: str) -> bool:
        return any(item.key == key and item.value is True for item in state.evidence)

    @staticmethod
    def _is_severe(state: InvestigationState) -> bool:
        return any(
            item.key == "reported_severity" and item.value == "SEVERE"
            for item in state.evidence
        )

    @staticmethod
    def _has_undated_regimen_change(state: InvestigationState) -> bool:
        dated_products = {
            item.value.get("product_id")
            for item in state.evidence
            if item.key == "recent_regimen_changes"
            and isinstance(item.value, dict)
            and item.value.get("effective_at") is not None
        }
        return any(
            item.key == "recent_regimen_changes"
            and isinstance(item.value, dict)
            and item.value.get("effective_at") is None
            and item.value.get("product_id") not in dated_products
            for item in state.evidence
        )

    @staticmethod
    def _gap(state: InvestigationState, gap_type: GapType) -> EvidenceGap | None:
        return next((gap for gap in state.evidence_gaps if gap.gap_type is gap_type), None)

    def _question_or_human(
        self, state: InvestigationState, gap_type: GapType
    ) -> NextActionDecision:
        candidate = self.questions.create(state, gap_type)
        if can_ask_question(state, candidate.text):
            return NextActionDecision(
                action=AgentAction.ASK_USER,
                reason=f"Required evidence gap {gap_type.value} remains open.",
                target_gap=gap_type,
                question_intent=gap_type.value,
            )
        return NextActionDecision(
            action=AgentAction.WAIT_FOR_HUMAN,
            reason="The required gap cannot be asked again within deterministic guards.",
            target_gap=gap_type,
        )

    @staticmethod
    def _tool_or_terminate(
        state: InvestigationState, *, tool_name: str, reason: str
    ) -> NextActionDecision:
        if state.max_steps - state.step_count < 3:
            return NextActionDecision(
                action=None,
                reason=f"Not enough transition budget remains for {tool_name}.",
                terminate=True,
            )
        return NextActionDecision(
            action=AgentAction.CALL_TOOL,
            reason=reason,
            tool_name=tool_name,
        )
