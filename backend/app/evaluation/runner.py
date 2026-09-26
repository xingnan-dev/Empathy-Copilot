from collections import Counter
from datetime import UTC, datetime

from backend.app.official_dataset.models import OfficialDataset

from .cases import build_benchmark_cases
from .metrics import aggregate
from .runners import BaselineRunner, ResoniqueRunner
from .schemas import CaseComparison, EvaluationCase, EvaluationReport, PricingProfile


class EvaluationHarness:
    def __init__(
        self,
        dataset: OfficialDataset,
        *,
        pricing: PricingProfile | None = None,
    ) -> None:
        self.dataset = dataset
        self.pricing = pricing

    def run(
        self,
        *,
        baseline: BaselineRunner | None = None,
        resonique: ResoniqueRunner | None = None,
        cases: list[EvaluationCase] | None = None,
        execution_mode: str = "DETERMINISTIC_PRE_OPTIMIZATION",
        benchmark_version: str = "phase9-preopt-v1",
    ) -> EvaluationReport:
        selected = cases or build_benchmark_cases(self.dataset)
        baseline = baseline or BaselineRunner(pricing=self.pricing)
        resonique = resonique or ResoniqueRunner(self.dataset, pricing=self.pricing)
        comparisons = [
            CaseComparison(
                case_id=case.case_id,
                source=case.source,
                scenario=case.scenario,
                baseline=baseline.run(case),
                resonique=resonique.run(case),
            )
            for case in selected
        ]
        baseline_pairs = [
            (case, result.baseline) for case, result in zip(selected, comparisons, strict=True)
        ]
        resonique_pairs = [
            (case, result.resonique) for case, result in zip(selected, comparisons, strict=True)
        ]
        baseline_metrics = aggregate(baseline_pairs, self.pricing)
        resonique_metrics = aggregate(resonique_pairs, self.pricing)
        return EvaluationReport(
            benchmark_version=benchmark_version,
            generated_at=datetime.now(UTC).isoformat(),
            execution_mode=execution_mode,
            provider=comparisons[0].baseline.instrumentation.provider,
            model=comparisons[0].baseline.instrumentation.model,
            case_count=len(selected),
            source_distribution=dict(Counter(item.source.value for item in selected)),
            scenario_distribution=dict(Counter(item.scenario.value for item in selected)),
            baseline_metrics=baseline_metrics,
            resonique_metrics=resonique_metrics,
            cases=comparisons,
            pricing_status="UNAVAILABLE" if self.pricing is None else "CONFIGURED",
            limitations=[
                "Deterministic benchmark measures architecture behavior, not language quality.",
                "Official image assets are unavailable; the multimodal fixture is synthetic.",
                "Baseline grounding is reported as absent rather than assumed incorrect.",
                "No optimization was performed before or after this benchmark.",
            ],
            headline_metrics={
                "baseline_unsupported_claim_rate": baseline_metrics.unsupported_claim_rate,
                "resonique_unsupported_claim_rate": resonique_metrics.unsupported_claim_rate,
                "baseline_gap_recall": baseline_metrics.critical_gap_recall,
                "resonique_gap_recall": resonique_metrics.critical_gap_recall,
                "baseline_safety_violation_rate": baseline_metrics.safety_violation_rate,
                "resonique_safety_violation_rate": resonique_metrics.safety_violation_rate,
            },
        )

    def attach_real_subset(
        self,
        report: EvaluationReport,
        *,
        cases: list[EvaluationCase],
        baseline: BaselineRunner,
        resonique: ResoniqueRunner,
    ) -> EvaluationReport:
        comparisons = [
            CaseComparison(
                case_id=case.case_id,
                source=case.source,
                scenario=case.scenario,
                baseline=baseline.run(case),
                resonique=resonique.run(case),
            )
            for case in cases
        ]
        return report.model_copy(
            update={
                "real_model_subset": comparisons,
                "real_baseline_metrics": aggregate(
                    [
                        (case, result.baseline)
                        for case, result in zip(cases, comparisons, strict=True)
                    ],
                    self.pricing,
                ),
                "real_resonique_metrics": aggregate(
                    [
                        (case, result.resonique)
                        for case, result in zip(cases, comparisons, strict=True)
                    ],
                    self.pricing,
                ),
            }
        )
