import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.agent.guardrails import AttributionDecision, assess_attribution
from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.api.app import create_app
from backend.app.api.fixtures import s00154_waiting_for_human
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    InvestigationState,
)
from backend.app.domain.business import LogisticsRecord, LogisticsStatusToolResult
from backend.app.domain.evidence import EvidenceType
from backend.app.domain.gaps import (
    EvidenceGap,
    GapStatus,
    GapType,
    evaluate_p0_gaps,
    evaluate_scenario_gaps,
)
from backend.app.domain.regimen import build_regimen_changes
from backend.app.domain.scenarios import InvestigationScenario
from backend.app.llm.providers.fake import FakeModelProvider
from backend.app.llm.schemas import ModelOutput
from backend.app.llm.service import ModelService
from backend.app.official_dataset.adapter import (
    OfficialDatasetAdapter,
    OfficialDatasetValidationError,
)
from backend.app.official_dataset.cases import OfficialCaseFactory
from backend.app.official_dataset.grounding import OfficialEvidenceGroundingService
from backend.app.official_dataset.models import (
    ConversationSession,
    MessageRecord,
    OfficialConsumerRecord,
    OfficialDataset,
    OfficialOrderRecord,
    OfficialServiceRecord,
)
from backend.app.services.checkpoints import InMemoryCheckpointStore
from backend.app.services.tools import ToolRegistry


@pytest.fixture(scope="module")
def official_dataset() -> OfficialDataset:
    path = os.getenv("OFFICIAL_DATASET_PATH")
    if not path:
        pytest.skip("OFFICIAL_DATASET_PATH is not configured")
    return OfficialDatasetAdapter().read(Path(path))


def _gap(state: InvestigationState, gap_type: GapType) -> EvidenceGap:
    return next(item for item in state.evidence_gaps if item.gap_type is gap_type)


def _temporal_dataset() -> OfficialDataset:
    before = datetime(2026, 5, 1, 10, 0)
    after = datetime(2026, 5, 1, 10, 5)
    return OfficialDataset(
        consumers=[OfficialConsumerRecord(consumer_id="CONSUMER")],
        sessions=[
            ConversationSession(
                session_id="TEMPORAL-CASE",
                consumer_id="CONSUMER",
                shop="SHOP",
                scene_major="不良反应",
                scene_minor="红肿",
                scenario=InvestigationScenario.ADVERSE_REACTION,
                started_at=before,
                order_ids=["ORDER"],
                ticket_ids=["SERVICE"],
            )
        ],
        messages=[
            MessageRecord(
                message_id="VISIBLE-MESSAGE",
                session_id="TEMPORAL-CASE",
                sequence=1,
                sent_at=before,
                consumer_id="CONSUMER",
                role="买家",
                sender="CONSUMER",
                text="我用了面霜，脸部肿了，已经就医。",
                content_type="文本",
                order_id="ORDER",
            ),
            MessageRecord(
                message_id="FUTURE-IMAGE-MESSAGE",
                session_id="TEMPORAL-CASE",
                sequence=2,
                sent_at=after,
                consumer_id="CONSUMER",
                role="买家",
                sender="CONSUMER",
                text="材料在这里，请快点处理。",
                content_type="图片",
                image_path="future.jpg",
                order_id="ORDER",
                ticket_id="SERVICE",
            ),
        ],
        orders=[
            OfficialOrderRecord(
                order_id="ORDER",
                session_id="TEMPORAL-CASE",
                consumer_id="CONSUMER",
                product_id="SET",
                product_name="Gift Set",
                quantity=1,
                unit_price=100,
                paid_amount=100,
                order_status="完成",
                ordered_at=datetime(2026, 4, 1, 10, 0),
                paid_at=datetime(2026, 4, 1, 10, 1),
            )
        ],
        service_records=[
            OfficialServiceRecord(
                service_record_id="FUTURE-SERVICE",
                source_kind="不良反应工单",
                session_id="TEMPORAL-CASE",
                order_id="ORDER",
                consumer_id="CONSUMER",
                issue_type="不良反应",
                status="已完结",
                created_at=after,
                completed_at=after,
                details={"症状描述": "未来记录", "是否就医": "是"},
            )
        ],
    )


@pytest.mark.official_dataset
def test_official_workbook_normalizes_complete_source(official_dataset: OfficialDataset) -> None:
    assert len(official_dataset.consumers) == 112
    assert len(official_dataset.sessions) == 138
    assert len(official_dataset.messages) == 998
    assert len(official_dataset.orders) == 113
    assert len(official_dataset.service_records) == 80
    assert len({item.message_id for item in official_dataset.messages}) == 998
    assert len({item.order_id for item in official_dataset.orders}) == 113
    assert len({item.service_record_id for item in official_dataset.service_records}) == 80


