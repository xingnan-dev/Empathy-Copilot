# Resonique

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
- The official competition `.xlsx` supplied by the organizer for official S00001/S00009 data.
- Optional network access and Qwen-compatible credentials for real generation/vision.

## Environment variables

Copy `.env.example` to an untracked `.env`; never commit it.

| Variable | Class | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | Required for Compose | Local competition database password |
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
2. Copy `.env.example` to `.env`; set `POSTGRES_PASSWORD` and optional Qwen values.
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
