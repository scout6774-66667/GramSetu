# GramSetu AI — Complete Dataset Inventory

**Inventory Date**: 2026-11-22  
**Specification Version**: 2.0-DataEng  
**Total Identified Datasets**: 34 Canonical Datasets  
**Functional Coverage**: 8 Core Business Areas (Components A – H)  
**Storage & Integration Model**: In-Memory State (`InMemoryStore`) + Atomic JSON Snapshots + CSV/JSON Ingestion Pipelines

---

## 1. Classification Framework

Datasets are categorized according to operational semantics and lifecycle constraints:

| Category Code | Category Name | Description & Behavioral Invariant |
|---|---|---|
| **REF** | **Static Reference Data** | Master catalogs, administrative boundaries, standards, rates, and classification registries. Immutable during transactions; version-controlled. |
| **OBS** | **Historical Observational Data** | Time-series market prices, mandi arrivals, weather records. Factual observations; never editable retroactively. |
| **OPS** | **Live Operational Data** | Executable transactions, actual inventory lots, active commitments, shipments. Must preserve mass and monetary invariants. |
| **FCT** | **Forecast & Model Data** | Predictive yields, expected harvests, demand forecasts, risk probability scores. **Never treated as verified physical stock**. |
| **OPT** | **Derived Optimization Data** | Solved recovery candidates, shortest-path road routes, capacity allocations. Output of deterministic algorithms. |
| **AUD** | **Audit & Provenance Data** | Immutable append-only event logs, SHA-256 evidence digests, reconciliation histories, version conflict logs. |

---

## 2. Dataset Master Inventory Table

| ID | Dataset Name | Category | Primary Module | Storage Collection | Status in Repo | Authoritative Real-World Source | Priority |
|---|---|---|---|---|---|---|---|
| **DS-01** | `commodity_master.csv` | **REF** | DemandSync | `items` | Missing (implicit) | Agmarknet / Ministry of Agriculture & Farmers Welfare | **P0** |
| **DS-02** | `commodity_grades.csv` | **REF** | BatchTrace | `items` | Missing (implicit) | Bureau of Indian Standards (BIS) / AGMARK Standards | **P0** |
| **DS-03** | `mandi_master.csv` | **REF** | Market Intel | `items` | Missing | Agmarknet / eNAM APMC Directory | **P0** |
| **DS-04** | `daily_mandi_prices.csv` | **OBS** | Market Intel | N/A (planned) | Missing | Agmarknet / Data.gov.in Daily Price Feeds | **P0** |
| **DS-05** | `daily_mandi_arrivals.csv` | **OBS** | Market Intel | N/A (planned) | Missing | Agmarknet Mandi Arrivals Bulletin | **P0** |
| **DS-06** | `historical_price_trends.csv` | **OBS** | Market Intel | N/A (planned) | Missing | Agmarknet 3-Year Modal Price Time-Series | **P1** |
| **DS-07** | `administrative_locations.csv` | **REF** | Logistics | `items` | Missing (implicit) | Local Government Directory (LGD) / Census of India | **P0** |
| **DS-08** | `road_nodes.csv` | **REF** | Logistics | `items` | Partial (8 hardcoded nodes) | OpenStreetMap (OSM) / Survey of India GIS | **P0** |
| **DS-09** | `road_segments.csv` | **REF** | Logistics | `items` | Partial (12 hardcoded edges)| OpenStreetMap Highway Extracts / NHAI Network | **P0** |
| **DS-10** | `weather_observations.csv` | **OBS** | RiskWatch | N/A (implicit) | Missing | India Meteorological Department (IMD) AWS | **P1** |
| **DS-11** | `weather_forecasts_alerts.csv`| **FCT** | RiskWatch | `incidents` | Missing | IMD Mausam District Agromet Advisories | **P1** |
| **DS-12** | `farmer_registry.csv` | **REF** | Overview / Auth | `items` | Hardcoded (`DEV_ACTORS`)| FPO Member Registries / PM-KISAN LGD Directory | **P0** |
| **DS-13** | `fpo_master.csv` | **REF** | Overview / Auth | `items` | Hardcoded (`fpo-alpha`) | SFAC (Small Farmers Agribusiness Consortium) / MCA | **P0** |
| **DS-14** | `harvest_forecasts.csv` | **FCT** | DemandSync | `forecasts` | Active in code | Farmer field declarations / FPO Village Aggregation| **P0** |
| **DS-15** | `inventory_lots.csv` | **OPS** | BatchTrace | `lots` | Active in code | FPO Warehouse Physical Inward Weighments | **P0** |
| **DS-16** | `inventory_movements.csv` | **AUD** | BatchTrace | `movements` | Active in code | Internal Mass Conservation Ledger | **P0** |
| **DS-17** | `buyer_registry.csv` | **REF** | Procurement | `items` | Hardcoded (`DEV_ACTORS`)| GSTN Portal / Corporate MCA Directory | **P0** |
| **DS-18** | `buyer_requirements.csv` | **OPS** | Procurement | `requirements` | Active in code | Buyer Procurement Platform Postings | **P0** |
| **DS-19** | `buyer_commitments.csv` | **OPS** | CommitGuard | `commitments` | Active in code | Contractually Binding Counterparty Agreement | **P0** |
| **DS-20** | `demand_gap_analysis.csv` | **OPT** | DemandSync | `metrics` | Active in code | Algorithmic Supply-Demand Net Balance | **P1** |
| **DS-21** | `storage_facilities.csv` | **REF** | BatchTrace | `items` | Missing (implicit) | WDRA (Warehousing Dev & Reg Authority) | **P0** |
| **DS-22** | `vehicle_fleet.csv` | **REF/OPS**| Logistics | `vehicles` | Active in code | Vahan Citizen Services / Transporter Registries | **P0** |
| **DS-23** | `logistics_shipments.csv` | **OPS** | Logistics | `shipments` | Active in code | Dispatch Waybills / Transporter Consignment Notes | **P0** |
| **DS-24** | `route_evaluations.csv` | **OPT** | Logistics | `metrics` | Active in code | `OfflineRoadGraphProvider` (Dijkstra Solver) | **P1** |
| **DS-25** | `crop_shelf_life_rules.csv` | **REF** | RiskWatch | `items` | Hardcoded (9 crops in code)| ICAR Post-Harvest Technology Standards | **P0** |
| **DS-26** | `quality_inspections.csv` | **OPS** | BatchTrace | `items` | Missing (implicit) | AGMARK Quality Assay Laboratories / Assay Certificates| **P1** |
| **DS-27** | `risk_incidents.csv` | **OPS/AUD**| RiskWatch | `incidents` | Active in code | Automated Rule Scanner (`scan_risk_incidents`) | **P0** |
| **DS-28** | `recovery_plans.csv` | **OPT** | RecoveryOpt | `recovery_plans` | Active in code | `optimize_recovery_allocation` Algorithm | **P0** |
| **DS-29** | `freight_rate_cards.csv` | **REF** | Logistics | `items` | Hardcoded formula in code| Regional Rural Transport Unions / FPO Rate Cards | **P1** |
| **DS-30** | `settlement_deductions.csv` | **REF** | SettleTrack | `items` | Missing (implicit) | State APMC Market Rules & Labour Schedules | **P0** |
| **DS-31** | `settlement_records.csv` | **OPS** | SettleTrack | `settlements` | Active in code | Accounting Settlement Ledger (`generate_settlement`)| **P0** |
| **DS-32** | `payment_evidence_records.csv`| **AUD** | SettleTrack | `evidence` | Active in code | Banking UTR Records & Weighbridge Scale Slips | **P0** |
| **DS-33** | `system_audit_events.csv` | **AUD** | Events (F11) | `events` | Active in code | Durable Local Event Sequence Ledger | **P1** |
| **DS-34** | `offline_commands_log.csv` | **AUD** | OfflineSync | `offline_commands` | Active in code | Optimistic Concurrency Mobile Sync Journal | **P2** |

