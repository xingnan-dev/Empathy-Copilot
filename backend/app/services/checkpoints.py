"""Development-only in-memory checkpoint storage."""

from backend.app.domain.agent import InvestigationState


class InMemoryCheckpointStore:
    """Store serialized state by case id; intentionally not durable across processes."""

    def __init__(self) -> None:
        self._states: dict[str, str] = {}

    def save(self, state: InvestigationState) -> None:
        self._states[state.case_id] = state.model_dump_json()

    def load(self, case_id: str) -> InvestigationState:
        try:
            serialized = self._states[case_id]
        except KeyError as error:
            raise KeyError(f"checkpoint not found for case {case_id}") from error
        return InvestigationState.model_validate_json(serialized)

    def exists(self, case_id: str) -> bool:
        return case_id in self._states

