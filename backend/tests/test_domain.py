from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.agent.guardrails import (
    AttributionDecision,
    apply_step_limit,
    assess_attribution,
    can_ask_question,
    normalize_question,
)
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    AskedQuestion,
    InvestigationState,
    QuestionStatus,
    ToolCallRecord,
    ToolCallStatus,
)
from backend.app.domain.evidence import Evidence, EvidenceType, SourceType
from backend.app.domain.gaps import GapStatus, GapType, evaluate_p0_gaps
from backend.app.domain.regimen import ChangeType, build_regimen_changes
from backend.tests.fixtures import (
    CASE_ID,
    NOW,
    d_cream_change_evidence,
    feedback_onset_evidence,
    first_use_evidence,
    fully_resolved_state,
    initial_state,
    message_evidence,
    order_evidence,
    severity_evidence,
)


def gap_status(evidence: list[Evidence], gap_type: GapType) -> GapStatus:
    return next(
        gap.status for gap in evaluate_p0_gaps(CASE_ID, evidence) if gap.gap_type is gap_type
    )


def question(status: QuestionStatus, *, question_id: str = "q1") -> AskedQuestion:
    return AskedQuestion(
        id=question_id,
        gap_type=GapType.ACTUAL_FIRST_USE_TIME,
        text="When did you first use it?",
        normalized_text=normalize_question("When did you first use it?"),
        status=status,
        asked_at=None if status is QuestionStatus.PENDING else NOW,
        answered_by_evidence_ids=["ev_m102_first_use"]
        if status is QuestionStatus.ANSWERED
        else [],
    )


@pytest.mark.parametrize(
    ("evidence_type", "source_type"),
    [
        (EvidenceType.VERIFIED_BUSINESS_FACT, SourceType.AI_REASONING),
        (EvidenceType.CONSUMER_REPORTED, SourceType.ORDER_SYSTEM),
        (EvidenceType.AI_INFERENCE, SourceType.ORDER_SYSTEM),
        (EvidenceType.AI_OBSERVATION, SourceType.CONSUMER_MESSAGE),
    ],
)
def test_invalid_evidence_source_combinations_rejected(
    evidence_type: EvidenceType, source_type: SourceType
) -> None:
    with pytest.raises(ValidationError):
        message_evidence(
            "ev_invalid", "source", "some_key", "value", evidence_type=evidence_type,
            source_type=source_type,
        )


def test_missing_provenance_rejected() -> None:
    data = order_evidence().model_dump()
    del data["source"]
    with pytest.raises(ValidationError):
        Evidence.model_validate(data)


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_extraction_confidence_rejected(confidence: float) -> None:
    data = order_evidence().model_dump()
    data["extraction_confidence"] = confidence
    with pytest.raises(ValidationError):
        Evidence.model_validate(data)


def test_non_json_evidence_value_rejected() -> None:
    data = order_evidence().model_dump()
    data["value"] = {"not_json": {"set"}}
    with pytest.raises(ValidationError):
        Evidence.model_validate(data)


def test_unknown_cannot_resolve_gap() -> None:
    item = message_evidence(
        "ev_unknown",
        "M200",
        "reported_severity",
        "MILD",
        evidence_type=EvidenceType.UNKNOWN,
    )
    assert gap_status([item], GapType.REPORTED_SEVERITY) is GapStatus.OPEN


def test_ai_inference_cannot_resolve_consumer_gap() -> None:
    item = message_evidence(
        "ev_inference",
        "AI1",
        "reported_severity",
        "MILD",
        evidence_type=EvidenceType.AI_INFERENCE,
        source_type=SourceType.AI_REASONING,
    )
    assert gap_status([item], GapType.REPORTED_SEVERITY) is GapStatus.OPEN


@pytest.mark.parametrize("value", [None, "", {}])
def test_empty_first_use_value_cannot_resolve(value: object) -> None:
    item = message_evidence("ev_empty", "M201", "actual_first_use_time", value)
    assert gap_status([item], GapType.ACTUAL_FIRST_USE_TIME) is GapStatus.OPEN


def test_wrong_valid_source_type_cannot_resolve_consumer_gap() -> None:
    item = message_evidence(
        "ev_service",
        "S1",
        "actual_first_use_time",
        {
            "product_id": "c_serum",
            "product_name": "C Serum",
            "first_use_at": "2026-09-12",
        },
        evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
        source_type=SourceType.SERVICE_SYSTEM,
    )
    assert gap_status([item], GapType.ACTUAL_FIRST_USE_TIME) is GapStatus.OPEN


