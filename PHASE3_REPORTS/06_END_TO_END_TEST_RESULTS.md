# GramSetu AI — End-to-End Regression & Acceptance Test Results
**Milestone:** Phase 3 Implementation & Unit Contract Hardening  
**Test Suite:** `tests/` and `VALIDATION_TESTS/`  
**Total Tests Executed:** 158  
**Pass Rate:** 100.0% (158 passed, 0 failed, 0 skipped, 0 xfailed)  
**Execution Duration:** ~8.64s  
**Platform:** Windows 11 Enterprise (win32), Python 3.11.9, pytest 9.1.1  

---

## 1. Summary of Test Results

| Test Module | Test Focus | Tests | Status |
| :--- | :--- | :---: | :---: |
| `tests/test_phase3_contracts.py` | Phase 3 Dataset Contracts & Acceptance Criteria | 15 | **PASSED** |
| `tests/test_final_acceptance.py` | Full Operational Lifecycle (F0–F13) | 26 | **PASSED** |
| `tests/test_commitguard.py` | Procurement & Commitment Logic (F4) | 12 | **PASSED** |
| `tests/test_demandsync.py` | Supply & Demand Synchronization (F2) | 11 | **PASSED** |
| `tests/test_batchtrace.py` | Lot Splitting, Merging & Conservation of Mass (F3) | 14 | **PASSED** |
| `tests/test_logistics.py` | Fleet Dispatch & Route Verification (F5) | 12 | **PASSED** |
| `tests/test_riskwatch.py` | Multi-Hazard Disruption Detection (F6) | 10 | **PASSED** |
| `tests/test_recoveryopt.py` | Disruption Recovery Optimization (F7) | 10 | **PASSED** |
| `tests/test_settletrack.py` | Financial Settlement & Deduction Auditing (F8) | 12 | **PASSED** |
| `tests/test_overview.py` | Role-Based Dashboards & Scoping (F9) | 8 | **PASSED** |
| `tests/test_offline_sync.py` | Vector Clocks & CRDT Conflict Resolution (F10) | 12 | **PASSED** |
| `tests/test_market_arrivals.py` | Market Arrivals Feeds & Fallbacks (F11) | 6 | **PASSED** |
| `tests/test_price_forecasting.py`| Pricing Model Inference & Invariants (F12) | 5 | **PASSED** |
| `VALIDATION_TESTS/` | Adversarial SRE & Concurrency Stress Suite | 5 | **PASSED** |
| **TOTAL** | **Comprehensive Backend Verification** | **158** | **100% PASS** |

---

## 2. Phase 3 Contract Suite Breakdown (`test_phase3_contracts.py`)

Every one of the 15 Phase 3 acceptance contracts has been implemented and tested:

1. `test_1_tampered_csv_bytes_reject_on_hash_failure`:
   - Single-byte corruption injected into `csv/commodities.csv`.
   - Result: `DatasetContractError: commodities: byte hash mismatch`. Rejected prior to state mutation.
2. `test_2_missing_csv_or_changed_column_rejects`:
   - A. Deleted `commodities.csv` from archive -> Rejected with `Table inventory mismatch`.
   - B. Modified column header in `manifest.json` -> Rejected with `commodities: header mismatch`.
3. `test_3_duplicate_pk_broken_fk_and_invalid_units`:
   - Unsupported units (`pounds`, `miles`) rejected with descriptive error.
   - Fractional grams and fractional meters rejected.
   - Negative values rejected.
   - Ambiguous naive ISO timestamps rejected.
4. `test_4_synthetic_import_into_production_denied`:
   - Attempt to import release into `environment="production"` strictly denied with `Production safety violation`.
5. `test_5_double_import_is_idempotent`:
   - Second execution returns `ALREADY_IMPORTED`. Zero duplicated items across all collections.
6. `test_6_import_failure_leaves_previous_durable_state_unchanged`:
   - Failed transaction with invalid demand invariant leaves durable state and disk snapshot 100% intact.
7. `test_7_market_arrivals_and_forecasts_explicit_unavailable_state`:
   - `market_arrivals_status` explicitly marked `UNAVAILABLE_AWAITING_SOURCE` (row count: 0).
   - `price_forecasts_status` explicitly marked `UNAVAILABLE_UNTRAINED_MODEL` (row count: 0).
8. `test_8_simulated_road_edges_not_navigable_real_routes`:
   - Verified that all 620 road edges have `simulation_flag=True`.
   - System readiness correctly reports `navigable_real_roads_verified: False`.
9. `test_9_administrative_location_proxies_labeled`:
   - Verified that 79 locations are administrative proxies; `site_coordinate_verified: False`.
   - System readiness reports `verified_farm_gps_connected: False`.
10. `test_10_demand_and_delivery_reconciliation`:
    - Demand semantics enforced: `uncommitted_grams <= remaining_grams <= needed_grams`.
    - Delivery reconciliation enforced: `delivered_grams == buyer_accepted_grams + buyer_rejected_grams`.
11. `test_11_canonical_unit_conversions`:
    - Verified exact conversion formulas: mass (grams), distance (meters), price (paise/kg), gross settlement formula.
12. `test_12_cross_module_contracts_and_availability`:
    - Vehicles capacity in integer grams; settlement amounts with zero penny leakage.
13. `test_13_core_store_invariants_preserved`:
    - Memory store collections preserved across imports.
14. `test_14_exercise_api_endpoints_with_sandbox_import`:
    - API tests via `TestClient`: seeded 8,321 records via `POST /api/v1/admin/import/sandbox-release`.
    - Verified querying `/api/v1/forecasts`, `/api/v1/lots`, `/api/v1/requirements`, `/api/v1/shipments`.
15. `test_15_readiness_endpoint_returns_not_ready`:
    - Verified `GET /api/v1/system/readiness` returns `NOT_READY_CRITICAL_OPERATIONAL_GAPS` before and after sandbox import.
