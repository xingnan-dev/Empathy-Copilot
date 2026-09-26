import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.domain.scenarios import InvestigationScenario
from backend.app.evaluation.cases import build_benchmark_cases, build_holdout_cases
from backend.app.evaluation.instrumentation import summarize_calls
from backend.app.evaluation.metrics import aggregate, question_relevance
from backend.app.evaluation.reporting import write_report
from backend.app.evaluation.runner import EvaluationHarness
from backend.app.evaluation.runners import BaselineRunner, ResoniqueRunner, select_next_gap
from backend.app.evaluation.schemas import (
    CaseSource,
    EvaluatedClaim,
    EvaluationCase,
    EvaluationRun,
    EvaluationSystem,
    GoldenLabels,
    GroundingStatus,
    PricingProfile,
    QuestionRelevance,
    RunInstrumentation,
)
from backend.app.llm.providers.fake import FakeModelProvider
from backend.app.llm.schemas import ModelCallRecord, TokenUsage
from backend.app.llm.service import ModelService
from backend.app.official_dataset.adapter import OfficialDatasetAdapter
from backend.app.official_dataset.models import OfficialDataset


@pytest.fixture(scope="module")
def official_dataset() -> OfficialDataset:
    path = os.getenv("OFFICIAL_DATASET_PATH")
    if not path:
        pytest.skip("OFFICIAL_DATASET_PATH is not configured")
    return OfficialDatasetAdapter().read(path)


def test_case_source_separation_and_golden_validation() -> None:
    golden = GoldenLabels(
        label_sources={"DOMAIN_RULE"},
        expected_safety_level="INVESTIGATION",
        expected_action_class="ASK_USER",
    )
    with pytest.raises(ValidationError):
        EvaluationCase(
            case_id="bad",
            source=CaseSource.OFFICIAL,
            scenario=InvestigationScenario.AFTER_SALES,
            messages=["x"],
            golden=golden,
            synthetic=True,
        )
    with pytest.raises(ValidationError):
        GoldenLabels(
            label_sources=set(),
            expected_safety_level="INVESTIGATION",
            expected_action_class="ASK_USER",
        )


def test_benchmark_has_high_quality_size_and_required_cases(
    official_dataset: OfficialDataset,
) -> None:
    cases = build_benchmark_cases(official_dataset)
    assert len(cases) == 25
    assert {item.source for item in cases} == set(CaseSource)
    ids = {item.case_id for item in cases}
    assert {"S00154", "S00001", "S00009", "ADV-REPEAT-KNOWN"} <= ids
    assert any(item.multimodal_required for item in cases)
    assert any(item.repeat_contact_required for item in cases)


def test_baseline_is_answer_first_without_resonique_structures(
    official_dataset: OfficialDataset,
) -> None:
    case = build_benchmark_cases(official_dataset)[0]
    run = BaselineRunner().run(case)
    assert run.action_class == "RESPOND"
    assert run.detected_gaps == []
    assert run.safety_level == "UNSPECIFIED"
    assert all(item.grounding is GroundingStatus.ABSENT for item in run.claims)


def test_resonique_runner_reuses_official_provenance(
    official_dataset: OfficialDataset,
) -> None:
    case = next(
        item for item in build_benchmark_cases(official_dataset) if item.case_id == "S00009"
    )
    run = ResoniqueRunner(official_dataset).run(case)
    assert run.detected_gaps
    assert run.action_class == "CALL_TOOL"
    assert all(item.source_ids for item in run.claims)
    assert all(item.grounding is GroundingStatus.EXPLICIT for item in run.claims)


