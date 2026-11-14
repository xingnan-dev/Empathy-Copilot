# Resonique Local Run Guide

This guide remains the runtime entry point for independent post-competition development.
Its filename is retained for existing links. The competition release is frozen; current scope
and verification status are in [PROJECT_STATE.md](PROJECT_STATE.md), with planned work in
[POST_COMPETITION_PLAN.md](POST_COMPETITION_PLAN.md). The case demonstrations and evaluation
results below retain baseline behavior; current recovery operation and verification are documented above.

## Start here: clean checkout with local synthetic inputs

The recovery demo and fault checks need no organizer workbook, model credentials or original
workspace files. Required: Git; Python 3.12+ with venv/pip (clean verification used 3.13.14);
Docker Desktop running Linux containers and a reachable Docker daemon; PostgreSQL 16 image;
network access for initial package/image downloads. The frontend additionally needs Node.js 22+
and npm (exact observed versions are in the W4 record). Python version ranges are declared in
`pyproject.toml`; frontend versions are pinned in `frontend/package-lock.json`. Python dependencies
are not locked: the W4 observed dependency list records the verified resolution, not a universal lock.

```powershell
git clone --branch codex/phase-e3-2-readonly-recovery https://github.com/xingnan-dev/Empathy-Copilot.git
cd Empathy-Copilot
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
$env:OFFICIAL_DATASET_PATH = ''
$env:LLM_API_KEY = ''
docker pull postgres:16-alpine
.\.venv\Scripts\python scripts/tool_recovery_experiment.py --cases F0 F6 F5 --repetitions 1 --regression
```

This runs normal-query control, readonly timeout/restart/manual recovery, and F5 completed-query
continuation with an independent CLI observer positive control. It creates a uniquely labelled
PostgreSQL test container on a random loopback port and single API child processes, waits for
readiness/boundary handshakes, then stops/waits the children and removes only its own container.
`backend/data/demo/*.json` supplies fixed synthetic records; reports contain input SHA-256 values.
The fault modes live only in the explicit experimental worker entry point. Ordinary API startup
never enables them. The Docker account must be permitted to create and remove its own containers.

The script prints a unique report directory. Inspect `report.json`, `regression.log` and
`regression.xml` there. It does not use a pre-existing TEST_DATABASE_URL. For the full process
matrix, use `--repetitions 3 --regression` without `--cases`; this may take several minutes.
For manual pytest, TEST_DATABASE_URL must name a separately created disposable database with
`test` in its name: fixtures rebuild public schema. Never point it at the application database.

### Single API process and explicit recovery

For ordinary local operation, use the native setup below, then run in a dedicated terminal:

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Stop with Ctrl+C in that terminal and wait until the process exits before restarting. Do not use
reload/multiple workers for this recovery experiment. A manager script must terminate and wait its
own API child before declaring `previous_process_exited=true`; a timestamp or timeout is insufficient.

GET `/api/cases/{case_id}` exposes revision and `context_passport.tool_attempts`. POST
`/api/cases/{case_id}/tool-recoveries` requires request_id(UUID), target_attempt_id(current leaf),
expected_revision, operator_id, reason, previous_process_exited. Only get_order_history is allowed;
retryable failures or confirmed interrupted attempts are eligible, subject to safety and four-step
budget checks. Operator/exit fields are declarations in a controlled local environment.
See the [W2 request example](W2_VALIDATION.md) and [D2 contract](phases/PHASE_E3_2.md).

A lost response is checked through GET `/api/cases/{case_id}/tool-recoveries/{request_id}` or the
identical original POST. Do not change request_id to retry HTTP. Stable results return 200,
in-progress records 202; first accepted completion 201. Another execution requires a new explicit
recovery of the current failed/interrupted leaf after its old execution process has exited.

If the tool is COMPLETED while continuation remains RUNNING, stop/wait the API and run offline:

```powershell
.\.venv\Scripts\python scripts/resume_completed_recovery.py --case-id <case_id> --request-id <UUID>
```

