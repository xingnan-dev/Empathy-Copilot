# Phase 1.1 — Domain Hardening

## Why

Passing Phase 1 tests did not prove the models were safe for a stateful graph. Review found
that key-only gaps could resolve from invalid evidence, state could contain illegal lifecycle
combinations, question/tool progress was not resumable, and the Golden Demo claimed C/D
concurrency without dated evidence.

## Changes

- Added strict Evidence type/source pairing, JSON-safe values, and unambiguous
  `extraction_confidence`.
- Replaced key-only gap matching with four deterministic same-case policies and typed payload
  validation.
- Added QuestionRecord lifecycle, minimal ToolCallRecord, state invariants, schema version,
  and state revision.
- Limited regimen derivation to explicit same-case consumer usage/change reports.
- Renamed conflict to attribution ambiguity and required genuinely overlapping known dates.
- Corrected Golden Demo evidence so purchase never implies use and D is concurrent only after
  the consumer supplies its date.
- Added negative, boundary, JSON, lifecycle, Golden Demo, and no-SUPPORTED-path tests.

## Deferred review findings

Evidence retraction/supersession, optimistic locking, multi-tenant source namespaces,
semantic question deduplication, distributed checkpointing, tool retry/execution, real
LangGraph, persistence, LLMs, and frontend work remain future considerations by design.

## Phase 2 readiness

Phase 1.1 provides a bounded, serializable state contract and deterministic evidence safety
foundation. Phase 2 may consume these models, but must implement formal transition helpers,
increment `state_revision` exactly once per transition, and keep all existing deterministic
guards outside LLM control.

