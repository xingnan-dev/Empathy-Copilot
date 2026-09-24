from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.schemas.cases import (
    CaseView,
    ConsumerMessageRequest,
    HumanApprovalRequest,
    ResponseDraftRequest,
    ResponseDraftView,
    ResumeRequest,
)
from backend.app.api.services.case_application_service import CaseApplicationService

router = APIRouter(prefix="/api/cases", tags=["cases"])


def unavailable_service() -> CaseApplicationService:
    raise RuntimeError("case service dependency is not configured")


CaseService = Annotated[CaseApplicationService, Depends(unavailable_service)]


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