DATABASE_URL must point to that case's database. The script loads its latest revision, passes it
as expected_revision and settles continuation in the next formal transition. It must not run
concurrently with API execution. Restart the single API and confirm GET200/SETTLED. This command
cannot execute pending attempts. The F5 experimental wrapper adds observation transactions and
calls the original CLI main; normal CLI logic has no observation instrumentation.

## What it is

Resonique is a Beauty Service Investigation Agent. It reconstructs customer context, separates
verified facts from reports and observations, identifies what is still unknown, and recommends a
safe next action for a human customer-service operator.

## Core principle

**Understand Before Answer. Act with Empathy.** LLM proposes; domain validates; Agent decides;
human approves. Purchase is not usage, temporal association is not causality, and no Evidence means
no attribution.

## Architecture

The runtime is React → FastAPI → `CaseApplicationService` → Evidence grounding/stateful Agent →
PostgreSQL checkpoint and business records. Qwen language and vision providers are optional and
bounded by deterministic validators. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements

- Docker Desktop with Compose (recommended), or Python 3.12+, Node.js 22+, npm, and PostgreSQL 16.
- Optional organizer `.xlsx`, only when authorized and when official S00001/S00009 paths are needed.
- Optional network access and Qwen-compatible credentials for real generation/vision.

## Environment variables

Copy `.env.example` to an untracked `.env`; never commit it.

| Variable | Class | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | PostgreSQL container setting | Currently fixed in `docker-compose.yml`; a same-named `.env` value is not interpolated |
| `DATABASE_URL` | Required for native backend | PostgreSQL application URL |
| `TEST_DATABASE_URL` | Test-only | Isolated DB name containing `test` |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL` | Optional | Real Qwen language generation; safe fallback remains when unavailable |
| `VISION_PROVIDER`, `VISION_MODEL` | Optional | Real Qwen vision using the same key/base URL |
| `OFFICIAL_DATASET_PATH` | Required for official supporting cases | Native workbook path or `/competition-data/official.xlsx` in Compose |
| `VITE_API_BASE_URL` | Frontend build | Browser-visible FastAPI origin; default `http://localhost:8000` |

An empty model configuration does not pretend that Qwen succeeded: model-dependent API actions
return a clear unavailable response or use an explicitly labelled deterministic fallback where the
existing service defines one.

## Docker installation and startup

1. Clone the repository and enter it.
2. Copy `.env.example` to `.env`; configure optional Qwen values. The current Compose file fixes
   local database credentials in both the PostgreSQL service and backend `DATABASE_URL`.
   Changing `.env` alone does not change those credentials; a password change requires a
   separate, coordinated database and configuration update, including any existing database volume.
3. If licensed to use the official workbook, copy it to `competition_data/official.xlsx` and set
   `OFFICIAL_DATASET_PATH=/competition-data/official.xlsx`. Do not add the workbook to Git.
4. Run `docker compose up --build`.
5. Wait until `docker compose ps` reports PostgreSQL, backend, and frontend healthy.
6. Open `http://localhost:5173/`.

The backend container runs Alembic migrations and the idempotent deterministic seed before Uvicorn.
The API readiness probe is `GET http://localhost:8000/health`.

