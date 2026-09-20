"""Typed business tools and grounded execution lifecycle."""

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    InvestigationState,
    ToolCallRecord,
    ToolCallStatus,
)
from backend.app.domain.business import (
    ConsumerMemoryToolResult,
    OrderHistoryToolResult,
    PolicyToolResult,
    ServiceHistoryToolResult,
)
from backend.app.domain.evidence import Evidence
from backend.app.domain.gaps import evaluate_p0_gaps
from backend.app.repositories import DemoRepositoryBundle
from backend.app.repositories.interfaces import (
    BusinessRepositoryBundle,
    ConsumerRepository,
    OrderRepository,
    ServiceHistoryRepository,
)
from backend.app.services.grounding import EvidenceGroundingService
from backend.app.services.memory import ConsumerMemoryService
from backend.app.services.transitions import StateTransitionService


class ConsumerLookupInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_id: str = Field(min_length=1)


ToolResult = (
    OrderHistoryToolResult
    | ServiceHistoryToolResult
    | ConsumerMemoryToolResult
    | PolicyToolResult
)
BusinessTool = Callable[[InvestigationState, dict[str, str]], ToolResult]


class BusinessToolSet:
    def __init__(
        self,
        consumers: ConsumerRepository,
        orders: OrderRepository,
        service_history: ServiceHistoryRepository,
    ) -> None:
        self.consumers = consumers
        self.orders = orders
        self.service_history = service_history

    def get_order_history(
        self, state: InvestigationState, arguments: dict[str, str]
    ) -> OrderHistoryToolResult:
        del state
        request = ConsumerLookupInput.model_validate(arguments)
        return OrderHistoryToolResult(
            consumer_id=request.consumer_id,
            records=self.orders.list_for_consumer(request.consumer_id),
        )

    def get_service_history(
        self, state: InvestigationState, arguments: dict[str, str]
    ) -> ServiceHistoryToolResult:
        del state
        request = ConsumerLookupInput.model_validate(arguments)
        return ServiceHistoryToolResult(
            consumer_id=request.consumer_id,
            records=self.service_history.list_for_consumer(request.consumer_id),
        )

    def get_consumer_memory(
        self, state: InvestigationState, arguments: dict[str, str]
    ) -> ConsumerMemoryToolResult:
        del state
        request = ConsumerLookupInput.model_validate(arguments)
        return ConsumerMemoryToolResult(
            consumer_id=request.consumer_id,
            consumer=self.consumers.get(request.consumer_id),
            recent_orders=self.orders.list_for_consumer(request.consumer_id),
            previous_service_contacts=self.service_history.list_for_consumer(
                request.consumer_id
            ),
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BusinessTool] = {}
        self.execution_counts: dict[str, int] = {}

    def register(self, name: str, tool: BusinessTool) -> None:
        self._tools[name] = tool

    def execute(
        self, name: str, state: InvestigationState, arguments: dict[str, str]
    ) -> ToolResult:
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise KeyError(f"tool is not registered: {name}") from error
        self.execution_counts[name] = self.execution_counts.get(name, 0) + 1
        return tool(state, arguments)


def retrieve_service_policy_stub(
    state: InvestigationState, arguments: dict[str, str]
) -> PolicyToolResult:
    del state
    return PolicyToolResult(policy_id=arguments["policy_id"])


class BusinessToolExecutionService:
    def __init__(
        self,
        registry: ToolRegistry,
        transitions: StateTransitionService,
        grounding: EvidenceGroundingService,
        memory: ConsumerMemoryService,
    ) -> None:
        self.registry = registry
        self.transitions = transitions
        self.grounding = grounding
        self.memory = memory

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
        pending = ToolCallRecord(
            id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            status=ToolCallStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        current = self.transitions.transition(
            state,
            to_status=AgentStatus.INVESTIGATING,
            action=action,
            reason=f"Prepared business tool call {tool_name}.",
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
            reason=f"Running business tool {tool_name}.",
            updates={"tool_calls": self._replace_call(current, running)},
        )

        raw_result = self.registry.execute(tool_name, current, arguments)
        grounded = self._ground(raw_result, current.case_id)
        existing_ids = {item.id for item in current.evidence}
        new_evidence = [item for item in grounded if item.id not in existing_ids]
        evidence = [*current.evidence, *new_evidence]
        completed_call = ToolCallRecord(
            id=running.id,
            tool_name=running.tool_name,
            arguments=running.arguments,
            status=ToolCallStatus.COMPLETED,
            created_at=running.created_at,
            completed_at=datetime.now(UTC),
            result_evidence_ids=[item.id for item in grounded],
        )
        updates: dict[str, object] = {
            "tool_calls": self._replace_call(current, completed_call),
            "evidence": evidence,
            "evidence_gaps": evaluate_p0_gaps(current.case_id, evidence),
        }
        if isinstance(raw_result, ConsumerMemoryToolResult):
            updates["consumer_memory"] = self.memory.build(current.consumer_id, evidence)
        return self.transitions.transition(
            current,
            to_status=AgentStatus.INVESTIGATING,
            action=action,
            reason=f"Grounded and completed business tool {tool_name}.",
            updates=updates,
        )

    def _ground(self, result: ToolResult, case_id: str) -> list[Evidence]:
        if isinstance(result, OrderHistoryToolResult):
            return self.grounding.ground_order_history(result, case_id)
        if isinstance(result, ServiceHistoryToolResult):
            return self.grounding.ground_service_history(result, case_id)
        if isinstance(result, ConsumerMemoryToolResult):
            return self.grounding.ground_consumer_memory(result, case_id)
        return self.grounding.ground_policy(result, case_id)

    @staticmethod
    def _replace_call(
        state: InvestigationState, replacement: ToolCallRecord
    ) -> list[ToolCallRecord]:
        return [
            replacement if call.id == replacement.id else call for call in state.tool_calls
        ]


def default_tool_registry(
    repositories: BusinessRepositoryBundle | None = None,
) -> ToolRegistry:
    bundle = repositories or DemoRepositoryBundle()
    tools = BusinessToolSet(bundle.consumers, bundle.orders, bundle.service_history)
    registry = ToolRegistry()
    registry.register("get_order_history", tools.get_order_history)
    registry.register("get_service_history", tools.get_service_history)
    registry.register("get_consumer_memory", tools.get_consumer_memory)
    # Retained from Phase 2; it is not a Phase 3 P0 business tool.
    registry.register("retrieve_service_policy", retrieve_service_policy_stub)
    return registry
