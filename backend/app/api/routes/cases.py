from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.schemas.cases import CaseView, HumanApprovalRequest, ResumeRequest
from backend.app.api.services.case_application_service import CaseApplicationService

router = APIRouter(prefix="/api/cases", tags=["cases"])


def unavailable_service() -> CaseApplicationService:
    raise RuntimeError("case service dependency is not configured")


CaseService = Annotated[CaseApplicationService, Depends(unavailable_service)]


@router.get("/{case_id}", response_model=CaseView)
def get_case(
    case_id: str, service: CaseService
) -> CaseView:
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
