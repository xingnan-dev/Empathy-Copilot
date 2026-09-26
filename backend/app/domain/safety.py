from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .agent import AgentStatus, InvestigationState
from .scenarios import InvestigationScenario


class SafetyGate(StrEnum):
    NORMAL = "NORMAL"
    INVESTIGATION = "INVESTIGATION"
    SAFETY = "SAFETY"


class SafetyAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: SafetyGate
    reasons: list[str]
    human_approval_required: bool


class SafetyGateService:
    def assess(self, state: InvestigationState, *, emotion: str | None = None) -> SafetyAssessment:
        del emotion
        safety_keys = {
            item.key
            for item in state.evidence
            if item.key in {"reported_severity", "reported_medical_attention", "reported_symptom"}
        }
        severe = any(
            item.key == "reported_severity" and item.value == "SEVERE" for item in state.evidence
        )
        if state.scenario is InvestigationScenario.ADVERSE_REACTION or severe or safety_keys:
            return SafetyAssessment(
                gate=SafetyGate.SAFETY,
                reasons=["Sourced adverse-reaction or medical-attention evidence."],
                human_approval_required=True,
            )
        if state.scenario in {
            InvestigationScenario.PRODUCT_DAMAGE,
            InvestigationScenario.LOGISTICS_EXCEPTION,
            InvestigationScenario.AFTER_SALES,
        }:
            return SafetyAssessment(
                gate=SafetyGate.INVESTIGATION,
                reasons=["Scenario requires evidence-backed business investigation."],
                human_approval_required=state.status is AgentStatus.WAITING_FOR_HUMAN,
            )
        return SafetyAssessment(
            gate=SafetyGate.NORMAL,
            reasons=["No sourced investigation or safety signal."],
            human_approval_required=False,
        )
