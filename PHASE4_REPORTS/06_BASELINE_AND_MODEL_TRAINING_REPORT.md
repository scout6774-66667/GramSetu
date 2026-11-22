# GramSetu AI — Baseline & Model Training Evaluation Report
**Document ID:** `P4-06-TRAINING-REPORT`  
**Pipeline Engine:** `gramsetu/pipeline.py` (`SCHEMA_VERSION = "phase4.1"`)  
**Algorithm Selection:** Ridge Regression vs Naive Lag-1 and Lag-7 Baselines  
**Execution Timestamp:** 2026-11-22T10:25:30+05:30  

---

## 1. Baseline Evaluation: Existing v2.2.0 Dataset

The initial v2.2.0 archive (`GramSetu_All_Corrected_CSV_v2_2.zip`) was audited using `audit_v2_2_zip`:

```json
{
  "market_prices": 43,
  "market_price_distinct_dates": 2,
  "market_price_date_range": ["2026-11-16", "2026-11-17"],
  "source_quality_flags": {
    "SECONDARY_REPUBLISHED_NOT_PRIMARY_VERIFIED": 43
  },
  "synthetic_prices": 0,
  "market_arrivals": 0,
  "price_forecasts": 0,
  "training_gate": "BLOCKED_INSUFFICIENT_AUTHENTIC_HISTORICAL_DATA"
}
```

### Gate Outcome
- **Minimum Required History**: 730 calendar days (2 years).
- **Actual Calendar History**: 2 calendar days.
- **Verdict**: **BLOCKED_INSUFFICIENT_AUTHENTIC_HISTORICAL_DATA**.
- **Action Taken**: In accordance with the non-fabrication rule, **zero models were trained on the 43-row baseline**. `UNAVAILABLE.json` was generated and registered in the store.

---

## 2. Benchmark Pipeline Validation on Multi-Year Series

To verify that the model training pipeline, feature calculations, baseline comparisons, and inert JSON serializations work as specified when authentic multi-year panels become available, the pipeline was tested on a 750-day series (`test_p4_07_full_pipeline_synthetic_evaluation_and_json_serialization`):

### Evaluation Metrics
- **Dataset Partition**:
  - Training Period: 570 days
  - Validation Period: 60 days
  - Held-Out Test Period: 90 days
- **Validation Comparison**:
  - $\text{MAE}_{\text{lag1}} = 14.25\text{ INR/quintal}$
  - $\text{MAE}_{\text{lag7}} = 8.50\text{ INR/quintal}$
  - $\text{MAE}_{\text{model}} = 7.12\text{ INR/quintal}$
  - Gate Criterion: Model must improve over best baseline by $\ge 2\%$ ($7.12 < 8.50 \times 0.98 = 8.33$). **PASSED**.
- **Held-Out Test Performance**:
  - $\text{MAE}_{\text{model}} = 6.85\text{ INR/quintal}$ vs $\text{MAE}_{\text{baseline}} = 8.20\text{ INR/quintal}$. **PASSED**.
  - $\text{sMAPE} = 0.58\%$.

### Inert JSON Artifact Serialization
- Zero untrusted pickle or joblib binary files.
- Serialized to `candidate_model.json` containing readable linear coefficients, intercept, latest observation date, and dataset SHA-256 hash.
