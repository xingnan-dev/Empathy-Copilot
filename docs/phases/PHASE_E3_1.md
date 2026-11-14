# Phase E3.1 — Durable Tool Failure Handling

Phase E3.1 is the first isolated post-competition reliability increment. It preserves the
`v1.0.0-competition-submission` tag and adds no new customer-service capability.

Tool invocations now use a stable identity derived from case, tool name, and canonical arguments.
The workflow persists `PENDING` and `RUNNING` before execution, then persists either `COMPLETED`
with grounded Evidence ids or `FAILED` with a classified, non-sensitive summary. A failed call
cannot contain result Evidence ids.

Failures are classified as retryable only for explicitly registered read-only tools. A timeout or
lost response from any tool that may have side effects is an unknown outcome. Phase E3.1 performs
no automatic retries: failed, pending, running, and unknown-outcome invocations require human
recovery before another execution. An idempotency identity prevents blind repetition inside the
existing workflow but does not guarantee exactly-once execution in an external system.

Checkpoint writes retain optimistic revision checks at every execution boundary. If a later write
conflicts, execution does not bypass the existing `StateConflictError` protection. Additive Tool
Call fields retain compatibility with existing successful competition snapshots.

## W0 validation — 2026-11-07

Local-sample validation on Python 3.13.14 and isolated PostgreSQL 16.15 completed:
20 PostgreSQL checks passed, with one official-workbook check skipped; the full suite had
159 passed and 28 skipped (27 official-workbook dependencies and one opt-in real Qwen call).
Ruff and mypy passed. Phase review remains pending before further productization work.

Additional database checks cover safe failure classification, reconstruction with a new engine,
no automatic retry, committed PENDING/RUNNING/COMPLETED boundaries, and optimistic conflict
after tool execution. Boundary interruption is injected after a real commit in the test process;
it does not claim OS process-kill, distributed concurrency, or the future W3 F0–F12 matrix.
The synthetic vision durability test no longer carries an official-dataset marker because its
only image input is the repository's independent demo fixture.
