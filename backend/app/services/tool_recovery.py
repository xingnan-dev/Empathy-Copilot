"""Explicit, revision-guarded local recovery; HTTP replays never gain execution rights."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

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
    ToolRecoveryRequest,
)
from backend.app.domain.tool_history import logical_call_id
from backend.app.services.checkpoints import StateConflictError
from backend.app.services.review_blocks import recovery_blocks, safety_blocks
from backend.app.services.tool_attempts import LegacyAmbiguityError, effective_tool_calls
from backend.app.services.tools import RecoveryExecutionPermit

if TYPE_CHECKING:
    from backend.app.agent.workflow import InvestigationWorkflow


class RecoveryError(Exception):
    def __init__(self, code: str, status: int = 409) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


class RecoveryView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    request_id: UUID
    logical_call_id: str
    target_attempt_id: str
    attempt_id: str
    attempt_status: ToolCallStatus
    failure_kind: ToolFailureKind | None
    error_summary: str | None
    result_evidence_ids: list[str]
    accepted_revision: int
    current_revision: int
    lifecycle: AgentStatus
    current_action: AgentAction | None
    continuation: ContinuationStatus
    replayed: bool


class ToolRecoveryService:
    ALLOWED_TOOLS = frozenset({"get_order_history"})

    def __init__(self, workflow: "InvestigationWorkflow") -> None:
        self.workflow = workflow
        self.store = workflow.checkpoints

    def _load(self, case_id: str) -> InvestigationState:
        try:
            return self.store.load(case_id)
        except KeyError as error:
            raise RecoveryError("CASE_NOT_FOUND", 404) from error
        except Exception as error:
            raise RecoveryError("RECOVERY_STORAGE_UNAVAILABLE", 503) from error

    def _save(self, state: InvestigationState, revision: int) -> None:
        try:
            self.store.save(state, expected_revision=revision)
        except StateConflictError:
            raise
        except Exception as error:
            raise RecoveryError("RECOVERY_STORAGE_UNAVAILABLE", 503) from error

    @staticmethod
    def _record(state: InvestigationState, request_id: UUID) -> ToolRecoveryRecord | None:
        return next((r for r in state.tool_recoveries if r.request_id == request_id), None)

    @staticmethod
    def _same(record: ToolRecoveryRecord, request: ToolRecoveryRequest) -> bool:
        return all(
            getattr(record, name) == getattr(request, name)
            for name in ToolRecoveryRequest.model_fields
        )

    def claim(self, case_id: str, request: ToolRecoveryRequest) -> RecoveryExecutionPermit | None:
        state = self._load(case_id)
        old = self._record(state, request.request_id)
        if old is not None:
            if not self._same(old, request):
                raise RecoveryError("REQUEST_ID_CONFLICT")
            return None
        if state.state_revision != request.expected_revision:
            raise RecoveryError("REVISION_CONFLICT")
        target = next((c for c in state.tool_calls if c.id == request.target_attempt_id), None)
        if target is None:
            raise RecoveryError("ATTEMPT_NOT_FOUND", 404)
        try:
            effective = effective_tool_calls(state)
        except LegacyAmbiguityError as error:
            raise RecoveryError("LEGACY_AMBIGUITY") from error
        key = logical_call_id(case_id, target.tool_name, target.arguments)
        if effective.get(key) != target:
            raise RecoveryError("ATTEMPT_SUPERSEDED")
        if target.tool_name not in self.ALLOWED_TOOLS:
            raise RecoveryError("RECOVERY_NOT_ALLOWED")
        try:
            read_only = self.workflow.tools.is_side_effect_free(target.tool_name)
        except KeyError:
            read_only = False
        if not read_only or target.status is ToolCallStatus.COMPLETED:
            raise RecoveryError("RECOVERY_NOT_ALLOWED")
        if (
            target.status is ToolCallStatus.FAILED
            and target.failure_kind is not ToolFailureKind.RETRYABLE
        ):
            raise RecoveryError("RECOVERY_NOT_ALLOWED")
        if not request.previous_process_exited:
            raise RecoveryError("PROCESS_EXIT_UNCONFIRMED")
        if any(
            c.id != target.id and c.status is not ToolCallStatus.COMPLETED
            for c in effective.values()
        ):
            raise RecoveryError("HUMAN_REVIEW_BLOCKED")
        if state.status is AgentStatus.WAITING_FOR_HUMAN:
            blocks = recovery_blocks(state, target)
            if blocks != {HumanReviewBlock.TOOL_RECOVERY}:
                raise RecoveryError("HUMAN_REVIEW_BLOCKED")
        elif (
            state.status is AgentStatus.INVESTIGATING
            and target.status in {ToolCallStatus.PENDING, ToolCallStatus.RUNNING}
            and state.current_action is AgentAction.CALL_TOOL
        ):
            blocks = set(state.human_review_blocks or []) | safety_blocks(state)
            if blocks - {HumanReviewBlock.TOOL_RECOVERY}:
                raise RecoveryError("HUMAN_REVIEW_BLOCKED")
        else:
            raise RecoveryError("RECOVERY_NOT_ALLOWED")
        if state.max_steps - state.step_count < 4:
            raise RecoveryError("STEP_BUDGET_EXHAUSTED")
        attempt = ToolCallRecord(
            id=f"attempt-{uuid4()}",
            tool_name=target.tool_name,
            arguments=target.arguments,
            status=ToolCallStatus.PENDING,
            created_at=datetime.now(UTC),
            invocation_id=key,
            attempt_sequence=(target.attempt_sequence or 1) + 1,
            previous_attempt_id=target.id,
            recovery_request_id=request.request_id,
        )
        record = ToolRecoveryRecord(
            **request.model_dump(),
            new_attempt_id=attempt.id,
            logical_call_id=key,
            accepted_at=datetime.now(UTC),
            interrupted_status=(
                target.status
                if target.status in {ToolCallStatus.PENDING, ToolCallStatus.RUNNING}
                else None
            ),
        )
        records = [
            ToolRecoveryRecord.model_validate(
                {**r.model_dump(), "continuation": ContinuationStatus.INTERRUPTED}
            )
            if r.new_attempt_id == target.id
            else r
            for r in state.tool_recoveries
        ]
        claimed = self.workflow.transitions.transition(
            state,
            to_status=AgentStatus.INVESTIGATING,
            action=AgentAction.CALL_TOOL,
            reason="Explicit readonly recovery claimed.",
            updates={
                "tool_calls": [*state.tool_calls, attempt],
                "tool_recoveries": [*records, record],
                "human_review_blocks": [],
                "next_question": None,
            },
        )
        try:
            self._save(claimed, request.expected_revision)
        except StateConflictError as error:
            current = self._load(case_id)
            winner = self._record(current, request.request_id)
            if winner is not None:
                if self._same(winner, request):
                    return None
                raise RecoveryError("REQUEST_ID_CONFLICT") from error
            raise RecoveryError("REVISION_CONFLICT") from error
        return self.workflow.tool_execution._issue_permit(claimed, attempt)

    def recover(self, case_id: str, request: ToolRecoveryRequest) -> tuple[RecoveryView, int]:
        permit = self.claim(case_id, request)
        if permit is None:
            view = self.get(case_id, request.request_id, replayed=True)
            return view, self.http_status(view)
        try:
            execution = self.workflow.tool_execution.execute_recovery(permit, self.store)
            if execution.state.status is AgentStatus.INVESTIGATING:
                self.workflow.run(execution.state, expected_revision=execution.persisted_revision)
        except StateConflictError as error:
            raise RecoveryError("REVISION_CONFLICT") from error
        except Exception as error:
            raise RecoveryError("RECOVERY_STORAGE_UNAVAILABLE", 503) from error
        view = self.get(case_id, request.request_id)
        return view, 201

    def get(self, case_id: str, request_id: UUID, *, replayed: bool = False) -> RecoveryView:
        state = self._load(case_id)
        record = self._record(state, request_id)
        if record is None:
            raise RecoveryError("RECOVERY_NOT_FOUND", 404)
        call = next(c for c in state.tool_calls if c.id == record.new_attempt_id)
        return RecoveryView(
            case_id=case_id,
            request_id=request_id,
            logical_call_id=record.logical_call_id,
            target_attempt_id=record.target_attempt_id,
            attempt_id=call.id,
            attempt_status=call.status,
            failure_kind=call.failure_kind,
            error_summary=call.error_summary,
            result_evidence_ids=call.result_evidence_ids,
            accepted_revision=record.expected_revision + 1,
            current_revision=state.state_revision,
            lifecycle=state.status,
            current_action=state.current_action,
            continuation=record.continuation,
            replayed=replayed,
        )

    @staticmethod
    def http_status(view: RecoveryView) -> int:
        return (
            200
            if view.continuation in {ContinuationStatus.SETTLED, ContinuationStatus.INTERRUPTED}
            else 202
        )

    def resume_completed(self, case_id: str, request_id: UUID) -> InvestigationState:
        state = self._load(case_id)
        record = self._record(state, request_id)
        if record is None:
            raise RecoveryError("RECOVERY_NOT_FOUND", 404)
        if record.continuation is ContinuationStatus.SETTLED:
            return state
        leaves = effective_tool_calls(state)
        call = leaves.get(record.logical_call_id)
        if (
            call is None
            or call.id != record.new_attempt_id
            or (
                call.status is not ToolCallStatus.COMPLETED
                or record.continuation is not ContinuationStatus.RUNNING
                or state.status is not AgentStatus.INVESTIGATING
            )
        ):
            raise RecoveryError("RECOVERY_NOT_ALLOWED")
        return self.workflow.run(state, expected_revision=state.state_revision)
