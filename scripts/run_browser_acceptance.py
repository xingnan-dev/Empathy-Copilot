"""Own disposable database and actual frontend/API processes for local browser acceptance."""

import json
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    run_id = "browser-" + uuid.uuid4().hex
    output = ROOT / "backend/evaluation_output" / run_id
    output.mkdir(parents=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(x in k.upper() for x in ("LLM", "QWEN", "VISION", "OFFICIAL", "DASHSCOPE"))
    }
    api_port = port()
    # Existing API CORS explicitly permits frontend port5173; refuse an occupied port.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 5173))
    label = "io.resonique.browser-acceptance"
    cid = subprocess.check_output(
        [
            "docker",
            "run",
            "-d",
            "--name",
            run_id,
            "--label",
            f"{label}={run_id}",
            "--tmpfs",
            "/var/lib/postgresql/data",
            "-e",
            "POSTGRES_PASSWORD=experiment",
            "-e",
            "POSTGRES_USER=experiment",
            "-p",
            "127.0.0.1::5432",
            "postgres:16-alpine",
        ],
        text=True,
        encoding="utf-8",
    ).strip()
    processes = []
    logs = []
    python = str(ROOT / ".venv/Scripts/python.exe")
    report = {
        "starting_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "run_id": run_id,
    }
    try:
        address = subprocess.check_output(["docker", "port", cid, "5432/tcp"], text=True).strip()
        for _ in range(60):
            if (
                subprocess.run(
                    ["docker", "exec", cid, "pg_isready", "-U", "experiment"],
                    stdout=subprocess.DEVNULL,
                ).returncode
                == 0
            ):
                break
            time.sleep(0.2)
        env.update(
            BROWSER_OUTPUT=str(output),
            BROWSER_API=f"http://127.0.0.1:{api_port}",
            BROWSER_FRONTEND="http://127.0.0.1:5173",
            VITE_API_BASE_URL=f"http://127.0.0.1:{api_port}",
        )
        log = (output / "frontend.log").open("w", encoding="utf-8")
        logs.append(log)
        frontend = subprocess.Popen(
            [
                "node",
                "node_modules/vite/bin/vite.js",
                "--host",
                "127.0.0.1",
                "--port",
                "5173",
                "--strictPort",
            ],
            cwd=ROOT / "frontend",
            env=env,
            stdout=log,
            stderr=log,
        )
        processes.append(frontend)
        report["cases"] = {}
        for mode in ("message", "unavailable", "approval", "conflict", "outage"):
            database = "test_" + mode
            subprocess.run(
                ["docker", "exec", cid, "createdb", "-U", "experiment", database], check=True
            )
            env["DATABASE_URL"] = f"postgresql+psycopg://experiment:experiment@{address}/{database}"
            env["BROWSER_TEST_MODEL"] = "fake" if mode == "message" else "none"
            subprocess.run(
                [python, "-m", "alembic", "upgrade", "head"],
                cwd=ROOT,
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                [python, "-m", "backend.app.persistence.seed_cli"], cwd=ROOT, env=env, check=True
            )
            log = (output / f"{mode}-api.log").open("w", encoding="utf-8")
            logs.append(log)
            backend = subprocess.Popen(
                [
                    python,
                    "-m",
                    "uvicorn",
                    "scripts.browser_acceptance_worker:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--workers",
                    "1",
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            processes.append(backend)
            for _ in range(100):
                try:
                    with urlopen(env["BROWSER_API"] + "/health", timeout=1):
                        break
                except OSError:
                    time.sleep(0.1)
            env["BROWSER_MODE"] = mode
            browser = subprocess.Popen(
                ["node", "scripts/browser_acceptance.mjs"], cwd=ROOT, env=env
            )
            processes.append(browser)
            if mode == "outage":
                for marker in ("stop-api", "restart-api"):
                    deadline = time.monotonic() + 60
                    while not (output / marker).exists():
                        if browser.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError("browser handshake failed")
                        time.sleep(0.1)
                    if marker == "stop-api":
                        backend.terminate()
                        backend.wait(timeout=15)
                        (output / "api-stopped").write_text("old PID exited")
                    else:
                        backend = subprocess.Popen(
                            [
                                python,
                                "-m",
                                "uvicorn",
                                "scripts.browser_acceptance_worker:app",
                                "--host",
                                "127.0.0.1",
                                "--port",
                                str(api_port),
                                "--workers",
                                "1",
                            ],
                            cwd=ROOT,
                            env=env,
                            stdout=log,
                            stderr=log,
                        )
                        processes.append(backend)
                        for _ in range(100):
                            try:
                                with urlopen(env["BROWSER_API"] + "/health", timeout=1):
                                    break
                            except OSError:
                                time.sleep(0.1)
                        (output / "api-restarted").write_text("new process healthy")
            returncode = browser.wait(timeout=120)
            snapshot = subprocess.check_output(
                [
                    "docker",
                    "exec",
                    cid,
                    "psql",
                    "-U",
                    "experiment",
                    "-d",
                    database,
                    "-At",
                    "-c",
                    "SELECT state_snapshot::text FROM investigation_checkpoints "
                    "WHERE case_id='S00154'",
                ],
                text=True,
                encoding="utf-8",
            )
            (output / f"{mode}-checkpoint.json").write_text(snapshot, encoding="utf-8")
            report["cases"][mode] = returncode
            backend.terminate()
            backend.wait(timeout=15)
        report["status"] = "PASSED" if all(x == 0 for x in report["cases"].values()) else "FAILED"
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
        for log in logs:
            log.close()
        actual = subprocess.check_output(
            ["docker", "inspect", cid, "--format", "{{json .Config.Labels}}"], text=True
        )
        if json.loads(actual).get(label) != run_id:
            raise RuntimeError("Refuse cleanup: label mismatch")
        subprocess.run(["docker", "rm", "-f", cid], check=True, stdout=subprocess.DEVNULL)
        report["cleanup"] = (
            "owned browser contexts closed; own services stopped; own database container removed"
        )
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(output)
    if report.get("status") != "PASSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
