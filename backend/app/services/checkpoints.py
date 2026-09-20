"""Checkpoint persistence contract and development in-memory implementation."""

from typing import Protocol

from backend.app.domain.agent import InvestigationState


class StateConflictError(RuntimeError):
    """A stale state attempted to overwrite a newer persisted revision."""


class CheckpointStore(Protocol):
    def save(
        self, state: InvestigationState, *, expected_revision: int | None = None
    ) -> None: ...

    def load(self, case_id: str) -> InvestigationState: ...

    def exists(self, case_id: str) -> bool: ...


class InMemoryCheckpointStore:
    """Store serialized state by case id; intentionally not durable across processes."""

    def __init__(self) -> None:
        self._states: dict[str, str] = {}

    def save(
        self, state: InvestigationState, *, expected_revision: int | None = None
    ) -> None:
        if expected_revision is not None and state.case_id in self._states:
            current = InvestigationState.model_validate_json(self._states[state.case_id])
            if current.state_revision != expected_revision:
                raise StateConflictError(
                    f"case {state.case_id} expected revision {expected_revision}, "
                    f"found {current.state_revision}"
                )
        self._states[state.case_id] = state.model_dump_json()

    def load(self, case_id: str) -> InvestigationState:
        try:
            serialized = self._states[case_id]
        except KeyError as error:
            raise KeyError(f"checkpoint not found for case {case_id}") from error
        return InvestigationState.model_validate_json(serialized)

    def exists(self, case_id: str) -> bool:
        return case_id in self._states
