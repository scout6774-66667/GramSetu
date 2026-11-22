# GramSetu AI — Component-Wise Data, Logic & Invariant Audit Report

**Document Reference**: GS-AUDIT-PHASE3-COMPONENTS-2026  
**Auditor**: Principal Data Engineer, Senior Backend Architect & Algorithm Auditor  
**Audit Scope**: Core Business Components A through H  
**Execution Environment**: Python 3.11+ / FastAPI / In-Memory Store / 143 Automated Pytest Tests  

---

## Component A: Agricultural Market Intelligence — DemandSync

### 1. Data Requirements & Availability
- **Required Datasets**: `markets`, `commodities`, `market_prices`, `market_arrivals`, `price_forecasts`, `source_registry`.
- **Available Datasets**: `markets` (12 rows), `commodities` (17 rows), `market_prices` (43 rows), `source_registry` (8 rows).
- **Missing Datasets**: `market_arrivals` (**0 rows**), `price_forecasts` (**0 rows**).
- **Architectural Gap**: `MarketIntelligenceService` is described in `ARCHITECTURE.md` but is **completely missing in code** (`gramsetu/services/` has no `market_intel.py`, and `main.py` has no `/api/v1/market-intel/*` endpoints).

### 2. Logic & Invariant Verification
- **Unit Conversion Check**:
  - Legacy `market_prices` stores prices in float INR/kg (e.g. `25.50`).
  - Verified Agmarknet prices in `data/verified/daily_mandi_prices.csv` use integer paise/gram:
    $$\text{modal\_price\_paise\_per\_gram} = \frac{\text{raw\_modal\_price\_rs\_per\_quintal}}{100}$$
  - Invariant $\text{min\_price} \le \text{modal\_price} \le \text{max\_price}$ is enforced by `MandiPriceLoader` and verified in `test_layer_5_numerical_correctness`.
- **Audit Findings**:
  - Without `market_arrivals`, the system cannot evaluate supply volume surges or detect local market gluts.
  - Without `price_forecasts` and its missing ML model, all downstream pricing relies on static historical observations or buyer ceilings.
- **Component A Verdict**: **PARTIALLY_OPERATIONAL_WITH_CRITICAL_GAPS** (Core reference data exists, but forecasting and arrival intelligence are missing).

---

## Component B: Farmer Supply and Inventory — BatchTrace / CommitGuard

### 1. Data Requirements & Availability
- **Required Datasets**: `farmers`, `organizations`, `harvest_forecasts`, `inventory_lots`, `inventory_movements`, `quality_inspections`.
- **Runtime Services**: `gramsetu/services/supply.py`, `gramsetu/services/inventory.py`.

### 2. Logic & Invariant Verification
- **Core Invariant**:
  $$0 \le \text{reserved\_grams} \le \text{quantity\_grams} \quad (\text{eligible physical stock})$$
- **Verification Evidence**:
  - Tested in `tests/test_commitguard.py::test_atomic_commitment_success_and_reservation`:
    1. Lot received with 400,000g available.
    2. Buyer commits 300,000g $\rightarrow$ `quantity_grams = 400,000`, `reserved_grams = 300,000`.
    3. Second buyer attempts to commit 200,000g $\rightarrow$ Rejected with `409 Conflict` (`Insufficient available lot quantity`).
  - Mass Conservation during Lot Split/Merge:
    - Tested in `tests/test_batchtrace.py`:
      $$\sum \text{child\_lots.quantity\_grams} = \text{parent\_lot.quantity\_grams}$$
      Split of 500,000g into 300,000g + 200,000g preserves exact mass. Merging requires matching `crop`, `grade`, and `fpo_id`.
  - Quality Grade Mutation: Tested in `VALIDATION_TESTS/test_data_scenarios.py::test_scenario_d_quality_failure` (Grade A downgraded to Grade B with recorded movement log).
- **Component B Verdict**: **PASS_VERIFIED** (Mathematical invariants and custody tracking strictly enforced).

---

## Component C: Buyer Demand and Procurement — DemandSync / CommitGuard

