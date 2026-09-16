# Empathy Copilot

Evidence-first, stateful investigation foundations for beauty-service support.

Current phase: **Phase 2 — Stateful Investigation Agent Loop**.

The repository contains the evidence-first domain foundation and a deterministic LangGraph
workflow with development-only in-memory checkpoints and stub tools. It deliberately contains
no frontend, database, real external tool, or real LLM integration.

## Development

Requires Python 3.12 or newer.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m mypy
```

The detailed product and architecture decisions live under `docs/`.
