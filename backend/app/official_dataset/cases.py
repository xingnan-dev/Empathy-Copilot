"""Build checkpoint-safe official cases from normalized records and grounded Evidence."""

from backend.app.domain.agent import AgentAction, AgentStatus, InvestigationState
from backend.app.domain.gaps import evaluate_scenario_gaps
from backend.app.domain.scenarios import InvestigationScenario
from backend.app.services.memory import ConsumerMemoryService
from backend.app.services.transitions import StateTransitionService

from .grounding import OfficialEvidenceGroundingService
from .models import OfficialDataset


class OfficialCaseFactory:
    def __init__(self) -> None:
        self.grounding = OfficialEvidenceGroundingService()
        self.transitions = StateTransitionService()
        self.memory = ConsumerMemoryService()

    def build(self, dataset: OfficialDataset, session_id: str) -> InvestigationState:
        session = dataset.session(session_id)
        if session.scenario is None:
            raise ValueError(f"unsupported official scene: {session.scene_major}")
        evidence = self.grounding.ground_case(dataset, session_id)
        state = InvestigationState(
            case_id=session_id,
            consumer_id=session.consumer_id,
            current_issue=f"Official {session.scene_major} / {session.scene_minor} case.",
            scenario=session.scenario,
            evidence=evidence,
            evidence_gaps=evaluate_scenario_gaps(session_id, session.scenario, evidence),
            consumer_memory=self.memory.build(session.consumer_id, evidence),
            created_at=session.started_at,
            updated_at=session.started_at,
        )
        if session.scenario is InvestigationScenario.ADVERSE_REACTION:
            return self.transitions.transition(
                state,
                to_status=AgentStatus.WAITING_FOR_HUMAN,
                action=AgentAction.WAIT_FOR_HUMAN,
                reason="Reported swelling and medical attention require human-reviewed escalation.",
            )
        return state
