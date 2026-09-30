import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.agent.guardrails import AttributionDecision, assess_attribution
from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.api.app import create_app
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    InvestigationState,
)
from backend.app.domain.business import LogisticsRecord, LogisticsStatusToolResult
from backend.app.domain.evidence import EvidenceType
from backend.app.domain.gaps import EvidenceGap, GapStatus, GapType, evaluate_scenario_gaps
from backend.app.domain.regimen import build_regimen_changes
from backend.app.domain.scenarios import InvestigationScenario
from backend.app.official_dataset.adapter import (
    OfficialDatasetAdapter,
    OfficialDatasetValidationError,
)
from backend.app.official_dataset.cases import OfficialCaseFactory
from backend.app.official_dataset.grounding import OfficialEvidenceGroundingService
from backend.app.official_dataset.models import MessageRecord, OfficialDataset
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