### 1. Data Requirements & Availability
- **Required Datasets**: `buyers`, `buyer_requirements`, `procurement_offers`, `commitments`, `delivery_acceptances`.
- **Runtime Services**: `gramsetu/services/procurement.py`.

### 2. Logic & Invariant Verification
- **Demand Gap Calculation**:
  $$\text{net\_gap\_grams} = \text{total\_demand\_grams} - \text{total\_forecast\_grams}$$
  - Tested in `tests/test_demandsync.py::test_demand_gap_calculation_and_disclaimer`:
    Demand of 500,000g vs Forecast of 0g $\rightarrow$ Deficit of 500,000g.
    Demand of 0g vs Forecast of 400,000g $\rightarrow$ Surplus of 400,000g (`net_gap = -400,000g`).
  - Every demand gap response carries an explicit mandatory disclaimer: `"PLANNING ONLY - NOT A REAL-TIME GUARANTEE"`.
- **Commitment Atomicity & Cancellation**:
  - Commitments lock physical inventory in RAM.
  - Cancelling a commitment (`POST /api/v1/commitments/{id}/cancel`) decrements `reserved_grams` and releases stock back to available status immediately.
- **Component C Verdict**: **PASS_VERIFIED** (Strict atomic reservation, zero double-allocation).

---

## Component D: Logistics — Transport / RiskWatch / RecoveryOpt

### 1. Data Requirements & Availability
- **Required Datasets**: `locations`, `road_nodes`, `road_edges`, `vehicles`, `vehicle_availability`, `freight_quotes`, `transport_routes`, `shipments`.
- **Runtime Services & Algorithms**: `gramsetu/services/logistics.py`, `gramsetu/algorithms.py`.

### 2. Logic & Invariant Verification
- **Road Network Topology**:
  - `OfflineRoadGraphProvider` in `algorithms.py` implements Dijkstra shortest-path search on directed graphs.
  - Tested in `tests/hardening/test_road_graph_routing.py`:
    - Validates shortest path traversal from warehouse to terminal hubs.
    - Path distance matches segment summation: $\text{Total Distance} = \sum \text{edge.distance\_meters}$.
    - Path duration computed conservatively from edge speeds: $\text{Duration} = \sum \frac{\text{distance}}{\text{speed}}$.
- **Vehicle Capacity & Assignment Guard**:
  - Single active shipment per vehicle constraint: A vehicle cannot be dispatched on a second shipment while `IN_TRANSIT`.
  - Tested in `tests/test_logistics.py`: Attempting to create shipment exceeding vehicle `capacity_grams` returns `400 Bad Request`.
- **Component D Verdict**: **PASS_VERIFIED** (Graph routing and capacity constraints verified).

---

## Component E: Storage and Quality — BatchTrace / RecoveryOpt

### 1. Data Requirements & Availability
- **Required Datasets**: `facilities`, `facility_commodities`, `storage_conditions`, `storage_reservations`.
- **Runtime Services**: `gramsetu/services/inventory.py`.

### 2. Logic & Invariant Verification
- **Capacity & Perishability Rules**:
  - Cold storage shelf life $\ge$ ambient shelf life (verified in `VALIDATION_TESTS/test_data_quality_10_layers.py::test_layer_7_business_logic_consistency`).
  - Storage locations are referenced during lot receipt and lot movements.
- **Gaps**:
  - Live IoT telemetry integration is not implemented; `storage_conditions` contains simulated static entries.
- **Component E Verdict**: **PASS_SYNTHETIC_ONLY** (Storage capacity bounds hold, but real-time telemetry is absent).

---

## Component F: Cost and Payment Intelligence — SettleTrack

### 1. Data Requirements & Availability
- **Required Datasets**: `cost_records`, `payable_ledger`, `payment_transactions`, `payment_evidence`.
- **Runtime Services**: `gramsetu/services/settlement.py`, `gramsetu/adapters/evidence.py`.

