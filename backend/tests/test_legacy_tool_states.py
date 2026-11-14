import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import AgentStatus, InvestigationState, ToolCallStatus
from backend.app.services.checkpoints import InMemoryCheckpointStore

FIXTURES = Path(__file__).parent / "fixtures/legacy_tool_states"


@pytest.mark.parametrize(
    "name",
    [
        "competition_completed",
        "competition_pending",
        "competition_running",
        "e31_completed",
        "e31_pending",
        "e31_running",
        "e31_failed",
    ],
)
def test_real_legacy_snapshot_load_save_and_continue(name: str) -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text("utf-8"))
    entry = next(item for item in manifest["files"] if item["file"] == name + ".json")
    data = (FIXTURES / entry["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    state = InvestigationState.model_validate_json(data)
    assert state.state_schema_version == 1
    assert state.tool_calls[0].attempt_sequence is None
    store = InMemoryCheckpointStore()
    store.save(state)
    assert store.load(state.case_id) == state
    workflow = InvestigationWorkflow(checkpoint_store=store)
    result = workflow.run(state, expected_revision=state.state_revision)
    assert workflow.tools.execution_counts == {}
    assert result.tool_calls == state.tool_calls
    if state.tool_calls[0].status is not ToolCallStatus.COMPLETED:
        assert result.status is AgentStatus.WAITING_FOR_HUMAN
    corrupted = state.model_dump()
    corrupted["unknown_new_field"] = True
    with pytest.raises(ValidationError):
        InvestigationState.model_validate(corrupted)
