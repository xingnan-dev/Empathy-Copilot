# Phase 3 — Business Tools + Evidence Grounding

## Goal

Connect the deterministic investigation loop to local demo business data without allowing
raw tool output to bypass provenance, gap policy, regimen policy, or attribution safety.
Phase 3 remains local and deterministic: there is no network API, database, frontend, or LLM.

## Architecture

The data path is deliberately one-way:

```text
JSON demo data -> repository protocol -> typed ToolResult
  -> EvidenceGroundingService -> Evidence -> InvestigationState
  -> deterministic gaps / memory / Context Passport / attribution
```

Only repository implementations read JSON. Business tools depend on repository protocols and
return typed raw records. `EvidenceGroundingService` is the conversion boundary: tools cannot
directly mutate State or manufacture unproven consumer experience.

## Business Data Model

`ConsumerRecord` stores only an identifier and explicit stored preferences. `OrderRecord`
stores order, consumer, product, timestamp, quantity, and first/repeat-purchase status.
`ServiceRecord` stores historical case identity, issue type, contact time, resolution status,
and source summary. The models deliberately contain no inferred personality, health, wealth,
brand-loyalty, usage, or causality fields.

## Repository Architecture

`ConsumerRepository`, `OrderRepository`, and `ServiceHistoryRepository` are narrow protocols.
The demo implementations validate local JSON into typed records and return copies selected by
consumer id. LangGraph, decision policy, and domain services never read fixture files.

## Demo repositories and tools

The local dataset contains consumers, orders, and historical service records. The three P0
business tools are `get_order_history`, `get_service_history`, and `get_consumer_memory`.
Calls retain the Phase 2 PENDING -> RUNNING -> COMPLETED lifecycle and link every grounded
Evidence id. Equivalent completed calls are not executed again after checkpoint restore. The
Phase 2 policy stub remains available but is not a Phase 3 P0 business tool.

## Provenance

Every grounded business fact uses the existing Phase 1 Evidence model. Source type identifies
the business system, source id identifies the exact order, service, or consumer record, and
source label remains displayable. Grounding sets observation time from the source record when
available; extraction confidence describes reliable record extraction, never causal certainty.

## Grounding rules

Orders become `VERIFIED_BUSINESS_FACT` Evidence with exact `ORDER_SYSTEM` record identity.
They prove purchase events only. They never establish actual usage, first-use time, current
regimen, symptoms, temporal concurrency, or causality.

Historical service records become `VERIFIED_BUSINESS_FACT` Evidence with exact
`SERVICE_SYSTEM` record identity. They are historical context and never establish the cause
of the current case. Explicit stored preferences are also service-system facts.

An unknown consumer returns empty typed results and therefore creates no synthetic Evidence.
The agent continues to ask for required consumer experience when deterministic gaps remain.

## Consumer memory and Context Passport

`ConsumerMemorySnapshot` is a projection of grounded Evidence, not a parallel source of
truth. Every fact carries one or more Evidence ids. It may summarize repeat purchases,
recent orders, previous service contacts, and explicit preferences; none asserts current use.

`ContextPassport` deterministically projects confirmed sourced facts, open gaps, question
history, completed tools, historical service context, lifecycle status, and current action.
AI inference and explicit unknowns are excluded from `confirmed_facts`. The passport supports
repeat-contact continuity but does not replace the full checkpointed State.

## Decision policy

The policy separates business-context acquisition from consumer-experience questions. It
retrieves order context first, then asks the consumer for actual first use. Once answered, it
retrieves historical service and evidence-backed memory before continuing through remaining
P0 consumer gaps. Empty completed tools are still complete and do not loop indefinitely.

## Safety boundaries

- Purchase time is never copied into usage time.
- Repeat purchase is not current-use proof.
- Historical service is not current-case causality.
- Tool results resolve no P0 experience gap unless grounded Evidence satisfies existing policy.
- Order and service Evidence cannot create a `RegimenChange`.
- Phase 3 retains no automatic `SUPPORTED` attribution path.

## Golden Demo and repeat contact

The Golden Demo begins with no preloaded order Evidence. `get_order_history` finds Order
`A1024` and grounds C Serum first purchase, while all four experience gaps remain open and no
regimen change is created. The agent asks when C Serum was actually first used. Message M102
supplies September 12 as consumer-reported first use; only that message resolves the gap and
creates the C Serum `NEW` regimen change.

On resume, the loop retrieves historical service context and consumer memory, preserving all
Evidence ids. A later workflow instance can load the checkpoint and build the same Context
Passport without re-asking the answered first-use question or repeating completed tools. An
undated D Cream report remains a consumer report and does not establish concurrency.

## Acceptance

- Repository protocols isolate demo JSON loading from tools and domain services.
- All three P0 tools return typed raw results.
- All raw business results pass through grounding before State mutation.
- Memory and passport facts are traceable to existing Evidence ids.
- Unknown consumers create no fake Evidence.
- Purchase, usage, regimen, historical context, and causality remain distinct.
- Checkpoint/resume preserves completed tool and question history.
- Full tests, Ruff, and strict mypy pass.

## Tests

Behavioral tests cover typed repository results, provenance, empty data, grounding boundaries,
purchase-versus-usage regressions, memory traceability, tool lifecycle and idempotency,
decision routing, Context Passport, checkpoint repeat contact, Golden Demo progression, and
C/D attribution guards. All earlier phase tests remain part of the full suite.

## Known Limitations

Repositories are process-local JSON adapters; checkpoints are process-local memory. There is
no persistence, network retry, distributed locking, semantic deduplication, source freshness
policy, LLM extraction, or external business integration. Context Passport is a deterministic
projection rather than an independently versioned persistence contract. These are later-phase
concerns and do not weaken the Phase 3 evidence boundaries.