def test_wrong_case_cannot_resolve_gap() -> None:
    item = message_evidence(
        "ev_other_case",
        "M202",
        "actual_first_use_time",
        {
            "product_id": "c_serum",
            "product_name": "C Serum",
            "first_use_at": "2026-09-12",
        },
        case_id="case_other",
    )
    assert gap_status([item], GapType.ACTUAL_FIRST_USE_TIME) is GapStatus.OPEN


def test_valid_first_use_resolves_gap_with_provenance() -> None:
    gaps = evaluate_p0_gaps(CASE_ID, [order_evidence(), first_use_evidence()])
    gap = next(item for item in gaps if item.gap_type is GapType.ACTUAL_FIRST_USE_TIME)
    assert gap.status is GapStatus.RESOLVED
    assert gap.resolved_by_evidence_ids == ["ev_m102_first_use"]


def test_multiple_valid_evidence_ids_are_retained() -> None:
    confirmation = message_evidence(
        "ev_m103_first_use_confirmation",
        "M103",
        "actual_first_use_time",
        {
            "product_id": "c_serum",
            "product_name": "C Serum",
            "first_use_at": "2026-09-12",
        },
    )
    gaps = evaluate_p0_gaps(CASE_ID, [first_use_evidence(), confirmation])
    gap = next(item for item in gaps if item.gap_type is GapType.ACTUAL_FIRST_USE_TIME)
    assert gap.resolved_by_evidence_ids == [
        "ev_m102_first_use",
        "ev_m103_first_use_confirmation",
    ]


def test_state_json_is_stable_across_round_trip() -> None:
    state = initial_state()
    encoded = state.model_dump_json()
    restored = InvestigationState.model_validate_json(encoded)
    assert restored.model_dump_json() == encoded


def test_action_and_status_remain_distinct_types() -> None:
    assert AgentAction.ASK_USER.value == "ASK_USER"
    assert AgentStatus.WAITING_FOR_USER.value == "WAITING_FOR_USER"
    assert not isinstance(AgentStatus.WAITING_FOR_USER, AgentAction)


@pytest.mark.parametrize(
    "status", [AgentStatus.CONCLUDED, AgentStatus.TERMINATED, AgentStatus.ESCALATED]
)
def test_terminal_status_rejects_action(status: AgentStatus) -> None:
    data = initial_state().model_dump()
    data.update({"status": status, "current_action": AgentAction.ASK_USER})
    with pytest.raises(ValidationError):
        InvestigationState.model_validate(data)


def test_waiting_for_user_requires_question() -> None:
    data = initial_state().model_dump()
    data["status"] = AgentStatus.WAITING_FOR_USER
    with pytest.raises(ValidationError):
        InvestigationState.model_validate(data)


def test_waiting_for_user_accepts_pending_question() -> None:
    data = initial_state().model_dump()
    data.update(
        {
            "status": AgentStatus.WAITING_FOR_USER,
            "current_action": AgentAction.ASK_USER,
            "asked_questions": [question(QuestionStatus.PENDING).model_dump()],
        }
    )
    state = InvestigationState.model_validate(data)
    assert state.question_count == 0


def test_answered_question_links_to_evidence_and_counts_once() -> None:
    record = question(QuestionStatus.ANSWERED)
    data = initial_state().model_dump()
    data.update({"asked_questions": [record.model_dump()], "question_count": 1})
    state = InvestigationState.model_validate(data)
    assert state.asked_questions[0].answered_by_evidence_ids == ["ev_m102_first_use"]
    assert state.question_count == 1


def test_max_questions_off_by_one() -> None:
    records = [question(QuestionStatus.ASKED, question_id=f"q{index}") for index in range(1, 3)]
    data = initial_state().model_dump()
    data.update({"asked_questions": records, "question_count": 2, "max_questions": 3})
    assert can_ask_question(InvestigationState.model_validate(data), "How severe is it?")
    records.append(question(QuestionStatus.ASKED, question_id="q3"))
    data.update({"asked_questions": records, "question_count": 3})
    assert not can_ask_question(InvestigationState.model_validate(data), "How severe is it?")


def test_duplicate_normalized_question_blocked() -> None:
    data = initial_state().model_dump()
    data.update(
        {
            "asked_questions": [question(QuestionStatus.ASKED).model_dump()],
            "question_count": 1,
        }
    )
    state = InvestigationState.model_validate(data)
    assert not can_ask_question(state, "  WHEN did you first use it !!! ")


@pytest.mark.parametrize(
    "status",
    [
        AgentStatus.TERMINATED,
        AgentStatus.CONCLUDED,
        AgentStatus.ESCALATED,
        AgentStatus.WAITING_FOR_HUMAN,
    ],
)
def test_lifecycle_status_blocks_question(status: AgentStatus) -> None:
    data = initial_state().model_dump()
    data["status"] = status
    state = InvestigationState.model_validate(data)
    assert not can_ask_question(state, "How severe is it?")


