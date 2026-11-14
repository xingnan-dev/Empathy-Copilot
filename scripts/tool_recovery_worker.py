"""Explicit W3-only API/claim worker. Never imported by the production entry point."""

import argparse
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402
from fastapi import Request  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.app.agent.workflow import InvestigationWorkflow  # noqa: E402
from backend.app.api.app import create_app  # noqa: E402
from backend.app.api.services.case_application_service import CaseApplicationService  # noqa: E402
from backend.app.domain.agent import (  # noqa: E402
    InvestigationState,
    ToolCallStatus,
    ToolRecoveryRequest,
)
from backend.app.persistence.checkpoints import PostgresCheckpointStore  # noqa: E402
from backend.app.persistence.config import DatabaseSettings  # noqa: E402
from backend.app.persistence.database import (  # noqa: E402
    create_database_engine,
    create_session_factory,
)
from backend.app.repositories.postgres import PostgresRepositoryBundle  # noqa: E402
from backend.app.services.tool_recovery import RecoveryError, ToolRecoveryService  # noqa: E402
from backend.app.services.tools import ToolOutcomeUnknownError, default_tool_registry  # noqa: E402


def build_worker(config: dict):
    engine = create_database_engine(DatabaseSettings(os.environ["W3_DATABASE_URL"]))
    sessions = create_session_factory(engine)
    actor = config["actor"]

    def event(kind: str, state: InvestigationState | None = None, **details: object) -> None:
        if state is not None:
            details["revision"] = state.state_revision
            details["attempt_id"] = state.tool_calls[-1].id if state.tool_calls else None
            details["request_id"] = (
                str(state.tool_calls[-1].recovery_request_id) if state.tool_calls else None
            )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO w3_observation.events(experiment,actor,kind,details) "
                    "VALUES (:experiment,:actor,:kind,CAST(:details AS jsonb))"
                ),
                dict(
                    experiment=config["experiment"],
                    actor=actor,
                    kind=kind,
                    details=json.dumps(details),
                ),
            )

    def gate(kind: str, state: InvestigationState | None = None) -> None:
        if config.get("gate") != kind:
            return
        event("GATE", state, boundary=kind)
        release = Path(config["release"])
        while not release.exists():
            threading.Event().wait(0.025)

    class Store(PostgresCheckpointStore):
        def save(self, state: InvestigationState, *, expected_revision: int | None = None) -> None:
            call = state.tool_calls[-1] if state.tool_calls else None
            if call is not None:
                if call.status is ToolCallStatus.PENDING:
                    gate("BEFORE_PENDING", state)
                if state.next_action_reason == "Explicit readonly recovery claimed.":
                    gate("BEFORE_CLAIM", state)
                if call.status is ToolCallStatus.COMPLETED:
                    gate("BEFORE_COMPLETED", state)
            super().save(state, expected_revision=expected_revision)
            event("SNAPSHOT_COMMITTED", state)
            if call is not None:
                if state.next_action_reason == "Explicit readonly recovery claimed." and config.get(
                    "uncertain_claim"
                ):
                    event("CLAIM_COMMIT_RECEIPT_LOST", state)
                    raise OSError("Injected loss of confirmed claim commit receipt")
                gate("AFTER_" + call.status.value, state)

    registry = default_tool_registry(PostgresRepositoryBundle(sessions))
    delegate = default_tool_registry(PostgresRepositoryBundle(sessions))

    def order(state: InvestigationState, arguments: dict[str, str]):
        event("TOOL_ENTRY", state)
        mode = config.get("tool_mode", "normal")
        if mode == "timeout":
            raise TimeoutError("Injected readonly timeout")
        if mode == "unknown":
            event("SIDE_EFFECT_MARKER", state)
            raise ToolOutcomeUnknownError("Injected response loss after external marker commit")
        result = delegate.execute("get_order_history", state, arguments)
        event("TOOL_RETURN", state)
        return result

    registry.register(
        "get_order_history", order, side_effect_free=config.get("tool_mode") != "unknown"
    )
    workflow = InvestigationWorkflow(checkpoint_store=Store(sessions), tool_registry=registry)
    service = CaseApplicationService(workflow, workflow.checkpoints)
    app = create_app(lambda: service)

    @app.post("/experiment/run")
    def run_case():
        state = workflow.restore_case(config["experiment"])
        return workflow.run(state, expected_revision=state.state_revision).model_dump(mode="json")

    @app.middleware("http")
    async def response_gate(request: Request, call_next):
        response = await call_next(request)
        if request.method == "POST" and request.url.path.endswith("/tool-recoveries"):
            if config.get("gate") == "BEFORE_HTTP_RESPONSE":
                state = workflow.restore_case(config["experiment"])
                # Do not block the ASGI loop: the gate is executed in a helper thread.
                import asyncio

                await asyncio.to_thread(gate, "BEFORE_HTTP_RESPONSE", state)
        return response

    return app, workflow, event


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--claim", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text("utf-8"))
    app, workflow, event = build_worker(config)
    if args.claim:
        request = ToolRecoveryRequest.model_validate(config["request"])
        service = ToolRecoveryService(workflow)
        try:
            permit = service.claim(config["experiment"], request)
            if permit is None:
                event("CLAIM_REPLAY")
            else:
                event("CLAIM_WON")
                execution = workflow.tool_execution.execute_recovery(permit, workflow.checkpoints)
                workflow.run(execution.state, expected_revision=execution.persisted_revision)
        except RecoveryError as error:
            event("CLAIM_REJECTED", code=error.code)
        return
    uvicorn.run(app, host="127.0.0.1", port=config["port"], workers=1, log_level="warning")


if __name__ == "__main__":
    main()
