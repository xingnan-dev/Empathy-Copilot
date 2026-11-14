"""Infrastructure checks without enabling fault injection in the ordinary API."""

import inspect

import pytest

from scripts.tool_recovery_experiment import CASES, ExperimentRun, wait_until


def test_wait_uses_explicit_condition_and_timeout() -> None:
    assert wait_until(lambda: "confirmed-boundary", timeout=1) == "confirmed-boundary"
    with pytest.raises(TimeoutError):
        wait_until(lambda: False, timeout=0)


def test_cleanup_refuses_unowned_container(monkeypatch: pytest.MonkeyPatch) -> None:
    run = object.__new__(ExperimentRun)
    run.token = "owned"
    run.container = "owned-container"
    run.children = []
    commands = []
    import subprocess

    def inspect_only(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(
            command, 0, '[{"Config":{"Labels":{"empathy.w3.owner":"other"}}}]', ""
        )

    monkeypatch.setattr(subprocess, "run", inspect_only)
    with pytest.raises(RuntimeError, match="ownership"):
        run.cleanup()
    assert len(commands) == 1 and commands[0][:2] == ["docker", "inspect"]


def test_production_does_not_import_experiment_faults() -> None:
    from backend.app.api import app

    assert "tool_recovery_worker" not in inspect.getsource(app)
    assert "W3_DATABASE_URL" not in inspect.getsource(app)
    assert {
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "F7_API",
        "F8_PROCESSES",
        "F9",
        "F12",
        "F15_HTTP",
        "F15_COMMIT",
    } <= set(CASES)
