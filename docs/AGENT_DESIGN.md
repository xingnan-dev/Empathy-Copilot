# Agent Design V1.1

## Evidence and provenance

Every `Evidence` requires an immutable structured `EvidenceSource`: source type, concrete
source id, and display label. Evidence type/source pairs are validated deterministically:

- verified business facts: order, service, product, or policy systems;
- consumer reports: consumer messages;
- AI observations: uploaded images;
- AI inferences: AI reasoning;
- explicit unknowns: business or consumer sources, never AI reasoning.

Unknown remains useful when a source explicitly says a value is unavailable. Ordinary
absence is an open gap. UNKNOWN never resolves a gap.

`extraction_confidence` measures the reliability of extraction or observation. It is not a
medical probability, causal probability, or product-blame probability. For a verified
business fact, it means the source record was read reliably; it does not establish causality.

Evidence value and metadata are JSON-safe. Dates used by domain behavior live in explicit
validated payload fields rather than arbitrary metadata.

## Deterministic P0 gaps

Each P0 gap has a fixed policy checking case id, key, value shape, evidence type, and source:

- actual first use requires a consumer-message payload with product id/name and first-use
  date or datetime;
- feedback onset requires a consumer-message onset date or datetime;
- recent regimen change requires product id/name, a valid change type, and optional effective
  date;
- reported severity requires an explicit consumer report of `MILD`, `MODERATE`, `SEVERE`, or
  `UNKNOWN`.

All supporting ids are retained when multiple valid Evidence records resolve one gap.
`NOT_APPLICABLE` and P1 gap vocabulary remain reserved; an LLM cannot set them.

## State, questions, and tool calls

`InvestigationState` separates action intent from lifecycle status and rejects the minimum
illegal combinations needed before orchestration. Waiting for a user requires a pending or
asked question. Waiting for a human cannot ask a user. Escalated, concluded, and terminated
states cannot have a current action.

`AskedQuestion` records identity, target gap, original and normalized text, lifecycle status,
send time, and answering Evidence ids. PENDING means generated but unsent; ASKED means sent;
ANSWERED means linked Evidence exists. `question_count` equals unique ASKED plus ANSWERED ids;
PENDING does not count. Deduplication is intentionally lexical (NFKC, case-fold, punctuation
and whitespace removal), not semantic.

`ToolCallRecord` records id, tool name, JSON arguments, status, timestamps, and result
Evidence ids. It does not execute or retry tools; it only provides enough checkpoint state
to avoid blindly repeating a completed call later.

`state_schema_version` identifies the State JSON schema and defaults to 1. `state_revision`
starts at 0 and is intended to increment once per formal transition. Phase 1.1 defines these
semantics; the implemented step-limit transition increments it exactly once. Phase 1.1 does
not implement persistence or optimistic locking.

## Regimen changes

Regimen changes require product id, product name, effective date when known, and source
Evidence ids. They are built only from same-case consumer-message Evidence that explicitly
reports first use or a new/replaced/stopped change. `STABLE` remains vocabulary but does not
resolve a recent-change gap in Phase 1.1. AI inference and first-purchase
orders cannot become routine facts. A confirmed first use may create `NEW`; a purchase may
not.

## Attribution guard

Decisions are `INSUFFICIENT_EVIDENCE`, `ATTRIBUTION_AMBIGUOUS`, and reserved `SUPPORTED`.
There is no automatic `SUPPORTED` path in Phase 1.1. Resolved gaps plus temporal ordering
remain insufficient. Ambiguity requires the candidate product and another explicitly
reported NEW/REPLACED product to share a known effective date; two names alone are not enough.

## Limits and lifecycle guards

`question_count` and `step_count` count completed external questions and completed formal
transitions respectively. With a maximum of 3, counts 0, 1, and 2 permit the next operation;
count 3 blocks it. Terminated, concluded, escalated, and waiting-for-human states cannot ask.

## LLM / deterministic boundary