## Native database and backend

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
docker compose up -d postgres
$env:DATABASE_URL="postgresql+psycopg://empathy:<password>@localhost:5432/empathy_copilot"
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m backend.app.persistence.seed_cli
.\.venv\Scripts\python -m uvicorn backend.app.api.main:app --port 8000
```

Set `OFFICIAL_DATASET_PATH` to the workbook's actual path before starting the API if official cases
are required. No source code contains a machine-specific workbook path.

## Frontend

```powershell
cd frontend
npm ci
$env:VITE_API_BASE_URL="http://localhost:8000"
npm run dev
```

The accepted UI remains frozen to the primary S00154 storyline. Supporting official cases are
selected through the stable case API (`GET /api/cases/S00001` and `GET /api/cases/S00009`) and the
prepared deterministic rehearsal, avoiding misleading S00154 Host conversation content. An
unknown/unavailable case produces an explicit API error. Emergency Demo Fixture Mode is visibly
labelled and is not represented as official data.

## Official dataset

The workbook remains an external organizer asset. `OFFICIAL_DATASET_PATH` is read at application
startup; records are normalized, persisted, grounded into Evidence, and checkpointed. The official
workbook references image paths, but those image files were not supplied. The runtime therefore
reports an unavailable official asset and never manufactures it.

### Usage scope pending verification

The repository documents the organizer source and requires permission before redistribution
in [SUBMISSION_MANIFEST.md](SUBMISSION_MANIFEST.md). No organizer license or authorization
document establishing post-competition use was found in the reviewed project materials.
Post-competition public display, redistribution, commercial use, and transmission to external
model providers therefore remain **pending verification**, including derived case excerpts,
screenshots, evaluation records, and database copies. Existing files are retained while this
scope is clarified; competition participation or a Git ignore rule does not establish permission.

[Phase 7](phases/PHASE_7.md) documents exclusion of payment credentials and handler identity
from normalized service records. The adapter still retains message text and source identifiers;
this is not evidence of complete anonymization. Confirm the organizer's masking process and
permitted fields before describing the dataset or its derivatives as safe to publish.

## Demo fixture

`backend/data/demo_assets/demo_broken_pump_001.png` is a synthetic, brand-free fixture for the
independent product-damage vision demonstration. Its identity is `DEMO_FIXTURE` with `fixture=true`.
It is never attached to S00001/S00154 and never becomes a verified business fact or quality verdict.

## Main demo — S00154

Open `/`. Show consumer report, verified business facts, open evidence gaps, SAFETY
gate, attribution other than `SUPPORTED`, provenance, human approval, and suggested response.
Refresh to demonstrate PostgreSQL checkpoint persistence. Do not describe the condition as a
diagnosis or claim that a product caused it.

## Supporting demo — S00001

With the official workbook configured, query `GET /api/cases/S00001` to show the official image
reference and unavailable asset. The independent synthetic fixture is accepted only through the bounded
vision acceptance path; narrate its `AI_OBSERVATION` as an observation, not a verified fact or
quality verdict.

## Supporting demo — S00009

Query `GET /api/cases/S00009`. The official state retains both verified delivery status and the consumer's
non-receipt report. The tested workflow demonstrates `CALL_TOOL` → grounded logistics record →
`WAIT`/checkpoint → resume with later evidence → gap reevaluation → `CONCLUDE`.

## Repeat contact demo

Return to `/` after refresh or backend restart. The checkpoint and Context Passport
restore known facts, service/order history, answered questions, and completed tools. The Agent does
not repeat a resolved question or completed lookup.

## Evaluation

The controlled primary benchmark contains 25 cases: critical-gap recall improved 0.975→1.000;
NBQ changed from 10 MATCH / 1 PARTIAL / 14 MISMATCH to 21 MATCH / 0 PARTIAL / 0 MISMATCH / 4 N/A;
safety mismatches changed 2→0; retrieval calls changed 25→17 (32% reduction). On the same three-case
real-Qwen subset, Resonique tokens changed 7556→5878 (22.21%) and latency 79919→67914 ms (~15.02%).
Unsupported claims remained 0/147. A disjoint four-case holdout retains one NBQ mismatch.

These are controlled project measurements, not industry accuracy. The three-case real-Qwen subset
is not a large-scale production benchmark. Baseline safety/no-question fields are unavailable, not
zero-violation superiority. Full limitations remain in `backend/evaluation_output/` and
`docs/phases/PHASE_9.md`.

## Safety boundaries

The system does not diagnose, confirm allergy/contact dermatitis, infer causality from sequence or
ingredients, promise replacement eligibility, or automatically send a high-impact response.
Consumer assertions stay consumer-reported; AI observations stay observations; human approval is
required at the checkpoint.

## Troubleshooting

- Backend unhealthy: inspect `docker compose logs backend`; verify the DB health and password.
- Case not found: configure the official workbook for S00001/S00009; S00154 is always seeded.
- Qwen unavailable: confirm variables are set without printing the key; the UI/API must show an
  unavailable/fallback state, never simulated success.
- Official image missing: expected for the supplied dataset; do not substitute the demo fixture.
- Port conflict: free ports 5432, 8000, and 5173 or explicitly adjust Compose and frontend API URL.
- Stale revision: refresh the case and repeat the human action using the current revision.
