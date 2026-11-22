# GramSetu AI — Missing Data Sources & Production Blockers
**Document ID:** `P4-10-PRODUCTION-BLOCKERS`  
**Verdict:** **PRODUCTION_BLOCKED**  
**Readiness State:** `NOT_READY_CRITICAL_OPERATIONAL_GAPS`  

---

## 1. Executive Disclosure

In accordance with Phase 4 governance rules, **training or evaluating a statistical model does not improve overall production readiness**. GramSetu AI remains strictly locked against real-world agricultural deployment.

The system readiness endpoint (`GET /api/v1/system/readiness`) continues to report:
```json
{
  "production_readiness": "NOT_READY_CRITICAL_OPERATIONAL_GAPS",
  "readiness_checks": {
    "verified_farm_gps_connected": false,
    "navigable_real_roads_verified": false,
    "two_way_bank_settlement_verified": false,
    "live_market_arrivals_verified": false,
    "certified_price_forecast_model_active": false
  }
}
```

---

## 2. Inventory of Critical Operational Blockers

### Blocker 1: Historical Agmarknet Mandi Coverage Deficit
- **Deficit**: Current v2.2.0 dataset has only 43 rows spanning 2 calendar days (`2026-11-16` and `2026-11-17`).
- **Required**: Minimum 730 calendar days (2 full annual harvest cycles) with $\ge 80\%$ daily reporting coverage per series.
- **Operational Impact**: Real price trends, seasonal festival surges, and monsoon supply shocks cannot be modeled without multi-year panel data.

### Blocker 2: Missing Real-Time Mandi Inward Arrivals Feed
- **Deficit**: `market_arrivals.csv` contains 0 rows.
- **Required**: Daily truck volume, lot arrivals, and quantity inward feeds from APMC electronic gates.
- **Operational Impact**: Supply-demand volume elasticity cannot be estimated; arrivals must never be imputed from price alone.

### Blocker 3: Missing Historical Weather Observations & IMD Feeds
- **Deficit**: IMD gridded rainfall, temperature, and relative humidity station feeds are currently disconnected.
- **Required**: Block-level daily meteorological observations aligned with farm sowing and harvest windows.
- **Operational Impact**: Perishability degradation during transit cannot incorporate real-time temperature stress.

### Blocker 4: Administrative Centroid Proxies
- **Deficit**: All 79 records in `locations.csv` remain administrative district centroids rather than physical farm-gate GPS coordinates.
- **Operational Impact**: Dispatching vehicles to district centroid coordinates will route trucks to administrative collectorates rather than rural fields.

### Blocker 5: Synthetic Non-Routable Road Graph
- **Deficit**: All 620 road edges in `road_edges.csv` are straight-line synthetic topology links.
- **Operational Impact**: Cannot be used for turn-by-turn navigation or heavy vehicle road suitability checks.

### Blocker 6: Two-Way Banking Gateway Absence
- **Deficit**: UTR numbers in `payable_ledger` represent simulated receipts.
- **Operational Impact**: Zero direct automated clearing house (NACH / UPI / RTGS) bank integration. Live money cannot be disbursed based on simulated ledger entries.
