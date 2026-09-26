import json
from pathlib import Path

from .schemas import EvaluationReport


def write_report(
    report: EvaluationReport, output_dir: Path, *, stem: str = "evaluation"
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}_report.json"
    markdown_path = output_dir / f"{stem}_summary.md"
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    b, r = report.baseline_metrics, report.resonique_metrics
    real = "Not run"
    if report.real_baseline_metrics and report.real_resonique_metrics:
        real = (
            f"{len(report.real_model_subset)} cases; "
            f"baseline tokens {report.real_baseline_metrics.total_tokens}; "
            f"Resonique tokens {report.real_resonique_metrics.total_tokens}"
        )
    unsupported_row = (
        f"| Unsupported claim rate | {b.unsupported_claim_rate:.3f} | "
        f"{r.unsupported_claim_rate:.3f} |"
    )
    gap_row = f"| Critical gap recall | {b.critical_gap_recall:.3f} | {r.critical_gap_recall:.3f} |"
    safety_row = (
        f"| Safety violation rate | {b.safety_violation_rate:.3f} | {r.safety_violation_rate:.3f} |"
    )
    repetition_row = (
        f"| Context repetition rate | {b.context_repetition_rate:.3f} | "
        f"{r.context_repetition_rate:.3f} |"
    )
    markdown_path.write_text(
        "\n".join(
            [
                "# Phase 9 Pre-optimization Evaluation Summary",
                "",
                f"- Benchmark: `{report.benchmark_version}`",
                f"- Generated: `{report.generated_at}`",
                f"- Cases: {report.case_count}",
                f"- Sources: {report.source_distribution}",
                f"- Scenarios: {report.scenario_distribution}",
                f"- Pricing: {report.pricing_status}; estimated cost remains null when unavailable",
                f"- Real model subset: {real}",
                "",
                "## Headline metrics",
                "",
                "| Metric | Answer-first baseline | Resonique |",
                "|---|---:|---:|",
                unsupported_row,
                gap_row,
                safety_row,
                f"| Explicit grounding | {b.grounding_explicit} | {r.grounding_explicit} |",
                repetition_row,
                f"| Model calls | {b.model_calls} | {r.model_calls} |",
                f"| Total tokens | {b.total_tokens} | {r.total_tokens} |",
                f"| Latency (ms) | {b.latency_ms} | {r.latency_ms} |",
                "",
                "## Methodology",
                "",
                "The deterministic benchmark uses independent golden labels.",
                "Baseline grounding remains absent when structured provenance is unavailable.",
                "Real-model results are reported separately.",
                "",
                "## Limitations",
                "",
                *[f"- {item}" for item in report.limitations],
                "",
                "No optimization was performed. This is the raw PRE-OPTIMIZATION BASELINE.",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path
