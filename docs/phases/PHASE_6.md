# Phase 6 — Real LLM Integration

## Scope and invariant

Phase 6 adds text-only model assistance inside the existing evidence-first investigation runtime. The invariant is:

> LLM proposes. Domain validates. Agent decides.

The model is never the authoritative state machine and cannot resolve a gap, set attribution, choose an action, approve a draft, or send a response.

## Architecture

`ModelProvider` isolates provider-specific calls. `QwenProvider` uses Alibaba's OpenAI-compatible chat-completions endpoint; `FakeModelProvider` supports deterministic tests. `ModelService` owns purpose-specific orchestration, candidate validation, wording guardrails, fallbacks, and non-sensitive call records.

The message path is:

`POST /api/cases/{id}/messages` → structured understanding → validated candidate → consumer-reported `Evidence` → gap reevaluation → existing LangGraph workflow → durable checkpoint → `CaseView`.

Response Studio explicitly requests `POST /api/cases/{id}/response-draft` after an Agent decision exists. The UI labels generated, human-edited, and fallback drafts. Human approval remains mandatory; no automatic send exists.

## Structured understanding and provenance

The typed output contains a small intent taxonomy, a small auxiliary emotion taxonomy, and candidate facts limited to exact product used, actual first-use date, and a consumer causality claim. Intent and emotion are auxiliary signals and never determine safety or priority.

Before conversion to Evidence, deterministic validation checks the allowed field, non-empty value, an exact source-text substring, date precision and bounds, case identity, and Evidence/source compatibility. Accepted Evidence retains message ID, source type, observation timestamp, original message, exact supporting excerpt, extracted field, and extraction method. Model confidence is not treated as truth probability.

Ambiguous dates remain unresolved. A consumer causality claim remains `CONSUMER_REPORTED`; the existing attribution guard remains authoritative.

## Questions, responses, and failure safety

The Agent decides which gap matters. The model only phrases that question. Validation rejects empty, duplicate, off-target, diagnostic, causality, safety, or medical wording and uses deterministic fallback text.

Response generation receives a minimal context: action, safety path, selected evidence, open uncertainty, attribution, checkpoint state, and the already-determined question. Unsafe or empty text becomes a deterministic fallback draft with a recorded reason.

Qwen calls have a 30-second default timeout and at most two attempts for timeout/network/rate-limit failures. Authentication, provider, malformed JSON, schema, and safety failures are surfaced as stable categories without provider traces. Call records contain operation, provider, model, status, latency, returned token usage, error category, and fallback status; prompts and secrets are not recorded.

## Configuration and local run

Copy placeholders from `.env.example` into a local untracked `.env` or process environment:

```text
LLM_PROVIDER=qwen
LLM_MODEL=<available Qwen text model>
LLM_API_KEY=<secret>
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

All model calls are server-side. Never expose the key to Vite/React.

Run FastAPI and React using the Phase 5 instructions. The host composer accepts a raw consumer message; Response Studio loads backend-generated wording.

## Tests

The default suite uses `FakeModelProvider` and covers schemas, candidate validation, provenance, ambiguity, causality, auxiliary signals, question guardrails, response safety, failures, token usage, prompt injection, API contracts, and optimistic concurrency.

The real test is explicitly opt-in:

```powershell
pytest -m qwen backend/tests/test_phase6_qwen.py
```

It requires the three Qwen credential variables and network access. PostgreSQL tests remain separate through `TEST_DATABASE_URL`.

## Known limitations

Phase 6 is text-only. It adds no official dataset adapter, RAG, vector store, image reasoning, automatic send, cost optimization, or expanded intent ontology. Model-call records are lightweight in-process observability rather than an analytics subsystem.
