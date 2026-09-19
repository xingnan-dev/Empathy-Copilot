from backend.app.agent.decision import DeterministicDecisionPolicy
from backend.app.agent.guardrails import AttributionDecision, assess_attribution
from backend.app.agent.questions import QuestionTemplateRegistry
from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import AgentAction, AgentStatus, InvestigationState, ToolCallStatus
from backend.app.domain.business import (
    ConsumerMemoryToolResult,
    OrderHistoryToolResult,
    OrderRecord,
    ServiceHistoryToolResult,
)
from backend.app.domain.evidence import EvidenceType, SourceType
from backend.app.domain.gaps import GapStatus, GapType, evaluate_p0_gaps
from backend.app.domain.regimen import build_regimen_changes
from backend.app.repositories.demo import DemoRepositoryBundle
from backend.app.services.checkpoints import InMemoryCheckpointStore
from backend.app.services.context_passport import ContextPassportService
from backend.app.services.grounding import EvidenceGroundingService
from backend.app.services.memory import ConsumerMemoryService
from backend.app.services.tools import BusinessToolSet, default_tool_registry
from backend.tests.fixtures import (
    CASE_ID,
    CONSUMER_ID,
    NOW,
    first_use_evidence,
    fully_resolved_state,
    message_evidence,
)


def phase3_initial_state(consumer_id: str = CONSUMER_ID) -> InvestigationState:
    return InvestigationState(
        case_id=CASE_ID,
        consumer_id=consumer_id,
        current_issue="我刚买的 C 精华用了以后感觉有点不舒服。",
        evidence=[],
        evidence_gaps=evaluate_p0_gaps(CASE_ID, []),
        created_at=NOW,
        updated_at=NOW,
    )


def business_tools() -> tuple[DemoRepositoryBundle, BusinessToolSet]:
    repositories = DemoRepositoryBundle()
    return repositories, BusinessToolSet(
        repositories.consumers,
        repositories.orders,
        repositories.service_history,
    )


def test_demo_repositories_load_expected_records() -> None:
    repositories = DemoRepositoryBundle()
    consumer = repositories.consumers.get(CONSUMER_ID)
    orders = repositories.orders.list_for_consumer(CONSUMER_ID)
    service = repositories.service_history.list_for_consumer(CONSUMER_ID)
    assert consumer is not None
    assert {record.order_id for record in orders} >= {"A1024", "A1010"}
    assert service[0].service_record_id == "SR1001"


def test_business_tools_return_typed_raw_results() -> None:
    _, tools = business_tools()
    state = phase3_initial_state()
    arguments = {"consumer_id": CONSUMER_ID}
    orders = tools.get_order_history(state, arguments)
    service = tools.get_service_history(state, arguments)
    memory = tools.get_consumer_memory(state, arguments)
    assert isinstance(orders, OrderHistoryToolResult)
    assert all(isinstance(record, OrderRecord) for record in orders.records)
    assert isinstance(service, ServiceHistoryToolResult)
    assert isinstance(memory, ConsumerMemoryToolResult)


def test_order_grounding_preserves_type_and_order_provenance() -> None:
    _, tools = business_tools()
    raw = tools.get_order_history(
        phase3_initial_state(), {"consumer_id": CONSUMER_ID}
    )
    evidence = EvidenceGroundingService().ground_order_history(raw, CASE_ID)
    c_order = next(item for item in evidence if item.source.source_id == "A1024")
    assert c_order.evidence_type is EvidenceType.VERIFIED_BUSINESS_FACT
    assert c_order.key == "first_purchase"
    assert c_order.source.source_type is SourceType.ORDER_SYSTEM
    assert c_order.source.source_label == "Order A1024"


def test_service_grounding_is_historical_service_fact() -> None:
    _, tools = business_tools()
    raw = tools.get_service_history(
        phase3_initial_state(), {"consumer_id": CONSUMER_ID}
    )
    evidence = EvidenceGroundingService().ground_service_history(raw, CASE_ID)
    assert len(evidence) == 1
    assert evidence[0].key == "previous_service_contact"
    assert evidence[0].source.source_type is SourceType.SERVICE_SYSTEM
    assert isinstance(evidence[0].value, dict)
    assert evidence[0].value["historical_case_id"] == "case_historical_001"


def test_purchase_never_resolves_first_use_or_creates_regimen_change() -> None:
    _, tools = business_tools()
    raw = tools.get_order_history(
        phase3_initial_state(), {"consumer_id": CONSUMER_ID}
    )
    evidence = EvidenceGroundingService().ground_order_history(raw, CASE_ID)
    first_use_gap = next(
        gap
        for gap in evaluate_p0_gaps(CASE_ID, evidence)
        if gap.gap_type is GapType.ACTUAL_FIRST_USE_TIME
    )
    assert first_use_gap.status is GapStatus.OPEN
    assert build_regimen_changes(CASE_ID, evidence) == []
    assert all(item.key != "actual_first_use_time" for item in evidence)


