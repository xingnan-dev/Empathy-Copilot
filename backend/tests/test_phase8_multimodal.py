import base64
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.agent.guardrails import AttributionDecision, assess_attribution
from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.domain.agent import InvestigationState
from backend.app.domain.gaps import GapType, evaluate_scenario_gaps
from backend.app.domain.safety import SafetyGate, SafetyGateService
from backend.app.domain.scenarios import InvestigationScenario
from backend.app.knowledge import IngredientContextChecker, KnowledgeType, LocalKnowledgeRetriever
from backend.app.official_dataset.adapter import OfficialDatasetAdapter
from backend.app.official_dataset.cases import OfficialCaseFactory
from backend.app.official_dataset.models import OfficialDataset
from backend.app.services.checkpoints import InMemoryCheckpointStore
from backend.app.vision.fake import FakeVisionProvider
from backend.app.vision.provider import VisionProviderError
from backend.app.vision.qwen import QwenVisionProvider
from backend.app.vision.schemas import ImageCategory, StructuredVisionObservation, Visibility
from backend.app.vision.service import VisionService
from backend.app.vision.validator import UnsafeVisionObservation, VisionSafetyValidator

DEMO_ASSET_ID = "DEMO_BROKEN_PUMP_001"
DEMO_MESSAGE_ID = "DEMO_BROKEN_PUMP_MESSAGE_001"
DEMO_ASSET_PATH = (
    Path(__file__).parents[1] / "data" / "demo_assets" / "demo_broken_pump_001.png"
)


def demo_image_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(DEMO_ASSET_PATH.read_bytes()).decode()


@pytest.fixture(scope="module")
def official_dataset() -> OfficialDataset:
    path = os.getenv("OFFICIAL_DATASET_PATH")
    if not path:
        pytest.skip("OFFICIAL_DATASET_PATH is not configured")
    return OfficialDatasetAdapter().read(path)


def observation(
    *,
    category: ImageCategory = ImageCategory.PRODUCT_DAMAGE,
    condition: str = "泵头部件存在可见位移。",
    features: list[str] | None = None,
    image_id: str = DEMO_ASSET_ID,
    message_id: str = DEMO_MESSAGE_ID,
) -> StructuredVisionObservation:
    return StructuredVisionObservation(
        observation_id=f"obs-{message_id}",
        source_image_id=image_id,
        source_message_id=message_id,
        image_category=category,
        visible_features=features or ["泵头", "部件位移"],
        visible_condition=condition,
        visibility=Visibility.CLEAR,
        sufficient=True,
        uncertainty="仅描述可见外观，无法判断原因或服务资格。",
        extraction_confidence=0.88,
        provider="fake-vision",
        model="fake-vision-v1",
    )


def demo_service(candidate: StructuredVisionObservation) -> CaseApplicationService:
    checkpoints = InMemoryCheckpointStore()
    workflow = InvestigationWorkflow(checkpoint_store=checkpoints)
    service = CaseApplicationService(
        workflow, checkpoints, vision_service=VisionService(FakeVisionProvider(candidate))
    )
    scenario = InvestigationScenario.PRODUCT_DAMAGE
    state = InvestigationState(
        case_id="DEMO-PRODUCT-DAMAGE",
        consumer_id="DEMO-CONSUMER",
        current_issue="Synthetic broken pump fixture acceptance",
        scenario=scenario,
    )
    state.evidence_gaps = evaluate_scenario_gaps(state.case_id, scenario, state.evidence)
    checkpoints.save(state)
    return service


def test_structured_vision_schema_rejects_malformed_output() -> None:
    with pytest.raises(ValidationError):
        StructuredVisionObservation.model_validate(
            {"observation_id": "x", "source_image_id": "image"}
        )


