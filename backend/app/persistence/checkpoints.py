"""Durable, validated, optimistic-concurrency-safe PostgreSQL checkpoints."""

from collections.abc import Callable
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.domain.agent import InvestigationState
from backend.app.services.checkpoints import StateConflictError

from .models import InvestigationCheckpointRow

SessionFactory = Callable[[], Session]


class PostgresCheckpointStore:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def save(
        self, state: InvestigationState, *, expected_revision: int | None = None
    ) -> None:
        snapshot = state.model_dump(mode="json")
        if expected_revision is not None and state.state_revision <= expected_revision:
            raise StateConflictError(
                "persisted state revision must advance beyond the expected revision"
            )
        with self._sessions() as session, session.begin():
            if expected_revision is None:
                self._insert(session, state, snapshot)
                return
            result = session.execute(
                update(InvestigationCheckpointRow)
                .where(
                    InvestigationCheckpointRow.case_id == state.case_id,
                    InvestigationCheckpointRow.state_revision == expected_revision,
                )
                .values(
                    consumer_id=state.consumer_id,
                    state_schema_version=state.state_schema_version,
                    state_revision=state.state_revision,
                    state_snapshot=snapshot,
                    updated_at=state.updated_at,
                )
            )
            if not isinstance(result, CursorResult) or result.rowcount != 1:
                raise StateConflictError(
                    f"case {state.case_id} no longer has revision {expected_revision}"
                )

    @staticmethod
    def _insert(
        session: Session, state: InvestigationState, snapshot: dict[str, Any]
    ) -> None:
        session.add(
            InvestigationCheckpointRow(
                case_id=state.case_id,
                consumer_id=state.consumer_id,
                state_schema_version=state.state_schema_version,
                state_revision=state.state_revision,
                state_snapshot=snapshot,
                updated_at=state.updated_at,
            )
        )
        try:
            session.flush()
        except IntegrityError as error:
            raise StateConflictError(
                f"checkpoint already exists for case {state.case_id}"
            ) from error

    def load(self, case_id: str) -> InvestigationState:
        with self._sessions() as session:
            row = session.scalar(
                select(InvestigationCheckpointRow).where(
                    InvestigationCheckpointRow.case_id == case_id
                )
            )
            if row is None:
                raise KeyError(f"checkpoint not found for case {case_id}")
            state = InvestigationState.model_validate(row.state_snapshot)
            if (
                state.case_id != row.case_id
                or state.consumer_id != row.consumer_id
                or state.state_schema_version != row.state_schema_version
                or state.state_revision != row.state_revision
            ):
                raise ValueError("checkpoint metadata does not match validated State snapshot")
            return state

    def exists(self, case_id: str) -> bool:
        with self._sessions() as session:
            return (
                session.scalar(
                    select(InvestigationCheckpointRow.case_id).where(
                        InvestigationCheckpointRow.case_id == case_id
                    )
                )
                is not None
            )
