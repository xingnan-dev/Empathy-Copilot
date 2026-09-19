from backend.app.agent.guardrails import can_ask_question, normalize_question
from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    AskedQuestion,
    AttributionDecision,
    InvestigationState,
    QuestionStatus,
    ToolCallStatus,
)
from backend.app.domain.evidence import EvidenceType, SourceType
from backend.app.domain.gaps import GapStatus, GapType, evaluate_p0_gaps
from backend.app.services.checkpoints import InMemoryCheckpointStore
from backend.app.services.tools import default_tool_registry
from backend.app.services.transitions import (
    InvalidStateTransitionError,
    StateTransitionService,
)
from backend.tests.fixtures import (
    CASE_ID,
    CONSUMER_ID,
    NOW,
    d_cream_change_evidence,
    feedback_onset_evidence,
    first_use_evidence,
    initial_state,
    message_evidence,
    severity_evidence,
)


def state_without_order() -> InvestigationState:
    return InvestigationState(
        case_id=CASE_ID,
        consumer_id=CONSUMER_ID,
        current_issue="我用了 C 精华后感觉不舒服。",
        evidence=[],
        evidence_gaps=evaluate_p0_gaps(CASE_ID, []),
        created_at=NOW,
        updated_at=NOW,
    )


def test_graph_initializes_with_expected_nodes() -> None:
    workflow = InvestigationWorkflow()
    nodes = set(workflow.graph.get_graph().nodes)
    assert {"evaluate_state", "decide_next_action", "prepare_question"} <= nodes


def test_initial_golden_case_asks_first_use_and_checkpoints() -> None:
    workflow = InvestigationWorkflow()
    result = workflow.run(initial_state())
    assert result.status is AgentStatus.WAITING_FOR_USER
    assert result.current_action is AgentAction.ASK_USER
    assert result.asked_questions[-1].gap_type is GapType.ACTUAL_FIRST_USE_TIME
    assert result.asked_questions[-1].status is QuestionStatus.ASKED
    assert workflow.checkpoints.exists(CASE_ID)
    assert workflow.checkpoints.load(CASE_ID) == result


def test_resume_re_evaluates_gap_and_does_not_repeat_answered_question() -> None:
    workflow = InvestigationWorkflow()
    waiting = workflow.run(initial_state())
    resumed = workflow.resume_with_evidence(waiting, [first_use_evidence()])
    actual_first_use = next(
        gap for gap in resumed.evidence_gaps if gap.gap_type is GapType.ACTUAL_FIRST_USE_TIME
    )
    assert actual_first_use.status is GapStatus.RESOLVED
    assert resumed.asked_questions[0].status is QuestionStatus.ANSWERED
    assert resumed.asked_questions[0].answered_by_evidence_ids == ["ev_m102_first_use"]
    assert resumed.asked_questions[-1].gap_type is GapType.FEEDBACK_ONSET_TIME
    assert sum(
        record.gap_type is GapType.ACTUAL_FIRST_USE_TIME
        for record in resumed.asked_questions
    ) == 1


def test_new_workflow_instance_resumes_shared_checkpoint() -> None:
    store = InMemoryCheckpointStore()
    first = InvestigationWorkflow(checkpoint_store=store)
    waiting = first.run(initial_state())
    assert waiting.status is AgentStatus.WAITING_FOR_USER
    second = InvestigationWorkflow(checkpoint_store=store)
    resumed = second.resume_case(CASE_ID, [first_use_evidence()])
    assert len(resumed.asked_questions) == 2
    assert resumed.asked_questions[0].status is QuestionStatus.ANSWERED
    assert second.checkpoints.load(CASE_ID).tool_calls == resumed.tool_calls


def test_resume_rejects_cross_case_evidence() -> None:
    workflow = InvestigationWorkflow()
    waiting = workflow.run(initial_state())
    other = message_evidence(
        "ev_other",
        "M999",
        "actual_first_use_time",
        {
            "product_id": "c_serum",
            "product_name": "C Serum",
            "first_use_at": "2026-09-12",
        },
        case_id="other_case",
    )
    try:
        workflow.resume_with_evidence(waiting, [other])
    except ValueError as error:
        assert "current case" in str(error)
    else:
        raise AssertionError("cross-case evidence must be rejected")


