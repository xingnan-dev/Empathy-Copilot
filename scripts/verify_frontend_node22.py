"""Validate the committed frontend Dockerfile in isolated, uniquely labelled resources."""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import tarfile
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
LABEL = "io.resonique.frontend-node22-validation"


def main() -> None:
    experiment = "node22-" + uuid.uuid4().hex
    output = ROOT / "backend/evaluation_output/frontend-dependency-fixes" / experiment
    output.mkdir(parents=True)
    containers: list[str] = []
    images: list[str] = []
    report: dict = {
        "experiment_id": experiment,
        "status": "INCOMPLETE",
        "commands": [],
        "cleanup": [],
    }

    def run(args: list[str], name: str, allowed: tuple[int, ...] = (0,)) -> str:
        print(name, flush=True)
        completed = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=900)
        text = completed.stdout.decode("utf-8", errors="replace")
        error = completed.stderr.decode("utf-8", errors="replace")
        # Docker progress prefixes leave spaces on otherwise blank output lines.
        log = "\n".join(line.rstrip(" \t") for line in (text + error).splitlines()) + "\n"
        (output / (name + ".log")).write_text(log, encoding="utf-8")
        report["commands"].append(
            {"argv": args, "log": name + ".log", "exit_code": completed.returncode}
        )
        if completed.returncode not in allowed:
            raise RuntimeError(f"{name} exited {completed.returncode}; see {output}")
        return text.strip()

    def inventory(name: str) -> list[dict]:
        # Do not publish other projects' names, mount paths, or networks in experiment logs.
        text = run(["docker", "ps", "-a", "--no-trunc", "--format", "{{.ID}} {{.State}}"], name)
        return [dict(zip(("id", "state"), line.split(), strict=True)) for line in text.splitlines()]

    def image_info(tag: str, name: str) -> dict:
        value = json.loads(run(["docker", "image", "inspect", tag, "--format", "{{json .}}"], name))
        return {
            "id": value["Id"],
            "digests": value.get("RepoDigests", []),
            "os": value["Os"],
            "architecture": value["Architecture"],
            "labels": value.get("Config", {}).get("Labels") or {},
        }

    def copy_file(container: str, source: str, name: str) -> Path:
        target = output / name
        run(
            ["docker", "cp", f"{container}:{source}", str(target)], "copy-" + name.replace(".", "-")
        )
        return target

    try:
        report["starting_commit"] = run(["git", "rev-parse", "HEAD"], "starting-commit")
        branch = run(["git", "branch", "--show-current"], "branch")
        if branch != "codex/frontend-dependency-fixes":
            raise RuntimeError("Run from the approved dependency-fixes branch")
        # Git archive deliberately excludes working-tree dependencies, .env, and build caches.
        tracked_changes = run(["git", "diff", "HEAD", "--", "frontend"], "frontend-diff")
        if tracked_changes:
            raise RuntimeError("Commit frontend changes before validating the delivery snapshot")
        report["docker"] = json.loads(
            run(["docker", "version", "--format", "{{json .}}"], "docker-version")
        )
        report["containers_before"] = inventory("containers-before")
        report["base_images"] = {}
        for tag in ("node:22-alpine", "nginx:1.27-alpine"):
            run(["docker", "pull", tag], "pull-" + tag.split(":")[0])
            report["base_images"][tag] = image_info(tag, "inspect-" + tag.split(":")[0])
        with tempfile.TemporaryDirectory(prefix=experiment + "-") as temporary:
            archive = subprocess.check_output(["git", "archive", "HEAD", "frontend"], cwd=ROOT)
            with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
                bundle.extractall(temporary, filter="data")
            context = Path(temporary) / "frontend"
            report["input_sha256"] = {
                name: hashlib.sha256((context / name).read_bytes()).hexdigest()
                for name in ("Dockerfile", "package.json", "package-lock.json", ".dockerignore")
            }
            builder = "resonique-node22-check:" + experiment
            delivery = "resonique-nginx-check:" + experiment
            # Register tags first so a partial build is also checked during cleanup.
            images.extend([builder, delivery])
            run(
                [
                    "docker",
                    "build",
                    "--no-cache",
                    "--progress=plain",
                    "--target",
                    "build",
                    "--label",
                    f"{LABEL}={experiment}",
                    "-t",
                    builder,
                    str(context),
                ],
                "build-node22",
            )
            run(
                [
                    "docker",
                    "build",
                    "--progress=plain",
                    "--label",
                    f"{LABEL}={experiment}",
                    "-t",
                    delivery,
                    str(context),
                ],
                "build-nginx",
            )
            report["build_image"] = image_info(builder, "inspect-build-image")
            report["delivery_image"] = image_info(delivery, "inspect-delivery-image")

        checks = r"""set -eu
node --version > /tmp/node-version.txt
npm --version > /tmp/npm-version.txt
cat /tmp/node-version.txt /tmp/npm-version.txt
echo 'COMMAND: npm ci'
npm ci
echo 'COMMAND: npm test'
npm test
echo 'COMMAND: clean incremental TypeScript outputs before typecheck'
./node_modules/.bin/tsc -b --clean
echo 'COMMAND: npm run typecheck'
npm run typecheck
echo 'COMMAND: npm run lint'
npm run lint
echo 'COMMAND: npm run build'
npm run build
sha256sum /app/package-lock.json > /tmp/lock-sha256.txt
npm ls --all --json > /tmp/installed-tree.json
audit_exit=0
npm audit --json > /tmp/audit.json || audit_exit=$?
echo "audit exit: $audit_exit"
test "$audit_exit" -le 1
node <<'JS'
const fs = require('fs'), crypto = require('crypto'), path = require('path');
function visit(p) {
  return fs.readdirSync(p, {withFileTypes: true}).flatMap(x =>
    x.isDirectory() ? visit(path.join(p, x.name)) : [path.join(p, x.name)]);
}
const result = Object.fromEntries(visit('/app/dist').map(p => [p.slice('/app/dist/'.length), {
  bytes: fs.statSync(p).size,
  sha256: crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')
}]));
fs.writeFileSync('/tmp/assets.json', JSON.stringify(result, null, 2));
JS
"""
        testing = experiment + "-checks"
        cid = run(
            [
                "docker",
                "create",
                "--name",
                testing,
                "--label",
                f"{LABEL}={experiment}",
                builder,
                "sh",
                "-c",
                checks,
            ],
            "create-check-container",
        )
        containers.append(cid)
        run(["docker", "start", "-a", cid], "node22-checks")
        # docker start -a is not used as the sole evidence for the container exit status.
        exit_code = int(
            run(["docker", "inspect", cid, "--format", "{{.State.ExitCode}}"], "checks-exit")
        )
        if exit_code != 0:
            raise RuntimeError(f"Node22 checks exited {exit_code}")
        report["check_container_exit"] = exit_code
        for name in (
            "node-version.txt",
            "npm-version.txt",
            "lock-sha256.txt",
            "installed-tree.json",
            "audit.json",
            "assets.json",
        ):
            copy_file(cid, "/tmp/" + name, name)
        report["node"] = (output / "node-version.txt").read_text().strip()
        report["npm"] = (output / "npm-version.txt").read_text().strip()
        if not report["node"].startswith("v22."):
            raise RuntimeError("Dockerfile no longer resolves to Node22")
        if (output / "lock-sha256.txt").read_text().split()[0] != report["input_sha256"][
            "package-lock.json"
        ]:
            raise RuntimeError("npm ci changed the lockfile")
        audit = json.loads((output / "audit.json").read_text())
        report["audit"] = audit["metadata"]["vulnerabilities"]
        report["audit_advisories"] = sorted(
            {
                item["url"]
                for value in audit["vulnerabilities"].values()
                for item in value["via"]
                if isinstance(item, dict)
            }
        )
        assets = json.loads((output / "assets.json").read_text())

        cid = run(
            [
                "docker",
                "create",
                "--name",
                experiment + "-nginx",
                "--label",
                f"{LABEL}={experiment}",
                "-p",
                "127.0.0.1::80",
                delivery,
            ],
            "create-nginx-container",
        )
        containers.append(cid)
        run(["docker", "start", cid], "start-nginx")
        address = run(["docker", "port", cid, "80/tcp"], "nginx-port")
        if not re.fullmatch(r"127\.0\.0\.1:\d+", address):
            raise RuntimeError(f"Unexpected published address {address}")
        base = "http://" + address
        deadline = time.monotonic() + 30
        while True:
            try:
                with urlopen(base, timeout=2) as response:
                    html = response.read()
                break
            except (URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
        paths = ["index.html", *re.findall(r'(?:src|href)="/(assets/[^"?#]+)"', html.decode())]
        if not any(p.endswith(".js") for p in paths) or not any(p.endswith(".css") for p in paths):
            raise RuntimeError("Index does not reference generated JS and CSS")
        report["http"] = []
        for name in paths:
            with urlopen(base + "/" + name, timeout=5) as response:
                body = response.read()
                item = {
                    "path": "/" + name,
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            if item["status"] != 200 or item["sha256"] != assets[name]["sha256"]:
                raise RuntimeError(f"Nginx response differs from Node22 build: {name}")
            expected_type = (
                "text/css"
                if name.endswith(".css")
                else "javascript"
                if name.endswith(".js")
                else "text/html"
            )
            if expected_type not in item["content_type"]:
                raise RuntimeError(f"Unexpected content type: {item}")
            report["http"].append(item)
        run(["docker", "exec", cid, "nginx", "-v"], "nginx-version")
        report["nginx_version"] = (output / "nginx-version.log").read_text().strip()
        run(
            ["docker", "exec", cid, "sh", "-c", "! command -v node && ! command -v npm"],
            "nginx-no-node-npm",
        )
        run(["docker", "logs", cid], "nginx-access")
        report["status"] = "PASSED"
    except Exception as error:
        report["status"] = "FAILED"
        report["error"] = str(error)
        raise
    finally:
        for index, cid in enumerate(reversed(containers)):
            try:
                labels = json.loads(
                    run(
                        ["docker", "inspect", cid, "--format", "{{json .Config.Labels}}"],
                        f"cleanup-container-label-{index}",
                    )
                )
                if labels.get(LABEL) != experiment:
                    raise RuntimeError("Refusing cleanup: container label mismatch")
                run(["docker", "rm", "-f", cid], f"cleanup-container-{index}")
                report["cleanup"].append({"container": cid, "removed": True})
            except Exception as error:
                report["cleanup"].append({"container": cid, "error": str(error)})
        for index, tag in enumerate(reversed(images)):
            try:
                info = image_info(tag, f"cleanup-image-label-{index}")
                if info["labels"].get(LABEL) != experiment:
                    raise RuntimeError("Refusing cleanup: image label mismatch")
                run(["docker", "image", "rm", tag], f"cleanup-image-{index}")
                report["cleanup"].append({"image_tag": tag, "removed": True})
            except Exception as error:
                report["cleanup"].append({"image_tag": tag, "error": str(error)})
        try:
            report["containers_after"] = inventory("containers-after")
            before = {item["id"]: item["state"] for item in report.get("containers_before", [])}
            after = {item["id"]: item["state"] for item in report["containers_after"]}
            report["preexisting_containers_preserved"] = all(
                after.get(cid) == state for cid, state in before.items()
            )
            if not report["preexisting_containers_preserved"]:
                report["status"] = "FAILED"
        finally:
            if any("error" in entry for entry in report["cleanup"]):
                report["status"] = "FAILED"
            (output / "report.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            print(f"{report['status']}: {output}", flush=True)
        if any("error" in entry for entry in report["cleanup"]):
            raise RuntimeError("Cleanup incomplete; see report")


if __name__ == "__main__":
    main()
