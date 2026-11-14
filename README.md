# Resonique — Empathy Copilot

Evidence-first, stateful investigation for beauty-service support. Resonique reconstructs
context, preserves provenance, identifies evidence gaps, and proposes a safe next action for
human approval. It does not diagnose or infer causality from timing alone.

Originally developed by Team Oasis for the L'Oréal Beauty Tech Hackathon 2026, Resonique is
now continuing as an independent post-competition development project. The competition has
ended and the team did not advance, as reported by the project owner. The competition release
remains a frozen historical baseline.

The runtime is React → FastAPI → deterministic domain/agent workflow → PostgreSQL, with
optional Qwen language and vision providers. W0 / E3.1 validation was accepted on 2026-11-14.
The [reviewed recovery specification](docs/phases/PHASE_E3_2.md) has been implemented in W2 with
local-sample and isolated PostgreSQL verification. See the [W2 handoff](docs/W2_VALIDATION.md)
for operation, results and limitations. W2 awaits review; W3 independent process-fault acceptance
has not started. The [W0 validation record](docs/W0_VALIDATION.md) remains the original baseline.

## Reading guide

- **Current development:** [Project state](docs/PROJECT_STATE.md),
  [Phase E3.1](docs/phases/PHASE_E3_1.md), and
  [post-competition plan](docs/POST_COMPETITION_PLAN.md). Coding agents must first follow
  the reading order in [AGENTS.md](AGENTS.md), including the [PRD](docs/PRD.md) and
  [Agent Design](docs/AGENT_DESIGN.md).
- **Run and understand the system:** [Run guide](docs/COMPETITION_RUN_GUIDE.md),
  [architecture](docs/ARCHITECTURE.md), and [demo operator guide](docs/DEMO_OPERATOR_GUIDE.md).
  The run guide retains its existing filename and covers current local setup, data sources,
  and usage permissions still to be verified.
- **Competition history:** [Submission manifest](docs/SUBMISSION_MANIFEST.md),
  [delivery freeze](docs/phases/PHASE_10_1.md), [phase records](docs/phases/),
  [early Golden Demo](docs/DEMO_SCRIPT.md), and [evaluation records](backend/evaluation_output/).
  The preserved release tag is `v1.0.0-competition-submission`.

## Development

Requires Python 3.12 or newer.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m mypy
```

## Local PostgreSQL

Set local environment values using `.env.example`; never commit real secrets.
The following command starts only the PostgreSQL service from the Compose stack:

```powershell
docker compose up -d postgres
$env:DATABASE_URL="postgresql+psycopg://empathy:empathy_local@localhost:5432/empathy_copilot"
alembic upgrade head
python -m backend.app.persistence.seed_cli
```

Integration tests require a separate database whose name contains `test`:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://empathy:empathy_local@localhost:5432/empathy_copilot_test"
python -m pytest -m postgres
```

The PostgreSQL tests intentionally refuse a `TEST_DATABASE_URL` whose database name does not
contain `test` before rebuilding its schema.

## Complete local runtime

Copy `.env.example` to a local, untracked `.env` and optionally configure Qwen. The current
Compose file uses fixed local database credentials; setting `POSTGRES_PASSWORD` in `.env`
does not override them. See the run guide for the configuration boundary.
If authorized to use the official cases, place the supplied workbook at
`competition_data/official.xlsx` and set `OFFICIAL_DATASET_PATH=/competition-data/official.xlsx`.
Then run:

```bash
docker compose up --build
```

Open `http://localhost:5173/`. The backend health endpoint is
`http://localhost:8000/health`. See the [run guide](docs/COMPETITION_RUN_GUIDE.md) for native development, supporting
demo paths, fixture disclosure, evaluation limitations, and troubleshooting.
