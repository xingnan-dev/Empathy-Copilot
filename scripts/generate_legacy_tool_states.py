"""Generate local-only snapshots using the models at each historical commit."""

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

BASELINES = {
    "competition": "e77ef5a063179cba3c7aa3cc0a3438d89b5646c2",
    "e31": "ff1e35b4ba67e952386253a09d772e0e6918965a",
}
GENERATOR = """
import json
from datetime import UTC, datetime
from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import InvestigationState, ToolCallRecord, ToolCallStatus
from backend.app.services.checkpoints import InMemoryCheckpointStore
from backend.app.services.tools import ToolRegistry
from backend.tests.fixtures import CASE_ID, CONSUMER_ID

def initial():
    return InvestigationState(
        case_id=CASE_ID, consumer_id=CONSUMER_ID, current_issue="Local fixture")

snapshots = {}
workflow = InvestigationWorkflow()
snapshots["completed"] = workflow.run(initial()).model_dump(mode="json")
if hasattr(workflow.tool_execution, "execute_durably"):
    class Stop(BaseException): pass
    for boundary in (ToolCallStatus.PENDING, ToolCallStatus.RUNNING):
        class Capture(InMemoryCheckpointStore):
            def save(self, state, *, expected_revision=None):
                super().save(state, expected_revision=expected_revision)
                if state.tool_calls and state.tool_calls[-1].status == boundary:
                    snapshots[boundary.value.lower()] = state.model_dump(mode="json")
                    raise Stop()
        try: InvestigationWorkflow(checkpoint_store=Capture()).run(initial())
        except Stop: pass
    registry = ToolRegistry()
    def fail(state, arguments): raise TimeoutError("local fixture failure")
    registry.register("get_order_history", fail, side_effect_free=True)
    failed = InvestigationWorkflow(tool_registry=registry).run(initial())
    snapshots["failed"] = failed.model_dump(mode="json")
else:
    for boundary in (ToolCallStatus.PENDING, ToolCallStatus.RUNNING):
        state = initial()
        state.tool_calls = [ToolCallRecord(id="legacy-model-only", tool_name="get_order_history",
            arguments={"consumer_id": CONSUMER_ID}, status=boundary, created_at=datetime.now(UTC))]
        snapshots[boundary.value.lower()] = state.model_dump(mode="json")
print(json.dumps(snapshots, ensure_ascii=False))
"""


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "backend/tests/fixtures/legacy_tool_states"
    output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "generator": "scripts/generate_legacy_tool_states.py",
        "files": [],
    }
    files = []
    for label, commit in BASELINES.items():
        archive = subprocess.check_output(["git", "archive", "--format=zip", commit], cwd=root)
        with tempfile.TemporaryDirectory(prefix="empathy-legacy-") as directory:
            with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                bundle.extractall(directory)
            payload = subprocess.check_output(
                [sys.executable, "-X", "utf8", "-c", GENERATOR], cwd=directory
            )
        for status, snapshot in json.loads(payload).items():
            name = f"{label}_{status}.json"
            data = (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            (output / name).write_bytes(data)
            files.append(
                {
                    "file": name,
                    "commit": commit,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "python": sys.version.split()[0],
                    "origin": "model-only intermediate"
                    if label == "competition" and status != "completed"
                    else "workflow execution",
                }
            )
    manifest["files"] = files
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