def test_max_steps_off_by_one() -> None:
    before = initial_state().model_copy(update={"step_count": 2, "max_steps": 3})
    assert apply_step_limit(before).status is AgentStatus.INVESTIGATING
    assert apply_step_limit(before).state_revision == before.state_revision
    at_limit = initial_state().model_copy(update={"step_count": 3, "max_steps": 3})
    terminated = apply_step_limit(at_limit)
    assert terminated.status is AgentStatus.TERMINATED
    assert terminated.state_revision == at_limit.state_revision + 1


def test_tool_call_record_serializes() -> None:
    call = ToolCallRecord(
        id="tool_1",
        tool_name="lookup_order",
        arguments={"order_id": "A1024"},
        status=ToolCallStatus.COMPLETED,
        created_at=NOW,
        completed_at=NOW,
        result_evidence_ids=["ev_order_a1024_first_purchase"],
    )
    assert ToolCallRecord.model_validate_json(call.model_dump_json()) == call


def test_purchase_does_not_create_usage_change() -> None:
    assert build_regimen_changes(CASE_ID, [order_evidence()]) == []


def test_stable_report_is_not_a_phase_1_1_regimen_change() -> None:
    stable = message_evidence(
        "ev_stable",
        "M300",
        "recent_regimen_changes",
        {
            "product_id": "existing_cream",
            "product_name": "Existing Cream",
            "change_type": "STABLE",
        },
    )
    assert build_regimen_changes(CASE_ID, [stable]) == []
    assert gap_status([stable], GapType.RECENT_REGIMEN_CHANGES) is GapStatus.OPEN


def test_confirmed_first_use_creates_c_new_change() -> None:
    changes = build_regimen_changes(CASE_ID, [first_use_evidence()])
    assert len(changes) == 1
    assert changes[0].product_id == "c_serum"
    assert changes[0].change_type is ChangeType.NEW
    assert changes[0].effective_at == date(2026, 9, 12)
    assert changes[0].source_evidence_ids == ["ev_m102_first_use"]


def test_d_change_without_date_does_not_prove_concurrency() -> None:
    state = fully_resolved_state(dated_d_change=False)
    changes = build_regimen_changes(CASE_ID, state.evidence)
    result = assess_attribution(state, "c_serum", changes)
    assert result.decision is AttributionDecision.INSUFFICIENT_EVIDENCE


def test_same_day_c_and_d_create_ambiguous_attribution() -> None:
    state = fully_resolved_state()
    changes = build_regimen_changes(CASE_ID, state.evidence)
    assert {change.product_id for change in changes} == {"c_serum", "d_cream"}
    result = assess_attribution(state, "c_serum", changes)
    assert result.decision is AttributionDecision.ATTRIBUTION_AMBIGUOUS


def test_single_c_temporal_association_is_insufficient() -> None:
    state = fully_resolved_state()
    changes = build_regimen_changes(CASE_ID, [first_use_evidence()])
    result = assess_attribution(state, "c_serum", changes)
    assert result.decision is AttributionDecision.INSUFFICIENT_EVIDENCE


def test_no_supported_attribution_path_for_current_scenarios() -> None:
    open_state = initial_state()
    resolved_state = fully_resolved_state()
    scenarios = [
        assess_attribution(open_state, "c_serum", []),
        assess_attribution(
            resolved_state,
            "c_serum",
            build_regimen_changes(CASE_ID, [first_use_evidence()]),
        ),
        assess_attribution(
            resolved_state,
            "c_serum",
            build_regimen_changes(CASE_ID, resolved_state.evidence),
        ),
    ]
    assert all(result.decision is not AttributionDecision.SUPPORTED for result in scenarios)


def test_golden_demo_gaps_after_first_use_and_d_change() -> None:
    evidence = [order_evidence(), first_use_evidence(), d_cream_change_evidence()]
    gaps = {gap.gap_type: gap.status for gap in evaluate_p0_gaps(CASE_ID, evidence)}
    assert gaps == {
        GapType.ACTUAL_FIRST_USE_TIME: GapStatus.RESOLVED,
        GapType.FEEDBACK_ONSET_TIME: GapStatus.OPEN,
        GapType.RECENT_REGIMEN_CHANGES: GapStatus.RESOLVED,
        GapType.REPORTED_SEVERITY: GapStatus.OPEN,
    }


def test_all_structured_p0_evidence_resolves_all_gaps() -> None:
    evidence = [
        first_use_evidence(),
        d_cream_change_evidence(),
        feedback_onset_evidence(),
        severity_evidence(),
    ]
    assert all(
        gap.status is GapStatus.RESOLVED for gap in evaluate_p0_gaps(CASE_ID, evidence)
    )