Future LLM work is limited to language understanding, structured extraction candidates,
candidate questions/replies, and image observations. Deterministic code owns provenance
validation, evidence payload validation, gaps, limits, deduplication, lifecycle legality,
attribution, high-impact action gates, human-review requirements, and termination.

## Future considerations beyond Phase 2

Evidence retraction/supersession, optimistic concurrency, distributed checkpoints,
multi-tenant source namespaces, semantic deduplication, real tool retry/execution, database
persistence, LLM integration, and frontend work are explicitly deferred.

## Phase 2 stateful agent loop

Phase 2 adds a compiled LangGraph `StateGraph` around the hardened domain state. Graph state
contains `InvestigationState` plus an ephemeral structured `NextActionDecision`; the latter
never bypasses domain validation. The graph performs deterministic evaluation, decision,
action preparation, and pause/termination routing.

The nodes are intentionally small: evaluate derived gaps, decide the next action, prepare a
question, execute a stub tool lifecycle, escalate, wait for a human, conclude, or terminate.
Tool completion routes back through evaluation. User/human pauses and terminal outcomes end
the invocation and are checkpointed by the workflow facade.

### Transition semantics

`StateTransitionService` is the sole entry point for formal lifecycle transitions. It checks
the allowed status edge, updates status/action/reason/timestamps, increments `state_revision`
exactly once, advances the completed-transition counter, and appends one `TransitionEvent`.
Derived gap refresh is explicitly non-transitional. Terminal states have no outgoing edges.

### Decision and execution boundary

`DeterministicDecisionPolicy` returns a typed decision containing action, reason, target gap,
tool name, and question intent. It does not execute the action or generate free-form answers.
Priority is transition limit, explicit severe report, human-review flag, missing order tool,
explicit policy retrieval, open P0 gaps, undated reported regimen changes, then conclusion.

Question wording comes from a deterministic registry. Questions move from locally prepared
PENDING records to ASKED records in the single send transition. Resume links matching
Evidence and marks the record ANSWERED before graph re-entry.

### Checkpoint and resume

`InMemoryCheckpointStore` serializes State JSON by case id. It is development-only and not a
database. A new workflow instance can share the store, load a paused case, ingest same-case
Evidence, answer matching questions, recompute gaps, transition back to INVESTIGATING, and
invoke a freshly compiled graph without losing question, tool, result, or trace history.

### Tool stubs and conclusion

The registry exposes deterministic `get_order_history` and `retrieve_service_policy` stubs.
Each call is recorded as PENDING, RUNNING, then COMPLETED, and output Evidence ids are linked.
A matching completed call is never executed again. These stubs make no network requests.

Conclusion stores only an `InvestigationResult` containing attribution decision and reason.
The Phase 2 attribution guard still has no automatic `SUPPORTED` path. An explicit SEVERE
consumer report escalates to human service without diagnosis or medical advice.

## Phase 3 business grounding

Phase 3 replaces the order lookup stub with repository-backed local demo tools and adds
service-history and consumer-memory tools. Repository protocols isolate data access; only the
demo repository implementation reads JSON. Tool results are typed raw records and cannot be
inserted into State directly.

`EvidenceGroundingService` is the single conversion boundary from raw tool results to
Evidence. Order records retain exact order provenance and prove purchase only. Historical
service records retain exact service-record provenance and remain historical context.
Neither source can prove actual use, regimen membership, symptoms, concurrent changes, or
causality. Unknown consumers produce empty results and no placeholder Evidence.

`ConsumerMemorySnapshot` and `ContextPassport` are deterministic Evidence projections. Every
memory fact references existing Evidence ids. Passport confirmed facts exclude AI inference
and explicit unknowns; it also carries open gaps, question history, completed tools,
historical service summary, lifecycle status, and current action for repeat-contact handoff.
The checkpointed `InvestigationState` remains authoritative.

The decision policy acquires order context before asking about actual first use, then acquires
historical service and memory context before continuing with remaining consumer-experience
gaps. A completed empty lookup is not retried. The existing attribution guard remains in
force and has no automatic `SUPPORTED` path.
