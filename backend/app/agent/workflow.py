"""Phase 2 LangGraph investigation workflow."""

from datetime import UTC, datetime
from typing import Literal, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from backend.app.agent.decision import DeterministicDecisionPolicy, NextActionDecision
from backend.app.agent.guardrails import assess_attribution
from backend.app.agent.questions import QuestionTemplateRegistry
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    AskedQuestion,
    InvestigationResult,
    InvestigationState,
    QuestionStatus,
)
from backend.app.domain.evidence import Evidence
from backend.app.domain.gaps import GapType, evaluate_p0_gaps
from backend.app.domain.regimen import build_regimen_changes
from backend.app.services.checkpoints import CheckpointStore, InMemoryCheckpointStore
from backend.app.services.context_passport import ContextPassport, ContextPassportService
from backend.app.services.grounding import EvidenceGroundingService
from backend.app.services.memory import ConsumerMemoryService
from backend.app.services.tools import (
    BusinessToolExecutionService,
    ToolRegistry,
    default_tool_registry,
)
from backend.app.services.transitions import StateTransitionService


class WorkflowState(TypedDict):
    investigation: InvestigationState
    decision: NextActionDecision | None


RouteName = Literal[
    "prepare_question",
    "prepare_tool_call",
    "prepare_escalation",
    "prepare_wait_for_human",
    "prepare_conclusion",
    "prepare_termination",
    "stop",
]


EVIDENCE_KEY_TO_GAP: dict[str, GapType] = {
    "actual_first_use_time": GapType.ACTUAL_FIRST_USE_TIME,
    "feedback_onset_time": GapType.FEEDBACK_ONSET_TIME,
    "recent_regimen_changes": GapType.RECENT_REGIMEN_CHANGES,
    "reported_severity": GapType.REPORTED_SEVERITY,
}


