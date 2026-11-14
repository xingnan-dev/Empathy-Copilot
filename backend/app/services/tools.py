"""Typed business tools and grounded execution lifecycle."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    ContinuationStatus,
    HumanReviewBlock,
    InvestigationState,
    ToolCallRecord,
    ToolCallStatus,
    ToolFailureKind,
    ToolRecoveryRecord,
)
from backend.app.domain.business import (
    ConsumerMemoryToolResult,
    LogisticsStatusToolResult,
    OrderHistoryToolResult,
    PolicyToolResult,
    ServiceHistoryToolResult,
)
from backend.app.domain.evidence import Evidence
from backend.app.domain.gaps import evaluate_p0_gaps, evaluate_scenario_gaps
from backend.app.domain.tool_history import logical_call_id
from backend.app.repositories import DemoRepositoryBundle
from backend.app.repositories.interfaces import (
    BusinessRepositoryBundle,
    ConsumerRepository,
    LogisticsRepository,
    OrderRepository,
    ServiceHistoryRepository,
)
from backend.app.services.checkpoints import CheckpointStore
from backend.app.services.grounding import (
    EvidenceContentConflict,
    EvidenceGroundingService,
    merge_evidence_batch,
)
from backend.app.services.memory import ConsumerMemoryService
from backend.app.services.tool_attempts import effective_tool_calls
from backend.app.services.transitions import StateTransitionService


class ConsumerLookupInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_id: str = Field(min_length=1)


class CaseLookupInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)


ToolResult = (
    OrderHistoryToolResult
    | ServiceHistoryToolResult
    | ConsumerMemoryToolResult
    | LogisticsStatusToolResult
    | PolicyToolResult
)
BusinessTool = Callable[[InvestigationState, dict[str, str]], ToolResult]


class ToolOutcomeUnknownError(RuntimeError):
    """The caller cannot prove whether an external side effect completed."""


@dataclass(frozen=True)
class RegisteredTool:
    execute: BusinessTool
    side_effect_free: bool


@dataclass(frozen=True)
class DurableToolExecution:
    state: InvestigationState
    persisted_revision: int


@dataclass(frozen=True)
class RecoveryExecutionPermit:
    case_id: str
    request_id: UUID
    attempt_id: str
    revision: int
    token: UUID


class BusinessToolSet:
    def __init__(
        self,
        consumers: ConsumerRepository,
        orders: OrderRepository,
        service_history: ServiceHistoryRepository,
        logistics: LogisticsRepository,
    ) -> None:
        self.consumers = consumers
        self.orders = orders
        self.service_history = service_history
        self.logistics = logistics

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
            previous_service_contacts=self.service_history.list_for_consumer(request.consumer_id),
        )

    def get_logistics_status(
        self, state: InvestigationState, arguments: dict[str, str]
    ) -> LogisticsStatusToolResult:
        del state
        request = CaseLookupInput.model_validate(arguments)
        return LogisticsStatusToolResult(
            case_id=request.case_id,
            record=self.logistics.get_for_case(request.case_id),
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self.execution_counts: dict[str, int] = {}

    def register(self, name: str, tool: BusinessTool, *, side_effect_free: bool = False) -> None:
        self._tools[name] = RegisteredTool(tool, side_effect_free)

    def is_side_effect_free(self, name: str) -> bool:
        try:
            return self._tools[name].side_effect_free
        except KeyError as error:
            raise KeyError(f"tool is not registered: {name}") from error

    def execute(
        self, name: str, state: InvestigationState, arguments: dict[str, str]
    ) -> ToolResult:
        try:
            tool = self._tools[name]
        except KeyError as error:
            raise KeyError(f"tool is not registered: {name}") from error
        self.execution_counts[name] = self.execution_counts.get(name, 0) + 1
        return tool.execute(state, arguments)


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
        self._permits: dict[UUID, RecoveryExecutionPermit] = {}

    def _issue_permit(
        self, state: InvestigationState, call: ToolCallRecord
    ) -> RecoveryExecutionPermit:
        assert call.recovery_request_id is not None
        permit = RecoveryExecutionPermit(
            state.case_id, call.recovery_request_id, call.id, state.state_revision, uuid4()
        )
        self._permits[permit.token] = permit
        return permit

    def execute_recovery(
        self,
        permit: RecoveryExecutionPermit,
        checkpoints: CheckpointStore,
    ) -> DurableToolExecution:
        if self._permits.pop(permit.token, None) is not permit:
            raise ValueError("recovery permit is absent or already consumed")
        state = checkpoints.load(permit.case_id)
        if state.state_revision != permit.revision:
            from backend.app.services.checkpoints import StateConflictError

            raise StateConflictError("recovery claim revision changed")
        pending = next(call for call in state.tool_calls if call.id == permit.attempt_id)
        if (
            pending.status is not ToolCallStatus.PENDING
            or pending.recovery_request_id != permit.request_id
        ):
            raise ValueError("permit does not identify a pending recovery attempt")
        result, revision = self._run_pending(
            state,
            pending,
            AgentAction.CALL_TOOL,
            lambda candidate, expected: checkpoints.save(candidate, expected_revision=expected),
            permit.revision,
        )
        assert revision is not None
        return DurableToolExecution(result, revision)

    def execute_once(
        self,
        state: InvestigationState,
        *,
        tool_name: str,
        action: AgentAction,
        arguments: dict[str, str],
    ) -> InvestigationState:
        return self._execute(state, tool_name=tool_name, action=action, arguments=arguments)[0]

    def execute_durably(
        self,
        state: InvestigationState,
        *,
        tool_name: str,
        action: AgentAction,
        arguments: dict[str, str],
        checkpoints: CheckpointStore,
        expected_revision: int | None,
    ) -> DurableToolExecution:
        def persist(candidate: InvestigationState, expected: int | None) -> None:
            checkpoints.save(candidate, expected_revision=expected)

        result, persisted_revision = self._execute(
            state,
            tool_name=tool_name,
            action=action,
            arguments=arguments,
            persist=persist,
            expected_revision=expected_revision,
        )
        assert persisted_revision is not None
        return DurableToolExecution(result, persisted_revision)

    def _execute(
        self,
        state: InvestigationState,
        *,
        tool_name: str,
        action: AgentAction,
        arguments: dict[str, str],
        persist: Callable[[InvestigationState, int | None], None] | None = None,
        expected_revision: int | None = None,
    ) -> tuple[InvestigationState, int | None]:
        invocation_id = self._invocation_id(state.case_id, tool_name, arguments)
        existing = effective_tool_calls(state).get(invocation_id)
        if existing is not None:
            return state, expected_revision
        if state.status is not AgentStatus.INVESTIGATING or any(
            call.status is not ToolCallStatus.COMPLETED
            for call in effective_tool_calls(state).values()
        ):
            return state, expected_revision

        call_id = f"tool-{invocation_id}"
        pending = ToolCallRecord(
            id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            status=ToolCallStatus.PENDING,
            created_at=datetime.now(UTC),
            invocation_id=invocation_id,
            attempt_sequence=1,
        )
        current = self.transitions.transition(
            state,
            to_status=AgentStatus.INVESTIGATING,
            action=action,
            reason=f"Prepared business tool call {tool_name}.",
            updates={"tool_calls": [*state.tool_calls, pending]},
        )
        persisted_revision = self._persist(persist, current, expected_revision)
        return self._run_pending(current, pending, action, persist, persisted_revision)

    def _run_pending(
        self,
        current: InvestigationState,
        pending: ToolCallRecord,
        action: AgentAction,
        persist: Callable[[InvestigationState, int | None], None] | None,
        persisted_revision: int | None,
    ) -> tuple[InvestigationState, int | None]:
        tool_name = pending.tool_name
        arguments = {key: str(value) for key, value in pending.arguments.items()}
        running = ToolCallRecord.model_validate(
            {
                **pending.model_dump(),
                "status": ToolCallStatus.RUNNING,
                "attempt_count": 1,
            }
        )
        current = self.transitions.transition(
            current,
            to_status=AgentStatus.INVESTIGATING,
            action=action,
            reason=f"Running business tool {tool_name}.",
            updates={
                "tool_calls": self._replace_call(current, running),
                "tool_recoveries": self._request_status(
                    current, running, ContinuationStatus.RUNNING
                ),
            },
        )
        persisted_revision = self._persist(persist, current, persisted_revision)

        try:
            raw_result = self.registry.execute(tool_name, current, arguments)
            grounded = self._ground(raw_result, current.case_id)
            evidence = merge_evidence_batch(current.evidence, grounded)
        except Exception as error:
            failure_kind, summary = self._classify_failure(tool_name, error)
            failed_call = ToolCallRecord.model_validate(
                {
                    **running.model_dump(),
                    "status": ToolCallStatus.FAILED,
                    "completed_at": datetime.now(UTC),
                    "failure_kind": failure_kind,
                    "error_summary": summary,
                }
            )
            failed = self.transitions.transition(
                current,
                to_status=AgentStatus.WAITING_FOR_HUMAN,
                action=AgentAction.WAIT_FOR_HUMAN,
                reason=f"Business tool {tool_name} failed; manual recovery is required.",
                updates={
                    "tool_calls": self._replace_call(current, failed_call),
                    "human_review_blocks": list(
                        dict.fromkeys(
                            [*(current.human_review_blocks or []), HumanReviewBlock.TOOL_RECOVERY]
                        )
                    ),
                    "tool_recoveries": self._request_status(
                        current, failed_call, ContinuationStatus.SETTLED
                    ),
                },
            )
            persisted_revision = self._persist(persist, failed, persisted_revision)
            return failed, persisted_revision
        completed_call = ToolCallRecord.model_validate(
            {
                **running.model_dump(),
                "status": ToolCallStatus.COMPLETED,
                "completed_at": datetime.now(UTC),
                "result_evidence_ids": list(dict.fromkeys(item.id for item in grounded)),
            }
        )
        gaps = (
            evaluate_scenario_gaps(current.case_id, current.scenario, evidence)
            if current.scenario
            else evaluate_p0_gaps(current.case_id, evidence)
        )
        updates: dict[str, object] = {
            "tool_calls": self._replace_call(current, completed_call),
            "evidence": evidence,
            "evidence_gaps": gaps,
        }
        if isinstance(raw_result, ConsumerMemoryToolResult):
            updates["consumer_memory"] = self.memory.build(current.consumer_id, evidence)
        completed = self.transitions.transition(
            current,
            to_status=AgentStatus.INVESTIGATING,
            action=action,
            reason=f"Grounded and completed business tool {tool_name}.",
            updates=updates,
        )
        persisted_revision = self._persist(persist, completed, persisted_revision)
        return completed, persisted_revision

    @staticmethod
    def _persist(
        persist: Callable[[InvestigationState, int | None], None] | None,
        state: InvestigationState,
        expected_revision: int | None,
    ) -> int | None:
        if persist is None:
            return expected_revision
        persist(state, expected_revision)
        return state.state_revision

    def _classify_failure(self, tool_name: str, error: Exception) -> tuple[ToolFailureKind, str]:
        if isinstance(error, EvidenceContentConflict):
            return ToolFailureKind.NON_RETRYABLE, "Evidence content conflict."
        if isinstance(error, ToolOutcomeUnknownError):
            return ToolFailureKind.UNKNOWN_OUTCOME, "External execution outcome is unknown."
        if isinstance(error, (TimeoutError, ConnectionError)):
            if self.registry.is_side_effect_free(tool_name):
                return ToolFailureKind.RETRYABLE, "Read-only tool is temporarily unavailable."
            return ToolFailureKind.UNKNOWN_OUTCOME, "External execution outcome is unknown."
        return ToolFailureKind.NON_RETRYABLE, "Tool execution failed validation or processing."

    @staticmethod
    def _invocation_id(case_id: str, tool_name: str, arguments: dict[str, str]) -> str:
        return logical_call_id(case_id, tool_name, dict(arguments))

    def _ground(self, result: ToolResult, case_id: str) -> list[Evidence]:
        if isinstance(result, OrderHistoryToolResult):
            return self.grounding.ground_order_history(result, case_id)
        if isinstance(result, ServiceHistoryToolResult):
            return self.grounding.ground_service_history(result, case_id)
        if isinstance(result, ConsumerMemoryToolResult):
            return self.grounding.ground_consumer_memory(result, case_id)
        if isinstance(result, LogisticsStatusToolResult):
            return self.grounding.ground_logistics_status(result, case_id)
        return self.grounding.ground_policy(result, case_id)

    @staticmethod
    def _replace_call(
        state: InvestigationState, replacement: ToolCallRecord
    ) -> list[ToolCallRecord]:
        matches = [call for call in state.tool_calls if call.id == replacement.id]
        if len(matches) != 1:
            raise ValueError("attempt update requires exactly one existing identity")
        old = matches[0]
        fields = (
            "tool_name",
            "arguments",
            "invocation_id",
            "attempt_sequence",
            "previous_attempt_id",
            "recovery_request_id",
            "created_at",
        )
        if any(getattr(old, field) != getattr(replacement, field) for field in fields):
            raise ValueError("attempt identity cannot change")
        return [replacement if call.id == replacement.id else call for call in state.tool_calls]

    @staticmethod
    def _request_status(
        state: InvestigationState, call: ToolCallRecord, status: ContinuationStatus
    ) -> list[ToolRecoveryRecord]:
        return [
            ToolRecoveryRecord.model_validate({**r.model_dump(), "continuation": status})
            if r.request_id == call.recovery_request_id
            else r
            for r in state.tool_recoveries
        ]


def default_tool_registry(
    repositories: BusinessRepositoryBundle | None = None,
) -> ToolRegistry:
    bundle = repositories or DemoRepositoryBundle()
    tools = BusinessToolSet(
        bundle.consumers, bundle.orders, bundle.service_history, bundle.logistics
    )
    registry = ToolRegistry()
    registry.register("get_order_history", tools.get_order_history, side_effect_free=True)
    registry.register("get_service_history", tools.get_service_history, side_effect_free=True)
    registry.register("get_consumer_memory", tools.get_consumer_memory, side_effect_free=True)
    registry.register("get_logistics_status", tools.get_logistics_status, side_effect_free=True)
    # Retained from Phase 2; it is not a Phase 3 P0 business tool.
    registry.register(
        "retrieve_service_policy", retrieve_service_policy_stub, side_effect_free=True
    )
    return registry