### 2. Logic & Invariant Verification
- **Settlement Mathematical Formula**:
  $$\text{gross\_payable\_paise} = \text{accepted\_grams} \times \text{agreed\_price\_paise\_per\_gram}$$
  $$\text{net\_payable\_paise} = \text{gross\_payable\_paise} - \sum \text{authorized\_deductions\_paise}$$
  - Tested in `tests/test_settletrack.py` and `VALIDATION_TESTS/test_data_scenarios.py::test_scenario_a_normal_fulfillment`:
    - Accepted grams: 1,000,000g @ 48 paise/g $\rightarrow$ Gross: 48,000,000 paise (₹480,000).
    - APMC Mandi Cess deduction: 504,000 paise (₹5,040).
    - Net payable: $48,000,000 - 504,000 = 47,496,000\text{ paise}$ (₹474,960).
- **Payment Verification Gate**:
  - Buyer self-reported payment (`POST /api/v1/settlements/{id}/report-payment`) does **not** update `paid_amount_paise`. Status remains `REPORTED`.
  - Only explicit FPO verification (`POST /api/v1/settlements/{id}/payments/{pid}/verify`) increments `paid_amount_paise` and decrements `remaining_balance_paise`.
- **Component F Verdict**: **PASS_VERIFIED** (Financial ledger invariants and 2-way verification strictly enforced).

---

## Component G: Risk and Recovery — RiskWatch / RecoveryOpt

### 1. Data Requirements & Availability
- **Required Datasets**: `risk_incidents`, `recovery_runs`, `recovery_candidates`, `recovery_decisions`, `recovery_outcomes`.
- **Runtime Services & Algorithms**: `gramsetu/services/risk.py`, `gramsetu/services/recovery.py`, `gramsetu/algorithms.py`.

### 2. Logic & Invariant Verification
- **RiskWatch Heuristic Detection**:
  - Scans for:
    1. `PERISHABLE_AT_RISK`: Lots approaching expiry based on shelf-life days.
    2. `SHORT_DELIVERY`: Delivery where $\text{delivered\_grams} < \text{shipped\_grams}$.
    3. `QUALITY_REJECTION`: Delivery where $\text{rejected\_grams} > 0$.
  - Deduplication tested in `tests/test_riskwatch.py::test_deduplication_prevents_alert_storms` (re-scanning does not duplicate open incidents).
- **Recovery Optimization Engine**:
  - Evaluates candidate buyer requirements to maximize net recovery proceeds:
    $$\max \sum (\text{allocable\_grams} \times \text{offered\_price} - \text{transport\_cost})$$
  - Hard constraint: Discards candidates where $\text{Net Return} \le 0$.
  - Tested in `tests/test_recoveryopt.py` and `tests/hardening/test_recovery_gt8_oracle.py`:
    - Evaluates up to 200 candidates without silent arbitrary truncation.
    - Execution finishes within 200ms time budget.
- **Component G Verdict**: **PASS_VERIFIED** (Optimization and deduplicated incident lifecycle verified).

---

## Component H: Provenance and Data Quality — All Modules

### 1. Data Requirements & Availability
- **Required Datasets**: `actors`, `geography_reference_points`, `domain_events`, `ingestion_runs`, `data_quality_results`, `snapshot_versions`.
- **Runtime Services**: `gramsetu/services/events.py`, `gramsetu/store.py`, `gramsetu/adapters/evidence.py`.

### 2. Logic & Invariant Verification
- **Immutable Domain Events**:
  - `append_event` records sequential, immutable audit events for every state mutation.
  - Tested in `tests/test_durable_events.py`: Events persist across restarts and maintain monotonically increasing sequence IDs.
- **Atomic Persistence & Process Writer Lock**:
  - Tested in `tests/hardening/test_process_writer_lock.py`: Attempting to initialize two concurrent `TransactionCoordinator` writers on the same lock file immediately raises `ProcessLockError`.
  - Atomic rename (`tempfile` + `fsync` + `replace`) guarantees zero corruption on unexpected process kill.
- **Component H Verdict**: **PASS_VERIFIED** (Audit durability and single-writer concurrency verified).
