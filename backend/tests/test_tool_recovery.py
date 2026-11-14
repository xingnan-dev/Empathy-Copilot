from dataclasses import replace
from typing import Never
from uuid import uuid4

import pytest

from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    ContinuationStatus,
    HumanReviewBlock,
    InvestigationState,
    ToolCallRecord,
    ToolCallStatus,
    ToolFailureKind,
    ToolRecoveryRequest,
)
from backend.app.services.checkpoints import (
    CheckpointStore,
    InMemoryCheckpointStore,
    StateConflictError,
)
from backend.app.services.tool_recovery import RecoveryError, ToolRecoveryService
from backend.app.services.tools import ToolOutcomeUnknownError, ToolRegistry
from backend.tests.fixtures import CASE_ID, CONSUMER_ID


def failed_state(
    store: CheckpointStore | None = None,
) -> tuple[CheckpointStore, InvestigationState]:
    store = store or InMemoryCheckpointStore()
    registry = ToolRegistry()

    def fail(_state: InvestigationState, _args: dict[str, str]) -> Never:
        raise TimeoutError("secret-not-to-store")

    registry.register("get_order_history", fail, side_effect_free=True)
    state = InvestigationWorkflow(checkpoint_store=store, tool_registry=registry).run(
        InvestigationState(case_id=CASE_ID, consumer_id=CONSUMER_ID, current_issue="local query")
    )
    return store, state


def request_for(state: InvestigationState) -> ToolRecoveryRequest:
    return ToolRecoveryRequest(
        request_id=uuid4(),
        target_attempt_id=state.tool_calls[-1].id,
        expected_revision=state.state_revision,
        operator_id="local-operator",
        reason="Previous API exited; retry readonly query",
        previous_process_exited=True,
    )


def test_success_replays_and_preserves_failure_and_provenance() -> None:
    store, failed = failed_state()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    service = ToolRecoveryService(workflow)
    request = request_for(failed)
    view, code = service.recover(CASE_ID, request)
    assert code == 201 and view.continuation is ContinuationStatus.SETTLED
    assert view.lifecycle is AgentStatus.WAITING_FOR_USER
    restored = store.load(CASE_ID)
    assert restored.tool_calls[0] == failed.tool_calls[0]
    assert restored.tool_calls[1].attempt_sequence == 2
    assert all(e.source.source_id for e in restored.evidence)
    again, code = service.recover(CASE_ID, request)
    assert code == 200 and again.replayed
    assert again.current_revision == view.current_revision
    assert workflow.tools.execution_counts == {"get_order_history": 1}
    assert len(restored.transition_events) == len(failed.transition_events) + 4
    assert service.get(CASE_ID, request.request_id).continuation is ContinuationStatus.SETTLED
    with pytest.raises(RecoveryError, match="REQUEST_ID_CONFLICT"):
        service.recover(CASE_ID, request.model_copy(update={"reason": "different"}))


def test_claim_is_atomic_and_replay_never_grants_execution() -> None:
    store, failed = failed_state()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    service = ToolRecoveryService(workflow)
    request = request_for(failed)
    permit = service.claim(CASE_ID, request)
    assert permit is not None
    assert service.claim(CASE_ID, request) is None
    assert workflow.tools.execution_counts == {}
    with pytest.raises(RecoveryError, match="REVISION_CONFLICT"):
        service.claim(CASE_ID, request_for(failed))
    view, code = service.recover(CASE_ID, request)
    assert code == 202 and view.attempt_status is ToolCallStatus.PENDING
    forged = replace(permit, token=uuid4())
    with pytest.raises(ValueError, match="permit"):
        workflow.tool_execution.execute_recovery(forged, store)
    execution = workflow.tool_execution.execute_recovery(permit, store)
    assert execution.state.tool_calls[-1].status is ToolCallStatus.COMPLETED
    with pytest.raises(ValueError, match="permit"):
        workflow.tool_execution.execute_recovery(permit, store)
    assert workflow.tools.execution_counts == {"get_order_history": 1}


