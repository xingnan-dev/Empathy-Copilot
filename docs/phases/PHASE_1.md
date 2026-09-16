# Phase 1 — Evidence & Agent Domain Foundation

## Goal

Create a small, testable domain foundation that preserves evidence provenance, tracks P0
investigation gaps, serializes state, and blocks unsupported causal attribution.

## Delivered scope

- Python 3.12 project bootstrap with FastAPI and Pydantic dependencies.
- Evidence/provenance, P0 gaps, action/status, investigation state, regimen changes, and
  deterministic guardrails.
- Structured Golden Demo fixtures and unit tests.
- Product, design, phase, and demo documentation.

Phase 1 established the concepts. The read-only architecture review identified loose payload
validation, incomplete recovery records, and fixture/document mismatches. Those findings are
addressed by the bounded Phase 1.1 hardening described in `PHASE_1_1.md`.

## Out of scope

No frontend, database, LLM/Qwen call, LangGraph workflow, RAG, multimodal API,
authentication, ingredient matching, multi-agent system, or deployment work.

