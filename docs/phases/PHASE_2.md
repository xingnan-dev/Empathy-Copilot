# Phase 2 — Stateful Investigation Agent Loop

## Goal

Prove a deterministic, evidence-first loop can evaluate State, choose and execute a typed
action, checkpoint at a pause, resume with new Evidence, re-evaluate, and reach a safe human
or structured conclusion outcome. Phase 2 uses LangGraph but no LLM.

## Architecture

`InvestigationWorkflow` owns a compiled LangGraph, deterministic decision policy, transition
service, question templates, stub tool registry, and an injected development checkpoint
store. `InvestigationState` remains the authoritative domain state. A graph-only decision
field transports the chosen action to its execution node.

## Graph and nodes

```text
START -> evaluate_state -> decide_next_action
  ASK_USER        -> prepare_question       -> END (WAITING_FOR_USER)
  CALL_TOOL       -> prepare_tool_call      -> evaluate_state
  RETRIEVE_POLICY -> prepare_tool_call      -> evaluate_state
  ESCALATE        -> prepare_escalation     -> END
  WAIT_FOR_HUMAN  -> prepare_wait_for_human -> END
  CONCLUDE        -> prepare_conclusion     -> END
  limit reached   -> prepare_termination    -> END
```

Evaluation only recomputes deterministic derived gaps. Decision returns a typed plan.
Execution nodes alone request formal transitions.

## Routing and decision policy

The policy prioritizes: maximum transitions, explicit SEVERE report, explicit human-review
flag, absent order lookup, explicit policy requirement, P0 gaps in fixed order, missing date
on a reported regimen change, then conclusion. Question/tool limits route to termination or
human review rather than an infinite loop.

## Transition semantics

Every formal transition uses `StateTransitionService`. A legal transition produces exactly
one revision increment and one `TransitionEvent` containing from/to status, action, reason,
revision, and timestamp. `step_count` is the count of completed agent transitions; a limit
termination preserves the already-reached maximum while still recording its revision/event.

## Checkpoint semantics

`InMemoryCheckpointStore` stores serialized State JSON by case id and supports save/load/
exists. It is explicitly development-only and disappears with the process. Tests recreate
the workflow with the same store to prove graph compilation and workflow objects need not
survive a user pause.

## Resume

Resume accepts a WAITING_FOR_USER state and same-case Evidence. It rejects cross-case input,
deduplicates Evidence ids, marks matching question records ANSWERED, links answering Evidence
ids, recomputes gaps, transitions to INVESTIGATING, and invokes the graph again. Lexical
question history prevents a still-open gap from being asked repeatedly.

## Tool stubs

The tool registry contains local deterministic order-history and service-policy stubs. Tool
calls transition PENDING -> RUNNING -> COMPLETED, retain arguments and result Evidence ids,
and are deduplicated by tool name plus arguments. No external API is called.

## Golden Demo

The initial first-purchase case asks for actual first use and checkpoints. M102 resolves that
gap and changes the next question. Feedback onset, D Cream report, and severity are ingested
through successive resumes. An undated D report triggers a specific date clarification; only
the dated follow-up establishes same-day C/D changes. With all P0 gaps resolved, conclusion
stores `ATTRIBUTION_AMBIGUOUS`. C alone remains `INSUFFICIENT_EVIDENCE`; neither path can
automatically produce `SUPPORTED`.

## Tests

Tests cover graph compilation, all core routes, pause/checkpoint/load, cross-instance resume,
question answer/deduplication, gap re-evaluation, tool and policy lifecycles, tool idempotency,
severity escalation, human wait, structured conclusions, attribution safety, limits, illegal
transitions, exact revision/event increments, and the end-to-end Golden Demo.

## Acceptance

- LangGraph graph compiles and routes typed deterministic decisions.
- Every formal state change uses the transition service.
- Pause/checkpoint/resume works across workflow instances.
- Questions and tool calls retain lifecycle history.
- Completed tools do not execute twice.
- Severe consumer reports escalate without medical claims.
- Conclusions are structured and never automatically SUPPORTED.
- All tests, Ruff, and strict mypy pass.
- No database, LLM, real tool, frontend, RAG, multi-agent, or LangSmith integration exists.