def test_call_tool_route_and_lifecycle() -> None:
    registry = default_tool_registry()
    workflow = InvestigationWorkflow(tool_registry=registry)
    result = workflow.run(state_without_order())
    assert result.status is AgentStatus.WAITING_FOR_USER
    assert result.tool_calls[-1].status is ToolCallStatus.COMPLETED
    assert result.tool_calls[-1].result_evidence_ids
    assert any(item.key == "first_purchase" for item in result.evidence)
    assert registry.execution_counts["get_order_history"] == 1
    tool_events = [
        event for event in result.transition_events if event.action is AgentAction.CALL_TOOL
    ]
    assert len(tool_events) == 3


def test_completed_tool_call_is_not_executed_twice() -> None:
    registry = default_tool_registry()
    workflow = InvestigationWorkflow(tool_registry=registry)
    result = workflow.run(state_without_order())
    call = result.tool_calls[-1]
    unchanged = workflow.tool_execution.execute_once(
        result,
        tool_name=call.tool_name,
        action=AgentAction.CALL_TOOL,
        arguments={"consumer_id": result.consumer_id},
    )
    assert unchanged == result
    assert registry.execution_counts["get_order_history"] == 1


def test_new_instance_resume_preserves_completed_tool_history() -> None:
    store = InMemoryCheckpointStore()
    registry = default_tool_registry()
    first = InvestigationWorkflow(checkpoint_store=store, tool_registry=registry)
    waiting = first.run(state_without_order())
    assert waiting.tool_calls[-1].status is ToolCallStatus.COMPLETED
    second = InvestigationWorkflow(checkpoint_store=store, tool_registry=registry)
    resumed = second.resume_case(CASE_ID, [first_use_evidence()])
    original_call = waiting.tool_calls[-1]
    assert original_call in resumed.tool_calls
    assert registry.execution_counts["get_order_history"] == 1


def test_retrieve_policy_uses_tool_style_stub_route() -> None:
    policy_required = message_evidence(
        "ev_policy_required",
        "S501",
        "policy_required",
        True,
        evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
        source_type=SourceType.SERVICE_SYSTEM,
    )
    base = initial_state()
    data = base.model_dump()
    evidence = [*base.evidence, first_use_evidence(), policy_required]
    data["evidence"] = evidence
    data["evidence_gaps"] = evaluate_p0_gaps(CASE_ID, evidence)
    result = InvestigationWorkflow().run(InvestigationState.model_validate(data))
    policy_call = next(
        call for call in result.tool_calls if call.tool_name == "retrieve_service_policy"
    )
    assert policy_call.status is ToolCallStatus.COMPLETED
    assert any(item.key == "policy_retrieved" for item in result.evidence)
    assert any(
        event.action is AgentAction.RETRIEVE_POLICY for event in result.transition_events
    )


def test_severe_consumer_report_escalates_without_medical_claim() -> None:
    severe = message_evidence(
        "ev_severe", "M500", "reported_severity", "SEVERE"
    )
    base = initial_state()
    evidence = [*base.evidence, severe]
    data = base.model_dump()
    data.update(
        {
            "evidence": evidence,
            "evidence_gaps": evaluate_p0_gaps(CASE_ID, evidence),
        }
    )
    result = InvestigationWorkflow().run(InvestigationState.model_validate(data))
    assert result.status is AgentStatus.ESCALATED
    assert result.current_action is None
    assert "human service" in (result.next_action_reason or "")
    assert not can_ask_question(result, "Can I ask another question?")


def test_human_review_flag_routes_to_waiting_for_human() -> None:
    flag = message_evidence(
        "ev_human",
        "S500",
        "human_review_required",
        True,
        evidence_type=EvidenceType.VERIFIED_BUSINESS_FACT,
        source_type=SourceType.SERVICE_SYSTEM,
    )
    base = initial_state()
    data = base.model_dump()
    data["evidence"] = [*base.evidence, flag]
    result = InvestigationWorkflow().run(InvestigationState.model_validate(data))
    assert result.status is AgentStatus.WAITING_FOR_HUMAN
    assert result.current_action is AgentAction.WAIT_FOR_HUMAN


