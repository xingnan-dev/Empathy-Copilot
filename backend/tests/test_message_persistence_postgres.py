from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.fixtures import s00154_waiting_for_human
from backend.app.api.schemas.cases import CaseView
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.llm.schemas import ModelOutput
from backend.app.persistence.checkpoints import (
    PostgresCheckpointStore,
    TransactionBoundCheckpointStore,
)
from backend.app.persistence.models import CaseInboundMessageRow
from backend.tests.test_phase4_postgres import postgres_engine as _engine
from backend.tests.test_phase4_postgres import postgres_sessions as _sessions

postgres_engine = _engine
postgres_sessions = _sessions
pytestmark = pytest.mark.postgres


def test_bound_checkpoint_and_message_roll_back_together(
    postgres_sessions: sessionmaker[Session],
) -> None:
    ordinary = PostgresCheckpointStore(postgres_sessions)
    initial = s00154_waiting_for_human()
    ordinary.save(initial)
    with pytest.raises(RuntimeError, match="abort"):
        with postgres_sessions.begin() as session:
            bound = TransactionBoundCheckpointStore(session)
            updated = initial.model_copy(update={"state_revision": initial.state_revision + 1})
            bound.save(updated, expected_revision=initial.state_revision)
            assert bound.load(initial.case_id).state_revision == updated.state_revision
            assert ordinary.load(initial.case_id).state_revision == initial.state_revision
            session.add(
                CaseInboundMessageRow(
                    case_id=initial.case_id,
                    message_id="atomic",
                    consumer_id=initial.consumer_id,
                    role="CONSUMER",
                    text="raw",
                    received_at=datetime.now(UTC),
                    sequence=1,
                    request_revision=initial.state_revision,
                    accepted_revision=updated.state_revision,
                    evidence_ids=[],
                )
            )
            session.flush()
            raise RuntimeError("abort")
    assert ordinary.load(initial.case_id) == initial
    with postgres_sessions() as session:
        assert session.scalar(select(CaseInboundMessageRow)) is None
    assert "case_inbound_messages" in inspect(postgres_sessions.kw["bind"]).get_table_names()


def test_ordinary_checkpoint_still_commits_each_save(
    postgres_sessions: sessionmaker[Session],
) -> None:
    first = PostgresCheckpointStore(postgres_sessions)
    second = PostgresCheckpointStore(postgres_sessions)
    state = s00154_waiting_for_human()
    first.save(state)
    assert second.load(state.case_id) == state
    changed = state.model_copy(update={"state_revision": state.state_revision + 1})
    first.save(changed, expected_revision=state.state_revision)
    assert second.load(state.case_id) == changed


def message_service(
    sessions: sessionmaker[Session], with_evidence: bool = False
) -> CaseApplicationService:
    from backend.app.llm.providers.fake import FakeModelProvider
    from backend.app.llm.schemas import CandidateFact, CandidateField, UnderstandingResult
    from backend.app.llm.service import ModelService
    from backend.app.persistence.factory import build_postgres_workflow
    from backend.tests.test_phase4_postgres import _seed

    _seed(sessions)
    understanding = UnderstandingResult(
        candidate_facts=[
            CandidateFact(field=CandidateField.EXACT_PRODUCT_USED, value="面霜", source_text="面霜")
        ]
        if with_evidence
        else []
    )
    workflow = build_postgres_workflow(sessions)
    service = CaseApplicationService(
        workflow, workflow.checkpoints, ModelService(FakeModelProvider(understanding))
    )
    service.ensure_integration_fixture()
    return service


