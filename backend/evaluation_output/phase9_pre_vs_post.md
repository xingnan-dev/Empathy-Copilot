# Phase 9 PRE vs POST

- Same 25 cases: yes
- Gap recall: 0.975 → 1.000
- NBQ: {'MATCH': 10, 'PARTIAL': 1, 'MISMATCH': 14, 'NOT_APPLICABLE': 0} → {'MATCH': 21, 'PARTIAL': 0, 'MISMATCH': 0, 'NOT_APPLICABLE': 4}
- Safety violations: 2 → 0
- Retrieval calls: 25 → 17
- Real Resonique tokens: 7556 → 5878 (22.2% reduction)
- Real Resonique latency: 79919 ms → 67914 ms (15.0% reduction)
- Unsupported claims: 0/147 → 0/147
- Quality regressions: none detected
