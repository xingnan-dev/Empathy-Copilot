"""Thin application boundary between HTTP events and the authoritative agent state."""

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.agent.guardrails import assess_attribution
from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import AgentAction, AgentStatus, InvestigationState
from backend.app.domain.evidence import Evidence, EvidenceType, SourceType
from backend.app.domain.regimen import build_regimen_changes
from backend.app.services.checkpoints import CheckpointStore, StateConflictError
from backend.app.services.context_passport import ContextPassportService
from backend.app.services.transitions import InvalidStateTransitionError, StateTransitionService

from ..fixtures import s00154_waiting_for_human
from ..schemas.cases import (
    ActivityView,
    CaseView,
    EvidenceView,
    GapView,
    HumanCheckpointView,
    ResponseContextView,
    ResumeRequest,
)


class CaseApplicationService:
    def __init__(self, workflow: InvestigationWorkflow, checkpoints: CheckpointStore) -> None:
        self.workflow = workflow
        self.checkpoints = checkpoints
        self.transitions = StateTransitionService()
        self.passports = ContextPassportService()

    def ensure_integration_fixture(self) -> None:
        if not self.checkpoints.exists("S00154"):
            self.checkpoints.save(s00154_waiting_for_human())

    def get_case(self, case_id: str) -> CaseView:
        return self._project(self.checkpoints.load(case_id))

    def approve(self, case_id: str, expected_revision: int) -> CaseView:
        current = self.checkpoints.load(case_id)
        if current.state_revision != expected_revision:
            raise StateConflictError(f"case {case_id} no longer has revision {expected_revision}")
        if current.status is not AgentStatus.WAITING_FOR_HUMAN:
            raise InvalidStateTransitionError("case is not waiting for human approval")
        approved = self.transitions.transition(
            current,
            to_status=AgentStatus.ESCALATED,
            action=AgentAction.ESCALATE,
            reason="Human approved the recommended escalation.",
        )
        self.checkpoints.save(approved, expected_revision=expected_revision)
        return self._project(approved)

    def resume(self, case_id: str, request: ResumeRequest) -> CaseView:
        current = self.checkpoints.load(case_id)
        if current.state_revision != request.expected_revision:
            raise StateConflictError(
                f"case {case_id} no longer has revision {request.expected_revision}"
            )
        evidence = Evidence.model_validate(
            {
                "id": f"api-{uuid4()}",
                "case_id": case_id,
                "key": request.gap.casefold(),
                "value": request.value,
                "evidence_type": EvidenceType.CONSUMER_REPORTED,
                "source": {
                    "source_type": SourceType.CONSUMER_MESSAGE,
                    "source_id": request.source_id,
                    "source_label": f"Consumer message · {request.source_id}",
                },
                "observed_at": datetime.now(UTC),
                "created_at": datetime.now(UTC),
                "extraction_confidence": 1.0,
            }
        )
        return self._project(self.workflow.resume_with_evidence(current, [evidence]))

    def _project(self, state: InvestigationState) -> CaseView:
        primary_product = next(
            (
                item.value.get("product_id")
                for item in state.evidence
                if item.key == "first_purchase" and isinstance(item.value, dict)
            ),
            "unknown_product",
        )
        attribution = assess_attribution(
            state, str(primary_product), build_regimen_changes(state.case_id, state.evidence)
        ).decision.value
        evidence = [self._project_evidence(item) for item in state.evidence]
        approved = state.status is AgentStatus.ESCALATED
        passport = self.passports.build(state)
        return CaseView(
            case_id=state.case_id,
            consumer=state.consumer_id,
            lifecycle=state.status.value,
            current_action="ESCALATE"
            if state.status in {AgentStatus.WAITING_FOR_HUMAN, AgentStatus.ESCALATED}
            else (state.current_action.value if state.current_action else "NONE"),
            safety_path="ESCALATION"
            if state.status in {AgentStatus.WAITING_FOR_HUMAN, AgentStatus.ESCALATED}
            else "STANDARD",
            attribution_status=attribution,
            evidence=evidence,
            gaps=self._presentation_gaps(state),
            questions=[item.model_dump(mode="json") for item in state.asked_questions],
            tool_activity=[
                ActivityView(
                    id=f"transition-{index}",
                    label=item.reason,
                    status="CURRENT"
                    if index == len(state.transition_events) - 1 and not approved
                    else "COMPLETED",
                    technical=item.action.value if item.action else item.to_status.value,
                )
                for index, item in enumerate(state.transition_events)
            ],
            context_passport=passport.model_dump(mode="json"),
            human_checkpoint=HumanCheckpointView(
                state="APPROVED"
                if approved
                else (
                    "REQUIRED" if state.status is AgentStatus.WAITING_FOR_HUMAN else "NOT_REQUIRED"
                ),
                can_approve=state.status is AgentStatus.WAITING_FOR_HUMAN,
            ),
            response_context=ResponseContextView(
                evidence_used_ids=[
                    item.id for item in state.evidence if item.id != "order-purchase"
                ],
                next_best_question="为了继续帮您处理，想确认一下，您实际使用的是礼盒中的哪一款产品？",
                question_resolves_gap="EXACT_PRODUCT_USED",
            ),
            updated_at=state.updated_at,
            revision=state.state_revision,
        )

    @staticmethod
    def _project_evidence(item: Evidence) -> EvidenceView:
        fact: object
        if isinstance(item.value, str):
            fact = item.value
        elif isinstance(item.value, dict):
            fact = item.value.get("summary") or (
                f"{item.value.get('product_name')} purchased · {item.value.get('paid')}"
                if item.key == "first_purchase"
                else item.key.replace("_", " ")
            )
        else:
            fact = item.key.replace("_", " ")
        source_type = item.source.source_type.value.replace("_", " ").title()
        return EvidenceView(
            id=item.id,
            fact=str(fact),
            type=item.evidence_type.value,
            source=item.source.source_label,
            provenance=f"{source_type} · {item.source.source_id}",
            timestamp=item.observed_at,
        )

    @staticmethod
    def _presentation_gaps(state: InvestigationState) -> list[GapView]:
        first_use_open = not any(item.key == "actual_first_use_time" for item in state.evidence)
        regimen_open = not any(item.key == "recent_regimen_changes" for item in state.evidence)
        specs = [
            (
                "EXACT_PRODUCT_USED",
                "Exact product used",
                "Purchase of a gift set does not prove which item was actually used.",
                "Ask consumer",
                True,
            ),
            (
                "ACTUAL_FIRST_USE_TIME",
                "Actual first-use time",
                "Purchase date does not prove actual usage date.",
                "Ask consumer",
                first_use_open,
            ),
            (
                "RECENT_REGIMEN_CHANGES",
                "Recent routine changes",
                "Other recent product changes may affect attribution.",
                "Ask consumer",
                regimen_open,
            ),
            (
                "CURRENT_SYMPTOM_PROGRESSION",
                "Current symptom progression",
                "Current symptom direction is absent from available records.",
                "Human follow-up",
                True,
            ),
        ]
        return [
            GapView(
                id=gap_id,
                label=label,
                why=why,
                resolve=resolve,
                status="OPEN" if is_open else "RESOLVED",
            )
            for gap_id, label, why, resolve, is_open in specs
        ]
