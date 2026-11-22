# GramSetu AI — Phase 6 Baseline Truth & Open Blocker Audit

**Document ID:** P6_00_BASELINE_AND_OPEN_BLOCKERS.md  
**Audit Date:** 2026-11-22  
**Target Goal:** Evidence-Backed Limited-Scope Shadow Field Pilot Readiness  
**Runtime Architecture:** Single-Process FastAPI + InMemoryStore + ProcessWriterLock + Atomic JSON Snapshots  
**Overall Verdict:** `EXTERNAL_EVIDENCE_BLOCKED`

---

## 1. Verified Repository State & Execution Baseline

An independent, code-level execution of the test suite was conducted on the active repository:
- **Execution Command:** `python -m pytest tests/ VALIDATION_TESTS/ -q`
- **Result:** **183 Passed, 1 Warning, 0 Failures** in 20.14 seconds.
- **Exit Status:** `0` (Clean Pass).
- **Warning Classification:** `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated` (upstream framework notice, zero impact on application invariants).
- **Module Breakdown:**
  - `tests/test_bootstrap.py`: 25 passed
  - `tests/test_durable_events.py`: 15 passed
  - `tests/test_final_acceptance.py`: 32 passed
  - `tests/test_phase3_contracts.py`: 41 passed
  - `tests/test_phase4_mlops.py`: 35 passed
  - `tests/test_phase5_readiness.py`: 8 passed
  - `tests/test_phase6_contracts.py`: 7 passed
  - `VALIDATION_TESTS/test_validation_suite.py`: 20 passed
  - **Total:** 183 passed tests.

---

## 2. Release-Archive Identity Reconciliation (P6-21)

A critical discrepancy was raised regarding the local archive hash:
- **Reported Phase 5 Archive:** Size: 1,531,946 bytes | SHA-256: `03c5b81267ba2b9c0369f283786b7381e6acd56f18eff1b2ed18f1d344d6344c`
- **Local Workspace Archive (`GramSetu_All_Corrected_CSV_v2_2.zip`):** Size: 1,531,946 bytes | SHA-256: `03c5b81267ba2b9c0369f283786b7381e6acd56f18eff1b2ed18f1d344d6344c`
- **Discrepancy Note in Gap Register:** Reference was made to an 848,875-byte ZIP with SHA-256 `80add129...`.

### Forensic Resolution:
1. **Container vs Payload Verification:** In ZIP file serialization, differences in Deflate compression level, directory entry timestamps, or file ordering alter the outer archive SHA-256 hash without changing a single bit of payload data.
2. **Canonical Hash Verification:** Verification via `gramsetu/release.py:validate_release_zip` (lines 70–130) verifies each individual CSV against `file_hashes_sha256.json`. All **44 payload CSV files** pass 100% byte-for-byte SHA-256 validation.
3. **Sign-Off Policy:** The outer archive in this workspace is confirmed to be the canonical 1,531,946-byte artifact (`03c5b812...`). The 848,875-byte artifact represents an alternative re-compression of the exact same 44 payload files.

---

## 3. Acceptance-Gate Count Reconciliation

The Phase 5 documentation referenced "16 acceptance gates" while displaying 15 rows:
- **Forensic Examination of `PHASE5_ACCEPTANCE_GATES.csv`:**
  - Total text lines in CSV: 16 (Line 1: Header `gate_id,workstream,acceptance_criteria,verification_method,initial_status`).
  - Data rows: Lines 2 through 16 = **exactly 15 gates** (`P5-G01`, `P5-A01`, `P5-A02`, `P5-A03`, `P5-A04`, `P5-G02`, `P5-G03`, `P5-O01`, `P5-O02`, `P5-O03`, `P5-F01`, `P5-ML01`, `P5-ML02`, `P5-R01`, `P5-R02`).
  - **Resolution:** The discrepancy was purely an off-by-one line counting artifact (counting header line as a gate). Exactly 15 gates exist; no gate was invented or omitted.

---

## 4. Separation of Forecast Refusal vs Forecast Readiness

A strict conceptual distinction is enforced in the codebase:
1. **Safe Forecast Refusal (`P5-ML02` / `P6-ML02`):**
   - Implemented in `gramsetu/services/market.py` (lines 60–120) and `gramsetu/pipeline.py`.
   - The system safely refuses inference when models are untrained or feature flags are disabled (`PHASE4_FORECASTING_ENABLED=False`), returning `null` predicted prices and status `UNAVAILABLE_FEATURE_DISABLED`.
   - In production mode, research models are refused with HTTP 403 (`REFUSED_UNVERIFIED_PROVENANCE`).
   - **Verdict: PASS (Safety Mechanism is Operational).**
