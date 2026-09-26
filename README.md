# Resonique — Empathy Copilot

Evidence-first, stateful investigation for beauty-service support. Resonique reconstructs
context, preserves provenance, identifies evidence gaps, and proposes a safe next action for
human approval. It does not diagnose or infer causality from timing alone.

The competition runtime is React → FastAPI → deterministic domain/agent workflow → PostgreSQL,
with optional Qwen language and vision providers. Start with
[`docs/COMPETITION_RUN_GUIDE.md`](docs/COMPETITION_RUN_GUIDE.md); competition operators should
use [`docs/DEMO_OPERATOR_GUIDE.md`](docs/DEMO_OPERATOR_GUIDE.md).

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

## Complete competition runtime

Copy `.env.example` to a local, untracked `.env`, change the database password, and optionally
configure Qwen. For official cases, place the supplied workbook at
`competition_data/official.xlsx` and set `OFFICIAL_DATASET_PATH=/competition-data/official.xlsx`.
Then run:

```bash
docker compose up --build
```

Open `http://localhost:5173/`. The backend health endpoint is
`http://localhost:8000/health`. See the competition guide for native development, supporting
demo paths, fixture disclosure, evaluation limitations, and troubleshooting.
