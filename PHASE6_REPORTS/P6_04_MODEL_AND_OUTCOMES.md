# GramSetu AI — ML Model Training, Evaluation & Outcome Tracking

**Document ID:** P6_04_MODEL_AND_OUTCOMES.md  
**Audit Phase:** Phase 6 Workstream P6.4  
**Verdict:** `TRAINING_REFUSED / INFERENCE_DISABLED`

---

## 1. MLOps Training Gate Enforcement

Under `gramsetu/pipeline.py` (lines 216–260), model training on agricultural time-series data requires:
1. **Minimum Historical Span:** $\ge 730$ consecutive calendar days per series.
2. **Minimum Coverage Ratio:** $\ge 80.0\%$ non-null observed days.
3. **Temporal Partitioning:** Minimum 300 days training, 45 days validation, 90 days held-out test split.
4. **Baseline Superiority:** Candidate regression models (e.g. Ridge Regression) must outperform both Lag-1 and Lag-7 naive baselines by at least 2% on validation:
   $$\text{MAE}_{\text{model}} < 0.98 \times \min(\text{MAE}_{\text{Lag-1}}, \text{MAE}_{\text{Lag-7}})$$
   and generalize to the held-out test partition.

### Evaluation Outcome on Baseline:
- Baseline market price series spans exactly 2 days (2026-11-16 and 2026-11-17).
- Training gate triggers refusal: `BLOCKED_INSUFFICIENT_AUTHENTIC_HISTORICAL_DATA`.
- Zero model weight artifacts are exported.
- Active forecasting endpoint `/api/v1/market/forecasts` remains fail-closed and returns explicit `UNAVAILABLE_FEATURE_DISABLED`.