---

## 3. Critical Data Boundaries & Architectural Separation of Facts

1. **Separation of Forecasts vs. Physical Inventory**:
   - `DS-14 (harvest_forecasts)` represents *anticipated yield* (probabilistic, subject to weather).
   - `DS-15 (inventory_lots)` represents *physically received produce* sitting inside a verified storage silo.
   - **Hard Invariant**: A forecast can never be allocated to a commitment, dispatched, or settled.
2. **Separation of Available vs. Reserved Stock**:
   - For every physical lot: $\text{quantity\_grams} = \text{available\_grams} + \text{reserved\_grams}$.
   - Once a commitment locks produce, `reserved_grams` increases and `available_grams` decreases.
   - **Hard Invariant**: Reserved inventory cannot be re-reserved or allocated to recovery plans.
3. **Separation of Market Observations vs. Executable Buyer Offers**:
   - `DS-04 (daily_mandi_prices)` reflects historical market transactions across regional APMCs.
   - `DS-18 (buyer_requirements)` reflects an executable, legally binding demand from a registered buyer.
   - **Hard Invariant**: An FPO cannot book commitments against mandi price trends without an active buyer requirement.
4. **Separation of Reported vs. Confirmed Payments**:
   - `DS-32 (payment_evidence_records)` marks buyer claims as `REPORTED`.
   - Only upon verification by the FPO or cryptographic bank webhook is it promoted to `OPERATOR_CONFIRMED` or `EXTERNALLY_VERIFIED`.
   - **Hard Invariant**: A settlement is never marked `SETTLED` while evidence remains in `REPORTED` state.
