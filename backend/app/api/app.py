"""FastAPI application factory for the Phase 5 vertical slice."""

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.persistence.config import DatabaseSettings
from backend.app.persistence.database import create_database_engine, create_session_factory
from backend.app.persistence.factory import build_postgres_workflow
from backend.app.services.checkpoints import StateConflictError
from backend.app.services.transitions import InvalidStateTransitionError

from .routes.cases import router, unavailable_service
from .schemas.cases import ErrorView
from .services.case_application_service import CaseApplicationService


def build_runtime_service() -> CaseApplicationService:
    engine = create_database_engine(DatabaseSettings.from_environment())
    sessions = create_session_factory(engine)
    workflow = build_postgres_workflow(sessions)
    service = CaseApplicationService(workflow, workflow.checkpoints)
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
