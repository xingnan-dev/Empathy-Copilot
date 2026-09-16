# Empathy Copilot — Product Requirements

## Positioning

Empathy Copilot is an evidence-first, stateful investigation agent for beauty-service
support. It helps an operator understand a consumer concern before suggesting a reply or
action. It is not a generic chatbot and does not make medical diagnoses.

## Core problem and principles

Beauty complaints often arrive as short, ambiguous narratives. A purchase record does not
prove use; temporal association does not prove causality; an ingredient match does not prove
causality. Before answering, the system must establish what is known, where it came from,
what remains unknown, and the safest next step.

The governing rules are **Understand Before Answer**, **Act with Empathy**, and **No Evidence
→ No Attribution**. `extraction_confidence` describes extraction or observation reliability,
never a medical or causal probability.

## Priorities

### P0

- Formal evidence with structured provenance.
- Deterministic gaps for first use, feedback onset, recent regimen changes, and severity.
- Checkpointable investigation state and bounded questioning.
- Attribution and high-impact-action safety boundaries.
- A credible C Serum / D Cream competition demo.

### P1 (reserved)

- Usage sequence, known sensitivity record, visual evidence, and service history.
- Full agent orchestration, persistence, policy retrieval, and human approval workflow.

### DROP for Phase 1

LLM calls, database/RAG, frontend, authentication, ingredient matching, diagnosis, emotion
models, multimodal processing, multi-agent architecture, and deployment infrastructure.

## Beauty-specific reasoning

The agent reasons from an evidence-backed *change set*, not an assumed complete routine.
New, replaced, stopped, or stable products may be recorded only when supported by evidence.
Concurrent changes weaken single-product attribution. Reports of discomfort remain consumer
reports unless independent evidence changes their classification.

## Competition demo goal

Show that the agent begins with a verified first-purchase order fact while keeping four P0
questions open, resolves first-use time from a sourced consumer message, records D Cream as
another recent factor, and treats it as concurrent only after the consumer confirms an
overlapping date. The agent refuses to claim that C Serum caused the reaction.
