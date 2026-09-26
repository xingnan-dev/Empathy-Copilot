# Phase 8 — Multimodal Evidence, Beauty Knowledge, and Safety

## Governing boundaries

Phase 8 adds two proposal/context providers while deterministic domain code remains authoritative:

`Image -> VisionProvider -> typed candidate -> safety validator -> AI_OBSERVATION Evidence`

`Case query -> KnowledgeRetriever -> provenance-bearing context -> WHY projection`

Vision never creates verified business facts. Retrieved knowledge is context, not case Evidence.
Neither path may diagnose, establish causality, certify product quality, authorize service eligibility,
or send a response. Safety and high-impact actions remain deterministic and human-reviewed.

## Source audit

The official workbook contains image references, including S00001 product-damage material and
S00154 medical/skin-related material. The referenced `mock_images` files are not present in the
repository or supplied Downloads directory, so an image reference proves availability only. It is
not an analyzed observation.

No official INCI, consumer-sensitivity, beauty-safety corpus, or complete service-policy corpus is
present. Phase 8 therefore uses a small local corpus whose records are explicitly marked
`DEMO_FIXTURE`; it must never be projected as official business Evidence.

Alibaba Model Studio's OpenAI-compatible Chat Completions API supports multimodal user content via
`image_url` (including Base64 data URLs). Runtime selection is independent through `VISION_MODEL`;
the implementation does not assume that the configured text model is the desired vision model.

## Structured observation

Every candidate includes observation identity, source image/message identity, category, visible
features and condition, visibility, sufficiency, uncertainty, confidence, provider, and model.
The deterministic validator rejects diagnostic, causal, treatment, quality-verdict, eligibility,
and unsupported safety language. Empty or insufficient candidates yield no Evidence.

Accepted observations become `AI_OBSERVATION` with `UPLOADED_IMAGE` provenance. The visual gap is
resolved only by a validated observation, not by `image_path` metadata.

## Knowledge retrieval

The local deterministic retriever supports only `PRODUCT_KNOWLEDGE`, `SERVICE_POLICY`, and
`BEAUTY_SAFETY_KNOWLEDGE`. Each item retains document ID, title, source, section, excerpt, type,
version/date, fixture status, and optional score. Missing knowledge returns an empty list.

## Safety gate

- `NORMAL`: ordinary supported enquiries without investigation or safety signals.
- `INVESTIGATION`: damage, logistics, and after-sales investigations.
- `SAFETY`: adverse reaction, explicit severe impact, swelling, or reported medical attention.

Severity and sourced safety evidence outrank emotion. Emotion alone cannot enter `SAFETY` or cause
escalation. `SAFETY` requires human approval and never enables automatic causal attribution.

## Ingredient context

Ingredient matching is an exact normalized comparison between a sourced sensitivity record and a
sourced product ingredient list. It produces context for human review only. Demo records are
explicitly labelled and cannot prove diagnosis, causality, or product unsafety.

## Persistence

Validated visual observations are Evidence inside the existing versioned investigation checkpoint
and therefore survive PostgreSQL reconstruction. Knowledge, safety, and ingredient projections are
deterministically rebuilt from checkpoint Evidence and versioned local knowledge; no parallel truth
store or Phase 8 migration is required.
