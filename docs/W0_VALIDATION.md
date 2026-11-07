# W0 — E3.1 local validation record

Date: 2026-11-07 (Asia/Shanghai). Status: local-sample verification passed; phase review pending.
This record does not accept W1, implement recovery, or complete the future W3 fault matrix.

## Git provenance and delivery

- Starting branch: `codex/phase-e3-1-tool-failures`, initially without an upstream.
- Starting HEAD: `e77ef5a063179cba3c7aa3cc0a3438d89b5646c2`.
- Remote: `origin`, `https://github.com/xingnan-dev/Empathy-Copilot.git`.
- Read-only `git ls-remote --heads --tags origin` confirmed remote `main` at starting HEAD,
  with no E3.1 remote branch at the start. Local `origin/main...HEAD` was 0 ahead / 0 behind.
- Technical freeze: `44073aca8077e46e187bb4eb7d4f8370a8452c8c`, verified ancestor of HEAD.
- Competition annotated tag: `v1.0.0-competition-submission`; tag object
  `74cab4ef7b78e738b32c0d93216a462c6faabb04`, peeled commit equal to starting HEAD.
- E3.1 implementation/test/phase-description commit:
  `a89bed63f5581280d4c2041016ba5f9645ec5a79`.
- The first commit adding this record is the W0 validated delivery baseline. Resolve its exact
  hash with `git log --diff-filter=A --format=%H -- docs/W0_VALIDATION.md`.
  It adds the accepted post-competition documentation, plan, navigation, and validation record
  on top of the tested implementation. The phase handoff reports the resolved hash and push result.
- Push destination: `origin/codex/phase-e3-1-tool-failures`, without force. Prepare
  `codex/phase-e3-2-readonly-recovery` from that baseline after successful delivery; W1 waits
  for review. Do not merge `main` or move existing tags as part of W0.

At entry, six source/test files plus README, run/operator guides and PROJECT_STATE were modified;
POST_COMPETITION_PLAN and PHASE_E3_1 were untracked. The implementation and phase document were
committed first; the plan and documents linking to it are delivered together in the next commit.
Explicit-path staging excludes the workbook, local environments, caches, credentials and prototype.

## Environment and isolation

- Windows; repository virtual environment Python 3.13.14 (system Python is separate).
- PostgreSQL 16.15 from existing `postgres:16-alpine` image.
- Dedicated container: `empathy-w0-e31-test-20261107`; database: `empathy_w0_test`;
  host binding: `127.0.0.1:55432`; data directory on container tmpfs.
- The existing application's PostgreSQL on port 5432 and its volume were not test targets.
  Docker Desktop startup also resumed existing application containers; W0 commands used only
  the named isolated test database for migrations, truncation, and checkpoint verification.
- pytest 8.4.2, Ruff 0.16.8, mypy 1.20.2, Pydantic 2.13.5, LangGraph 1.2.12,
  SQLAlchemy 2.0.54, psycopg 3.3.6, Alembic 1.20.0, FastAPI 0.141.1, httpx 0.28.1.
- The existing virtual environment lacks pip; installed test tools were usable, so no dependency
  installation or environment replacement was necessary. These are observed versions, not a lockfile.

## Input and network dependency audit

- C Serum / D Cream records come from `backend/data/demo/*.json` and local test fixtures.
- Synthetic vision input is `backend/data/demo_assets/demo_broken_pump_001.png`, with
  `FakeVisionProvider`; language paths use `FakeModelProvider` or mocked HTTP responses.
- Official tests load a workbook through `OFFICIAL_DATASET_PATH`. Some Phase 9 tests depend on
  the fixture without an `official_dataset` marker, so marker exclusion alone is insufficient.
- Real Qwen execution is opt-in through three environment variables in
  `test_phase6_qwen.py`. W0 explicitly cleared the key and official workbook path in test processes.
- No official workbook was loaded or uploaded, no real model call was made, and no historical
  evaluation report was regenerated. External network use was limited to Git remote operations;
  database tests used loopback. API TestClient tests run in-process.