def test_max_steps_terminates_before_another_action() -> None:
    data = initial_state().model_dump()
    data.update({"step_count": 3, "max_steps": 3})
    result = InvestigationWorkflow().run(InvestigationState.model_validate(data))
    assert result.status is AgentStatus.TERMINATED
    assert result.step_count == 3
    assert result.state_revision == 1


def test_max_questions_routes_to_human_instead_of_looping() -> None:
    records = [
        AskedQuestion(
            id=f"q{index}",
            gap_type=GapType.ACTUAL_FIRST_USE_TIME,
            text=f"Question {index}",
            normalized_text=normalize_question(f"Question {index}"),
            status=QuestionStatus.ASKED,
            asked_at=NOW,
        )
        for index in range(1, 4)
    ]
    data = initial_state().model_dump()
    data.update(
        {
            "asked_questions": records,
            "question_count": 3,
            "max_questions": 3,
        }
    )
    result = InvestigationWorkflow().run(InvestigationState.model_validate(data))
    assert result.status is AgentStatus.WAITING_FOR_HUMAN


def test_illegal_transition_rejected() -> None:
    service = StateTransitionService()
    terminal_data = initial_state().model_dump()
    terminal_data["status"] = AgentStatus.CONCLUDED
    terminal = InvestigationState.model_validate(terminal_data)
    try:
        service.transition(
            terminal,
            to_status=AgentStatus.INVESTIGATING,
            action=None,
            reason="Illegal resume.",
        )
    except InvalidStateTransitionError:
        pass
    else:
        raise AssertionError("illegal transition must fail")


def test_revision_and_trace_increment_exactly_once_per_transition() -> None:
    result = InvestigationWorkflow().run(initial_state())
    assert result.state_revision == 1
    assert result.step_count == 1
    assert len(result.transition_events) == 1
    assert result.transition_events[0].state_revision == 1


def test_golden_demo_reaches_ambiguous_structured_conclusion() -> None:
    workflow = InvestigationWorkflow()
    state = workflow.run(initial_state())
    state = workflow.resume_with_evidence(state, [first_use_evidence()])
    assert state.asked_questions[-1].gap_type is GapType.FEEDBACK_ONSET_TIME
    state = workflow.resume_with_evidence(state, [feedback_onset_evidence()])
    assert state.asked_questions[-1].gap_type is GapType.RECENT_REGIMEN_CHANGES
    state = workflow.resume_with_evidence(state, [d_cream_change_evidence()])
    assert state.asked_questions[-1].gap_type is GapType.REPORTED_SEVERITY
    state = workflow.resume_with_evidence(state, [severity_evidence()])
    assert "D Cream" in (state.next_question or "")
    state = workflow.resume_with_evidence(
        state, [d_cream_change_evidence(with_date=True)]
    )
    assert state.status is AgentStatus.CONCLUDED
    assert state.investigation_result is not None
    assert (
        state.investigation_result.attribution_decision
        is AttributionDecision.ATTRIBUTION_AMBIGUOUS
    )
    assert workflow.checkpoints.load(CASE_ID) == state


def test_single_product_temporal_sequence_concludes_insufficient() -> None:
    workflow = InvestigationWorkflow()
    state = workflow.run(initial_state())
    state = workflow.resume_with_evidence(state, [first_use_evidence()])
    state = workflow.resume_with_evidence(state, [feedback_onset_evidence()])
    no_other_changes = message_evidence(
        "ev_no_changes",
        "M510",
        "recent_regimen_changes",
        {
            "product_id": "c_serum",
            "product_name": "C Serum",
            "change_type": "NEW",
            "effective_at": "2026-09-12",
        },
    )
    state = workflow.resume_with_evidence(state, [no_other_changes])
    state = workflow.resume_with_evidence(state, [severity_evidence()])
    assert state.status is AgentStatus.CONCLUDED
    assert state.investigation_result is not None
    assert (
        state.investigation_result.attribution_decision
        is AttributionDecision.INSUFFICIENT_EVIDENCE
    )
