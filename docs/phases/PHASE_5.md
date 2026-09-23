# Phase 5 — Product Integration

## Goal

Connect the frozen React UI to the authoritative `InvestigationState` through a thin
FastAPI application boundary. Human approval and structured consumer answers travel back
through validated domain transitions and durable checkpoints.

## Architecture

`React -> FastAPI -> CaseApplicationService -> Workflow/TransitionService -> CheckpointStore`.
The API returns an explicit `CaseView`; it never exposes the full domain snapshot. Safety
path and UI-specific S00154 gaps are deterministic presentation projections, not new domain
facts. Evidence type and structured provenance remain intact.

## API

- `GET /api/cases/{case_id}` loads a case projection.
- `POST /api/cases/{case_id}/human-approval` accepts only `expected_revision`.
- `POST /api/cases/{case_id}/resume` accepts one allow-listed structured consumer answer.

Errors use stable codes: `CASE_NOT_FOUND`, `STATE_CONFLICT`, `INVALID_TRANSITION`, and
`VALIDATION_ERROR`. The browser uses `BACKEND_UNAVAILABLE` only as a presentation error.

## Runtime state and concurrency

The frontend loads before rendering case content and does not silently substitute fixture
data. An explicit Demo Fixture Mode remains available for visual development. Mutations
carry `expected_revision`; stale writes return HTTP 409. Approval uses
`StateTransitionService` and persists the advanced revision through the configured store.

## Local run

```powershell
docker compose up -d postgres
$env:DATABASE_URL="postgresql+psycopg://empathy:empathy_local@localhost:5432/empathy_copilot"
alembic upgrade head
python -m backend.app.persistence.seed_cli
uvicorn backend.app.api.main:app --reload
cd frontend
npm run dev
```

Set `VITE_API_BASE_URL` only when the API is not at `http://localhost:8000`.

## Tests

API tests cover projection boundaries, not-found behavior, approval, invalid transitions,
revision conflicts, resume validation, provenance, gaps, attribution, and purchase/usage
separation. PostgreSQL integration reuses the Phase 4 isolated database infrastructure.

## Known limitations

S00154 is a backend-owned integration fixture until the official dataset adapter exists.
Suggested response wording remains a clearly labelled deterministic frontend placeholder.

**NO LLM IN PHASE 5. NO OFFICIAL DATASET ADAPTER IN PHASE 5.**
