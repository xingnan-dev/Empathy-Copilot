"""Tool interfaces and deterministic Phase 2 stubs."""

from collections.abc import Callable
from datetime import UTC, datetime

from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    InvestigationState,
    ToolCallRecord,
    ToolCallStatus,
)
from backend.app.domain.evidence import Evidence, EvidenceSource, EvidenceType, SourceType
from backend.app.domain.gaps import evaluate_p0_gaps
from backend.app.services.transitions import StateTransitionService

StubTool = Callable[[InvestigationState, dict[str, str]], list[Evidence]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, StubTool] = {}
        self.execution_counts: dict[str, int] = {}

    def register(self, name: str, tool: StubTool) -> None:
        self._tools[name] = tool

    def execute(
        self, name: str, state: InvestigationState, arguments: dict[str, str]
    ) -> list[Evidence]:
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise KeyError(f"tool is not registered: {name}") from error
        self.execution_counts[name] = self.execution_counts.get(name, 0) + 1
        return tool(state, arguments)


def get_order_history_stub(
    state: InvestigationState, arguments: dict[str, str]
) -> list[Evidence]:
    now = datetime.now(UTC)
    consumer_id = arguments["consumer_id"]
    return [
        Evidence(
            id=f"ev-tool-order-{state.case_id}-{consumer_id}",
            case_id=state.case_id,
            key="first_purchase",
            value={
                "product_id": "c_serum",
                "product_name": "C Serum",
                "first_purchase": True,
            },
            evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
            source=EvidenceSource(
                source_type=SourceType.ORDER_SYSTEM,
                source_id="A1024",
                source_label="Stub order #A1024",
            ),
            observed_at=now,
            created_at=now,
            extraction_confidence=1.0,
        )
    ]


def retrieve_service_policy_stub(
    state: InvestigationState, arguments: dict[str, str]
) -> list[Evidence]:
    now = datetime.now(UTC)
    return [
        Evidence(
            id=f"ev-tool-policy-{state.case_id}",
            case_id=state.case_id,
            key="policy_retrieved",
            value={"policy_id": arguments["policy_id"]},
            evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
            source=EvidenceSource(
                source_type=SourceType.POLICY_DATABASE,
                source_id=arguments["policy_id"],
                source_label="Stub service policy",
            ),
            observed_at=now,
            created_at=now,
            extraction_confidence=1.0,
        )
    ]


class StubToolExecutionService:
    def __init__(
        self, registry: ToolRegistry, transitions: StateTransitionService
    ) -> None:
        self.registry = registry
        self.transitions = transitions

    def execute_once(
        self,
        state: InvestigationState,
        *,
        tool_name: str,
        action: AgentAction,
        arguments: dict[str, str],
    ) -> InvestigationState:
        completed = next(
            (
                call
                for call in state.tool_calls
                if call.tool_name == tool_name
                and call.arguments == arguments
                and call.status is ToolCallStatus.COMPLETED
            ),
            None,
        )
        if completed is not None:
            return state

        call_id = f"tool-{state.case_id}-{tool_name}"
        now = datetime.now(UTC)
        pending = ToolCallRecord(
            id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            status=ToolCallStatus.PENDING,
            created_at=now,
        )
        current = self.transitions.transition(
            state,
            to_status=AgentStatus.INVESTIGATING,
            action=action,
            reason=f"Prepared stub tool call {tool_name}.",
            updates={"tool_calls": [*state.tool_calls, pending]},
        )
        running = ToolCallRecord(
            id=pending.id,
            tool_name=pending.tool_name,
            arguments=pending.arguments,
            status=ToolCallStatus.RUNNING,
            created_at=pending.created_at,
        )
        current = self.transitions.transition(
            current,
            to_status=AgentStatus.INVESTIGATING,
            action=action,
            reason=f"Running stub tool {tool_name}.",
            updates={"tool_calls": self._replace_call(current, running)},
        )
        result = self.registry.execute(tool_name, current, arguments)
        existing_ids = {item.id for item in current.evidence}
        new_evidence = [item for item in result if item.id not in existing_ids]
        completed_call = ToolCallRecord(
            id=running.id,
            tool_name=running.tool_name,
            arguments=running.arguments,
            status=ToolCallStatus.COMPLETED,
            created_at=running.created_at,
            completed_at=datetime.now(UTC),
            result_evidence_ids=[item.id for item in new_evidence],
        )
        evidence = [*current.evidence, *new_evidence]
        return self.transitions.transition(
            current,
            to_status=AgentStatus.INVESTIGATING,
            action=action,
            reason=f"Completed stub tool {tool_name}.",
            updates={
                "tool_calls": self._replace_call(current, completed_call),
                "evidence": evidence,
                "evidence_gaps": evaluate_p0_gaps(current.case_id, evidence),
            },
        )

    @staticmethod
    def _replace_call(
        state: InvestigationState, replacement: ToolCallRecord
    ) -> list[ToolCallRecord]:
        return [
            replacement if call.id == replacement.id else call for call in state.tool_calls
        ]


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("get_order_history", get_order_history_stub)
    registry.register("retrieve_service_policy", retrieve_service_policy_stub)
    return registry
