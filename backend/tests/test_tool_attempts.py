from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    ContinuationStatus,
    InvestigationState,
    ToolCallRecord,
    ToolCallStatus,
    ToolFailureKind,
    ToolRecoveryRecord,
    ToolRecoveryRequest,
)
from backend.app.domain.tool_history import logical_call_id
from backend.app.services.tool_attempts import LegacyAmbiguityError, effective_tool_calls
from backend.tests.fixtures import CASE_ID, CONSUMER_ID, NOW


def chain_data() -> dict[str, Any]:
    key = logical_call_id(CASE_ID, "get_order_history", {"consumer_id": CONSUMER_ID})
    parent = ToolCallRecord(
        id="old",
        tool_name="get_order_history",
        arguments={"consumer_id": CONSUMER_ID},
        status=ToolCallStatus.FAILED,
        created_at=NOW,
        completed_at=NOW,
        failure_kind=ToolFailureKind.RETRYABLE,
        error_summary="Unavailable.",
    )
    rid = uuid4()
    child = ToolCallRecord(
        id="new",
        tool_name=parent.tool_name,
        arguments=parent.arguments,
        status=ToolCallStatus.PENDING,
        created_at=datetime.now(UTC),
        invocation_id=key,
        attempt_sequence=2,
        previous_attempt_id=parent.id,
        recovery_request_id=rid,
    )
    record = ToolRecoveryRecord(
        request_id=rid,
        target_attempt_id=parent.id,
        expected_revision=3,
        operator_id="local",
        reason="Retry read",
        previous_process_exited=True,
        new_attempt_id=child.id,
        logical_call_id=key,
        accepted_at=datetime.now(UTC),
        interrupted_status=None,
    )
    return dict(
        case_id=CASE_ID,
        consumer_id=CONSUMER_ID,
        current_issue="test",
        tool_calls=[parent.model_dump(), child.model_dump()],
        tool_recoveries=[record.model_dump()],
    )


def test_selects_explicit_successor_and_preserves_old_failure() -> None:
    state = InvestigationState.model_validate(chain_data())
    assert [c.id for c in effective_tool_calls(state).values()] == ["new"]
    assert state.tool_calls[0].status is ToolCallStatus.FAILED
    assert state.tool_calls[0].attempt_sequence is None
    assert InvestigationState.model_validate_json(state.model_dump_json()) == state


@pytest.mark.parametrize("mutation", ["missing", "sequence", "arguments", "request", "fork"])
def test_bad_chain_is_rejected(mutation: str) -> None:
    data = chain_data()
    child = data["tool_calls"][1]
    if mutation == "missing":
        child["previous_attempt_id"] = "absent"
    if mutation == "sequence":
        child["attempt_sequence"] = 4
    if mutation == "arguments":
        child["arguments"] = {"consumer_id": "other"}
    if mutation == "request":
        data["tool_recoveries"][0]["new_attempt_id"] = "absent"
    if mutation == "fork":
        data["tool_calls"].append({**child, "id": "fork"})
    with pytest.raises(ValidationError):
        InvestigationState.model_validate(data)


def test_ambiguous_legacy_roots_retained_but_execution_refused() -> None:
    data = chain_data()
    parent = data["tool_calls"][0]
    data["tool_calls"] = [parent, {**parent, "id": "other"}]
    data["tool_recoveries"] = []
    state = InvestigationState.model_validate(data)
    with pytest.raises(LegacyAmbiguityError):
        effective_tool_calls(state)


def test_request_fields_are_strict_and_nonblank() -> None:
    data = chain_data()["tool_recoveries"][0]
    fields = ToolRecoveryRequest.model_fields
    request = {k: v for k, v in data.items() if k in fields}
    for change in (
        {"reason": " "},
        {"previous_process_exited": "true"},
        {"expected_revision": True},
        {"extra": "value"},
    ):
        with pytest.raises(ValidationError):
            ToolRecoveryRequest.model_validate({**request, **change})


def test_completed_successor_unblocks_history_but_pending_cannot_execute_normally() -> None:
    data = chain_data()
    pending = InvestigationState.model_validate(data)
    workflow = InvestigationWorkflow()
    assert (
        workflow.tool_execution.execute_once(
            pending,
            tool_name="get_order_history",
            action=AgentAction.CALL_TOOL,
            arguments={"consumer_id": CONSUMER_ID},
        )
        == pending
    )
    assert workflow.tools.execution_counts == {}
    data["tool_calls"][1].update(status=ToolCallStatus.COMPLETED, completed_at=datetime.now(UTC))
    data["tool_recoveries"][0]["continuation"] = ContinuationStatus.RUNNING
    completed = InvestigationState.model_validate(data)
    result = workflow.run(completed)
    assert result.status is AgentStatus.WAITING_FOR_USER
    assert workflow.tools.execution_counts == {}
    passport = workflow.passports.build(result)
    assert len(passport.tool_attempts) == 2 and len(passport.tool_recoveries) == 1
    assert passport.completed_tools == ["get_order_history"]