class InvestigationWorkflow:
    def __init__(
        self,
        *,
        checkpoint_store: CheckpointStore | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.checkpoints = checkpoint_store or InMemoryCheckpointStore()
        self.transitions = StateTransitionService()
        self.questions = QuestionTemplateRegistry()
        self.policy = DeterministicDecisionPolicy(self.questions)
        self.tools = tool_registry or default_tool_registry()
        self.tool_execution = BusinessToolExecutionService(
            self.tools,
            self.transitions,
            EvidenceGroundingService(),
            ConsumerMemoryService(),
        )
        self.passports = ContextPassportService()
        self.graph: CompiledStateGraph[WorkflowState, None, WorkflowState, WorkflowState] = (
            self._build_graph()
        )

    def _build_graph(
        self,
    ) -> CompiledStateGraph[WorkflowState, None, WorkflowState, WorkflowState]:
        builder = StateGraph(WorkflowState)
        builder.add_node(  # type: ignore[call-overload]
            "evaluate_state", self._evaluate_state, input_schema=WorkflowState
        )
        builder.add_node(  # type: ignore[call-overload]
            "decide_next_action", self._decide_next_action, input_schema=WorkflowState
        )
        builder.add_node(  # type: ignore[call-overload]
            "prepare_question", self._prepare_question, input_schema=WorkflowState
        )
        builder.add_node(  # type: ignore[call-overload]
            "prepare_tool_call", self._prepare_tool_call, input_schema=WorkflowState
        )
        builder.add_node(  # type: ignore[call-overload]
            "prepare_escalation", self._prepare_escalation, input_schema=WorkflowState
        )
        builder.add_node(  # type: ignore[call-overload]
            "prepare_wait_for_human",
            self._prepare_wait_for_human,
            input_schema=WorkflowState,
        )
        builder.add_node(  # type: ignore[call-overload]
            "prepare_conclusion", self._prepare_conclusion, input_schema=WorkflowState
        )
        builder.add_node(  # type: ignore[call-overload]
            "prepare_termination", self._prepare_termination, input_schema=WorkflowState
        )
        builder.add_edge(START, "evaluate_state")
        builder.add_edge("evaluate_state", "decide_next_action")
        builder.add_conditional_edges(
            "decide_next_action",
            self._route_decision,
            {
                "prepare_question": "prepare_question",
                "prepare_tool_call": "prepare_tool_call",
                "prepare_escalation": "prepare_escalation",
                "prepare_wait_for_human": "prepare_wait_for_human",
                "prepare_conclusion": "prepare_conclusion",
                "prepare_termination": "prepare_termination",
                "stop": END,
            },
        )
        builder.add_edge("prepare_tool_call", "evaluate_state")
        for terminal_node in (
            "prepare_question",
            "prepare_escalation",
            "prepare_wait_for_human",
            "prepare_conclusion",
            "prepare_termination",
        ):
            builder.add_edge(terminal_node, END)
        return builder.compile()

    def run(
        self, state: InvestigationState, *, expected_revision: int | None = None
    ) -> InvestigationState:
        output = self.graph.invoke({"investigation": state, "decision": None})
        result = cast(InvestigationState, output["investigation"])
        self.checkpoints.save(result, expected_revision=expected_revision)
        return result

    def resume_with_evidence(
        self, current: InvestigationState, new_evidence: list[Evidence]
    ) -> InvestigationState:
        if current.status is not AgentStatus.WAITING_FOR_USER:
            raise ValueError("evidence resume requires WAITING_FOR_USER state")
        if any(item.case_id != current.case_id for item in new_evidence):
            raise ValueError("all resumed evidence must belong to the current case")

        existing_ids = {item.id for item in current.evidence}
        additions = [item for item in new_evidence if item.id not in existing_ids]
        answered_gaps = {
            EVIDENCE_KEY_TO_GAP[item.key]
            for item in additions
            if item.key in EVIDENCE_KEY_TO_GAP
        }
        questions = [
            self._answer_question(
                record,
                [
                    item
                    for item in additions
                    if EVIDENCE_KEY_TO_GAP.get(item.key) is record.gap_type
                ],
            )
            if record.gap_type in answered_gaps
            and record.status in {QuestionStatus.PENDING, QuestionStatus.ASKED}
            else record
            for record in current.asked_questions
        ]
        evidence = [*current.evidence, *additions]
        resumed = self.transitions.transition(
            current,
            to_status=AgentStatus.INVESTIGATING,
            action=None,
            reason="Ingested consumer evidence and resumed investigation.",
            updates={
                "evidence": evidence,
                "evidence_gaps": evaluate_p0_gaps(current.case_id, evidence),
                "asked_questions": questions,
                "current_action": None,
                "next_question": None,
            },
        )
        return self.run(resumed, expected_revision=current.state_revision)

    def resume_case(self, case_id: str, new_evidence: list[Evidence]) -> InvestigationState:
        return self.resume_with_evidence(self.checkpoints.load(case_id), new_evidence)

    def restore_case(self, case_id: str) -> InvestigationState:
        return self.checkpoints.load(case_id)

    def context_passport(self, case_id: str) -> ContextPassport:
        return self.passports.build(self.restore_case(case_id))

    def _evaluate_state(self, graph_state: WorkflowState) -> WorkflowState:
        refreshed = self.transitions.refresh_derived_gaps(graph_state["investigation"])
        return {"investigation": refreshed, "decision": graph_state.get("decision")}

    def _decide_next_action(self, graph_state: WorkflowState) -> WorkflowState:
        state = graph_state["investigation"]
        return {"investigation": state, "decision": self.policy.decide(state)}

    @staticmethod
    def _route_decision(graph_state: WorkflowState) -> RouteName:
        decision = graph_state["decision"]
        if decision is None or (decision.action is None and not decision.terminate):
            return "stop"
        if decision.terminate:
            return "prepare_termination"
        routes: dict[AgentAction, RouteName] = {
            AgentAction.ASK_USER: "prepare_question",
            AgentAction.CALL_TOOL: "prepare_tool_call",
            AgentAction.RETRIEVE_POLICY: "prepare_tool_call",
            AgentAction.ESCALATE: "prepare_escalation",
            AgentAction.WAIT_FOR_HUMAN: "prepare_wait_for_human",
            AgentAction.CONCLUDE: "prepare_conclusion",
        }
        assert decision.action is not None
        return routes[decision.action]

    def _prepare_question(self, graph_state: WorkflowState) -> WorkflowState:
        state = graph_state["investigation"]
        decision = self._required_decision(graph_state)
        if decision.target_gap is None:
            raise ValueError("ASK_USER decision requires target_gap")
        pending = self.questions.create(
            state, decision.target_gap, intent=decision.question_intent
        )
        asked = AskedQuestion(
            id=pending.id,
            gap_type=pending.gap_type,
            text=pending.text,
            normalized_text=pending.normalized_text,
            status=QuestionStatus.ASKED,
            asked_at=datetime.now(UTC),
        )
        result = self.transitions.transition(
            state,
            to_status=AgentStatus.WAITING_FOR_USER,
            action=AgentAction.ASK_USER,
            reason=decision.reason,
            updates={
                "asked_questions": [*state.asked_questions, asked],
                "question_count": state.question_count + 1,
                "next_question": asked.text,
            },
        )
        return {"investigation": result, "decision": decision}

    def _prepare_tool_call(self, graph_state: WorkflowState) -> WorkflowState:
        state = graph_state["investigation"]
        decision = self._required_decision(graph_state)
        if decision.tool_name is None or decision.action is None:
            raise ValueError("tool decision requires tool_name and action")
        business_tools = {
            "get_order_history",
            "get_service_history",
            "get_consumer_memory",
        }
        arguments = (
            {"consumer_id": state.consumer_id}
            if decision.tool_name in business_tools
            else {"policy_id": "beauty_service_default"}
        )
        result = self.tool_execution.execute_once(
            state,
            tool_name=decision.tool_name,
            action=decision.action,
            arguments=arguments,
        )
        return {"investigation": result, "decision": decision}

    def _prepare_escalation(self, graph_state: WorkflowState) -> WorkflowState:
        state = graph_state["investigation"]
        decision = self._required_decision(graph_state)
        result = self.transitions.transition(
            state,
            to_status=AgentStatus.ESCALATED,
            action=AgentAction.ESCALATE,
            reason=decision.reason,
            updates={"next_question": None},
        )
        return {"investigation": result, "decision": decision}

    def _prepare_wait_for_human(self, graph_state: WorkflowState) -> WorkflowState:
        state = graph_state["investigation"]
        decision = self._required_decision(graph_state)
        result = self.transitions.transition(
            state,
            to_status=AgentStatus.WAITING_FOR_HUMAN,
            action=AgentAction.WAIT_FOR_HUMAN,
            reason=decision.reason,
            updates={"next_question": None},
        )
        return {"investigation": result, "decision": decision}

    def _prepare_conclusion(self, graph_state: WorkflowState) -> WorkflowState:
        state = graph_state["investigation"]
        decision = self._required_decision(graph_state)
        changes = build_regimen_changes(state.case_id, state.evidence)
        attribution = assess_attribution(state, self._primary_product_id(state), changes)
        result = self.transitions.transition(
            state,
            to_status=AgentStatus.CONCLUDED,
            action=AgentAction.CONCLUDE,
            reason=decision.reason,
            updates={
                "next_question": None,
                "investigation_result": InvestigationResult(
                    attribution_decision=attribution.decision,
                    reason=attribution.reason,
                ),
            },
        )
        return {"investigation": result, "decision": decision}

    def _prepare_termination(self, graph_state: WorkflowState) -> WorkflowState:
        state = graph_state["investigation"]
        decision = self._required_decision(graph_state)
        result = self.transitions.transition(
            state,
            to_status=AgentStatus.TERMINATED,
            action=None,
            reason=decision.reason,
            updates={"next_question": None},
        )
        return {"investigation": result, "decision": decision}

    @staticmethod
    def _required_decision(graph_state: WorkflowState) -> NextActionDecision:
        decision = graph_state["decision"]
        if decision is None:
            raise ValueError("workflow node requires a decision")
        return decision

    @staticmethod
    def _answer_question(record: AskedQuestion, evidence: list[Evidence]) -> AskedQuestion:
        return AskedQuestion(
            id=record.id,
            gap_type=record.gap_type,
            text=record.text,
            normalized_text=record.normalized_text,
            status=QuestionStatus.ANSWERED,
            asked_at=record.asked_at or datetime.now(UTC),
            answered_by_evidence_ids=[item.id for item in evidence],
        )

    @staticmethod
    def _primary_product_id(state: InvestigationState) -> str:
        for item in state.evidence:
            if item.key == "first_purchase" and isinstance(item.value, dict):
                product_id = item.value.get("product_id")
                if isinstance(product_id, str) and product_id:
                    return product_id
        return "unknown_product"
