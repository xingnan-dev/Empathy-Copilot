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


def test_pg_commit_ack_loss_is_unconfirmed_then_original_replay(
    postgres_sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    from backend.app.services.message_errors import MessageError

    service = message_service(postgres_sessions)
    before = service.get_case("S00154")

    def lose_ack(session: Session) -> None:
        if session.info.get("ack_injected"):
            return
        session.info["ack_injected"] = True
        raise OperationalError("commit ack lost", {}, RuntimeError("injected"))

    event.listen(Session, "after_commit", lose_ack)
    try:
        with pytest.raises(MessageError) as caught:
            service.ingest_message(
                "S00154",
                message="persist once",
                message_id="ack",
                expected_revision=before.revision,
            )
        assert caught.value.code == "MESSAGE_COMMIT_UNCERTAIN"
    finally:
        event.remove(Session, "after_commit", lose_ack)
    service.model_service = None
    replay = service.ingest_message(
        "S00154", message="persist once", message_id="ack", expected_revision=before.revision
    )
    assert replay.message_receipt is not None and replay.message_receipt.replayed
    assert [(m.id, m.sequence) for m in replay.messages if m.origin == "LIVE"] == [("ack", 1)]


def test_pg_model_failure_leaves_no_message_or_revision(
    postgres_sessions: sessionmaker[Session],
) -> None:
    from backend.app.llm.provider import ModelProviderError
    from backend.app.llm.providers.fake import FakeModelProvider
    from backend.app.llm.service import ModelService

    service = message_service(postgres_sessions)
    before = service.checkpoints.load("S00154")
    service.model_service = ModelService(FakeModelProvider(error="UNAVAILABLE"))
    with pytest.raises(ModelProviderError):
        service.ingest_message(
            "S00154",
            message="not accepted",
            message_id="failed-model",
            expected_revision=before.state_revision,
        )
    assert service.checkpoints.load("S00154") == before
    assert not any(m.origin == "LIVE" for m in service.get_case("S00154").messages)


def _process_message(
    url: str, barrier: Any, queue: Any, message_id: str, revision: int, with_evidence: bool
) -> None:
    from backend.app.api.services.case_application_service import CaseApplicationService
    from backend.app.llm.providers.fake import FakeModelProvider
    from backend.app.llm.schemas import ModelOutput
    from backend.app.llm.service import ModelService
    from backend.app.persistence.config import DatabaseSettings
    from backend.app.persistence.database import create_database_engine, create_session_factory
    from backend.app.persistence.factory import build_postgres_workflow
    from backend.app.services.checkpoints import StateConflictError

    engine = create_database_engine(DatabaseSettings(url))

    class RacingProvider(FakeModelProvider):
        def extract_facts(self, context: dict[str, object]) -> ModelOutput:
            barrier.wait(timeout=20)
            return super().extract_facts(context)

    from backend.app.llm.schemas import CandidateFact, CandidateField, UnderstandingResult

    understanding = UnderstandingResult(
        candidate_facts=[
            CandidateFact(field=CandidateField.EXACT_PRODUCT_USED, value="面霜", source_text="面霜")
        ]
        if with_evidence
        else []
    )
    try:
        workflow = build_postgres_workflow(create_session_factory(engine))
        service = CaseApplicationService(
            workflow, workflow.checkpoints, ModelService(RacingProvider(understanding))
        )
        try:
            view = service.ingest_message(
                "S00154",
                message="面霜 process request",
                message_id=message_id,
                expected_revision=revision,
            )
            queue.put(("ok", view.revision, workflow.tools.execution_counts))
        except StateConflictError:
            queue.put(("conflict", None, workflow.tools.execution_counts))
    finally:
        engine.dispose()


@pytest.mark.parametrize("with_evidence", [False, True])
@pytest.mark.parametrize("same_request", [False, True])
def test_pg_independent_processes_compete_for_message(
    postgres_sessions: sessionmaker[Session],
    same_request: bool,
    with_evidence: bool,
) -> None:
    import multiprocessing
    import os

    service = message_service(postgres_sessions)
    before = service.checkpoints.load("S00154")
    ctx = multiprocessing.get_context("spawn")
    barrier, queue = ctx.Barrier(2), ctx.Queue()
    processes = [
        ctx.Process(
            target=_process_message,
            args=(
                os.environ["TEST_DATABASE_URL"],
                barrier,
                queue,
                "same" if same_request else str(i),
                before.state_revision,
                with_evidence,
            ),
        )
        for i in range(2)
    ]
    try:
        for process in processes:
            process.start()
        result = [queue.get(timeout=40) for _ in processes]
        for process in processes:
            process.join(timeout=20)
            assert process.exitcode == 0
        assert sum(r[0] == "ok" for r in result) == (2 if same_request else 1)
        assert all(r[2] == {} for r in result)
        restored = service.get_case("S00154")
        assert restored.revision == before.state_revision + (2 if with_evidence else 1)
        assert [(m.sequence, m.text) for m in restored.messages if m.origin == "LIVE"] == [
            (1, "面霜 process request")
        ]
        restored_state = service.checkpoints.load("S00154")
        assert len(restored_state.evidence) == len(before.evidence) + int(with_evidence)
        assert restored_state.evidence[: len(before.evidence)] == before.evidence
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
        queue.close()


def test_pg_official_history_respects_persisted_cutoff_and_never_upserts_live(
    postgres_sessions: sessionmaker[Session],
) -> None:
    from backend.app.persistence.models import ConsumerRow, ConversationSessionRow, MessageRow
    from backend.app.services.message_errors import MessageError

    service = message_service(postgres_sessions)
    state = service.checkpoints.load("S00154")
    evidence = [
        e.model_copy(
            update={
                "metadata": {
                    **e.metadata,
                    "official_data": True,
                    "official_message_sequence_cutoff": 1,
                }
            }
        )
        for e in state.evidence
    ]
    official = state.model_copy(
        update={"evidence": evidence, "state_revision": state.state_revision + 1}
    )
    service.checkpoints.save(official, expected_revision=state.state_revision)
    now = datetime.now(UTC)
    with postgres_sessions.begin() as session:
        if session.get(ConsumerRow, state.consumer_id) is None:
            session.add(ConsumerRow(consumer_id=state.consumer_id, explicit_preferences=[]))
            session.flush()
        session.add(
            ConversationSessionRow(
                session_id=state.case_id,
                consumer_id=state.consumer_id,
                shop="synthetic",
                scene_major="synthetic",
                scene_minor="synthetic",
                scenario=None,
                started_at=now,
                order_ids=[],
                ticket_ids=[],
            )
        )
        session.flush()
        for i in (1, 2):
            session.add(
                MessageRow(
                    message_id=f"history-{i}",
                    session_id=state.case_id,
                    sequence=i,
                    sent_at=now,
                    consumer_id=state.consumer_id,
                    role="买家",
                    sender="synthetic",
                    text=f"known original {i}",
                    content_type="文本",
                    image_path=None,
                    order_id=None,
                    ticket_id=None,
                )
            )
    view = service.get_case("S00154")
    assert [(m.id, m.text, m.origin) for m in view.messages] == [
        ("history-1", "known original 1", "OFFICIAL")
    ]
    assert view.message_history.historical_complete
    with pytest.raises(MessageError) as collision:
        service.ingest_message(
            "S00154", message="different", message_id="history-1", expected_revision=view.revision
        )
    assert collision.value.code == "MESSAGE_ID_CONFLICT"
    assert service.model_service is not None and service.model_service.calls == []
    with postgres_sessions.begin() as session:
        session.add(
            MessageRow(
                message_id="history-duplicate",
                session_id=state.case_id,
                sequence=1,
                sent_at=now,
                consumer_id=state.consumer_id,
                role="unknown",
                sender="synthetic",
                text="explicit duplicate sequence",
                content_type="文本",
                image_path=None,
                order_id=None,
                ticket_id=None,
            )
        )
    partial = service.get_case("S00154")
    assert not partial.message_history.historical_complete
    assert any(m.role == "UNKNOWN" for m in partial.messages)


def test_pg_missing_message_table_returns_explicit_service_error(
    postgres_sessions: sessionmaker[Session],
) -> None:
    from sqlalchemy import text

    from backend.app.services.message_errors import MessageError

    service = message_service(postgres_sessions)
    # Rename temporarily in one transaction; restore even if the assertion fails.
    with postgres_sessions.begin() as session:
        session.execute(text("ALTER TABLE case_inbound_messages RENAME TO unavailable_messages"))
    try:
        with pytest.raises(MessageError) as error:
            service.get_case("S00154")
        assert error.value.code == "MESSAGE_PERSISTENCE_UNAVAILABLE"
    finally:
        with postgres_sessions.begin() as session:
            session.execute(
                text("ALTER TABLE unavailable_messages RENAME TO case_inbound_messages")
            )


def test_pg_additive_migration_downgrade_preserves_old_snapshot_and_refuses_data_loss(
    postgres_sessions: sessionmaker[Session],
) -> None:
    from alembic import command
    from alembic.config import Config

    service = message_service(postgres_sessions)
    before = service.checkpoints.load("S00154")
    config = Config("alembic.ini")
    command.downgrade(config, "20260924_0002")
    assert service.checkpoints.load("S00154") == before
    command.upgrade(config, "head")
    service.ingest_message(
        "S00154", message="preserve", message_id="no-drop", expected_revision=before.state_revision
    )
    with pytest.raises(RuntimeError, match="Refusing downgrade"):
        command.downgrade(config, "20260924_0002")
    assert service.get_case("S00154").messages[-1].text == "preserve"


def test_pg_committed_replay_does_not_repeat_real_readonly_tool_entries(
    postgres_sessions: sessionmaker[Session],
) -> None:
    from backend.tests.fixtures import initial_state

    service = message_service(postgres_sessions, True)
    from backend.app.domain.gaps import evaluate_p0_gaps

    initial = initial_state()
    initial = initial.model_copy(
        update={"evidence": [], "evidence_gaps": evaluate_p0_gaps(initial.case_id, [])}
    )
    service.checkpoints.save(initial)
    first = service.ingest_message(
        initial.case_id,
        message="面霜",
        message_id="tool-once",
        expected_revision=initial.state_revision,
    )
    counts = dict(service.workflow.tools.execution_counts)
    assert counts.get("get_order_history", 0) == 1
    assert service.model_service is not None and len(service.model_service.calls) == 1
    service.model_service = None
    replay = service.ingest_message(
        initial.case_id,
        message="面霜",
        message_id="tool-once",
        expected_revision=initial.state_revision,
    )
    assert replay.message_receipt is not None and replay.message_receipt.replayed
    assert replay.revision == first.revision
    assert service.workflow.tools.execution_counts == counts


@pytest.mark.parametrize("stored_text", ["  我用的是面霜。\n", None])
def test_pg_live_original_message_matching_or_missing_is_compatible(
    postgres_sessions: sessionmaker[Session], stored_text: str | None
) -> None:
    service = message_service(postgres_sessions, True)
    before = service.checkpoints.load("S00154")
    raw = "  我用的是面霜。\n"
    accepted = service.ingest_message(
        "S00154", message=raw, message_id="provenance", expected_revision=before.state_revision
    )
    state = service.checkpoints.load("S00154")
    ids = accepted.messages[-1].evidence_ids
    assert ids
    for evidence in state.evidence:
        if evidence.id in ids:
            assert evidence.metadata["original_message"] == raw
            if stored_text is None:
                evidence.metadata.pop("original_message")
    if stored_text is None:
        revision = state.state_revision
        state.state_revision += 1
        service.checkpoints.save(state, expected_revision=revision)
    assert service.get_case("S00154").messages[-1].text == raw
    restored = service.checkpoints.load("S00154")
    if stored_text is None:
        assert all("original_message" not in e.metadata for e in restored.evidence if e.id in ids)


def test_pg_provenance_write_conflict_rolls_back_all_state(
    postgres_sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from backend.app.api.app import create_app

    service = message_service(postgres_sessions, True)
    before = service.checkpoints.load("S00154")
    original = service._apply_message

    def mismatched(*args: Any, **kwargs: Any) -> Any:
        for evidence in args[1]:
            evidence.metadata["original_message"] = "different raw text"
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_apply_message", mismatched)
    response = TestClient(create_app(lambda: service)).post(
        "/api/cases/S00154/messages",
        json={
            "message": "面霜",
            "message_id": "conflicting-source",
            "expected_revision": before.state_revision,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "MESSAGE_PROVENANCE_CONFLICT"
    assert service.checkpoints.load("S00154") == before
    with postgres_sessions() as session:
        assert session.scalar(select(CaseInboundMessageRow)) is None


@pytest.mark.parametrize("corrupt_text", ["我用的是面霜。", "  我用的是面霜。\n ", None])
def test_pg_get_live_provenance_conflict_is_explicit_and_never_repaired(
    postgres_sessions: sessionmaker[Session], corrupt_text: str | None
) -> None:
    from fastapi.testclient import TestClient

    from backend.app.api.app import create_app

    service = message_service(postgres_sessions, True)
    before = service.checkpoints.load("S00154")
    raw = "  我用的是面霜。\n"
    accepted = service.ingest_message(
        "S00154", message=raw, message_id="read-conflict", expected_revision=before.state_revision
    )
    state = service.checkpoints.load("S00154")
    for evidence in state.evidence:
        if evidence.id in accepted.messages[-1].evidence_ids:
            evidence.metadata["original_message"] = corrupt_text
    revision = state.state_revision
    state.state_revision += 1
    service.checkpoints.save(state, expected_revision=revision)
    client = TestClient(create_app(lambda: service))
    for response in (
        client.get("/api/cases/S00154"),
        client.post(
            "/api/cases/S00154/messages",
            json={
                "message": raw,
                "message_id": "read-conflict",
                "expected_revision": before.state_revision,
            },
        ),
    ):
        assert response.status_code == 409
        assert response.json()["code"] == "MESSAGE_PROVENANCE_CONFLICT"
    assert service.checkpoints.load("S00154") == state
    with postgres_sessions() as session:
        assert session.scalar(select(CaseInboundMessageRow.text)) == raw
