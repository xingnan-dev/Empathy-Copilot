# Phase 7 — Official Dataset Adapter and Multi-scenario Grounding

## Scope

Phase 7 replaces the single-case fixture boundary with a read-only adapter for the official
competition workbook. It normalizes consumers, sessions, messages, orders, and service records;
persists those records; grounds auditable evidence; and projects four supported investigation
scenarios through the existing application API. It does not redesign the UI or add model, vision,
retrieval, or autonomous action capabilities.

## Architecture boundary

The workbook adapter performs schema validation and record normalization only. It does not decide
case actions, resolve attribution, or infer facts absent from source fields. Grounding creates
typed Evidence with source IDs, labels, timestamps, and official-record metadata. Deterministic
domain policies then evaluate gaps and safety state.

The supported flow is:

`official workbook -> normalized records -> PostgreSQL -> grounded Evidence -> scenario gaps ->
checkpoint -> API projection -> existing React UI`

## Normalized records

- `OfficialConsumerRecord`: stable consumer identity.
- `ConversationSession`: source scene, scenario classification, and linked order/ticket IDs.
- `MessageRecord`: ordered message transcript, role, content type, and optional image metadata.
- `OfficialOrderRecord`: order and product facts; purchase never proves actual use.
- `OfficialServiceRecord`: ticket status and operational fields, excluding payment credentials and
  handler identity from the normalized model.

Imports are idempotent upserts keyed by source record IDs. Conversation sessions and messages are
stored separately so reconstruction does not depend on the source workbook remaining available.

## Scenario taxonomy and required gaps

| Official scene | Scenario | Required evidence themes |
| --- | --- | --- |
| 不良反应 | `ADVERSE_REACTION` | exact product used, usage/onset timing, regimen changes, severity, current symptoms, medical attention |
| 补发换货 | `PRODUCT_DAMAGE` | affected item, damage description, image availability, order match, replacement eligibility |
| 物流异常 | `LOGISTICS_EXCEPTION` | order/logistics status, consumer receipt status, delivery evidence, investigation and resolution |
| 退款打款 / 售后退货 | `AFTER_SALES` | request/status, order match, eligibility, required evidence, resolution path |

Unknown scenes remain unclassified rather than being forced into a scenario.

## Evidence semantics

- Consumer statements remain `CONSUMER_REPORTED`, including statements copied into a service
  record. They do not become verified business facts merely because they appear in a ticket.
- Order, logistics, and workflow status fields can be `VERIFIED_BUSINESS_FACT` when grounded in
  their authoritative business records.
- An image path proves only that image evidence is available. `vision_analyzed=false` is retained;
  no visual observation is invented.
- Conflicting verified and consumer-reported facts are retained together and explicitly projected.
- Prior sessions for the same consumer are grounded as service-history context, preserving source
  session and ticket identity.

## Safety invariants

- No Evidence -> No Attribution.
- Purchase is not usage.
- Temporal association is not causality.
- Consumer causal language is not system-confirmed causality.
- Adverse-reaction escalation remains human-reviewed.
- The adapter cannot send responses or take service actions.

## Acceptance cases

- `S00154`: adverse reaction and medical attention; exact used product remains an open gap when the
  gift-set order is the only product record.
- `S00001`: damaged product with image metadata and a replacement ticket; no vision inference.
- `S00009`: system delivery status and consumer non-receipt report are both retained as a conflict.
- Consumer `郭a**`: earlier and current after-sales sessions remain linked as source-grounded
  continuity without merging their orders or tickets.

## Explicit exclusions

Phase 7 does not add Phase 8 functionality, new UI design, image understanding, vector retrieval,
knowledge-base RAG, automatic attribution, automatic sending, or new LLM-provider behavior.
