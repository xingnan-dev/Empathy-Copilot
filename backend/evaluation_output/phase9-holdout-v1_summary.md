# Phase 9 Pre-optimization Evaluation Summary

- Benchmark: `phase9-holdout-v1`
- Generated: `2026-09-26T13:26:45.789070+00:00`
- Cases: 4
- Sources: {'OFFICIAL': 4}
- Scenarios: {'ADVERSE_REACTION': 1, 'PRODUCT_DAMAGE': 1, 'LOGISTICS_EXCEPTION': 1, 'AFTER_SALES': 1}
- Pricing: UNAVAILABLE; estimated cost remains null when unavailable
- Real model subset: Not run

## Headline metrics

| Metric | Answer-first baseline | Resonique |
|---|---:|---:|
| Unsupported claim rate | 0.000 | 0.000 |
| Critical gap recall | 0.000 | 1.000 |
| Safety violation rate | 0.000 | 0.000 |
| Explicit grounding | 0 | 44 |
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