@pytest.mark.parametrize(
    "unsafe",
    [
        "这是接触性皮炎。",
        "该面霜导致了过敏。",
        "产品存在质量缺陷。",
        "符合换货标准。",
        "建议涂抹药物治疗。",
    ],
)
def test_vision_validator_rejects_unsafe_conclusions(unsafe: str) -> None:
    with pytest.raises(UnsafeVisionObservation):
        VisionSafetyValidator().validate(observation(condition=unsafe))


def test_insufficient_observation_does_not_become_evidence() -> None:
    candidate = observation(image_id="image", message_id="message").model_copy(
        update={"visibility": Visibility.INSUFFICIENT, "sufficient": False}
    )
    result = VisionService(FakeVisionProvider(candidate)).analyze(
        case_id="C1",
        image_uri=demo_image_uri(),
        image_id="image",
        message_id="message",
        case_context="fixture",
        observed_at=datetime.now(UTC),
    )
    assert result is None


@pytest.mark.official_dataset
def test_s00001_official_reference_is_not_an_available_or_analyzed_asset(
    official_dataset: OfficialDataset,
) -> None:
    state = OfficialCaseFactory().build(official_dataset, "S00001")
    reference = next(item for item in state.evidence if item.key == "image_reference")
    assert isinstance(reference.value, dict)
    assert reference.value["reference_exists"] is True
    assert reference.value["asset_available"] is False
    assert reference.metadata["vision_analyzed"] is False
    assert not any(item.evidence_type.value == "AI_OBSERVATION" for item in state.evidence)
    assert next(
        gap for gap in state.evidence_gaps if gap.gap_type is GapType.VISUAL_EVIDENCE
    ).status.value == "OPEN"


@pytest.mark.official_dataset
def test_unavailable_official_asset_cannot_reach_vision_provider(
    official_dataset: OfficialDataset,
) -> None:
    message = next(
        item
        for item in official_dataset.messages
        if item.session_id == "S00001" and item.image_path
    )
    candidate = observation(
        image_id=Path(str(message.image_path)).name,
        message_id=message.message_id,
    )
    provider = FakeVisionProvider(candidate)
    checkpoints = InMemoryCheckpointStore()
    workflow = InvestigationWorkflow(checkpoint_store=checkpoints)
    service = CaseApplicationService(
        workflow, checkpoints, vision_service=VisionService(provider)
    )
    service.register_official_cases(official_dataset, ["S00001"])
    before = service.get_case("S00001")
    with pytest.raises(ValueError, match="not grounded"):
        service.analyze_image(
            "S00001",
            image_uri="unavailable://official-image-reference",
            image_id=candidate.source_image_id,
            message_id=candidate.source_message_id,
            expected_revision=before.revision,
        )
    assert provider.calls == 0


def test_demo_fixture_creates_strictly_provenanced_ai_observation() -> None:
    assert DEMO_ASSET_PATH.is_file()
    service = demo_service(observation())
    before = service.get_case("DEMO-PRODUCT-DAMAGE")
    after = service.analyze_demo_fixture(
        "DEMO-PRODUCT-DAMAGE",
        image_uri=demo_image_uri(),
        asset_id=DEMO_ASSET_ID,
        message_id=DEMO_MESSAGE_ID,
        expected_revision=before.revision,
    )
    visual = next(item for item in after.evidence if item.type == "AI_OBSERVATION")
    projected = after.visual_observations[0]
    assert visual.type != "VERIFIED_BUSINESS_FACT"
    assert projected["source"] == "DEMO_FIXTURE"
    assert projected["fixture"] is True
    assert projected["asset_id"] == DEMO_ASSET_ID
    assert projected["scenario"] == "PRODUCT_DAMAGE"
    assert next(gap for gap in after.gaps if gap.id == "VISUAL_EVIDENCE").status == "RESOLVED"
    assert after.human_checkpoint.state == "REQUIRED"
    assert after.safety_gate == "INVESTIGATION"
    assert after.attribution_status != "SUPPORTED"