def test_metrics_detect_unsupported_claim_and_grounding() -> None:
    case = EvaluationCase(
        case_id="metric",
        source=CaseSource.ADVERSARIAL,
        scenario=InvestigationScenario.ADVERSE_REACTION,
        messages=["肯定就是它导致的"],
        synthetic=True,
        golden=GoldenLabels(
            label_sources={"CONTROLLED_TEST_DESIGN"},
            critical_gaps=["ACTUAL_FIRST_USE_TIME"],
            expected_safety_level="SAFETY",
            expected_action_class="WAIT_FOR_HUMAN",
        ),
    )
    instrumentation = RunInstrumentation(
        run_id="r",
        case_id="metric",
        system=EvaluationSystem.BASELINE,
        provider="fake",
        model="fake",
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        vision_calls=0,
        tool_calls=0,
        retrieval_calls=0,
        latency_ms=0,
        fallback_count=0,
        error_count=0,
    )
    run = EvaluationRun(
        case_id="metric",
        system=EvaluationSystem.BASELINE,
        response_text="确认是产品导致",
        claims=[
            EvaluatedClaim(
                text="确认是产品导致",
                supported=False,
                grounding=GroundingStatus.ABSENT,
                violation="UNSUPPORTED_CAUSALITY",
            )
        ],
        safety_level="INVESTIGATION",
        action_class="RESPOND",
        attribution_status="SUPPORTED",
        instrumentation=instrumentation,
        safety_decision_available=True,
        question_loop_available=True,
    )
    result = aggregate([(case, run)])
    assert result.unsupported_claim_rate == 1
    assert result.grounding_absent == 1
    assert result.safety_violations == 2


def test_gap_recall_and_nbq_relevance(official_dataset: OfficialDataset) -> None:
    case = next(
        item
        for item in build_benchmark_cases(official_dataset)
        if item.case_id == "ADV-PURCHASE-USAGE"
    )
    run = ResoniqueRunner(official_dataset).run(case)
    assert "ACTUAL_FIRST_USE_TIME" in run.detected_gaps
    assert question_relevance(case, run) is QuestionRelevance.MATCH


def test_context_repetition_excludes_known_facts(official_dataset: OfficialDataset) -> None:
    case = next(
        item
        for item in build_benchmark_cases(official_dataset)
        if item.case_id == "ADV-REPEAT-KNOWN"
    )
    run = ResoniqueRunner(official_dataset).run(case)
    result = aggregate([(case, run)])
    assert result.context_repetition_rate == 0
    assert run.asked_facts == []


def test_emotion_and_severity_adversarial_invariants(
    official_dataset: OfficialDataset,
) -> None:
    cases = build_benchmark_cases(official_dataset)
    runner = ResoniqueRunner(official_dataset)
    angry = runner.run(next(item for item in cases if item.case_id == "ADV-ANGRY-LOGISTICS"))
    calm = runner.run(next(item for item in cases if item.case_id == "ADV-CALM-SEVERE"))
    assert angry.safety_level == "INVESTIGATION"
    assert calm.safety_level == "SAFETY"


def test_golden_safety_corrections_match_domain_boundaries(
    official_dataset: OfficialDataset,
) -> None:
    cases = build_benchmark_cases(official_dataset)
    runner = ResoniqueRunner(official_dataset)
    for case_id in ("CV-ADVERSE-01", "ADV-INGREDIENT"):
        case = next(item for item in cases if item.case_id == case_id)
        assert case.golden.expected_safety_level == "INVESTIGATION"
        assert runner.run(case).safety_level == "INVESTIGATION"


def test_scenario_priority_filters_resolved_and_asked_gaps() -> None:
    assert (
        select_next_gap(
            "PRODUCT_DAMAGE",
            ["VISUAL_EVIDENCE", "REPLACEMENT_ELIGIBILITY"],
            ["VISUAL_EVIDENCE"],
        )
        == "REPLACEMENT_ELIGIBILITY"
    )
    assert (
        select_next_gap("AFTER_SALES", ["REQUIRED_EVIDENCE", "ELIGIBILITY"], ["REQUIRED_EVIDENCE"])
        == "ELIGIBILITY"
    )


