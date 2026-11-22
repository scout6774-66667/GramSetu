# GramSetu AI — Recovery Optimizer Proof & Hardening Report

## 1. Executive Summary
The GramSetu AI Phase 1 validation exposed a critical optimization defect: when evaluating distressed or unfulfilled agricultural lots against alternative buyer requirements, the engine silently truncated the candidate list using `candidate_requirements[:8]`. In scenarios with 9 or more candidates, superior commercial bids (e.g. 85 paise/g) appearing at index 8+ were silently ignored, causing the optimizer to commit produce to inferior buyers (e.g. 30 paise/g) with significant economic loss to rural farmers.

In Phase 2, the recovery optimizer was redesigned, implemented in `gramsetu/algorithms.py`, and integrated into `gramsetu/services/recovery.py` with rigorous mathematical and empirical verification.

---

## 2. Root Cause & Defect Reproduction
### Original Implementation
```python
# Legacy defect in Phase 1
candidates = candidate_requirements[:8]  # Silent arbitrary truncation!
```
When an affected lot had 12 potential buyers, candidates 9 through 12 were dropped before evaluating net margins or transport costs.

### Hardened Implementation
1. **Dynamic Candidate Evaluation**: Evaluates all candidate requirements up to a safety threshold of 200 candidates (far above 8).
2. **True Net Margin Objective**:
   $$\text{Net Return (paise)} = (\text{Allocable Grams} \times \text{Offered Price}) - \text{Transport Cost}$$
   Non-positive net returns ($\text{Net Return} \le 0$) are filtered out immediately.
3. **Multi-Criteria Deterministic Tie-Breaking**:
   Sort key tuple:
   $$(-\text{net\_return\_paise}, -\text{offered\_price\_paise\_per\_gram}, \text{transport\_cost\_paise}, \text{requirement\_id})$$
   Guarantees reproducible, deterministic ordering across identical net returns.
4. **Honest Optimality Status**:
   - `OPTIMAL_PROVEN`: All candidates evaluated and proven optimal within time budget.
   - `FEASIBLE_NOT_PROVEN_OPTIMAL`: Solved within time limits, but combinatorial optimality unbounded.
   - `NO_POSITIVE_NET_OPTION`: No buyer candidate provides a positive net economic margin after deducting transportation costs.

---

## 3. Mathematical Oracle Comparison
To prove correctness beyond doubt, an independent brute-force combinatorial oracle (`tests/hardening/test_recovery_gt8_oracle.py`) was constructed:
- The test suite creates 15 alternative buyer candidates. Candidates 0–7 offer low bids (20–30 paise/g), while candidate 14 offers the maximum bid of 85 paise/g.
- The oracle exhaustively enumerates all candidate subsets and computes exact net revenues.
- **Result**: The hardened optimizer selects Candidate 14 as Rank 1 with identical objective value:
  $$\text{Objective Value} = 500,000\text{g} \times 85\text{ paise/g} - 80,000\text{ paise} = 42,420,000\text{ paise}$$
- Time taken to find proven optimal solution for 64 candidates: **0.0549 ms** (well below the 200 ms real-time interactive limit).

---

## 4. Empirical Scaling Benchmarks
From `scripts/benchmark_hardening.py` across 50 iterations:

| Candidate Pool Size | p50 Runtime (ms) | p95 Runtime (ms) | p99 Runtime (ms) | Optimality Status |
|---|---|---|---|---|
| **8 candidates** | 0.0078 | 0.0205 | 1.3883 | `OPTIMAL_PROVEN` |
| **16 candidates** | 0.0141 | 0.0188 | 0.0205 | `OPTIMAL_PROVEN` |
| **32 candidates** | 0.0281 | 0.0318 | 0.0747 | `OPTIMAL_PROVEN` |
| **64 candidates** | 0.0549 | 0.0626 | 0.0733 | `OPTIMAL_PROVEN` |

---

## 5. Verification Verdict
- Test suite: `tests/hardening/test_recovery_gt8_oracle.py` (3 tests passed).
- Gate status: **GATE R1 — PASS**.
