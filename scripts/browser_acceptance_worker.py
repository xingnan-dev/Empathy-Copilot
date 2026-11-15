"""Experiment-only API entry: no real models or official data."""

import os

from backend.app.api.app import build_runtime_service, create_app
from backend.app.llm.providers.fake import FakeModelProvider
from backend.app.llm.schemas import CandidateFact, CandidateField, UnderstandingResult
from backend.app.llm.service import ModelService


def factory():
    service = build_runtime_service()
    if os.environ.get("BROWSER_TEST_MODEL") == "fake":
        service.model_service = ModelService(
            FakeModelProvider(
                UnderstandingResult(
                    candidate_facts=[
                        CandidateFact(
                            field=CandidateField.EXACT_PRODUCT_USED,
                            value="面霜",
                            source_text="我实际用的是面霜。",
                        )
                    ]
                )
            )
        )
    elif os.environ.get("BROWSER_TEST_MODEL") == "empty":
        service.model_service = ModelService(FakeModelProvider())
    mode = os.environ.get("BROWSER_MODE")
    if mode in {"db-failure", "commit-uncertain"}:
        from sqlalchemy import event
        from sqlalchemy.exc import OperationalError
        from sqlalchemy.orm import Session

        from backend.app.persistence.models import CaseInboundMessageRow

        if mode == "db-failure":

            def fail_insert(*_args):
                raise OperationalError("experimental insert failure", {}, RuntimeError("injected"))

            event.listen(CaseInboundMessageRow, "before_insert", fail_insert)
        else:
            used = [False]

            def mark_message(session, *_args):
                if any(isinstance(row, CaseInboundMessageRow) for row in session.new):
                    session.info["browser_message"] = True

            def lose_receipt(session):
                if session.info.get("browser_message") and not used[0]:
                    used[0] = True
                    raise OperationalError(
                        "experimental receipt loss", {}, RuntimeError("injected")
                    )

            event.listen(Session, "before_flush", mark_message)
            event.listen(Session, "after_commit", lose_receipt)
    return service


app = create_app(factory)
