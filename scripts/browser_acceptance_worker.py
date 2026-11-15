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
    return service


app = create_app(factory)
