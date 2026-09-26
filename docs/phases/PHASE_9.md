# Phase 9 — Evaluation and Pre-optimization Baseline

Phase 9 adds an evaluation-only harness comparing a fair answer-first baseline with the
existing evidence-first production path. It does not add Agent capabilities or optimize
prompts, context, retrieval, model selection, caching, or decision policy.

The benchmark uses independent golden labels from official facts, deterministic domain rules,
and controlled test design. Core safety, grounding, provenance, gap, repetition, and tool metrics
are deterministic; an LLM judge is not authoritative. Official, controlled, and adversarial cases
remain explicitly separated.

Runtime output belongs under `backend/evaluation_output`, outside the production package. Model
telemetry may record provider, model, calls, token counts, latency, fallbacks, and errors, but never
credentials, full prompts, image Base64, or database passwords. Prices are configurable and costs
remain null when no verified pricing profile is supplied.

This round records the raw pre-optimization baseline and stops. Optimization and Phase 10 are out
of scope.

## Round 2 measurement boundary

Round 2 preserves `phase9-preopt-v1` and runs the identical 25 cases as `phase9-postopt-v1`.
Corrections are limited to documented golden-label errors, deterministic scenario gap priority,
resolved/asked-gap filtering, conditional evaluation retrieval, and provenance-preserving relevant
Evidence selection. PRE and POST reports remain separate, and an untouched four-case official
holdout checks generalization. Model-call count is not reduced when one response generation remains
necessary. No product capability, model, production prompt, or case-id-specific production behavior
is added.
