# GramSetu AI — ML Model Training & Temporal Backtest Audit

**Audit Date:** 2026-11-22  
**Audit Scope:** Statistical Price Forecasting, Temporal Holdout Validation, MLOps Pipelines  
**Audited Datasets:** `market_prices.csv` (43 rows), `market_arrivals.csv` (0 rows), `price_forecasts.csv` (0 rows)  
**Evaluator:** Principal MLOps Engineer & Statistical Forecasting Auditor  
**Verdict:** `TRAINING_REFUSED / INFERENCE_DISABLED / PRODUCTION_BLOCKED`

---

## 1. Executive Summary

DemandSync’s agricultural market price forecasting module (`gramsetu/pipeline.py` and `gramsetu/services/market.py`) is designed to predict future modal prices for key agricultural commodities (e.g., Potato, Tomato, Onion) across rural APMC mandis.

An exhaustive audit of the baseline data and training pipeline confirms:
1. **Mathematical Impossibility of Model Training on v2.2:** The entire market price panel in v2.2 consists of only **43 secondary observations across 2 calendar days** (2026-11-16 and 2026-11-17). The arrivals table contains **0 rows**.
2. **Correct Enforcement of Training Refusal Gates:** `gramsetu/pipeline.py` strictly refuses model training when observed series span is less than 730 days or daily coverage is less than 80%. When evaluated against v2.2, the pipeline outputs:
   `"BLOCKED_INSUFFICIENT_AUTHENTIC_HISTORICAL_DATA: span=2 days, required >= 730 days"`.
3. **Safe Inference Behavior:** The backend refuses unreviewed predictive pricing in production mode and disables active forecasting by default (`PHASE4_FORECASTING_ENABLED=False`), returning explicit `UNAVAILABLE_FEATURE_DISABLED` states with `null` predicted prices rather than hallucinated estimates.

---

## 2. Statistical Analysis of the v2.2 Market Panel

```
+-----------------------------------------------------------------------------+
| DATASET TIME SPAN VS MINIMUM MLOps REQUIREMENTS                            |
+-----------------------------------------------------------------------------+
|                                                                             |
|  [ Current v2.2 Baseline ]                                                  |
|  [2026-11-16] [2026-11-17]  (2 Calendar Days / 43 Observations)             |
|                                                                             |
|  [ Minimum Production Training Requirement ]                                |
|  |<--------------------------- 730 Calendar Days -------------------------->|
|  |--- Train (>=300 days) ---|--- Val (>=45 days) ---|--- Test (>=90 days) --|
|                                                                             |
+-----------------------------------------------------------------------------+
```

Attempting to train machine learning models (e.g., Ridge Regression, Gradient Boosted Trees, or Neural Networks) on 43 rows spanning 2 days violates fundamental statistical principles:
- **Degrees of Freedom Deficit:** The canonical feature vector requires 10 features (`lag_1`, `lag_7`, `lag_14`, `lag_28`, `rolling_mean_7`, `rolling_std_7`, day-of-week sine/cosine, day-of-year sine/cosine). With only 2 observed dates, lags 7, 14, and 28 cannot even be computed.
- **Complete Lack of Seasonality:** Agricultural commodities exhibit profound annual seasonal cycles driven by sowing, harvest, and monsoon seasons. A 2-day sample contains zero seasonal variance.
- **High Risk of Overfitting & Hallucination:** Any model trained on this data would memorize arbitrary noise, producing dangerously deceptive price advisories for FPO managers.

---

## 3. Verified Temporal Validation Contracts in `pipeline.py`

The repository's pipeline code enforces strict, leakage-free temporal walk-forward evaluation contracts:

1. **Expanding Window Temporal Split:**
   - Shuffle splits and random cross-validation are strictly forbidden to eliminate lookahead bias.
   - Evaluation requires three distinct temporal partitions:
     - **Training Split:** Minimum 300 calendar days
     - **Validation Split:** Minimum 45 calendar days
     - **Test Holdout Split:** Minimum 90 calendar days

2. **Baseline Superiority Benchmark:**
   - A trained statistical model is rejected unless it outperforms naive benchmarks on the validation split by at least 2%:
     $$\text{MAE}_{\text{model}} < 0.98 \times \min(\text{MAE}_{\text{Lag-1}}, \text{MAE}_{\text{Lag-7}})$$
   - The selected model must also beat the naive baseline on the unvisited test holdout split:
     $$\text{MAE}_{\text{test}} < \text{MAE}_{\text{baseline\_test}}$$

3. **Inert JSON Serialization:**
   - Pickling model weights (`pickle`, `joblib`) is strictly forbidden to prevent arbitrary code execution vulnerabilities.
   - Model parameters (intercept, feature coefficients, feature names, training metadata) are serialized exclusively as human-readable, schema-validated JSON.

---

## 4. Operational Gating Verification Results

| Pipeline Component | Configured Gate / Policy | Evaluated Outcome on v2.2 | Invariant Status |
| :--- | :--- | :--- | :--- |
| **Data Integrity Check** | 17 canonical fields present; valid decimal prices | Passed on 43 records | **VERIFIED** |
| **History Span Gate** | $\text{span} \ge 730 \text{ days}$ | Failed: $\text{span} = 2 \text{ days}$ | **CORRECTLY REFUSED** |
| **Coverage Ratio Gate** | $\text{coverage} \ge 80.0\%$ | Failed: $< 1.0\%$ | **CORRECTLY REFUSED** |
| **Model Training State** | No training executed without passing gates | 0 model artifacts generated | **SAFE & UNTRAINED** |
| **API Inference State** | `PHASE4_FORECASTING_ENABLED=False` | Returns `null` price, `UNAVAILABLE` | **SAFE & DISABLED** |
| **Production Mode Lock** | Refuses research models in production | Returns `403 REFUSED_UNVERIFIED` | **SECURE** |

---

## 5. Phase 5 Verdict

Model training and active price forecasting remain **strictly blocked** until at least 730 consecutive calendar days of primary, authenticated DMI/AGMARKNET price and arrival feeds are ingested and independently validated.
