from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.app.api.schemas.cases import (
    CaseView,
    ConsumerMessageRequest,
    HumanApprovalRequest,
    ResponseDraftRequest,
    ResponseDraftView,
    ResumeRequest,
)
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.domain.agent import ToolRecoveryRequest
from backend.app.services.tool_recovery import RecoveryView, ToolRecoveryService

router = APIRouter(prefix="/api/cases", tags=["cases"])


def unavailable_service() -> CaseApplicationService:
    raise RuntimeError("case service dependency is not configured")


CaseService = Annotated[CaseApplicationService, Depends(unavailable_service)]


def recovery_response(case_id: str, view: RecoveryView, status: int) -> JSONResponse:
    headers = {"Location": f"/api/cases/{case_id}/tool-recoveries/{view.request_id}"}
    return JSONResponse(status_code=status, content=view.model_dump(mode="json"), headers=headers)


@router.post("/{case_id}/tool-recoveries", response_model=RecoveryView)
def recover_tool(case_id: str, request: ToolRecoveryRequest, service: CaseService) -> JSONResponse:
    view, status = service.recover_tool(case_id, request)
    return recovery_response(case_id, view, status)


@router.get("/{case_id}/tool-recoveries/{request_id}", response_model=RecoveryView)
def get_tool_recovery(case_id: str, request_id: UUID, service: CaseService) -> JSONResponse:
    view = service.get_tool_recovery(case_id, request_id)
    return recovery_response(case_id, view, ToolRecoveryService.http_status(view))


@router.get("/{case_id}", response_model=CaseView)
def get_case(case_id: str, service: CaseService) -> CaseView:
    return service.get_case(case_id)


@router.post("/{case_id}/human-approval", response_model=CaseView)
def approve_case(
    case_id: str,
    request: HumanApprovalRequest,
    service: CaseService,
) -> CaseView:
    return service.approve(case_id, request.expected_revision)


@router.post("/{case_id}/resume", response_model=CaseView)
def resume_case(
    case_id: str,
    request: ResumeRequest,
    service: CaseService,
) -> CaseView:
    return service.resume(case_id, request)


@router.post("/{case_id}/messages", response_model=CaseView)
def ingest_message(case_id: str, request: ConsumerMessageRequest, service: CaseService) -> CaseView:
    return service.ingest_message(
        case_id,
        message=request.message,
        message_id=request.message_id,
        expected_revision=request.expected_revision,
    )


@router.post("/{case_id}/response-draft", response_model=ResponseDraftView)
def response_draft(
    case_id: str, request: ResponseDraftRequest, service: CaseService
) -> ResponseDraftView:
    return ResponseDraftView.model_validate(
        service.generate_response_draft(case_id, request.expected_revision).model_dump()
    )
