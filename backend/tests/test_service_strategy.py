from datetime import UTC, datetime

from backend.app.agent.guardrails import assess_attribution
from backend.app.domain.agent import InvestigationState
from backend.app.domain.evidence import Evidence, EvidenceType, SourceType
from backend.app.domain.safety import SafetyGate, SafetyGateService
from backend.app.domain.scenarios import InvestigationScenario
from backend.app.domain.service_strategy import (
    HumanAttention,
    ServiceStrategy,
    ServiceStrategyPolicy,
    SignalSource,
)

NOW = datetime(2026, 9, 30, tzinfo=UTC)


def _evidence(
    case_id: str,
    key: str,
    value: object,
    *,
    evidence_type: EvidenceType = EvidenceType.CONSUMER_REPORTED,
    source_type: SourceType = SourceType.CONSUMER_MESSAGE,
) -> Evidence:
    return Evidence.model_validate(
        {
            "id": f"{case_id}-{key}",
            "case_id": case_id,
            "key": key,
            "value": value,
            "evidence_type": evidence_type,
            "source": {
                "source_type": source_type,
                "source_id": f"source-{key}",
                "source_label": f"Source {key}",
            },
            "observed_at": NOW,
            "created_at": NOW,
            "extraction_confidence": 1.0,
        }
    )


def _project(
    state: InvestigationState,
    *,
    emotion: str | None,
    gap: str | None = "LOGISTICS_STATUS",
    question: str | None = "Could you confirm the latest tracking status?",
) -> ServiceStrategy:
    safety = SafetyGateService().assess(state)
    return ServiceStrategyPolicy().project(
        state,
        safety=safety,
        critical_gap=gap,
        next_question=question,
        emotion=emotion,
    )


def test_emotion_changes_communication_but_not_truth_or_safety() -> None:
    state = InvestigationState(
        case_id="LOGISTICS-CONTRAST",
        consumer_id="consumer",
        current_issue="delivery delay",
        scenario=InvestigationScenario.LOGISTICS_EXCEPTION,
    )
    before = state.model_dump(mode="json")
    attribution_before = assess_attribution(state, "unknown", []).decision
    calm = _project(state, emotion="CALM")
    angry = _project(state, emotion="ANGRY")

    assert calm.communication != angry.communication
    assert angry.consumer_signal.source is SignalSource.LLM_AUXILIARY
    assert angry.consumer_signal.semantic_type == "AI_INFERENCE"
    assert SafetyGateService().assess(state).gate is SafetyGate.INVESTIGATION
    assert angry.human_attention is HumanAttention.PRIORITY_REVIEW
    assert assess_attribution(state, "unknown", []).decision is attribution_before
    assert state.model_dump(mode="json") == before


def test_calm_severe_adverse_reaction_remains_safety() -> None:
    state = InvestigationState(
        case_id="CALM-SEVERE-CONTRAST",
        consumer_id="consumer",
        current_issue="reported swelling",
        scenario=InvestigationScenario.ADVERSE_REACTION,
        evidence=[_evidence("CALM-SEVERE-CONTRAST", "reported_severity", "SEVERE")],
    )
    strategy = _project(state, emotion="CALM", gap="CURRENT_SYMPTOM_STATUS")

    assert strategy.consumer_signal.label == "Language appears calm."
    assert SafetyGateService().assess(state).gate is SafetyGate.SAFETY
    assert strategy.human_attention is HumanAttention.SAFETY_ESCALATION


def test_repeat_contact_uses_restored_context_without_safety_promotion() -> None:
    state = InvestigationState(
        case_id="REPEAT-CONTRAST",
        consumer_id="consumer",
        current_issue="refund follow-up",
        scenario=InvestigationScenario.AFTER_SALES,
        evidence=[
            _evidence(
                "REPEAT-CONTRAST",
                "previous_service_contact",
                {"summary": "Consumer already supplied the order number."},
                evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
                source_type=SourceType.SERVICE_SYSTEM,
            )
        ],
    )
    strategy = _project(state, emotion=None, gap="ELIGIBILITY")

    assert any("restored service context" in item for item in strategy.investigation)
    assert any("avoid repeating known questions" in item for item in strategy.investigation)
    assert SafetyGateService().assess(state).gate is SafetyGate.INVESTIGATION
    assert strategy.human_attention is HumanAttention.PRIORITY_REVIEW


def test_no_emotion_signal_degrades_safely_and_strategy_has_one_gap() -> None:
    state = InvestigationState(
        case_id="NO-SIGNAL-CONTRAST",
        consumer_id="consumer",
        current_issue="ordinary question",
    )
    strategy = _project(state, emotion=None, gap="REQUEST_TYPE", question="What do you need?")

    assert strategy.consumer_signal.source is SignalSource.NONE
    assert strategy.human_attention is HumanAttention.NORMAL_HANDLING
    assert strategy.critical_gap == "REQUEST_TYPE"
    assert strategy.next_question == "What do you need?"
    assert sum("Ask one highest-value" in item for item in strategy.investigation) == 1


def test_language_cue_generalizes_without_case_specific_logic() -> None:
    state = InvestigationState(
        case_id="ARBITRARY-CONTRAST",
        consumer_id="consumer",
        current_issue="issue",
        evidence=[_evidence("ARBITRARY-CONTRAST", "consumer_message", "请尽快帮我看下怎么回事")],
    )
    strategy = _project(state, emotion=None)

    assert strategy.consumer_signal.source is SignalSource.DETERMINISTIC_LANGUAGE_CUE
    assert strategy.consumer_signal.semantic_type == "AI_INFERENCE"