@pytest.mark.parametrize("with_evidence", [False, True])
def test_pg_raw_message_replay_and_recreated_workflow(
    postgres_sessions: sessionmaker[Session],
    with_evidence: bool,
) -> None:
    from backend.app.persistence.factory import build_postgres_workflow
    from backend.app.services.message_errors import MessageError

    service = message_service(postgres_sessions, with_evidence)
    before = service.checkpoints.load("S00154")
    text = "  我用的是面霜。\n"
    first = service.ingest_message(
        "S00154", message=text, message_id="stable", expected_revision=before.state_revision
    )
    accepted = service.checkpoints.load("S00154")
    assert first.message_receipt is not None
    assert bool(first.message_receipt.evidence_ids) == with_evidence
    assert first.messages[-1].text == text
    if not with_evidence:
        for key in (
            "step_count",
            "question_count",
            "transition_events",
            "human_review_blocks",
            "status",
            "current_action",
        ):
            # The domain calls intent current_action only in the API, not State.
            if key in type(before).model_fields:
                assert getattr(before, key) == getattr(accepted, key)
        assert accepted.evidence == before.evidence
        assert accepted.state_revision == before.state_revision + 1
    assert service.model_service is not None
    calls = len(service.model_service.calls)
    service.approve("S00154", first.revision)
    service.model_service = None
    replay = service.ingest_message(
        "S00154", message=text, message_id="stable", expected_revision=before.state_revision
    )
    assert replay.message_receipt is not None
    assert replay.message_receipt.replayed and replay.lifecycle == "ESCALATED"
    assert len([m for m in replay.messages if m.origin == "LIVE"]) == 1
    assert calls == 1
    with pytest.raises(MessageError, match="different content"):
        service.ingest_message(
            "S00154",
            message="different",
            message_id="stable",
            expected_revision=before.state_revision,
        )
    restarted = build_postgres_workflow(postgres_sessions)
    restored = CaseApplicationService(restarted, restarted.checkpoints).get_case("S00154")
    assert restored.messages[-1] == first.messages[-1]
    assert restored.message_receipt is None


def test_pg_message_insert_failure_rolls_back_workflow_and_evidence(
    postgres_sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    from backend.app.services.message_errors import MessageError

    service = message_service(postgres_sessions, True)
    before = service.checkpoints.load("S00154")

    def fail_insert(_mapper: Any, _connection: Any, _target: Any) -> None:
        raise OperationalError("injected insert", {}, RuntimeError("disk unavailable"))

    event.listen(CaseInboundMessageRow, "before_insert", fail_insert)
    try:
        with pytest.raises(MessageError) as caught:
            service.ingest_message(
                "S00154",
                message="面霜",
                message_id="failed",
                expected_revision=before.state_revision,
            )
        assert caught.value.code == "MESSAGE_PERSISTENCE_UNAVAILABLE"
    finally:
        event.remove(CaseInboundMessageRow, "before_insert", fail_insert)
    assert service.checkpoints.load("S00154") == before
    assert not any(m.origin == "LIVE" for m in service.get_case("S00154").messages)


@pytest.mark.parametrize("same_request", [False, True])
def test_pg_two_connections_only_winning_message_advances(
    postgres_sessions: sessionmaker[Session],
    same_request: bool,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from backend.app.llm.providers.fake import FakeModelProvider
    from backend.app.llm.service import ModelService
    from backend.app.services.checkpoints import StateConflictError

    service = message_service(postgres_sessions)
    initial = service.get_case("S00154")
    barrier = Barrier(2)

    class RacingProvider(FakeModelProvider):
        def extract_facts(self, context: dict[str, object]) -> ModelOutput:
            barrier.wait(timeout=10)
            return super().extract_facts(context)

    service.model_service = ModelService(RacingProvider())

    def submit(index: int) -> CaseView | None:
        try:
            return service.ingest_message(
                "S00154",
                message="same text",
                message_id="same" if same_request else str(index),
                expected_revision=initial.revision,
            )
        except StateConflictError:
            return None

    with ThreadPoolExecutor(2) as executor:
        result = list(executor.map(submit, range(2)))
    assert sum(r is not None for r in result) == (2 if same_request else 1)
    current = service.get_case("S00154")
    assert current.revision == initial.revision + 1
    assert [(m.sequence, m.text) for m in current.messages if m.origin == "LIVE"] == [
        (1, "same text")
    ]
