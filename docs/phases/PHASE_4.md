# Phase 4 — PostgreSQL Persistence + Durable Agent State

## Goal

Make business records and authoritative `InvestigationState` durable across process, engine,
session, repository, and workflow recreation without weakening evidence-first semantics.
Phase 4 adds persistence, not new agent intelligence.

## PostgreSQL architecture

```text
Business Tool -> Repository protocol -> PostgreSQL repository -> relational business tables

InvestigationState -> PostgresCheckpointStore -> versioned JSONB snapshot
                   -> restore -> Pydantic/domain validation -> resume
```

SQLAlchemy 2.x supplies typed persistence adapters, psycopg supplies the PostgreSQL driver,
and Alembic owns schema migration. `DATABASE_URL` and `TEST_DATABASE_URL` come only from the
environment. Graph and decision code never execute SQL.

## Schema

`consumers`, `orders`, and `service_records` are normalized relational business tables with
stable business identifiers and consumer foreign keys. `investigation_checkpoints` stores
case/consumer identity, state schema version, state revision, update time, and one JSONB State
snapshot. Evidence, gaps, questions, tool calls, transitions, result, and Consumer Memory are
inside that authoritative validated snapshot. Regimen changes and Context Passport remain
deterministic Evidence projections rather than duplicate truth tables.

## Repository implementations

`PostgresConsumerRepository`, `PostgresOrderRepository`, and
`PostgresServiceHistoryRepository` implement the Phase 3 protocols. Every operation owns a
short session scope and returns existing domain records. `PostgresRepositoryBundle` can be
passed to the unchanged business-tool registry.

## Investigation persistence

`PostgresCheckpointStore` implements `save`, `load`, and `exists`. Save serializes with
Pydantic JSON mode inside one database transaction. Load validates the JSONB payload as an
`InvestigationState`, then verifies case id, consumer id, schema version, and revision against
relational metadata. Invalid persisted data never becomes an agent State.

State validation also enforces same-case Evidence, business-Evidence consumer consistency,
and live Evidence references from answered questions, completed tools, and Consumer Memory.

## Checkpoint persistence

`InvestigationWorkflow` accepts the common `CheckpointStore` protocol. In-memory checkpoints
remain available for fast tests. The PostgreSQL factory wires durable checkpoints and
PostgreSQL business repositories without changing graph nodes or safety policy.

## Optimistic concurrency

Updates use `WHERE case_id = ... AND state_revision = expected_revision`. A zero-row update or
duplicate initial insert raises `StateConflictError`; stale State cannot silently overwrite a
newer revision. Snapshot and revision metadata are written in the same transaction. No
distributed lock or event sourcing is introduced.

## Migration

Alembic revision `20260920_0001` creates all four tables and indexes from an empty PostgreSQL
database. Runtime code does not call `metadata.create_all()` as schema management.

## Seed

The Phase 3 JSON dataset remains the deterministic seed source. PostgreSQL `ON CONFLICT DO
UPDATE` statements make repeat seed runs idempotent by business primary key. The runtime
PostgreSQL repositories query tables and do not reread JSON.

## Restart semantics

Integration tests persist the Golden Demo pause, discard the first workflow/repository/session
stack, create a new SQLAlchemy engine and workflow, restore the same case, and resume with the
consumer's first-use Evidence. Evidence provenance, question answers, completed tools,
transition history, counters, revisions, memory, gaps, and derived regimen changes survive.
The order tool is not rerun and the answered first-use question is not repeated.

## Tests

Fast tests retain all Phase 1–3 behavior. Isolated PostgreSQL tests rebuild only a database
whose name contains `test`, run Alembic from empty, verify idempotent seed and repositories,
exercise grounding through real tools, round-trip full State, reject damaged snapshots, prove
optimistic conflict rollback, and exercise Golden Demo and repeat-contact restarts.

## Limitations

Checkpoint history is latest-snapshot only. There is no event sourcing, distributed locking,
retry framework, managed backup, authentication, API surface, or production deployment.
State schema migration between future schema versions is not yet implemented. PostgreSQL
availability and operational monitoring remain deployment concerns.