def test_purchase_timestamp_does_not_become_usage_timestamp() -> None:
    repositories, tools = business_tools()
    raw = tools.get_order_history(
        phase3_initial_state(), {"consumer_id": CONSUMER_ID}
    )
    evidence = EvidenceGroundingService().ground_order_history(raw, CASE_ID)
    c_order = next(
        record
        for record in repositories.orders.list_for_consumer(CONSUMER_ID)
        if record.order_id == "A1024"
    )
    assert c_order.ordered_at.isoformat() in {
        item.value["ordered_at"] for item in evidence if isinstance(item.value, dict)
    }
    assert all(
        "first_use_at" not in item.value
        for item in evidence
        if isinstance(item.value, dict)
    )


def test_repeat_purchase_does_not_claim_current_usage() -> None:
    _, tools = business_tools()
    raw = tools.get_order_history(
        phase3_initial_state(), {"consumer_id": CONSUMER_ID}
    )
    evidence = EvidenceGroundingService().ground_order_history(raw, CASE_ID)
    repeat = next(item for item in evidence if item.key == "repeat_purchase")
    assert isinstance(repeat.value, dict)
    assert repeat.value["product_id"] == "a_serum"
    assert all(item.key != "current_usage" for item in evidence)


def test_consumer_memory_facts_all_reference_existing_evidence() -> None:
    _, tools = business_tools()
    raw = tools.get_consumer_memory(
        phase3_initial_state(), {"consumer_id": CONSUMER_ID}
    )
    evidence = EvidenceGroundingService().ground_consumer_memory(raw, CASE_ID)
    memory = ConsumerMemoryService().build(CONSUMER_ID, evidence)
    evidence_ids = {item.id for item in evidence}
    facts = (
        memory.repeat_purchase_products
        + memory.recent_orders
        + memory.previous_service_contacts
        + memory.explicit_preferences
    )
    assert facts
    assert all(set(fact.evidence_ids) <= evidence_ids for fact in facts)


def test_unknown_consumer_tools_and_grounding_produce_no_fake_evidence() -> None:
    _, tools = business_tools()
    state = phase3_initial_state("consumer_unknown")
    arguments = {"consumer_id": "consumer_unknown"}
    order_raw = tools.get_order_history(state, arguments)
    memory_raw = tools.get_consumer_memory(state, arguments)
    grounding = EvidenceGroundingService()
    assert order_raw.records == []
    assert memory_raw.consumer is None
    assert grounding.ground_order_history(order_raw, CASE_ID) == []
    assert grounding.ground_consumer_memory(memory_raw, CASE_ID) == []


def test_unknown_consumer_workflow_asks_user_after_empty_order_lookup() -> None:
    state = InvestigationWorkflow().run(phase3_initial_state("consumer_unknown"))
    assert state.status is AgentStatus.WAITING_FOR_USER
    assert state.asked_questions[-1].gap_type is GapType.ACTUAL_FIRST_USE_TIME
    order_call = next(call for call in state.tool_calls if call.tool_name == "get_order_history")
    assert order_call.status is ToolCallStatus.COMPLETED
    assert order_call.result_evidence_ids == []
    assert state.evidence == []


def test_decision_chooses_business_tool_then_consumer_question() -> None:
    policy = DeterministicDecisionPolicy(QuestionTemplateRegistry())
    missing_context = policy.decide(phase3_initial_state())
    assert missing_context.action is AgentAction.CALL_TOOL
    assert missing_context.tool_name == "get_order_history"

    workflow = InvestigationWorkflow()
    waiting = workflow.run(phase3_initial_state())
    assert waiting.status is AgentStatus.WAITING_FOR_USER
    assert waiting.asked_questions[-1].gap_type is GapType.ACTUAL_FIRST_USE_TIME
    assert waiting.current_action is AgentAction.ASK_USER


def test_golden_order_tool_grounds_records_and_links_tool_result_ids() -> None:
    workflow = InvestigationWorkflow()
    waiting = workflow.run(phase3_initial_state())
    order_call = next(call for call in waiting.tool_calls if call.tool_name == "get_order_history")
    assert order_call.status is ToolCallStatus.COMPLETED
    assert order_call.result_evidence_ids
    assert set(order_call.result_evidence_ids) <= {item.id for item in waiting.evidence}
    c_order = next(item for item in waiting.evidence if item.source.source_id == "A1024")
    assert c_order.key == "first_purchase"
    first_use_gap = next(
        gap
        for gap in waiting.evidence_gaps
        if gap.gap_type is GapType.ACTUAL_FIRST_USE_TIME
    )
    assert first_use_gap.status is GapStatus.OPEN


def test_completed_equivalent_business_tool_is_not_executed_twice() -> None:
    registry = default_tool_registry()
    workflow = InvestigationWorkflow(tool_registry=registry)
    waiting = workflow.run(phase3_initial_state())
    order_call = next(call for call in waiting.tool_calls if call.tool_name == "get_order_history")
    unchanged = workflow.tool_execution.execute_once(
        waiting,
        tool_name="get_order_history",
        action=AgentAction.CALL_TOOL,
        arguments={"consumer_id": CONSUMER_ID},
    )
    assert unchanged == waiting
    assert order_call in unchanged.tool_calls
    assert registry.execution_counts["get_order_history"] == 1


