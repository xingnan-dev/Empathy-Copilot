# Phase 9 Pre-optimization Evaluation Summary

- Benchmark: `phase9-preopt-v1`
- Generated: `2026-09-26T13:11:01.904310+00:00`
- Cases: 25
- Sources: {'OFFICIAL': 12, 'CONTROLLED_VARIANT': 6, 'ADVERSARIAL': 7}
- Scenarios: {'ADVERSE_REACTION': 9, 'PRODUCT_DAMAGE': 5, 'LOGISTICS_EXCEPTION': 5, 'AFTER_SALES': 6}
- Pricing: UNAVAILABLE; estimated cost remains null when unavailable
- Real model subset: 3 cases; baseline tokens 4044; Resonique tokens 7556

## Headline metrics

| Metric | Answer-first baseline | Resonique |
|---|---:|---:|
| Unsupported claim rate | 0.000 | 0.000 |
| Critical gap recall | 0.000 | 0.975 |
| Safety violation rate | 0.000 | 0.080 |
| Explicit grounding | 0 | 134 |
| Context repetition rate | 0.000 | 0.000 |
| Model calls | 0 | 0 |
| Total tokens | 0 | 0 |
| Latency (ms) | 0 | 0 |

## Methodology

The deterministic benchmark uses independent golden labels.
Baseline grounding remains absent when structured provenance is unavailable.
Real-model results are reported separately.

## Limitations

- Deterministic benchmark measures architecture behavior, not language quality.
- Official image assets are unavailable; the multimodal fixture is synthetic.
- Baseline grounding is reported as absent rather than assumed incorrect.
- No optimization was performed before or after this benchmark.

No optimization was performed. This is the raw PRE-OPTIMIZATION BASELINE.