import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.api.app import create_app
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    ContinuationStatus,
    InvestigationState,
    ToolCallStatus,
    ToolFailureKind,
)
from backend.app.domain.evidence import Evidence
from backend.app.persistence.checkpoints import PostgresCheckpointStore
from backend.app.persistence.config import DatabaseSettings
from backend.app.persistence.database import create_database_engine, create_session_factory
from backend.app.persistence.factory import build_postgres_workflow
from backend.app.services.grounding import EvidenceGroundingService
from backend.app.services.tool_recovery import RecoveryError, ToolRecoveryService
from backend.tests.fixtures import CASE_ID, CONSUMER_ID
from backend.tests.test_legacy_tool_states import FIXTURES
from backend.tests.test_phase4_postgres import (
    _seed,
)
from backend.tests.test_phase4_postgres import (
    postgres_engine as _engine_fixture,
)
from backend.tests.test_phase4_postgres import (
    postgres_sessions as _sessions_fixture,
)
from backend.tests.test_tool_recovery import failed_state, request_for

postgres_engine = _engine_fixture
postgres_sessions = _sessions_fixture
pytestmark = pytest.mark.postgres


def test_recovery_pg_api_and_new_engine_preserve_history(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    store = PostgresCheckpointStore(postgres_sessions)
    _, failed = failed_state(store)
    workflow = build_postgres_workflow(postgres_sessions)
    request = request_for(failed)
    url = f"/api/cases/{CASE_ID}/tool-recoveries"
    client = TestClient(create_app(lambda: CaseApplicationService(workflow, store)))
    response = client.post(url, json=request.model_dump(mode="json"))
    assert response.status_code == 201
    engine = create_database_engine(DatabaseSettings(os.environ["TEST_DATABASE_URL"]))
    try:
        restarted = build_postgres_workflow(create_session_factory(engine))
        service = ToolRecoveryService(restarted)
        view, code = service.recover(CASE_ID, request)
        assert code == 200 and view.continuation is ContinuationStatus.SETTLED
        restored = restarted.restore_case(CASE_ID)
        assert restored.tool_calls[0] == failed.tool_calls[0]
        assert len(restored.tool_calls) == 2
        assert restarted.tools.execution_counts == {}
        assert client.get(response.headers["location"]).status_code == 200
    finally:
        engine.dispose()


@pytest.mark.parametrize("same_request", [False, True])
def test_pg_two_claimants_only_winner_gets_permit(
    postgres_sessions: sessionmaker[Session],
    same_request: bool,
) -> None:
    store = PostgresCheckpointStore(postgres_sessions)
    _, failed = failed_state(store)
    barrier = Barrier(2)

    class RacingStore(PostgresCheckpointStore):
        def save(self, state: InvestigationState, *, expected_revision: int | None = None) -> None:
            if state.next_action_reason == "Explicit readonly recovery claimed.":
                barrier.wait(timeout=10)
            super().save(state, expected_revision=expected_revision)

    workflows = [
        InvestigationWorkflow(checkpoint_store=RacingStore(postgres_sessions)) for _ in range(2)
    ]
    requests = [request_for(failed), request_for(failed)]
    if same_request:
        requests[1] = requests[0]

    def claim(index: int) -> tuple[int, object]:
        try:
            return index, ToolRecoveryService(workflows[index]).claim(CASE_ID, requests[index])
        except RecoveryError as error:
            return index, error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    from backend.app.services.tools import RecoveryExecutionPermit

    winners = [(i, permit) for i, permit in results if isinstance(permit, RecoveryExecutionPermit)]
    assert len(winners) == 1
    assert (
        sum(value is None if same_request else value == "REVISION_CONFLICT" for _, value in results)
        == 1
    )
    assert all(w.tools.execution_counts == {} for w in workflows)
    index, permit = winners[0]
    workflows[index].tool_execution.execute_recovery(permit, store)
    assert workflows[index].tools.execution_counts == {"get_order_history": 1}
    assert workflows[1 - index].tools.execution_counts == {}


def test_pg_evidence_conflict_fails_atomically_and_restart_reads_failure(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    store = PostgresCheckpointStore(postgres_sessions)
    _, failed = failed_state(store)
    workflow = build_postgres_workflow(postgres_sessions)
    raw = workflow.tools.execute("get_order_history", failed, {"consumer_id": CONSUMER_ID})
    from backend.app.domain.business import OrderHistoryToolResult

    assert isinstance(raw, OrderHistoryToolResult)
    candidates = EvidenceGroundingService().ground_order_history(raw, CASE_ID)
    original = candidates[-1]
    assert isinstance(original.value, dict)
    conflict = Evidence.model_validate(
        {**original.model_dump(), "value": {**original.value, "quantity": 999}}
    )
    with_conflict = workflow.transitions.transition(
        failed,
        to_status=AgentStatus.INVESTIGATING,
        action=None,
        reason="Fixture previous observation",
        updates={"evidence": [conflict]},
    )
    # Keep the original tool pause while recording the pre-existing observation in this fixture.
    with_conflict = workflow.transitions.transition(
        with_conflict,
        to_status=AgentStatus.WAITING_FOR_HUMAN,
        action=AgentAction.WAIT_FOR_HUMAN,
        reason="Business tool get_order_history failed; manual recovery is required.",
    )
    store.save(with_conflict, expected_revision=failed.state_revision)
    service = ToolRecoveryService(workflow)
    request = request_for(with_conflict)
    view, code = service.recover(CASE_ID, request)
    assert code == 201 and view.failure_kind is ToolFailureKind.NON_RETRYABLE
    assert view.result_evidence_ids == []
    restored = PostgresCheckpointStore(postgres_sessions).load(CASE_ID)
    assert restored.evidence == [conflict]  # no partial additions from earlier candidates
    assert restored.tool_calls[-1].error_summary == "Evidence content conflict."
    assert restored.tool_recoveries[-1].continuation is ContinuationStatus.SETTLED
    assert service.http_status(service.get(CASE_ID, request.request_id)) == 200


def test_completed_recovery_cli_continues_without_requery(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    store = PostgresCheckpointStore(postgres_sessions)
    _, failed = failed_state(store)
    workflow = build_postgres_workflow(postgres_sessions)
    service = ToolRecoveryService(workflow)
    request = request_for(failed)
    permit = service.claim(CASE_ID, request)
    assert permit is not None
    workflow.tool_execution.execute_recovery(permit, store)
    assert service.get(CASE_ID, request.request_id).continuation is ContinuationStatus.RUNNING
    env = dict(
        os.environ,
        DATABASE_URL=os.environ["TEST_DATABASE_URL"],
        LLM_API_KEY="",
        OFFICIAL_DATASET_PATH="",
    )
    command = [
        sys.executable,
        "scripts/resume_completed_recovery.py",
        "--case-id",
        CASE_ID,
        "--request-id",
        str(request.request_id),
    ]
    first = subprocess.run(command, env=env, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(first.stdout)["continuation"] == "SETTLED"
    state = store.load(CASE_ID)
    again = subprocess.run(command, env=env, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(again.stdout)["current_revision"] == state.state_revision
    assert len(state.tool_calls) == 2
    assert state.status is AgentStatus.WAITING_FOR_USER
    # This parent counter covers only the pre-CLI query. It cannot observe child CLI calls.
    # Cross-process zero-query evidence is provided by the W3 observed CLI + positive control.
    assert workflow.tools.execution_counts == {"get_order_history": 1}
    assert service.http_status(service.get(CASE_ID, request.request_id)) == 200


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*_*.json")))
def test_legacy_pg_roundtrip_and_relational_metadata(
    postgres_sessions: sessionmaker[Session], path: Path
) -> None:
    state = InvestigationState.model_validate_json(path.read_bytes())
    store = PostgresCheckpointStore(postgres_sessions)
    store.save(state)
    assert store.load(state.case_id) == state
    workflow = build_postgres_workflow(postgres_sessions)
    restored = workflow.run(state, expected_revision=state.state_revision)
    assert restored.tool_calls == state.tool_calls
    assert workflow.tools.execution_counts == {}
    assert store.load(state.case_id) == restored


@pytest.mark.parametrize("boundary", ["BEFORE_PENDING", "RUNNING", "BEFORE_COMPLETED"])
def test_local_commit_boundary_interruption_then_explicit_recovery(
    postgres_sessions: sessionmaker[Session],
    boundary: str,
) -> None:
    _seed(postgres_sessions)

    class Interrupted(BaseException):
        pass

    class BoundaryStore(PostgresCheckpointStore):
        def save(self, state: InvestigationState, *, expected_revision: int | None = None) -> None:
            call = state.tool_calls[-1] if state.tool_calls else None
            if call is not None and (
                (boundary == "BEFORE_PENDING" and call.status is ToolCallStatus.PENDING)
                or (boundary == "BEFORE_COMPLETED" and call.status is ToolCallStatus.COMPLETED)
            ):
                raise Interrupted
            super().save(state, expected_revision=expected_revision)
            if call is not None and boundary == "RUNNING" and call.status is ToolCallStatus.RUNNING:
                raise Interrupted

    store = PostgresCheckpointStore(postgres_sessions)
    state = InvestigationState(case_id=CASE_ID, consumer_id=CONSUMER_ID, current_issue="test")
    store.save(state)
    first = InvestigationWorkflow(checkpoint_store=BoundaryStore(postgres_sessions))
    with pytest.raises(Interrupted):
        first.run(state, expected_revision=0)
    restored = store.load(CASE_ID)
    restarted = build_postgres_workflow(postgres_sessions)
    if boundary == "BEFORE_PENDING":
        assert restored.tool_calls == []
        result = restarted.run(restored, expected_revision=restored.state_revision)
        assert result.status is AgentStatus.WAITING_FOR_USER
    else:
        assert restored.tool_calls[-1].status is ToolCallStatus.RUNNING
        assert restored.evidence == []
        view, _ = ToolRecoveryService(restarted).recover(CASE_ID, request_for(restored))
        assert view.continuation is ContinuationStatus.SETTLED
        result = store.load(CASE_ID)
        assert result.tool_calls[0] == restored.tool_calls[0]
        assert len(result.tool_calls) == 2
    assert first.tools.execution_counts.get("get_order_history", 0) == (
        1 if boundary == "BEFORE_COMPLETED" else 0
    )
    assert restarted.tools.execution_counts == {"get_order_history": 1}


def test_failure_cas_does_not_overwrite_concurrent_state(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    store = PostgresCheckpointStore(postgres_sessions)
    _, failed = failed_state(store)

    class RacingFailureStore(PostgresCheckpointStore):
        def save(self, state: InvestigationState, *, expected_revision: int | None = None) -> None:
            if state.tool_calls[-1].failure_kind is ToolFailureKind.NON_RETRYABLE:
                current = store.load(CASE_ID)
                newer = InvestigationWorkflow().transitions.transition(
                    current,
                    to_status=AgentStatus.INVESTIGATING,
                    action=AgentAction.CALL_TOOL,
                    reason="Concurrent update before failure write",
                )
                store.save(newer, expected_revision=current.state_revision)
            super().save(state, expected_revision=expected_revision)

    from backend.app.domain.business import OrderHistoryToolResult
    from backend.app.services.tools import ToolRegistry

    registry = ToolRegistry()

    def bad_output(
        _state: InvestigationState, _arguments: dict[str, str]
    ) -> OrderHistoryToolResult:
        raise ValueError("invalid output")

    registry.register("get_order_history", bad_output, side_effect_free=True)
    workflow = InvestigationWorkflow(
        checkpoint_store=RacingFailureStore(postgres_sessions), tool_registry=registry
    )
    with pytest.raises(RecoveryError, match="REVISION_CONFLICT"):
        ToolRecoveryService(workflow).recover(CASE_ID, request_for(failed))
    state = store.load(CASE_ID)
    assert state.tool_calls[-1].status is ToolCallStatus.RUNNING
    assert state.evidence == []
    assert state.next_action_reason == "Concurrent update before failure write"
