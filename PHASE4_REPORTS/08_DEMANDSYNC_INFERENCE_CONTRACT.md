# GramSetu AI — DemandSync Inference Contract & API Specification
**Document ID:** `P4-08-DEMANDSYNC-CONTRACT`  
**Endpoint:** `GET /api/v1/market/forecasts`  
**Service:** `gramsetu/services/market.py`  
**Schema Model:** `MarketForecastResponse` in `gramsetu/schemas.py`  

---

## 1. Request Contract

```http
GET /api/v1/market/forecasts?market_id=MKT_000001&commodity_id=COM_POTATO&variety=Jyoti&grade=A&target_date=2026-11-18 HTTP/1.1
Host: localhost:8000
Authorization: Bearer <valid_jwt_token>
```

### Parameters
- `market_id` (string, required): Canonical GramSetu market identifier (e.g. `MKT_000001`).
- `commodity_id` (string, required): Canonical commodity identifier (e.g. `COM_POTATO`).
- `variety` (string, optional, default: `"NOT_REPORTED"`): Crop variety.
- `grade` (string, optional, default: `"NOT_REPORTED"`): Quality grade.
- `target_date` (ISO date, optional): Prediction target day (strictly next-day forecasting).

---

## 2. Response Contract

```json
{
  "status": "UNAVAILABLE_FEATURE_DISABLED",
  "market_id": "MKT_000001",
  "commodity_id": "COM_POTATO",
  "variety": "Jyoti",
  "grade": "A",
  "forecast_target_date": "2026-11-18",
  "forecast_issue_timestamp_utc": "2026-11-22T10:24:00Z",
  "price_unit": "INR/quintal",
  "predicted_modal_price_inr_quintal": null,
  "model_version": null,
  "training_dataset_sha256": null,
  "source_review_tier": null,
  "feature_availability": {
    "lag_1": "UNAVAILABLE",
    "lag_7": "UNAVAILABLE",
    "lag_14": "UNAVAILABLE",
    "lag_28": "UNAVAILABLE",
    "market_arrivals": "UNAVAILABLE_AWAITING_SOURCE",
    "historical_weather": "UNAVAILABLE_AWAITING_SOURCE"
  },
  "planning_disclaimer": "PLANNING DISCLOSURE: Wholesale mandi forecasts are indicative estimates only and must NEVER be treated as binding buyer procurement offers or settlement rates.",
  "operational_notice": "Phase 4 Market Price Forecasting is DISABLED by system configuration (PHASE4_FORECASTING_ENABLED=False). Set PHASE4_FORECASTING_ENABLED=True to activate."
}
```

---

## 3. Architectural & Commercial Invariants

1. **Explicit Distinguishable States**:
   - `predicted_modal_price_inr_quintal` is `null` when a forecast is unavailable. It is NEVER represented as `0` or `0.0`.
   - Distinct statuses distinguish feature gate disabled (`UNAVAILABLE_FEATURE_DISABLED`), missing trained model (`UNAVAILABLE_NO_TRAINED_MODEL`), and production refusal (`REFUSED_UNVERIFIED_PROVENANCE`).
2. **Non-Binding Price Guarantee**:
   - A wholesale market forecast is purely an advisory planning input.
   - It NEVER alters buyer commitment prices, offer reservations, or farmer settlement ledger entries.