def test_restart_pending_requires_new_request_and_preserves_attempts() -> None:
    store, failed = failed_state()
    first = ToolRecoveryService(InvestigationWorkflow(checkpoint_store=store))
    request = request_for(failed)
    first.claim(CASE_ID, request)
    restarted = InvestigationWorkflow(checkpoint_store=store)
    pending = store.load(CASE_ID)
    stopped = restarted.run(pending, expected_revision=pending.state_revision)
    assert stopped.status is AgentStatus.WAITING_FOR_HUMAN
    assert restarted.tools.execution_counts == {}
    view, _ = ToolRecoveryService(restarted).recover(CASE_ID, request_for(stopped))
    assert view.continuation is ContinuationStatus.SETTLED
    state = store.load(CASE_ID)
    assert len(state.tool_calls) == 3
    assert state.tool_recoveries[0].continuation is ContinuationStatus.INTERRUPTED
    assert state.tool_calls[1].status is ToolCallStatus.PENDING


def test_completed_offline_continuation_settles_without_tool_execution() -> None:
    store, failed = failed_state()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    service = ToolRecoveryService(workflow)
    request = request_for(failed)
    permit = service.claim(CASE_ID, request)
    assert permit is not None
    execution = workflow.tool_execution.execute_recovery(permit, store)
    assert execution.state.tool_recoveries[-1].continuation is ContinuationStatus.RUNNING
    restarted = InvestigationWorkflow(checkpoint_store=store)
    after = ToolRecoveryService(restarted)
    assert after.http_status(after.get(CASE_ID, request.request_id)) == 202
    result = after.resume_completed(CASE_ID, request.request_id)
    assert result.status is AgentStatus.WAITING_FOR_USER
    assert restarted.tools.execution_counts == {}
    assert after.http_status(after.get(CASE_ID, request.request_id)) == 200
    assert after.resume_completed(CASE_ID, request.request_id) == result


@pytest.mark.parametrize(
    "block",
    [
        HumanReviewBlock.OTHER,
        HumanReviewBlock.BUSINESS_REVIEW,
        HumanReviewBlock.SAFETY,
        HumanReviewBlock.QUESTION_LIMIT,
    ],
)
def test_other_review_reasons_cannot_be_cleared(block: HumanReviewBlock) -> None:
    store, state = failed_state()
    changed = InvestigationState.model_validate(
        {**state.model_dump(), "human_review_blocks": [block]}
    )
    store.save(changed)
    with pytest.raises(RecoveryError, match="HUMAN_REVIEW_BLOCKED"):
        ToolRecoveryService(InvestigationWorkflow(checkpoint_store=store)).recover(
            CASE_ID, request_for(changed)
        )
    assert store.load(CASE_ID) == changed


def test_exit_declaration_budget_and_legacy_unknown_reason_are_rejected() -> None:
    store, state = failed_state()
    service = ToolRecoveryService(InvestigationWorkflow(checkpoint_store=store))
    with pytest.raises(RecoveryError, match="PROCESS_EXIT_UNCONFIRMED"):
        service.recover(
            CASE_ID, request_for(state).model_copy(update={"previous_process_exited": False})
        )
    limited = InvestigationState.model_validate(
        {**state.model_dump(), "max_steps": state.step_count + 3}
    )
    store.save(limited)
    with pytest.raises(RecoveryError, match="STEP_BUDGET_EXHAUSTED"):
        service.recover(CASE_ID, request_for(limited))
    unknown = InvestigationState.model_validate(
        {**state.model_dump(), "human_review_blocks": None, "next_action_reason": "unknown"}
    )
    store.save(unknown)
    with pytest.raises(RecoveryError, match="HUMAN_REVIEW_BLOCKED"):
        service.recover(CASE_ID, request_for(unknown))


