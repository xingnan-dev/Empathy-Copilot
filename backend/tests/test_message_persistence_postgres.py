from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.fixtures import s00154_waiting_for_human
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
