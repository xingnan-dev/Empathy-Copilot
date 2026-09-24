import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, inspect, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from backend.app.agent.guardrails import AttributionDecision, assess_attribution
from backend.app.api.fixtures import s00154_waiting_for_human
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.domain.agent import AgentStatus, InvestigationState, QuestionStatus, ToolCallStatus
from backend.app.domain.gaps import GapStatus, GapType, evaluate_p0_gaps
from backend.app.domain.regimen import build_regimen_changes
from backend.app.llm.providers.fake import FakeModelProvider
from backend.app.llm.schemas import CandidateFact, CandidateField, UnderstandingResult
from backend.app.llm.service import ModelService
from backend.app.persistence.checkpoints import PostgresCheckpointStore
from backend.app.persistence.config import DatabaseSettings
from backend.app.persistence.database import create_database_engine, create_session_factory
from backend.app.persistence.factory import build_postgres_workflow
from backend.app.persistence.models import (
    ConsumerRow,
    InvestigationCheckpointRow,
    OrderRow,
    ServiceRecordRow,
)
from backend.app.persistence.seed import seed_demo_data_transactionally
from backend.app.repositories.postgres import PostgresRepositoryBundle
from backend.app.services.checkpoints import StateConflictError
from backend.tests.fixtures import CASE_ID, CONSUMER_ID, NOW, first_use_evidence


