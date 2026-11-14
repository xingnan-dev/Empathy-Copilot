"""W3 local process acceptance. Owns only its uniquely labelled disposable container/children."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.app.domain.agent import InvestigationState  # noqa: E402
from backend.app.persistence.checkpoints import PostgresCheckpointStore  # noqa: E402
from backend.app.persistence.config import DatabaseSettings  # noqa: E402
from backend.app.persistence.database import (  # noqa: E402
    create_database_engine,
    create_session_factory,
)
from backend.app.persistence.seed import seed_demo_data_transactionally  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    "F0",
    "F1",
    "F2",
    "F3",
    "F4",
    "F5",
    "F6",
    "F7_API",
    "F8_PROCESSES",
    "F9",
    "F12",
    "F15_HTTP",
    "F15_COMMIT",
]


def wait_until[T](check: Callable[[], T], timeout: float = 30) -> T:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        threading.Event().wait(0.025)
    raise TimeoutError("Explicit readiness/boundary deadline expired")


def http(port: int, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


class Worker:
    def __init__(self, run: "ExperimentRun", experiment: str, **options: Any) -> None:
        self.run = run
        self.actor = options.pop("actor", "api-" + uuid4().hex[:8])
        self.release = run.directory / (self.actor + ".release")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        config = dict(
            experiment=experiment,
            actor=self.actor,
            release=str(self.release),
            port=self.port,
            **options,
        )
        path = run.directory / (self.actor + ".config.json")
        path.write_text(json.dumps(config), encoding="utf-8")
        self.log = (run.directory / (self.actor + ".log")).open("w", encoding="utf-8")
        command = [sys.executable, "scripts/tool_recovery_worker.py", "--config", str(path)]
        if options.get("claim_only"):
            command.append("--claim")
        self.process = subprocess.Popen(
            command, cwd=ROOT, env=run.env, stdout=self.log, stderr=self.log
        )
        self.record = dict(
            actor=self.actor,
            pid=self.process.pid,
            started_at=datetime.now(UTC).isoformat(),
            single_api_worker=not options.get("claim_only", False),
        )
        run.children.append(self)
        if not options.get("claim_only"):

            def ready() -> bool:
                if self.process.poll() is not None:
                    raise RuntimeError("Worker exited before ready: " + self.actor)
                try:
                    return http(self.port, "/health")[0] == 200
                except (OSError, urllib.error.URLError):
                    return False

            wait_until(ready)

    def stop(self, kill: bool = False) -> None:
        if self.process.poll() is None:
            self.process.kill() if kill else self.process.terminate()
        self.record.update(
            exit_code=self.process.wait(timeout=15),
            wait_confirmed=True,
            stop_method="kill" if kill else "terminate-or-exited",
        )
        self.log.close()


class ExperimentRun:
    def __init__(self, output_root: Path) -> None:
        self.token = uuid4().hex
        self.directory = (output_root / ("w3-" + self.token)).resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.container = "empathy-w3-test-" + self.token[:12]
        self.children: list[Worker] = []
        self.results: list[dict[str, Any]] = []
        self.exit_declarations: dict[str, list[dict[str, Any]]] = {}
        self.started = datetime.now(UTC).isoformat()

    def __enter__(self) -> "ExperimentRun":
        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    self.container,
                    "--label",
                    "empathy.w3.owner=" + self.token,
                    "--publish",
                    "127.0.0.1::5432",
                    "--env",
                    "POSTGRES_USER=w3_test",
                    "--env",
                    "POSTGRES_PASSWORD=w3_local_test_only",
                    "--env",
                    "POSTGRES_DB=empathy_w3_test",
                    "--tmpfs",
                    "/var/lib/postgresql/data",
                    "postgres:16-alpine",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            raw = subprocess.check_output(["docker", "inspect", self.container], text=True)
            details = json.loads(raw)[0]
            port = details["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
            self.url = (
                f"postgresql+psycopg://w3_test:w3_local_test_only@127.0.0.1:{port}/empathy_w3_test"
            )
            self.engine = create_database_engine(DatabaseSettings(self.url))

            def ready() -> bool:
                try:
                    with self.engine.connect() as connection:
                        return bool(connection.scalar(text("SELECT 1")) == 1)
                except Exception:
                    return False

            wait_until(ready)
            self.sessions = create_session_factory(self.engine)
            self.store = PostgresCheckpointStore(self.sessions)
            previous = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = self.url
            try:
                command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
            finally:
                if previous is None:
                    os.environ.pop("DATABASE_URL", None)
                else:
                    os.environ["DATABASE_URL"] = previous
            with self.sessions() as session:
                seed_demo_data_transactionally(session)
            with self.engine.begin() as connection:
                connection.execute(text("CREATE SCHEMA w3_observation"))
                connection.execute(
                    text(
                        "CREATE TABLE w3_observation.events ("
                        "id bigserial PRIMARY KEY, experiment text NOT NULL, actor text NOT NULL,"
                        "kind text NOT NULL, details jsonb NOT NULL, "
                        "recorded_at timestamptz DEFAULT now())"
                    )
                )
            self.env = dict(
                os.environ,
                W3_DATABASE_URL=self.url,
                DATABASE_URL=self.url,
                OFFICIAL_DATASET_PATH="",
                LLM_API_KEY="",
                PYTHONIOENCODING="utf-8",
            )
            self.environment = dict(
                python=sys.version,
                postgres=details["Image"],
                database="empathy_w3_test",
                host_binding="127.0.0.1",
                tmpfs=True,
            )
            return self
        except BaseException:
            self.cleanup()
            raise

    def cleanup(self) -> None:
        for worker in self.children:
            if not worker.log.closed:
                worker.stop(kill=True)
        if hasattr(self, "engine"):
            self.engine.dispose()
        found = subprocess.run(
            ["docker", "inspect", self.container], capture_output=True, text=True
        )
        if found.returncode == 0:
            resource = json.loads(found.stdout)[0]
            if resource["Config"]["Labels"].get("empathy.w3.owner") != self.token:
                raise RuntimeError("Refusing cleanup: container ownership label mismatch")
            subprocess.run(
                ["docker", "rm", "--force", self.container], check=True, capture_output=True
            )

    def __exit__(self, *_args: object) -> None:
        self.cleanup()

    def events(self, experiment: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT id,actor,kind,details,recorded_at FROM w3_observation.events "
                        "WHERE experiment=:experiment ORDER BY id"
                    ),
                    dict(experiment=experiment),
                )
                .mappings()
                .all()
            )
            return [dict(row, recorded_at=row["recorded_at"].isoformat()) for row in rows]

    def gate(self, experiment: str, worker: Worker, boundary: str) -> dict[str, Any]:
        result = wait_until(
            lambda: next(
                (
                    e
                    for e in self.events(experiment)
                    if e["actor"] == worker.actor
                    and e["kind"] == "GATE"
                    and e["details"]["boundary"] == boundary
                ),
                None,
            )
        )

        assert result is not None
        return result

    def snapshot(self, experiment: str) -> dict[str, Any]:
        state = self.store.load(experiment)
        assert state.state_revision == state.step_count == len(state.transition_events)
        assert all(
            set(c.result_evidence_ids) <= {e.id for e in state.evidence} for c in state.tool_calls
        )
        return state.model_dump(mode="json")

    def request(self, experiment: str) -> dict[str, Any]:
        state = self.store.load(experiment)
        target = state.tool_calls[-1].id
        events = self.events(experiment)
        origins = [
            e
            for e in events
            if e["details"].get("attempt_id") == target
            and e["kind"] in {"SNAPSHOT_COMMITTED", "TOOL_ENTRY"}
        ]
        if not origins:
            raise RuntimeError("No recorded process owns target attempt")
        origin = origins[0]["actor"]
        old = next(w for w in self.children if w.actor == origin)
        if old.process.poll() is None or not old.record.get("wait_confirmed"):
            raise RuntimeError("Old target execution process has not exited and been waited")
        self.exit_declarations.setdefault(experiment, []).append(
            dict(
                target_attempt_id=target,
                old_actor=origin,
                old_pid=old.process.pid,
                wait_confirmed=True,
                exit_code=old.process.returncode,
            )
        )
        return dict(
            request_id=str(uuid4()),
            target_attempt_id=state.tool_calls[-1].id,
            expected_revision=state.state_revision,
            operator_id="W3-local-harness",
            reason="Managed previous API process has exited; explicit readonly recovery",
            previous_process_exited=True,
        )

    def counts(self, experiment: str) -> dict[str, int]:
        events = self.events(experiment)
        return {
            kind: sum(e["kind"] == kind for e in events)
            for kind in ("TOOL_ENTRY", "TOOL_RETURN", "SIDE_EFFECT_MARKER")
        }

    def case(self, name: str, iteration: int) -> None:
        experiment = name.lower().replace("_", "-") + "-" + uuid4().hex
        initial = InvestigationState(
            case_id=experiment,
            consumer_id="consumer_001",
            current_issue="W3 fixed local readonly order investigation",
        )
        self.store.save(initial)
        result: dict[str, Any] = dict(
            scenario=name, iteration=iteration, experiment=experiment, checkpoints=[], requests=[]
        )
        url = f"/api/cases/{experiment}/tool-recoveries"
        start_child = len(self.children)

        def capture(label: str) -> None:
            result["checkpoints"].append(
                dict(label=label, state=self.snapshot(experiment), counts=self.counts(experiment))
            )

        def recover(worker: Worker, request: dict[str, Any] | None = None) -> tuple[int, Any]:
            request = request or self.request(experiment)
            result["requests"].append(request)
            return http(worker.port, url, request)

        def failed_setup(mode: str = "timeout") -> None:
            worker = Worker(self, experiment, tool_mode=mode)
            status, _ = http(worker.port, "/experiment/run", {})
            assert status == 200
            capture("failure_before_restart")
            worker.stop()

        try:
            if name in {"F0", "F1", "F2", "F3", "F4"}:
                boundary = {
                    "F0": None,
                    "F1": "BEFORE_PENDING",
                    "F2": "AFTER_PENDING",
                    "F3": "AFTER_RUNNING",
                    "F4": "BEFORE_COMPLETED",
                }[name]
                worker = Worker(self, experiment, gate=boundary)
                if boundary:
                    with ThreadPoolExecutor() as pool:
                        pending = pool.submit(http, worker.port, "/experiment/run", {})
                        self.gate(experiment, worker, boundary)
                        capture("handshake_before_kill")
                        worker.stop(kill=True)
                        try:
                            pending.result()
                        except (OSError, urllib.error.URLError):
                            pass
                    at_crash = self.store.load(experiment)
                    if name == "F1":
                        assert not at_crash.tool_calls and at_crash.state_revision == 0
                    else:
                        assert at_crash.tool_calls[-1].status.value == (
                            "PENDING" if name == "F2" else "RUNNING"
                        )
                        assert not at_crash.evidence
                    assert self.counts(experiment)["TOOL_ENTRY"] == (1 if name == "F4" else 0)
                    worker = Worker(self, experiment)
                status, _ = http(worker.port, "/experiment/run", {})
                assert status == 200
                if name in {"F2", "F3", "F4"}:
                    assert self.store.load(experiment).status.value == "WAITING_FOR_HUMAN"
                    status, view = recover(worker)
                    assert status == 201 and view["continuation"] == "SETTLED"
                assert self.store.load(experiment).status.value == "WAITING_FOR_USER"
                expected = 2 if name == "F4" else 1
                assert self.counts(experiment) == dict(
                    TOOL_ENTRY=expected, TOOL_RETURN=expected, SIDE_EFFECT_MARKER=0
                )
                worker.stop()
            elif name == "F12":
                failed_setup("unknown")
                assert (
                    str(self.store.load(experiment).tool_calls[-1].failure_kind)
                    == "UNKNOWN_OUTCOME"
                )
                worker = Worker(self, experiment)
                status, view = recover(worker)
                assert status == 409 and view["code"] == "RECOVERY_NOT_ALLOWED"
                assert self.counts(experiment) == dict(
                    TOOL_ENTRY=1, TOOL_RETURN=0, SIDE_EFFECT_MARKER=1
                )
                worker.stop()
            else:
                failed_setup()
                if name in {"F6", "F7_API"}:
                    worker = Worker(
                        self, experiment, gate="AFTER_RUNNING" if name == "F7_API" else None
                    )
                    request = self.request(experiment)
                    result["requests"].append(request)
                    if name == "F7_API":
                        with ThreadPoolExecutor() as pool:
                            first = pool.submit(http, worker.port, url, request)
                            self.gate(experiment, worker, "AFTER_RUNNING")
                            second_status, second = http(worker.port, url, request)
                            assert second_status == 202 and second["replayed"]
                            assert self.counts(experiment)["TOOL_ENTRY"] == 1
                            worker.release.touch()
                            status, view = first.result()
                        result["competition_layer"] = "two HTTP clients / one single-worker API"
                    else:
                        status, view = http(worker.port, url, request)
                    assert status == 201 and view["continuation"] == "SETTLED"
                    again, replay = http(worker.port, url, request)
                    assert again == 200 and replay["replayed"]
                    worker.stop()
                elif name == "F8_PROCESSES":
                    request1, request2 = self.request(experiment), self.request(experiment)
                    result["requests"].extend([request1, request2])
                    workers = [
                        Worker(self, experiment, gate="BEFORE_CLAIM", claim_only=True, request=r)
                        for r in (request1, request2)
                    ]
                    for worker in workers:
                        self.gate(experiment, worker, "BEFORE_CLAIM")
                    capture("both_processes_before_claim_CAS")
                    for worker in workers:
                        worker.release.touch()
                    for worker in workers:
                        assert worker.process.wait(timeout=30) == 0
                        worker.stop()
                    events = self.events(experiment)
                    won = [e for e in events if e["kind"] == "CLAIM_WON"]
                    rejected = [e for e in events if e["kind"] == "CLAIM_REJECTED"]
                    assert len(won) == len(rejected) == 1
                    assert rejected[0]["details"]["code"] == "REVISION_CONFLICT"
                    assert not any(
                        e["kind"] == "TOOL_ENTRY" and e["actor"] == rejected[0]["actor"]
                        for e in events
                    )
                    result["competition_layer"] = (
                        "two independent execution processes / same PostgreSQL revision CAS"
                    )
                elif name == "F15_COMMIT":
                    worker = Worker(self, experiment, uncertain_claim=True)
                    request = self.request(experiment)
                    status, view = recover(worker, request)
                    assert status == 503 and view["code"] == "RECOVERY_STORAGE_UNAVAILABLE"
                    capture("confirmed_claim_commit_receipt_lost")
                    worker.stop()
                    worker = Worker(self, experiment)
                    assert http(worker.port, url + "/" + request["request_id"])[0] == 202
                    assert recover(worker, request)[0] == 202
                    assert self.counts(experiment)["TOOL_ENTRY"] == 1
                    # Another explicit attempt is allowed only after this API process also exits.
                    worker.stop()
                    worker = Worker(self, experiment)
                    assert recover(worker)[0] == 201
                    worker.stop()
                else:
                    boundary = {
                        "F5": "AFTER_COMPLETED",
                        "F9": "AFTER_RUNNING",
                        "F15_HTTP": "BEFORE_HTTP_RESPONSE",
                    }[name]
                    worker = Worker(self, experiment, gate=boundary)
                    request = self.request(experiment)
                    result["requests"].append(request)
                    with ThreadPoolExecutor() as pool:
                        pending = pool.submit(http, worker.port, url, request)
                        self.gate(experiment, worker, boundary)
                        capture("recovery_handshake_before_kill")
                        worker.stop(kill=True)
                        try:
                            pending.result()
                        except (OSError, urllib.error.URLError):
                            result["http_response_lost"] = True
                    if name == "F5":
                        state = self.store.load(experiment)
                        assert state.tool_calls[-1].status.value == "COMPLETED"
                        assert state.tool_recoveries[-1].continuation.value == "RUNNING"
                        before = self.counts(experiment)
                        cli = subprocess.run(
                            [
                                sys.executable,
                                "scripts/resume_completed_recovery.py",
                                "--case-id",
                                experiment,
                                "--request-id",
                                request["request_id"],
                            ],
                            cwd=ROOT,
                            env=self.env,
                            capture_output=True,
                            text=True,
                            check=True,
                            timeout=30,
                        )
                        result["offline_cli"] = json.loads(cli.stdout)
                        assert self.counts(experiment) == before
                    worker = Worker(self, experiment)
                    if name == "F9":
                        assert recover(worker)[0] == 201
                        assert len(self.store.load(experiment).tool_calls) == 3
                        assert (
                            self.store.load(experiment).tool_recoveries[0].continuation.value
                            == "INTERRUPTED"
                        )
                    else:
                        assert http(worker.port, url + "/" + request["request_id"])[0] == 200
                        assert recover(worker, request)[0] == 200
                    worker.stop()
                assert self.store.load(experiment).status.value == "WAITING_FOR_USER"
                assert self.counts(experiment) == dict(
                    TOOL_ENTRY=2, TOOL_RETURN=1, SIDE_EFFECT_MARKER=0
                )
            capture("final")
            result["status"] = "PASS"
        except Exception as error:
            result.update(status="FAIL", error=type(error).__name__ + ": " + str(error))
            capture("failure_scene")
            raise
        finally:
            for worker in self.children[start_child:]:
                if not worker.log.closed:
                    worker.stop(kill=True)
            result["processes"] = [w.record for w in self.children[start_child:]]
            result["events"] = self.events(experiment)
            result["exit_declarations"] = self.exit_declarations.get(experiment, [])
            self.results.append(result)
            self.write_report()

    def write_report(self, regression: dict[str, Any] | None = None) -> None:
        samples = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "backend/data/demo").glob("*.json"))
        }
        report = dict(
            run_id=self.token,
            started_at=self.started,
            git_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            environment=self.environment,
            sample_sha256=samples,
            results=self.results,
        )
        if regression:
            report["regression"] = regression
        (self.directory / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "backend/evaluation_output/w3")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    parser.add_argument("--regression", action="store_true")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("repetitions must be positive")
    with ExperimentRun(args.output_root) as run:
        print(str(run.directory), flush=True)
        for iteration in range(1, args.repetitions + 1):
            for case in args.cases:
                run.case(case, iteration)
                print(f"{case} iteration {iteration}: PASS", flush=True)
        if args.regression:
            junit = run.directory / "regression.xml"
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-rs", "--tb=short", "--junitxml", str(junit)],
                cwd=ROOT,
                env=dict(run.env, TEST_DATABASE_URL=run.url),
                capture_output=True,
                text=True,
                timeout=180,
            )
            (run.directory / "regression.log").write_text(
                completed.stdout + completed.stderr, encoding="utf-8"
            )
            run.write_report(
                dict(exit_code=completed.returncode, junit="regression.xml", log="regression.log")
            )
            if completed.returncode:
                raise RuntimeError("Regression failed; inspect regression.log")


if __name__ == "__main__":
    main()