def test_lost_claim_commit_receipt_does_not_execute_on_replay() -> None:
    class LostReceipt(InMemoryCheckpointStore):
        lose = False

        def save(self, state: InvestigationState, *, expected_revision: int | None = None) -> None:
            super().save(state, expected_revision=expected_revision)
            if self.lose:
                self.lose = False
                raise OSError("lost database receipt")

    store = LostReceipt()
    _, state = failed_state(store)
    service = ToolRecoveryService(InvestigationWorkflow(checkpoint_store=store))
    request = request_for(state)
    store.lose = True
    with pytest.raises(RecoveryError, match="RECOVERY_STORAGE_UNAVAILABLE"):
        service.recover(CASE_ID, request)
    view, code = service.recover(CASE_ID, request)
    assert code == 202 and view.attempt_status is ToolCallStatus.PENDING
    assert service.workflow.tools.execution_counts == {}


def test_consumed_stale_permit_cannot_execute() -> None:
    store, failed = failed_state()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    service = ToolRecoveryService(workflow)
    permit = service.claim(CASE_ID, request_for(failed))
    assert permit is not None
    current = store.load(CASE_ID)
    advanced = workflow.transitions.transition(
        current,
        to_status=AgentStatus.INVESTIGATING,
        action=AgentAction.CALL_TOOL,
        reason="Concurrent update",
    )
    store.save(advanced, expected_revision=current.state_revision)
    with pytest.raises(StateConflictError):
        workflow.tool_execution.execute_recovery(permit, store)
    assert workflow.tools.execution_counts == {}


def test_ordinary_executor_cannot_bypass_pause_with_different_arguments() -> None:
    store, state = failed_state()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    for tool, arguments in [
        ("get_order_history", {"consumer_id": "different"}),
        ("get_service_history", {"consumer_id": CONSUMER_ID}),
    ]:
        assert (
            workflow.tool_execution.execute_once(
                state, tool_name=tool, action=AgentAction.CALL_TOOL, arguments=arguments
            )
            == state
        )
    assert workflow.tools.execution_counts == {}


@pytest.mark.parametrize("kind", [ToolFailureKind.UNKNOWN_OUTCOME, ToolFailureKind.NON_RETRYABLE])
def test_forbidden_failure_kinds_are_not_recoverable(kind: ToolFailureKind) -> None:
    store, state = failed_state()
    call = ToolCallRecord.model_validate(
        {**state.tool_calls[-1].model_dump(), "failure_kind": kind}
    )
    state = InvestigationState.model_validate({**state.model_dump(), "tool_calls": [call]})
    store.save(state)
    workflow = InvestigationWorkflow(checkpoint_store=store)
    with pytest.raises(RecoveryError, match="RECOVERY_NOT_ALLOWED"):
        ToolRecoveryService(workflow).recover(CASE_ID, request_for(state))
    assert workflow.tools.execution_counts == {}


def test_exactly_four_steps_allows_recovery() -> None:
    store, state = failed_state()
    state = InvestigationState.model_validate(
        {**state.model_dump(), "max_steps": state.step_count + 4}
    )
    store.save(state)
    view, _ = ToolRecoveryService(InvestigationWorkflow(checkpoint_store=store)).recover(
        CASE_ID, request_for(state)
    )
    assert view.continuation is ContinuationStatus.SETTLED
    assert store.load(CASE_ID).step_count == state.max_steps


def test_unknown_side_effect_fixture_never_retries() -> None:
    markers = []
    registry = ToolRegistry()

    def lost_receipt(_state: InvestigationState, _args: dict[str, str]) -> Never:
        markers.append("external-marker")
        raise ToolOutcomeUnknownError("response lost")

    registry.register("get_order_history", lost_receipt, side_effect_free=False)
    workflow = InvestigationWorkflow(tool_registry=registry)
    state = workflow.run(
        InvestigationState(case_id=CASE_ID, consumer_id=CONSUMER_ID, current_issue="test")
    )
    assert state.tool_calls[-1].failure_kind is ToolFailureKind.UNKNOWN_OUTCOME
    with pytest.raises(RecoveryError, match="RECOVERY_NOT_ALLOWED"):
        ToolRecoveryService(workflow).recover(CASE_ID, request_for(state))
    assert markers == ["external-marker"]