def test_source_identity_mismatch_is_rejected() -> None:
    candidate = observation(image_id="WRONG_ASSET")
    service = demo_service(candidate)
    before = service.get_case("DEMO-PRODUCT-DAMAGE")
    with pytest.raises(VisionProviderError, match="source identity mismatch"):
        service.analyze_demo_fixture(
            "DEMO-PRODUCT-DAMAGE",
            image_uri=demo_image_uri(),
            asset_id=DEMO_ASSET_ID,
            message_id=DEMO_MESSAGE_ID,
            expected_revision=before.revision,
        )


def test_fake_and_qwen_provider_boundary() -> None:
    fake = FakeVisionProvider(observation())
    real = QwenVisionProvider(
        api_key="non-secret-test-placeholder",
        model="qwen3.7-plus",
        base_url="https://example.invalid/compatible-mode/v1",
    )
    assert fake.name == "fake-vision"
    assert real.name == "qwen"
    assert real.model == "qwen3.7-plus"


@pytest.mark.official_dataset
def test_s00154_missing_official_image_preserves_safety_boundary(
    official_dataset: OfficialDataset,
) -> None:
    state = OfficialCaseFactory().build(official_dataset, "S00154")
    checkpoints = InMemoryCheckpointStore()
    checkpoints.save(state)
    service = CaseApplicationService(
        InvestigationWorkflow(checkpoint_store=checkpoints), checkpoints
    )
    projected = service.get_case("S00154")
    reference = next(item for item in state.evidence if item.key == "image_reference")
    assert isinstance(reference.value, dict)
    assert reference.value["asset_available"] is False
    assert projected.visual_observations == []
    assert projected.safety_gate == "SAFETY"
    assert projected.human_checkpoint.state == "REQUIRED"
    assert projected.attribution_status != "SUPPORTED"


def test_local_knowledge_retrieval_has_provenance_and_missing_is_empty() -> None:
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve(
        "damaged product policy", knowledge_types={KnowledgeType.SERVICE_POLICY}
    )
    assert results and results[0].document_id == "DEMO-POLICY-DAMAGE-001"
    assert results[0].source == "DEMO_FIXTURE" and results[0].fixture is True
    assert retriever.retrieve("unfindable-zebra-quantum") == []


def test_ingredient_match_is_context_not_causality() -> None:
    matches = IngredientContextChecker().match(
        product_id="DEMO-CREAM",
        ingredients=["Water", "Fragrance"],
        sensitivity="fragrance",
        ingredient_source_id="DEMO-PRODUCT-001",
        sensitivity_source_id="DEMO-SENSITIVITY-001",
        fixture=True,
    )
    assert len(matches) == 1 and matches[0].ingredient == "Fragrance"
    assert "does not establish" in matches[0].uncertainty
    assert not hasattr(matches[0], "attribution")


@pytest.mark.official_dataset
def test_severity_outranks_emotion(official_dataset: OfficialDataset) -> None:
    factory = OfficialCaseFactory()
    severe = factory.build(official_dataset, "S00154")
    logistics = factory.build(official_dataset, "S00009")
    gates = SafetyGateService()
    assert gates.assess(severe, emotion="CALM").gate is SafetyGate.SAFETY
    assert gates.assess(logistics, emotion="ANGRY").gate is SafetyGate.INVESTIGATION


def test_safety_gate_normal_without_investigation_signals() -> None:
    state = InvestigationState(case_id="NORMAL", consumer_id="U", current_issue="产品怎么使用")
    assert SafetyGateService().assess(state, emotion="ANGRY").gate is SafetyGate.NORMAL


def test_rag_context_cannot_change_evidence_or_attribution() -> None:
    state = InvestigationState(case_id="C-RAG", consumer_id="U", current_issue="damage")
    before = assess_attribution(state, "P", []).decision
    retrieved = LocalKnowledgeRetriever().retrieve("damaged product policy")
    after = assess_attribution(state, "P", []).decision
    assert retrieved
    assert before is after is AttributionDecision.INSUFFICIENT_EVIDENCE
    assert state.evidence == []
