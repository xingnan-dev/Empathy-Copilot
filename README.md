# Empathy Copilot

Evidence-first, stateful investigation foundations for beauty-service support.

Current phase: **Phase 3 — Business Tools + Evidence Grounding**.

The repository contains the evidence-first domain foundation, a deterministic LangGraph
workflow, development-only in-memory checkpoints, local demo business repositories, typed
business tools, and an explicit Evidence grounding boundary. It deliberately contains no
frontend, database, network business API, or real LLM integration.

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