def _initial_state() -> InvestigationState:
    return InvestigationState(
        case_id=CASE_ID,
        consumer_id=CONSUMER_ID,
        current_issue="我刚买的 C 精华用了以后感觉有点不舒服。",
        evidence=[],
        evidence_gaps=evaluate_p0_gaps(CASE_ID, []),
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    settings = DatabaseSettings(value)
    settings.validate(test=True)
    engine = create_database_engine(settings)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    old_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = value
    try:
        command.upgrade(Config("alembic.ini"), "head")
        yield engine
    finally:
        if old_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_database_url
        engine.dispose()


@pytest.fixture()
def postgres_sessions(
    postgres_engine: Engine,
) -> Iterator[sessionmaker[Session]]:
    sessions = create_session_factory(postgres_engine)
    with postgres_engine.begin() as connection:
        for table in (
            "investigation_checkpoints",
            "service_records",
            "orders",
            "consumers",
        ):
            connection.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    yield sessions


def _seed(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        seed_demo_data_transactionally(session)


@pytest.mark.postgres
def test_migration_from_empty_database_created_phase4_schema(
    postgres_engine: Engine,
) -> None:
    tables = set(inspect(postgres_engine).get_table_names())
    assert {
        "alembic_version",
        "consumers",
        "orders",
        "service_records",
        "investigation_checkpoints",
    } <= tables


@pytest.mark.postgres
def test_phase6_model_evidence_and_gap_survive_service_restart(
    postgres_sessions: sessionmaker[Session],
) -> None:
    workflow = build_postgres_workflow(postgres_sessions)
    provider = FakeModelProvider(
        UnderstandingResult(
            candidate_facts=[
                CandidateFact(
                    field=CandidateField.EXACT_PRODUCT_USED,
                    value="Firming Cream",
                    source_text="礼盒里的面霜",
                )
            ]
        )
    )
    service = CaseApplicationService(workflow, workflow.checkpoints, ModelService(provider))
    service.ensure_integration_fixture()
    before = service.get_case("S00154")
    changed = service.ingest_message(
        "S00154",
        message="我实际用的是礼盒里的面霜。",
        message_id="M-PG-P6",
        expected_revision=before.revision,
    )

    restarted_workflow = build_postgres_workflow(postgres_sessions)
    restarted = CaseApplicationService(restarted_workflow, restarted_workflow.checkpoints)
    restored = restarted.get_case("S00154")

    assert restored.revision == changed.revision
    assert any(item.source == "Consumer message · M-PG-P6" for item in restored.evidence)
    assert next(gap for gap in restored.gaps if gap.id == "EXACT_PRODUCT_USED").status == "RESOLVED"
    assert restored.attribution_status == "INSUFFICIENT_EVIDENCE"


@pytest.mark.postgres
def test_demo_seed_is_idempotent(postgres_sessions: sessionmaker[Session]) -> None:
    _seed(postgres_sessions)
    _seed(postgres_sessions)
    with postgres_sessions() as session:
        assert session.scalar(select(func.count()).select_from(ConsumerRow)) == 1
        assert session.scalar(select(func.count()).select_from(OrderRow)) == 3
        assert session.scalar(select(func.count()).select_from(ServiceRecordRow)) == 1


@pytest.mark.postgres
def test_postgres_business_repositories_return_typed_records(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    repositories = PostgresRepositoryBundle(postgres_sessions)
    consumer = repositories.consumers.get(CONSUMER_ID)
    orders = repositories.orders.list_for_consumer(CONSUMER_ID)
    service = repositories.service_history.list_for_consumer(CONSUMER_ID)
    assert consumer is not None and consumer.consumer_id == CONSUMER_ID
    assert {order.order_id for order in orders} >= {"A1024", "A1010"}
    assert service[0].service_record_id == "SR1001"


@pytest.mark.postgres
def test_postgres_tool_path_preserves_purchase_usage_boundary(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    workflow = build_postgres_workflow(postgres_sessions)
    waiting = workflow.run(_initial_state())
    order = next(item for item in waiting.evidence if item.source.source_id == "A1024")
    assert order.key == "first_purchase"
    assert order.source.source_type.value == "ORDER_SYSTEM"
    assert all(item.key != "actual_first_use_time" for item in waiting.evidence)
    assert build_regimen_changes(CASE_ID, waiting.evidence) == []
    gap = next(
        item for item in waiting.evidence_gaps if item.gap_type is GapType.ACTUAL_FIRST_USE_TIME
    )
    assert gap.status is GapStatus.OPEN


@pytest.mark.postgres
def test_checkpoint_roundtrip_preserves_full_validated_state(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    workflow = build_postgres_workflow(postgres_sessions)
    waiting = workflow.run(_initial_state())
    resumed = workflow.resume_with_evidence(waiting, [first_use_evidence()])

    restored = PostgresCheckpointStore(postgres_sessions).load(CASE_ID)
    assert restored == resumed
    assert restored.state_revision == resumed.state_revision
    assert restored.step_count == resumed.step_count
    assert restored.transition_events == resumed.transition_events
    assert restored.consumer_memory == resumed.consumer_memory
    assert restored.asked_questions[0].status is QuestionStatus.ANSWERED
    assert restored.asked_questions[0].answered_by_evidence_ids == ["ev_m102_first_use"]
    assert all(call.status is ToolCallStatus.COMPLETED for call in restored.tool_calls)
    assert build_regimen_changes(CASE_ID, restored.evidence) == build_regimen_changes(
        CASE_ID, resumed.evidence
    )


@pytest.mark.postgres
def test_invalid_persisted_state_is_rejected(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    workflow = build_postgres_workflow(postgres_sessions)
    workflow.run(_initial_state())
    with postgres_sessions.begin() as session:
        row = session.get(InvestigationCheckpointRow, CASE_ID)
        assert row is not None
        broken = dict(row.state_snapshot)
        broken["consumer_id"] = "wrong_consumer"
        session.execute(
            update(InvestigationCheckpointRow)
            .where(InvestigationCheckpointRow.case_id == CASE_ID)
            .values(state_snapshot=broken)
        )
    with pytest.raises(ValueError):
        PostgresCheckpointStore(postgres_sessions).load(CASE_ID)


@pytest.mark.postgres
def test_stale_revision_conflicts_and_rolls_back(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    store = PostgresCheckpointStore(postgres_sessions)
    original = build_postgres_workflow(postgres_sessions).run(_initial_state())
    stale_a = store.load(CASE_ID)
    stale_b = store.load(CASE_ID)
    data_a = stale_a.model_dump()
    data_a["state_revision"] = stale_a.state_revision + 1
    data_a["updated_at"] = datetime.now(UTC)
    newer = InvestigationState.model_validate(data_a)
    store.save(newer, expected_revision=stale_a.state_revision)

    data_b = stale_b.model_dump()
    data_b["state_revision"] = stale_b.state_revision + 1
    data_b["updated_at"] = datetime.now(UTC)
    with pytest.raises(StateConflictError):
        store.save(
            InvestigationState.model_validate(data_b),
            expected_revision=stale_b.state_revision,
        )
    persisted = store.load(CASE_ID)
    assert persisted.state_revision == newer.state_revision
    assert persisted.state_revision == original.state_revision + 1


@pytest.mark.postgres
def test_golden_demo_survives_new_engine_session_and_workflow(
    postgres_engine: Engine,
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    workflow_a = build_postgres_workflow(postgres_sessions)
    waiting = workflow_a.run(_initial_state())
    assert waiting.status is AgentStatus.WAITING_FOR_USER

    second_engine = create_database_engine(DatabaseSettings(os.environ["TEST_DATABASE_URL"]))
    try:
        second_sessions = create_session_factory(second_engine)
        workflow_b = build_postgres_workflow(second_sessions)
        restored = workflow_b.restore_case(CASE_ID)
        assert restored == waiting
        assert restored.tool_calls[0].status is ToolCallStatus.COMPLETED
        resumed = workflow_b.resume_case(CASE_ID, [first_use_evidence()])
        assert resumed.asked_questions[0].status is QuestionStatus.ANSWERED
        assert (
            sum(
                question.gap_type is GapType.ACTUAL_FIRST_USE_TIME
                for question in resumed.asked_questions
            )
            == 1
        )
        assert workflow_b.tools.execution_counts.get("get_order_history", 0) == 0
        resolved = next(
            gap for gap in resumed.evidence_gaps if gap.gap_type is GapType.ACTUAL_FIRST_USE_TIME
        )
        assert resolved.status is GapStatus.RESOLVED
    finally:
        second_engine.dispose()


@pytest.mark.postgres
def test_repeat_contact_regenerates_passport_and_safe_attribution(
    postgres_sessions: sessionmaker[Session],
) -> None:
    _seed(postgres_sessions)
    first = build_postgres_workflow(postgres_sessions)
    waiting = first.run(_initial_state())
    first.resume_with_evidence(waiting, [first_use_evidence()])

    restarted = build_postgres_workflow(postgres_sessions)
    state = restarted.restore_case(CASE_ID)
    passport = restarted.context_passport(CASE_ID)
    assert passport.confirmed_facts
    assert passport.asked_questions[0].status is QuestionStatus.ANSWERED
    assert GapType.FEEDBACK_ONSET_TIME in passport.open_gaps
    assert {"get_order_history", "get_service_history", "get_consumer_memory"} <= set(
        passport.completed_tools
    )
    decision = assess_attribution(state, "c_serum", build_regimen_changes(CASE_ID, state.evidence))
    assert decision.decision is AttributionDecision.INSUFFICIENT_EVIDENCE


@pytest.mark.postgres
def test_phase5_approval_survives_new_service_and_postgres_session(
    postgres_sessions: sessionmaker[Session],
) -> None:
    store = PostgresCheckpointStore(postgres_sessions)
    initial = s00154_waiting_for_human()
    store.save(initial)
    first = CaseApplicationService(build_postgres_workflow(postgres_sessions), store)
    approved = first.approve(initial.case_id, initial.state_revision)
    assert approved.human_checkpoint.state == "APPROVED"

    restarted_store = PostgresCheckpointStore(postgres_sessions)
    restarted = CaseApplicationService(build_postgres_workflow(postgres_sessions), restarted_store)
    restored = restarted.get_case(initial.case_id)
    assert restored.revision == approved.revision
    assert restored.lifecycle == "ESCALATED"
    assert restored.human_checkpoint.state == "APPROVED"
