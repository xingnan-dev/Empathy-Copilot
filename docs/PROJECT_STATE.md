# Project State

## Project identity

- **Product:** Resonique
- **Repository:** Empathy-Copilot
- **Role:** Beauty Service Investigation Agent
- **Development mode:** Independent post-competition development, building on the preserved Team Oasis baseline.
- **Operating model:** ChatGPT project `blackkesong` owns planning, product design, review, and project materials; Codex owns code changes, tests, and Git. This repository is the single source of truth.

## Competition history

- **Event:** L'Oréal Beauty Tech Hackathon 2026
- **Team:** Oasis
- **Entry:** Resonique
- **Submission date:** 2026-10-05
- **Competition PPT:** SUBMITTED
- **Demo Video:** SUBMITTED
- **Final Submission Audit:** COMPLETE
- **Competition submission:** COMPLETE
- **Outcome:** The competition has ended and the team did not advance, as reported by the project owner on 2026-11-07.

Submission dates and completed PPT/video records above are historical facts, not current
development requirements. See [the submission manifest](SUBMISSION_MANIFEST.md).

## Product positioning

Resonique is an evidence-aware, stateful investigation agent for beauty-service support. It reconstructs what is known, preserves provenance and uncertainty, and prepares empathetic, actionable next steps for human approval.

## Frozen competition baseline

- **Version:** V1.0 Technical Freeze
- **Release:** Resonique v1.0.0 Competition Submission
- **Historical phase:** Competition delivery freeze (Phase 10.1)
- **Frozen technical baseline:** `44073aca8077e46e187bb4eb7d4f8370a8452c8c`
- **Competition release tag:** `v1.0.0-competition-submission`
- **Competition release commit:** `e77ef5a063179cba3c7aa3cc0a3438d89b5646c2`
- **Freeze scope:** The competition technical baseline and release remain frozen. Independent development proceeds in separately reviewed post-competition increments.

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

- **Productization branch:** `codex/phase-e3-2-readonly-recovery`
- **Phase E3.1:** Durable tool failure handling implemented and locally validated on isolated
  PostgreSQL: 159 tests passed, 28 skipped for documented official-data/real-model dependencies;
  the PostgreSQL subset passed 20 checks with one official-data skip. Ruff and mypy passed.
  See [W0 validation](W0_VALIDATION.md) for scope, environment, and limitations. W0/E3.1 review was accepted on 2026-11-14; the frozen competition tag and commit remain unchanged.
- **Implementation commit:** `a89bed63f5581280d4c2041016ba5f9645ec5a79`.
- **Current phase:** W1 and its supplement accepted; W2 implementation and local validation
  accepted by static review; W3 independent-process acceptance in progress against [D2 / E3.2](phases/PHASE_E3_2.md) at
  `af52b577ac8b69daca0e97995c613efd2427c124`.
  W3 starting checkpoint: `3893e68012c2236cdfa5844b27430656bc8357cf`.
- **W2 verification:** [Execution and validation handoff](W2_VALIDATION.md): 218 passed,
  28 external-input skips; PostgreSQL subset 36 passed / 1 official-data skip; Ruff and mypy passed.
  Implementation checked at `da131051af0f4849b6ae2a3677e15e7c887ba8f8`.
- **Plan:** [Post-competition engineering plan](POST_COMPETITION_PLAN.md); further recovery work
  follows the reviewed D2 contract; W3 process-fault acceptance remains pending.
- Keep the competition technical baseline and submission tag frozen during independent development.
- **Accepted post-competition baseline:** `ff1e35b4ba67e952386253a09d772e0e6918965a`.
  W2 now implements manual readonly recovery; independent process fault acceptance is not complete.

## Reading and operation

- Follow [AGENTS.md](../AGENTS.md) for the required development reading order; the active phase
  is [E3.2 / W2](phases/PHASE_E3_2.md).
- Use the [run guide](COMPETITION_RUN_GUIDE.md) for local setup and data-source requirements,
  and the [operator guide](DEMO_OPERATOR_GUIDE.md) for the existing demonstration paths.
- Historical phase requirements and submission records remain available as baseline evidence;
  they do not set new submission deadlines or replace current phase acceptance criteria.
