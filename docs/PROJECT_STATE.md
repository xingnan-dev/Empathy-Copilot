# Project State

## Project identity

- **Product:** Resonique
- **Repository:** Empathy-Copilot
- **Role:** Beauty Service Investigation Agent
- **Operating model:** ChatGPT project `blackkesong` owns planning, product design, review, and competition materials; Codex owns code changes, tests, and Git. This repository is the single source of truth.

## Competition

- **Event:** L'Oréal Beauty Tech Hackathon 2026
- **Current focus:** Competition packaging

## Product positioning

Resonique is an evidence-aware, stateful investigation agent for beauty-service support. It reconstructs what is known, preserves provenance and uncertainty, and prepares empathetic, actionable next steps for human approval.

## Current baseline

- **Version:** V1.0 Technical Freeze
- **Phase:** Phase 10.2 — Competition PPT & Storytelling
- **Main HEAD:** `fb534f6b5f56cf611407a4f5a24bba02950f215a`
- **Technical development:** COMPLETE / FROZEN

## Core innovations

1. Evidence-aware Reasoning
2. Stateful Investigation Agent
3. Actionable Empathy

## Core principles

- **Understand Before Answer.**
- **Act with Empathy.**
- **LLM proposes. Domain validates. Agent decides. Human approves.**

## Demo cases

- **Primary:** S00154
- **Supporting:** S00001, S00009, Repeat Contact

## Technical stack

- **Frontend:** React, Vite, TypeScript, Tailwind
- **Backend:** Python, FastAPI
- **Agent:** LangGraph
- **Model:** Qwen
- **Database:** PostgreSQL
- **Deployment:** Docker Compose

## Completed phases summary

Phases 0–9 established and validated the evidence/provenance domain, deterministic safety boundaries, stateful LangGraph investigation, business grounding, durable persistence, API and accepted UI, Qwen integration, official competition data, multimodal handling, and evaluation/optimization. Phase 10.1 completed competition delivery readiness and froze accepted product behavior.

## Current restrictions

- No new product features or unrelated technical phases.
- Only fix demo blockers, critical bugs, or deployment blockers.
- Do not redesign the accepted UI.
- Do not modify `ui-prototype/` unless explicitly instructed.
- Preserve evidence provenance and deterministic safety boundaries.

## Current work

- Competition PPT and storytelling
- Demo video preparation
- Final submission audit

## Pending competition deliverables

- Competition PPT
- Demo Video
- Final Submission Audit
