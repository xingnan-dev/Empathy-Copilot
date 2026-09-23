# Empathy Copilot

Evidence-first, stateful investigation foundations for beauty-service support.

Current phase: **Phase 5 — Product Integration**.

The repository contains the evidence-first domain foundation, a deterministic LangGraph
workflow, local demo and PostgreSQL business repositories, typed business tools, an explicit
Evidence grounding boundary, durable PostgreSQL checkpoints, and a thin FastAPI projection
used by the React UI. It deliberately contains no real LLM or official dataset integration.

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

Copy `.env.example` values into your shell environment; do not create or commit real secrets.
The included Compose file starts PostgreSQL only:

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

The detailed product and architecture decisions live under `docs/`.
