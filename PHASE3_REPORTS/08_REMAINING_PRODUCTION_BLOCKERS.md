# GramSetu AI — Remaining Production Blockers & Operational Gaps
**Milestone:** Phase 3 Dataset-to-Backend Integration  
**Status:** `NOT READY FOR REAL-WORLD AGRICULTURAL PROCUREMENT`  
**Classification:** Development & Sandbox Evaluation Baseline  

---

## 1. Executive Disclosure

While Phase 3 successfully integrates the 44 normalized CSV datasets and validates unit contract invariants across the backend, **GramSetu AI is strictly not certified for live farm-gate procurement or physical logistics dispatch**.

The system readiness endpoint (`GET /api/v1/system/readiness`) explicitly returns:
```json
{
  "production_readiness": "NOT_READY_CRITICAL_OPERATIONAL_GAPS",
  "data_authenticity_notice": "CRITICAL NOTICE: SYSTEM DATA REPRESENTS SYNTHETIC / SIMULATED RECORDS FOR ARCHITECTURAL EVALUATION. NOT CERTIFIED FOR REAL-WORLD AGRICULTURAL PROCUREMENT."
}
```

---

## 2. Enumeration of Critical Operational Blockers

### Blocker 1: Missing Mandi Feeds (`market_arrivals` is Header-Only)
- **Current State**: The dataset contains 0 rows for `market_arrivals`.
- **Backend Representation**: Explicitly set to `UNAVAILABLE_AWAITING_SOURCE` with row count 0.
- **Operational Impact**: FPO price discovery and dynamic floor calculations cannot function without verified daily Agmarknet mandi feeds.

### Blocker 2: Untrained Price Prediction Model (`price_forecasts` is Header-Only)
- **Current State**: The dataset contains 0 rows for `price_forecasts`.
- **Backend Representation**: Explicitly set to `UNAVAILABLE_UNTRAINED_MODEL` with row count 0. Zero fake ML scripts or random heuristic weights were created.
- **Operational Impact**: Farmers and FPOs cannot rely on AI crop pricing without an audited time-series model trained on real historical APMC market transactions.

### Blocker 3: Administrative Location Centroid Proxies
- **Current State**: All 79 records in `locations.csv` are district or block administrative centroids.
- **Operational Impact**: Zero actual farm coordinates or warehouse GPS locations are verified (`site_coordinate_verified: False`). Routing vehicles to administrative centroids will dispatch trucks to district collectorates rather than farm gates or collection centers.

### Blocker 4: Synthetic Non-Routable Road Edges
- **Current State**: All 620 records in `road_edges.csv` are straight-line synthetic topology links (`simulation_flag: True`).
- **Operational Impact**: Real physical roads possess terrain barriers, weight-restricted bridges, and seasonal monsoon blockages. Using synthetic road edges for vehicle turn-by-turn navigation or dispatch will cause transit failure.

### Blocker 5: Unverified Financial Settlements
- **Current State**: The 32 records in `payable_ledger` represent simulated book settlements.
- **Operational Impact**: UTR numbers (`verified_paid_paise`) are synthetic strings. GramSetu AI does not currently have a direct bank clearing gateway (such as NPCI / NACH / UPI or direct bank API integration). Live payments must not be authorized based on simulated ledger receipts.

---

## 3. Production Deployment Prerequisites

Before deploying GramSetu AI to an active Farmer Producer Organization:
1. Connect verified API feeds for Agmarknet mandi market arrivals.
2. Train, validate, and register an audited agricultural price forecasting model.
3. Replace administrative centroid proxies with verified GPS coordinates of physical farm gates and FPO collection centers.
4. Integrate a real routable GIS road network (e.g., OpenStreetMap / PMGSY rural road telemetry).
5. Implement a two-way banking / payment gateway integration with cryptographic webhook validation.