def test_consumer_first_use_remains_independent_and_resolves_gap() -> None:
    workflow = InvestigationWorkflow()
    waiting = workflow.run(phase3_initial_state())
    resumed = workflow.resume_with_evidence(waiting, [first_use_evidence()])
    gap = next(
        item
        for item in resumed.evidence_gaps
        if item.gap_type is GapType.ACTUAL_FIRST_USE_TIME
    )
    assert gap.status is GapStatus.RESOLVED
    consumer_usage = next(item for item in resumed.evidence if item.id == "ev_m102_first_use")
    order = next(item for item in resumed.evidence if item.source.source_id == "A1024")
    assert consumer_usage.source.source_type is SourceType.CONSUMER_MESSAGE
    assert order.source.source_type is SourceType.ORDER_SYSTEM
    assert resumed.asked_questions[0].status.value == "ANSWERED"


def test_context_passport_contains_only_evidence_backed_facts() -> None:
    workflow = InvestigationWorkflow()
    waiting = workflow.run(phase3_initial_state())
    passport = ContextPassportService().build(waiting)
    evidence_ids = {item.id for item in waiting.evidence}
    assert passport.confirmed_facts
    assert all(set(fact.evidence_ids) <= evidence_ids for fact in passport.confirmed_facts)
    assert "get_order_history" in passport.completed_tools
    assert GapType.ACTUAL_FIRST_USE_TIME in passport.open_gaps


def test_context_passport_does_not_promote_ai_inference_to_confirmed_fact() -> None:
    state = phase3_initial_state()
    inference = message_evidence(
        "ev_ai_guess",
        "reasoning_1",
        "suspected_cause",
        "c_serum",
        evidence_type=EvidenceType.AI_INFERENCE,
        source_type=SourceType.AI_REASONING,
    )
    data = state.model_dump()
    data["evidence"] = [inference]
    passport = ContextPassportService().build(InvestigationState.model_validate(data))
    assert passport.confirmed_facts == []


def test_repeat_contact_restores_passport_without_reasking_first_use() -> None:
    store = InMemoryCheckpointStore()
    registry = default_tool_registry()
    first_workflow = InvestigationWorkflow(
        checkpoint_store=store, tool_registry=registry
    )
    waiting = first_workflow.run(phase3_initial_state())
    after_answer = first_workflow.resume_with_evidence(waiting, [first_use_evidence()])

    second_workflow = InvestigationWorkflow(
        checkpoint_store=store, tool_registry=registry
    )
    restored = second_workflow.restore_case(CASE_ID)
    passport = second_workflow.context_passport(CASE_ID)
    assert restored == after_answer
    assert restored.asked_questions[0].status.value == "ANSWERED"
    assert sum(
        question.gap_type is GapType.ACTUAL_FIRST_USE_TIME
        for question in restored.asked_questions
    ) == 1
    assert passport.asked_questions == restored.asked_questions
    assert {"get_order_history", "get_service_history", "get_consumer_memory"} <= set(
        passport.completed_tools
    )


def test_service_history_cannot_prove_current_case_causality() -> None:
    _, tools = business_tools()
    raw = tools.get_service_history(
        phase3_initial_state(), {"consumer_id": CONSUMER_ID}
    )
    historical = EvidenceGroundingService().ground_service_history(raw, CASE_ID)
    state = fully_resolved_state()
    data = state.model_dump()
    data["evidence"] = [*state.evidence, *historical]
    with_history = InvestigationState.model_validate(data)
    decision = assess_attribution(
        with_history,
        "c_serum",
        build_regimen_changes(CASE_ID, with_history.evidence),
    )
    assert decision.decision is AttributionDecision.ATTRIBUTION_AMBIGUOUS


def test_d_without_date_remains_non_concurrent_and_same_date_is_ambiguous() -> None:
    state = fully_resolved_state(dated_d_change=False)
    without_date = assess_attribution(
        state,
        "c_serum",
        build_regimen_changes(CASE_ID, state.evidence),
    )
    assert without_date.decision is AttributionDecision.INSUFFICIENT_EVIDENCE

    dated = fully_resolved_state()
    with_date = assess_attribution(
        dated,
        "c_serum",
        build_regimen_changes(CASE_ID, dated.evidence),
    )
    assert with_date.decision is AttributionDecision.ATTRIBUTION_AMBIGUOUS


def test_memory_tool_does_not_turn_order_into_usage() -> None:
    workflow = InvestigationWorkflow()
    waiting = workflow.run(phase3_initial_state())
    resumed = workflow.resume_with_evidence(waiting, [first_use_evidence()])
    assert resumed.consumer_memory is not None
    business_only = [
        item
        for item in resumed.evidence
        if item.source.source_type in {SourceType.ORDER_SYSTEM, SourceType.SERVICE_SYSTEM}
    ]
    assert build_regimen_changes(CASE_ID, business_only) == []
    assert all(item.key != "actual_first_use_time" for item in business_only)