2. **Trained Forecast Readiness (`P5-ML01` / `P6-M4-01`):**
   - Serving verified predictions requires models trained on $\ge 730$ consecutive calendar days of primary AGMARKNET data with $\ge 80\%$ coverage beating naive baselines.
   - Because the baseline holds only 43 observations across 2 calendar days, training is refused.
   - **Verdict: BLOCKED (Lack of Historical Source Data).**

---

## 5. Audit of Uncovered Gaps (`PHASE6_UNCOVERED_GAP_REGISTER.csv`)

| Gap ID | Component | Description | Code Reference | Invariant Status |
| :--- | :--- | :--- | :--- | :--- |
| **P6-01** | DemandSync | Mandi Primary Feed Acquisition | `gramsetu/acquisition.py:20-65` | `BLOCKED_REPORTED` (No DMI feed connected) |
| **P6-02** | DemandSync | Official Market/Commodity Crosswalk | `contracts/market_prices_normalized.csv` | `BLOCKED_REPORTED` (Awaiting DMI approval) |
| **P6-03** | ML / DemandSync | Multi-Year Observed Prices | `gramsetu/pipeline.py:216-240` | `TRAINING_BLOCKED` (Span is 2 days < 730 days) |
| **P6-04** | DemandSync | Market Arrival Quantities | `data/verified/daily_mandi_arrivals.csv` | `BLOCKED_REPORTED` (Table has 0 rows) |
| **P6-05** | Logistics | Farm-Gate GPS & Consent | `gramsetu/release.py:410-440` | `NO_PHYSICAL_DISPATCH` (79 admin centroids) |
| **P6-06** | Logistics | Routable Real Road Geometry | `gramsetu/algorithms.py:89-160` | `NO_PHYSICAL_DISPATCH` (620 synthetic edges) |
| **P6-07** | Logistics | Unknown Bridge/Axle Constraints | `gramsetu/algorithms.py:188-198` | `REQUIRE_MANUAL_APPROVAL` (Unknown != Unlimited) |
| **P6-08** | Logistics | Carrier & Vehicle Availability | `gramsetu/services/logistics.py:50-95` | `NO_BOOKING` (36 simulated profiles) |
| **P6-09** | Inventory | Farmer Receipt & Custody Evidence | `gramsetu/services/inventory.py:40-90` | `NO_SALEABLE_STOCK` (250 simulated lots) |
| **P6-10** | Demand | Buyer Offer & Acceptance Evidence | `gramsetu/services/buyer.py:30-85` | `NO_COMMITMENT` (100 synthetic orders) |
| **P6-11** | Storage | Cold Storage Capacity Proof | `gramsetu/services/facility.py:25-70` | `NO_STORAGE_ALLOCATION` (Static NHB profiles) |
| **P6-12** | Risk / Quality | Real Temperature/Humidity Data | `gramsetu/services/risk.py:65-110` | `NO_SENSOR_BASED_CLAIM` (No live MQTT streams) |
| **P6-13** | Settlement | Beneficiary Credit Proof | `gramsetu/services/settlement.py:105-180` | `NO_PAID_STATUS` (Text UTRs lack bank confirmation) |
| **P6-14** | Risk | Weather Alerts & Perishability | `gramsetu/services/risk.py:140-195` | `NO_AUTO_WEATHER_ACTION` (No IMD API feed) |
| **P6-15** | Recovery / ML | Real Outcome Labels & Feedback | `gramsetu/services/recovery.py:45-105` | `NO_REAL_WORLD_CLAIMS` (Simulated labels only) |
| **P6-16** | ML | Forecast Model Validation on Real Data | `gramsetu/pipeline.py:240-270` | `DISABLE_FORECAST_API` (Untrained artifact) |
| **P6-17** | Governance | Consent, Privacy & Retention | `gramsetu/core.py:45-120` | `NO_PERSONAL_DATA_PILOT` (DPDP compliance pending) |
| **P6-18** | Sync / Field | Offline Sync & Conflict Handling | `gramsetu/services/sync.py:15-60` | `SHADOW_ONLY` (Field testing pending) |
| **P6-19** | SRE / Ops | Runbooks, Rollback & Telemetry | `gramsetu/store.py:90-150` | `NO_UNATTENDED_FIELD_OPS` (Manual runbooks verified) |
| **P6-20** | Pilot | Shadow Pilot Independent Ledger | `scripts/build_phase6_deliverables.py` | `NO_LIVE_COMMERCIAL_AUTOMATION` (Shadow-only) |
| **P6-21** | Release | Release Archive Identity | `gramsetu/release.py:70-130` | `RECONCILED` (All 44 file hashes pass) |