- Removed the erroneous `official_dataset` marker from the synthetic vision PostgreSQL test;
  its body depends only on the local synthetic image, fake provider, and isolated database.

## Results and corrections

| Check | Result | Scope / reason |
| --- | --- | --- |
| Initial PostgreSQL run inside sandbox | 14 setup errors | Loopback connection denied, Windows error 10013; no assertion result |
| Initial full-suite sandbox attempt | Interrupted, incomplete | Progress stalled entering API tests; no passing-suite claim; rerun outside sandbox |
| First permitted PostgreSQL run | 13 passed, 1 skipped | Existing E3.1 checks; official workbook disabled |
| First permitted full suite | 152 passed, 28 skipped | Local baseline before supplementary checks |
| Final `pytest -m postgres -rs --tb=short` | 20 passed, 1 skipped, 166 deselected | Supplementary durability checks included |
| Final `pytest -rs --tb=short` | 159 passed, 28 skipped | 187 collected; zero test failures/errors |
| `ruff check .` | Passed | No lint findings |
| `mypy` | Passed | 94 source files |
| `git diff --check` | Passed | No whitespace errors |

Environment access issues were resolved with approved execution outside the sandbox; Git read-only
access and Docker access initially failed there as well. No production implementation defect was
exposed by the completed checks. W0 corrected the test marker and expanded verification while
preserving the pre-existing E3.1 implementation.

Skip accounting for the final full suite:

| Test module | Skipped | Reason |
| --- | ---: | --- |
| `test_phase4_postgres.py` | 1 | Official import/reconstruction requires workbook |
| `test_phase7_official_dataset.py` | 10 | Official case assertions require workbook |
| `test_phase8_multimodal.py` | 4 | Official metadata/case paths require workbook |
| `test_phase9_evaluation.py` | 12 | Official benchmark inputs require workbook |
| `test_phase6_qwen.py` | 1 | Real provider credentials deliberately disabled |

All required local E3.1 database checks executed. Skipped external-input tests are not counted as
passes; official-data regression and real-model quality/availability are outside this validation.

## E3.1 evidence and limits

- Four failure cases: read-only timeout, potentially side-effecting timeout, validation failure,
  and explicit unknown outcome. Fresh engines restore safe classified failures without success
  Evidence, exception details, or automatic repeated calls.
- Three committed boundaries: PENDING, RUNNING, COMPLETED. An injected BaseException after a real
  commit interrupts the test workflow. New engines/workflows restore the exact call record;
  unfinished calls pause for human handling, completed calls continue without reexecution.
- A concurrent revision update after tool entry prevents COMPLETED from overwriting the newer
  RUNNING snapshot. The successful query's Evidence is not incorrectly persisted after conflict.
- Existing checks cover normal grounding, migrations, seed idempotency, checkpoint validation,
  stale revisions, resumed questions, human approval, and independent synthetic vision persistence.
- These are in-process boundary injections with real PostgreSQL and fresh connection engines,
  not independent process termination or multi-worker races. F0–F12 recovery acceptance remains
  future work. This is a local E3.1 verification baseline, not production certification.

## Reproduction

Use a dedicated disposable database: the fixture drops and rebuilds its public schema. Do not
point TEST_DATABASE_URL at the application database. In a PowerShell session with the existing
development dependencies installed, set TEST_DATABASE_URL to the isolated database URL, then:

```powershell
$env:OFFICIAL_DATASET_PATH = ''
$env:LLM_API_KEY = ''
.\.venv\Scripts\python -m pytest -m postgres -rs --tb=short
.\.venv\Scripts\python -m pytest -rs --tb=short
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy
git diff --check
```

Stop the dedicated tmpfs container after verification; its test rows are disposable and can be
recreated by the migration/seed fixtures. Historical reports, official data and application volumes
are retained. The review handoff records final branch, baseline hash, push verification and any
remaining worktree changes before W1 starts.
