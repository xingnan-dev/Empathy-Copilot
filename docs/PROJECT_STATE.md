# Project State

## Project identity

- **Product:** Resonique
- **Repository:** Empathy-Copilot
- **Role:** Beauty Service Investigation Agent
- **Operating model:** ChatGPT project `blackkesong` owns planning, product design, review, and competition materials; Codex owns code changes, tests, and Git. This repository is the single source of truth.

## Competition

- **Event:** L'Oréal Beauty Tech Hackathon 2026
- **Team:** Oasis
- **Entry:** Resonique
- **Submission date:** 2026-10-05
- **Competition PPT:** SUBMITTED
- **Demo Video:** SUBMITTED
- **Final Submission Audit:** COMPLETE
- **Competition submission:** COMPLETE
- **Current focus:** Post-submission stabilization

## Product positioning

Resonique is an evidence-aware, stateful investigation agent for beauty-service support. It reconstructs what is known, preserves provenance and uncertainty, and prepares empathetic, actionable next steps for human approval.

## Current baseline

- **Version:** V1.0 Technical Freeze
- **Release:** Resonique v1.0.0 Competition Submission
- **Phase:** Post-submission Stabilization
- **Frozen technical baseline:** `44073aca8077e46e187bb4eb7d4f8370a8452c8c`
- **Technical development:** COMPLETE / PERMANENTLY FROZEN

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

Competition Hotfix 1 is complete. Explicit consumer-reported product usage is grounded as `CONSUMER_REPORTED`; for S00154, `exact_product_used = 面霜` and the deterministic NBQ advances to `ACTUAL_FIRST_USE_TIME`.

Competition Enhancement 1 is complete. The deterministic, read-only `ServiceStrategyPolicy` implements **Consumer Signal → Service Strategy → Action**. Emotion remains an auxiliary `AI_INFERENCE`; it does not change Evidence, Attribution, Safety, Agent routing, or human-approval requirements. No new LLM call was added.

## Current restrictions

- The competition version may receive only critical bug, security, or deployment fixes.
- New functionality must enter a separate v1.1 phase and must not directly modify the competition version.
- Do not redesign the accepted UI.
- Do not modify `ui-prototype/` unless explicitly instructed.
- Preserve evidence provenance and deterministic safety boundaries.

## Current work

- **Next phase:** Await competition results while planning the v1.1 investigation loop.
- Keep the technical baseline frozen during post-submission stabilization.