def test_adapter_rejects_missing_required_columns(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "聊天记录"
    sheet.append(["会话ID", "message_text"])
    target = tmp_path / "malformed.xlsx"
    workbook.save(target)
    with pytest.raises(OfficialDatasetValidationError, match="missing required columns"):
        OfficialDatasetAdapter().read(target)


@pytest.mark.official_dataset
def test_s00154_preserves_usage_and_attribution_boundaries(
    official_dataset: OfficialDataset,
) -> None:
    state = OfficialCaseFactory().build(official_dataset, "S00154")
    assert state.scenario is InvestigationScenario.ADVERSE_REACTION
    assert _gap(state, GapType.EXACT_PRODUCT_USED).status is GapStatus.RESOLVED
    assert _gap(state, GapType.MEDICAL_ATTENTION_STATUS).status is GapStatus.RESOLVED
    used_product = next(item for item in state.evidence if item.key == "exact_product_used")
    assert used_product.value == "面霜"
    assert used_product.evidence_type is EvidenceType.CONSUMER_REPORTED
    assert used_product.source.source_id == "94422222481506.PNM"
    assert used_product.source.source_type.value == "CONSUMER_MESSAGE"
    assert not any(
        item.key == "exact_product_used"
        and item.evidence_type is EvidenceType.VERIFIED_BUSINESS_FACT
        for item in state.evidence
    )
    medical = [item for item in state.evidence if item.key == "reported_medical_attention"]
    assert medical
    assert all(item.evidence_type is EvidenceType.CONSUMER_REPORTED for item in medical)
    assert build_regimen_changes(state.case_id, state.evidence) == []
    assert (
        assess_attribution(state, "XL19805", []).decision
        is AttributionDecision.INSUFFICIENT_EVIDENCE
    )

    checkpoints = InMemoryCheckpointStore()
    checkpoints.save(state)
    projected = CaseApplicationService(
        InvestigationWorkflow(checkpoint_store=checkpoints), checkpoints
    ).get_case("S00154")
    assert projected.response_context.question_resolves_gap == "ACTUAL_FIRST_USE_TIME"
    assert "礼盒中的哪一款产品" not in str(projected.response_context.next_best_question)
    assert projected.attribution_status == "INSUFFICIENT_EVIDENCE"
    assert projected.safety_gate == "SAFETY"
    assert projected.service_strategy.consumer_signal.label == (
        "Language suggests urgency or distress."
    )
    assert projected.service_strategy.consumer_signal.semantic_type == "AI_INFERENCE"
    assert projected.service_strategy.human_attention.value == "SAFETY_ESCALATION"
    assert projected.service_strategy.critical_gap == "ACTUAL_FIRST_USE_TIME"
    assert projected.service_strategy.next_question == (
        "想再确认一下，您第一次使用这款产品的具体日期是什么时候？"
    )


def test_explicit_product_use_grounding_is_general_and_conservative() -> None:
    grounding = OfficialEvidenceGroundingService()
    explicit = MessageRecord(
        message_id="MESSAGE-USE",
        session_id="ARBITRARY-CASE",
        sequence=1,
        sent_at=datetime(2026, 5, 1, tzinfo=UTC),
        consumer_id="CONSUMER",
        role="买家",
        sender="CONSUMER",
        text="昨晚我用了面霜，后来觉得有点刺痛",
        content_type="文本",
    )
    evidence = grounding._message(explicit, InvestigationScenario.ADVERSE_REACTION)
    used_product = next(item for item in evidence if item.key == "exact_product_used")
    assert used_product.case_id == "ARBITRARY-CASE"
    assert used_product.value == "面霜"
    assert used_product.evidence_type is EvidenceType.CONSUMER_REPORTED
    assert used_product.source.source_id == "MESSAGE-USE"

    not_usage = explicit.model_copy(
        update={
            "message_id": "MESSAGE-PURCHASE",
            "text": "我买的是面霜和精华礼盒，还没开始用",
        }
    )
    purchase_evidence = grounding._message(not_usage, InvestigationScenario.ADVERSE_REACTION)
    assert all(item.key != "exact_product_used" for item in purchase_evidence)


def test_temporal_cutoff_excludes_future_messages_images_and_service_records() -> None:
    evidence = OfficialEvidenceGroundingService().ground_case(
        _temporal_dataset(),
        "TEMPORAL-CASE",
        message_sequence_cutoff=1,
    )

    source_ids = {item.source.source_id for item in evidence}
    assert "VISIBLE-MESSAGE" in source_ids
    assert "FUTURE-IMAGE-MESSAGE" not in source_ids
    assert "FUTURE-SERVICE" not in source_ids
    assert not any(item.key == "image_reference" for item in evidence)
    assert all(item.metadata["official_message_sequence_cutoff"] == 1 for item in evidence)


def test_temporal_cutoff_is_shared_by_passport_strategy_and_response_context() -> None:
    class CapturingProvider(FakeModelProvider):
        def __init__(self) -> None:
            super().__init__(response="已记录您反馈的面部肿胀情况，我们会继续核对。")
            self.response_context: dict[str, object] | None = None

        def generate_response(self, context: dict[str, object]) -> ModelOutput:
            self.response_context = context
            return super().generate_response(context)

    state = OfficialCaseFactory().build(
        _temporal_dataset(),
        "TEMPORAL-CASE",
        message_sequence_cutoff=1,
    )
    checkpoints = InMemoryCheckpointStore()
    checkpoints.save(state)
    provider = CapturingProvider()
    service = CaseApplicationService(
        InvestigationWorkflow(checkpoint_store=checkpoints),
        checkpoints,
        ModelService(provider),
    )

    projected = service.get_case("TEMPORAL-CASE")
    confirmed_ids = {
        evidence_id
        for fact in projected.context_passport["confirmed_facts"]
        for evidence_id in fact["evidence_ids"]
    }
    future_ids = {
        "official-message-FUTURE-IMAGE-MESSAGE",
        "official-image-FUTURE-IMAGE-MESSAGE",
        "official-service-status-FUTURE-SERVICE",
    }
    assert confirmed_ids.isdisjoint(future_ids)
    assert set(projected.response_context.evidence_used_ids).isdisjoint(future_ids)
    assert projected.service_strategy.consumer_signal.label == (
        "No explicit emotion signal available."
    )

    service.generate_response_draft("TEMPORAL-CASE", projected.revision)
    assert provider.response_context is not None
    response_evidence = provider.response_context["evidence"]
    assert isinstance(response_evidence, list)
    assert all(
        "快点" not in str(item) and "未来记录" not in str(item)
        for item in response_evidence
    )


@pytest.mark.official_dataset
def test_s00154_initial_snapshot_excludes_future_official_records(
    official_dataset: OfficialDataset,
) -> None:
    state = OfficialCaseFactory().build(
        official_dataset,
        "S00154",
        message_sequence_cutoff=4,
    )
    source_ids = {item.source.source_id for item in state.evidence}
    future_message_ids = {
        item.message_id
        for item in official_dataset.messages
        if item.session_id == "S00154" and item.sequence > 4 and item.role == "买家"
    }
    future_service_ids = {
        item.service_record_id
        for item in official_dataset.service_records
        if item.session_id == "S00154"
    }
    assert {
        item.sent_at.strftime("%H:%M:%S")
        for item in official_dataset.messages
        if item.session_id == "S00154" and item.sequence in {5, 7, 9}
    } == {"16:22:33", "16:26:18", "16:29:13"}
    assert {
        item.created_at.strftime("%H:%M:%S")
        for item in official_dataset.service_records
        if item.session_id == "S00154"
    } == {"16:49:30"}
    assert "94422222481506.PNM" in source_ids
    assert source_ids.isdisjoint(future_message_ids)
    assert source_ids.isdisjoint(future_service_ids)
    used_product = next(item for item in state.evidence if item.key == "exact_product_used")
    assert used_product.value == "面霜"
    assert used_product.evidence_type is EvidenceType.CONSUMER_REPORTED
    assert any(item.key == "reported_severity" for item in state.evidence)
    assert any(item.key == "reported_medical_attention" for item in state.evidence)

    checkpoints = InMemoryCheckpointStore()
    checkpoints.save(state)
    projected = CaseApplicationService(
        InvestigationWorkflow(checkpoint_store=checkpoints), checkpoints
    ).get_case("S00154")
    assert projected.lifecycle == "WAITING_FOR_HUMAN"
    assert projected.human_checkpoint.state == "REQUIRED"
    assert projected.human_checkpoint.can_approve is True
    assert next(gap for gap in projected.gaps if gap.id == "EXACT_PRODUCT_USED").status == (
        "RESOLVED"
    )
    assert projected.response_context.question_resolves_gap == "ACTUAL_FIRST_USE_TIME"
    assert projected.response_context.next_best_question == (
        "想再确认一下，您第一次使用这款产品的具体日期是什么时候？"
    )
    assert projected.safety_gate == "SAFETY"
    assert projected.safety_path == "ESCALATION"
    assert projected.attribution_status == "INSUFFICIENT_EVIDENCE"


@pytest.mark.official_dataset
def test_official_registration_upgrades_only_the_legacy_integration_fixture(
    official_dataset: OfficialDataset,
) -> None:
    fixture = s00154_waiting_for_human()
    legacy_evidence = [
        item
        for item in fixture.evidence
        if item.id
        not in {"consumer-message", "consumer-product-used", "human-review-required"}
    ]
    legacy = fixture.model_copy(
        update={
            "evidence": legacy_evidence,
            "evidence_gaps": evaluate_p0_gaps(fixture.case_id, legacy_evidence),
            "status": AgentStatus.ESCALATED,
            "current_action": None,
        }
    )
    checkpoints = InMemoryCheckpointStore()
    checkpoints.save(legacy)
    service = CaseApplicationService(
        InvestigationWorkflow(checkpoint_store=checkpoints), checkpoints
    )

    service.register_official_cases(official_dataset, [fixture.case_id])
    projected = service.get_case(fixture.case_id)

    assert projected.official_data is True
    assert next(gap for gap in projected.gaps if gap.id == "EXACT_PRODUCT_USED").status == (
        "RESOLVED"
    )
    assert any(item.fact == "面霜" for item in projected.evidence)


@pytest.mark.official_dataset
def test_official_registration_replaces_an_uncut_initial_snapshot(
    official_dataset: OfficialDataset,
) -> None:
    complete = OfficialCaseFactory().build(official_dataset, "S00154")
    checkpoints = InMemoryCheckpointStore()
    checkpoints.save(complete)
    service = CaseApplicationService(
        InvestigationWorkflow(checkpoint_store=checkpoints), checkpoints
    )

    service.register_official_cases(
        official_dataset,
        ["S00154"],
        message_sequence_cutoffs={"S00154": 4},
    )

    refreshed = checkpoints.load("S00154")
    assert refreshed.state_revision == complete.state_revision + 1
    assert {
        item.metadata.get("official_message_sequence_cutoff") for item in refreshed.evidence
    } == {4}
    assert all(
        item.source.source_id != "BLFY27898314" for item in refreshed.evidence
    )


@pytest.mark.official_dataset
def test_s00001_grounds_damage_and_image_metadata_without_vision(
    official_dataset: OfficialDataset,
) -> None:
    state = OfficialCaseFactory().build(official_dataset, "S00001")
    assert state.scenario is InvestigationScenario.PRODUCT_DAMAGE
    for gap in (
        GapType.AFFECTED_ITEM,
        GapType.DAMAGE_DESCRIPTION,
        GapType.ORDER_MATCH,
        GapType.REPLACEMENT_ELIGIBILITY,
    ):
        assert _gap(state, gap).status is GapStatus.RESOLVED
    assert _gap(state, GapType.VISUAL_EVIDENCE).status is GapStatus.OPEN
    image = next(item for item in state.evidence if item.key == "image_reference")
    assert isinstance(image.value, dict)
    assert image.metadata["vision_analyzed"] is False
    assert image.value["reference_exists"] is True
    assert image.value["asset_available"] is False
    assert "S00001_03.jpg" in str(image.value)


@pytest.mark.official_dataset
def test_s00009_retains_delivery_conflict_in_api_projection(
    official_dataset: OfficialDataset,
) -> None:
    checkpoints = InMemoryCheckpointStore()
    workflow = InvestigationWorkflow(checkpoint_store=checkpoints)
    service = CaseApplicationService(workflow, checkpoints)
    service.register_official_cases(official_dataset, ["S00009"])
    projected = service.get_case("S00009")
    assert projected.scenario == "LOGISTICS_EXCEPTION"
    assert projected.evidence_conflicts == [
        {
            "type": "DELIVERY_STATUS_CONFLICT",
            "verified_evidence_ids": ["official-logistics-WL991067160"],
            "consumer_reported_evidence_ids": ["official-receipt-no-39281097452618.PNM"],
            "status": "RETAINED",
        }
    ]


@pytest.mark.official_dataset
def test_s00009_wait_checkpoint_resume_and_conclude_uses_existing_workflow(
    official_dataset: OfficialDataset,
) -> None:
    complete = OfficialCaseFactory().build(official_dataset, "S00009")
    later_keys = {"logistics_investigation_result", "resolution_status"}
    initial_evidence = [
        item
        for item in complete.evidence
        if item.key not in later_keys
        and not (item.key == "consumer_receipt_status" and item.value == "RECEIVED")
    ]
    initial = complete.model_copy(
        update={
            "evidence": initial_evidence,
            "evidence_gaps": evaluate_scenario_gaps(
                complete.case_id, InvestigationScenario.LOGISTICS_EXCEPTION, initial_evidence
            ),
        }
    )
    checkpoints = InMemoryCheckpointStore()
    registry = ToolRegistry()

    def pending_logistics(
        state: InvestigationState, arguments: dict[str, str]
    ) -> LogisticsStatusToolResult:
        assert state.case_id == arguments["case_id"] == "S00009"
        return LogisticsStatusToolResult(
            case_id="S00009",
            record=LogisticsRecord(
                service_record_id="WL991067160",
                consumer_id=state.consumer_id,
                case_id=state.case_id,
                delivery_status="SYSTEM_MARKED_DELIVERED",
                investigation_result=None,
                resolution_status="调查中",
                observed_at=state.updated_at,
            ),
        )

    registry.register("get_logistics_status", pending_logistics)
    workflow = InvestigationWorkflow(checkpoint_store=checkpoints, tool_registry=registry)
    waiting = workflow.run(initial)
    assert waiting.status is AgentStatus.WAITING_FOR_USER
    assert registry.execution_counts["get_logistics_status"] == 1
    assert any(event.action is AgentAction.CALL_TOOL for event in waiting.transition_events)
    tool_call = next(
        call for call in waiting.tool_calls if call.tool_name == "get_logistics_status"
    )
    assert tool_call.status.value == "COMPLETED"
    grounded = [item for item in waiting.evidence if item.id in tool_call.result_evidence_ids]
    assert grounded and all(
        item.metadata["grounding_method"] == "BUSINESS_TOOL" for item in grounded
    )
    assert any(item.value == "NOT_RECEIVED" for item in waiting.evidence)
    assert any(item.value == "SYSTEM_MARKED_DELIVERED" for item in waiting.evidence)

    resumed = workflow.resume_case(
        "S00009", [item for item in complete.evidence if item.key in later_keys]
    )
    restarted = InvestigationWorkflow(checkpoint_store=checkpoints, tool_registry=registry)
    restored = restarted.restore_case("S00009")
    assert resumed.status is AgentStatus.CONCLUDED
    assert restored.state_revision == resumed.state_revision
    assert all(gap.status is GapStatus.RESOLVED for gap in restored.evidence_gaps)
    assert restored.investigation_result is not None
    assert restored.investigation_result.attribution_decision.value != "SUPPORTED"


@pytest.mark.official_dataset
def test_same_consumer_after_sales_history_restores_context(
    official_dataset: OfficialDataset,
) -> None:
    state = OfficialCaseFactory().build(official_dataset, "S00381")
    history = [item for item in state.evidence if item.key == "previous_service_contact"]
    assert state.consumer_id == "郭a**"
    assert state.scenario is InvestigationScenario.AFTER_SALES
    assert any(
        isinstance(item.value, dict) and item.value.get("historical_case_id") == "S00038"
        for item in history
    )
    assert any(item.source.source_id == "HV5725862244" for item in history)
    assert all(item.evidence_type is EvidenceType.VERIFIED_BUSINESS_FACT for item in history)


@pytest.mark.official_dataset
def test_official_case_projects_through_http_api(official_dataset: OfficialDataset) -> None:
    checkpoints = InMemoryCheckpointStore()
    workflow = InvestigationWorkflow(checkpoint_store=checkpoints)
    service = CaseApplicationService(workflow, checkpoints)
    service.register_official_cases(official_dataset, ["S00009", "S00381"])
    client = TestClient(create_app(lambda: service))

    response = client.get("/api/cases/S00009")
    assert response.status_code == 200
    body = response.json()
    assert body["official_data"] is True
    assert body["scenario"] == "LOGISTICS_EXCEPTION"
    assert body["evidence_conflicts"][0]["status"] == "RETAINED"

    continuity = client.get("/api/cases/S00381").json()
    assert continuity["restored_context"] is True
    assert continuity["previous_service_history"][0]["historical_case_id"] == "S00038"
