"""FastAPI application factory for the Phase 5 vertical slice."""

import os
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.llm.provider import ModelProviderError
from backend.app.llm.providers.qwen import QwenProvider
from backend.app.llm.service import ModelService
from backend.app.official_dataset import OfficialDatasetAdapter
from backend.app.official_dataset.persistence import OfficialDatasetImporter
from backend.app.persistence.config import DatabaseSettings
from backend.app.persistence.database import create_database_engine, create_session_factory
from backend.app.persistence.factory import build_postgres_workflow
from backend.app.services.checkpoints import StateConflictError
from backend.app.services.transitions import InvalidStateTransitionError
from backend.app.vision import VisionService
from backend.app.vision.qwen import QwenVisionProvider

from .routes.cases import router, unavailable_service
from .schemas.cases import ErrorView
from .services.case_application_service import CaseApplicationService


def build_runtime_service() -> CaseApplicationService:
    engine = create_database_engine(DatabaseSettings.from_environment())
    sessions = create_session_factory(engine)
    workflow = build_postgres_workflow(sessions)
    model_service = None
    vision_service = None
    if os.getenv("LLM_PROVIDER", "").casefold() == "qwen" and all(
        os.getenv(name) for name in ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL")
    ):
        model_service = ModelService(
            QwenProvider(
                api_key=os.environ["LLM_API_KEY"],
                model=os.environ["LLM_MODEL"],
                base_url=os.environ["LLM_BASE_URL"],
            )
        )
    if os.getenv("VISION_PROVIDER", "").casefold() == "qwen" and all(
        os.getenv(name) for name in ("LLM_API_KEY", "VISION_MODEL", "LLM_BASE_URL")
    ):
        vision_service = VisionService(
            QwenVisionProvider(
                api_key=os.environ["LLM_API_KEY"],
                model=os.environ["VISION_MODEL"],
                base_url=os.environ["LLM_BASE_URL"],
            )
        )
    service = CaseApplicationService(workflow, workflow.checkpoints, model_service, vision_service)
    official_path = os.getenv("OFFICIAL_DATASET_PATH")
    if official_path:
        official = OfficialDatasetAdapter().read(official_path)
        OfficialDatasetImporter().import_dataset(official, sessions)
        service.register_official_cases(official)
    service.ensure_integration_fixture()
    return service


def create_app(
    service_factory: Callable[[], CaseApplicationService] = build_runtime_service,
) -> FastAPI:
    app = FastAPI(title="Resonique Case API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    service = service_factory()
    app.dependency_overrides[unavailable_service] = lambda: service
    app.include_router(router)

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        """Container and operator readiness probe; no case data or secrets are exposed."""
        return {"status": "ok"}

    def error(code: str, message: str, status: int) -> JSONResponse:
        return JSONResponse(
            status_code=status, content=ErrorView(code=code, message=message).model_dump()
        )

    @app.exception_handler(KeyError)
    async def not_found(_request: Request, _exc: KeyError) -> JSONResponse:
        return error("CASE_NOT_FOUND", "Case was not found.", 404)

    @app.exception_handler(StateConflictError)
    async def conflict(_request: Request, _exc: StateConflictError) -> JSONResponse:
        return error("STATE_CONFLICT", "Case updated elsewhere. Refresh current state.", 409)

    @app.exception_handler(ModelProviderError)
    async def model_error(_request: Request, exc: ModelProviderError) -> JSONResponse:
        return error("MODEL_UNAVAILABLE", f"Model operation unavailable ({exc.category}).", 503)

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_transition(
        _request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        return error("INVALID_TRANSITION", str(exc), 409)

    @app.exception_handler(ValidationError)
    @app.exception_handler(ValueError)
    async def invalid_data(_request: Request, _exc: Exception) -> JSONResponse:
        return error("VALIDATION_ERROR", "Submitted event could not be validated.", 422)

    @app.exception_handler(RequestValidationError)
    async def request_invalid(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error("VALIDATION_ERROR", "Submitted event could not be validated.", 422)

    return app