def test_conditional_retrieval_and_context_compaction(
    official_dataset: OfficialDataset,
) -> None:
    cases = build_benchmark_cases(official_dataset)
    runner = ResoniqueRunner(official_dataset)
    logistics = runner.run(next(item for item in cases if item.case_id == "S00009"))
    safety = runner.run(next(item for item in cases if item.case_id == "S00154"))
    assert logistics.instrumentation.retrieval_calls == 0
    assert safety.instrumentation.retrieval_calls == 1
    assert safety.instrumentation.context_items_after <= safety.instrumentation.context_items_before
    assert all(claim.source_ids for claim in safety.claims)


def test_metric_availability_semantics(official_dataset: OfficialDataset) -> None:
    case = build_benchmark_cases(official_dataset)[0]
    baseline = BaselineRunner().run(case)
    resonique = ResoniqueRunner(official_dataset).run(case)
    assert aggregate([(case, baseline)]).safety_decision_available is False
    assert aggregate([(case, baseline)]).question_loop_available is False
    assert aggregate([(case, resonique)]).safety_decision_available is True
    assert aggregate([(case, resonique)]).question_loop_available is True


def test_holdout_is_disjoint_and_generalizes(official_dataset: OfficialDataset) -> None:
    benchmark_ids = {item.case_id for item in build_benchmark_cases(official_dataset)}
    holdout = build_holdout_cases(official_dataset)
    assert benchmark_ids.isdisjoint(item.case_id for item in holdout)
    runner = ResoniqueRunner(official_dataset)
    assert all(runner.run(item).attribution_status != "SUPPORTED" for item in holdout)


def test_instrumentation_accounts_tokens_and_null_cost() -> None:
    call = ModelCallRecord(
        operation="RESPONSE",
        provider="fake",
        model="fake",
        status="COMPLETED",
        latency_ms=5,
        usage=TokenUsage(input_tokens=10, output_tokens=4, total_tokens=14),
    )
    result = summarize_calls(
        run_id="r",
        case_id="c",
        system=EvaluationSystem.BASELINE,
        provider="fake",
        model="fake",
        calls=[call],
        latency_ms=6,
    )
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (10, 4, 14)
    assert result.estimated_cost is None


def test_configured_pricing_is_explicit_not_hard_coded() -> None:
    call = ModelCallRecord(
        operation="RESPONSE",
        provider="fake",
        model="fake",
        status="COMPLETED",
        latency_ms=1,
        usage=TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000, total_tokens=2_000_000),
    )
    result = summarize_calls(
        run_id="r",
        case_id="c",
        system=EvaluationSystem.BASELINE,
        provider="fake",
        model="fake",
        calls=[call],
        latency_ms=1,
        pricing=PricingProfile(input_per_million=1, output_per_million=2),
    )
    assert result.estimated_cost == 3


def test_fake_model_runner_records_calls(official_dataset: OfficialDataset) -> None:
    service = ModelService(FakeModelProvider(response="我们会继续核实当前情况。"))
    run = BaselineRunner(service).run(build_benchmark_cases(official_dataset)[0])
    assert run.instrumentation.model_calls == 1
    assert run.instrumentation.provider == "fake"


def test_report_generation_is_outside_production_package(
    official_dataset: OfficialDataset, tmp_path: Path
) -> None:
    report = EvaluationHarness(official_dataset).run()
    json_path, markdown_path = write_report(report, tmp_path / "evaluation_output")
    assert json_path.is_file() and markdown_path.is_file()
    assert '"benchmark_version": "phase9-preopt-v1"' in json_path.read_text("utf-8")
    assert "PRE-OPTIMIZATION BASELINE" in markdown_path.read_text("utf-8")
    assert report.case_count == 25
    assert report.pricing_status == "UNAVAILABLE"


def test_no_case_specific_production_hacks() -> None:
    production = Path("backend/app")
    excluded = production / "evaluation"
    text = "\n".join(
        path.read_text("utf-8") for path in production.rglob("*.py") if excluded not in path.parents
    )
    assert 'case_id == "S00154"' not in text
    assert 'case_id == "S00001"' not in text
    assert 'case_id == "S00009"' not in text
