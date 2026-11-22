# GramSetu AI — Complete Repository Discovery & Architectural Audit

**Document Reference**: GS-AUDIT-PHASE0-DISCOVERY-2026  
**Auditor**: Principal Data Engineer, Senior ML Engineer & Backend Systems Architect  
**Audit Date**: November 2026  
**Repository Baseline**: GramSetu AI Backend (Python 3.11+ / FastAPI / Pydantic v2 / Database-Free Engine)

---

## 1. Executive Overview & System Mode

GramSetu AI is an agricultural supply chain resilience and recovery platform designed for Farmer Producer Organizations (FPOs), smallholder farmers, agricultural buyers, and transport operators in rural India.

### Architectural Operating Mode
- **Persistence Architecture**: Database-Free Monolith. Does **not** use PostgreSQL, SQLite, MySQL, MongoDB, Redis, or Celery.
- **State Store**: Injectable `InMemoryStore` maintaining deep-copied in-memory dictionary collections.
- **Durable Snapshot**: Copy-on-write atomic JSON file persistence (`tempfile` + `fsync` + atomic `os.replace`).
- **Concurrency Protection**: Single-writer process boundary enforced via OS-level file locking (`msvcrt` on Windows / `fcntl` on POSIX via `ProcessWriterLock` in `gramsetu/store.py`).
- **Core Units**:
  - Quantity: Integer grams ($1\text{ quintal} = 100,000\text{g}$, $1\text{ MT} = 1,000,000\text{g}$).
  - Currency: Integer paise ($1\text{ INR} = 100\text{ paise}$).
  - Time: ISO 8601 UTC string timestamps (`YYYY-MM-DDTHH:MM:SSZ`).
  - IDs: String UUIDv4 or domain-prefixed identifier strings.

---

## 2. Backend Entry Points & Server Lifecycle

- **Entry Point File**: `gramsetu/main.py`
- **Application Factory**: `create_app(settings: Optional[Settings] = None, store: Optional[InMemoryStore] = None, coordinator: Optional[TransactionCoordinator] = None) -> FastAPI` (line 125)
- **Server Startup Command**: `uvicorn gramsetu.main:app --host 0.0.0.0 --port 8000 --workers 1`
  > *Constraint*: Hardcoded single-worker rule. Multi-worker uvicorn configurations violate the single-process in-memory concurrency model and are strictly prevented by `ProcessWriterLock`.
- **Runtime Startup Behavior**:
  - If `cfg.SNAPSHOT_PATH` exists on disk, `InMemoryStore.load_from_snapshot(cfg.SNAPSHOT_PATH)` hydrates RAM state.
  - If no snapshot path is provided, `create_app()` initializes an **empty `InMemoryStore`**.
  - **CRITICAL AUDIT FINDING**: The backend application **does NOT automatically ingest or load** `gramsetu_all_records.csv`, `data_dictionary.csv`, or the canonical CSV files in `data/` upon server startup. It boots completely empty unless populated by API calls or an existing JSON snapshot.

---

## 3. API Routers & Endpoint Inventory

The backend exposes **56 HTTP routes** registered directly on the `FastAPI` application instance in `gramsetu/main.py`. Path alias middleware transparently maps `/v1/*` to `/api/v1/*`.

| Route Path | HTTP Method | Endpoint Function Name | Line in `main.py` | Target Domain Service | Auth Role Required |
|---|---|---|---|---|---|
| `/health` | GET | `health_check` | L164 | Core Health Check | Public |
| `/api/v1/auth/me` | GET | `auth_me` | L182 | Security / Identity | Any authenticated actor |
| `/api/v1/auth/fpo-only` | GET | `auth_fpo_only` | L190 | Security / Identity | `FPO_ADMIN` |
| `/api/v1/auth/fpo/{fpo_id}/check` | GET | `auth_fpo_org_check` | L195 | Security / Identity | `FPO_ADMIN` (Scoped) |
| `/api/v1/auth/driver-action` | POST | `auth_driver_action` | L201 | Security / Identity | `DRIVER` |
| `/api/v1/forecasts` | POST | `post_forecast` | L213 | `supply.create_harvest_forecast` | `FARMER` |
| `/api/v1/forecasts` | GET | `get_forecasts` | L223 | `supply.list_harvest_forecasts` | `FARMER`, `FPO_ADMIN` |
| `/api/v1/requirements` | POST | `post_requirement` | L234 | `procurement.create_buyer_requirement` | `BUYER` |
| `/api/v1/requirements` | GET | `get_requirements` | L245 | `procurement.list_buyer_requirements` | `BUYER`, `FPO_ADMIN` |
| `/api/v1/demand-gap` | GET | `get_demand_gap` | L256 | `procurement.compute_demand_gap` | `FPO_ADMIN`, `BUYER` |
| `/api/v1/demand-gaps` | GET | `get_demand_gap` | L256 | `procurement.compute_demand_gap` | `FPO_ADMIN`, `BUYER` |
| `/api/v1/commitments` | POST | `post_commitment` | L272 | `procurement.create_commitment` | `BUYER` |
| `/api/v1/commitments/{id}` | GET | `get_single_commitment` | L284 | `procurement.get_commitment` | `BUYER`, `FPO_ADMIN` |
| `/api/v1/commitments` | GET | `get_all_commitments` | L291 | `procurement.list_commitments` | `BUYER`, `FPO_ADMIN` |
| `/api/v1/commitments/{id}/cancel` | POST | `post_cancel_commitment` | L299 | `procurement.cancel_commitment` | `BUYER`, `FPO_ADMIN` |
| `/api/v1/vehicles` | POST | `post_vehicle` | L310 | `logistics.register_vehicle` | `FPO_ADMIN` |
| `/api/v1/vehicles` | GET | `get_vehicles` | L320 | `logistics.list_vehicles` | `FPO_ADMIN`, `DRIVER` |
| `/api/v1/shipments` | POST | `post_shipment` | L328 | `logistics.create_shipment` | `FPO_ADMIN` |
| `/api/v1/shipments/{id}` | GET | `get_single_shipment` | L338 | `logistics.get_shipment` | `FPO_ADMIN`, `DRIVER`, `BUYER` |
| `/api/v1/shipments` | GET | `get_all_shipments` | L345 | `logistics.list_shipments` | `FPO_ADMIN`, `DRIVER`, `BUYER` |
| `/api/v1/shipments/{id}/pickup` | POST | `post_shipment_pickup` | L353 | `logistics.record_pickup` | `DRIVER` |
| `/api/v1/shipments/{id}/delivery` | POST | `post_shipment_delivery` | L361 | `logistics.record_delivery` | `DRIVER` |
| `/api/v1/logistics/routes/verify` | POST | `verify_logistics_route` | L370 | `algorithms.OfflineRoadGraphProvider` | `FPO_ADMIN`, `DRIVER` |
| `/api/v1/risk/scan` | POST | `post_risk_scan` | L381 | `risk.scan_risk_incidents` | `FPO_ADMIN`, `SYSTEM` |
| `/api/v1/risk/incidents` | GET | `get_risk_incidents` | L390 | `risk.list_incidents` | `FPO_ADMIN` |
| `/api/v1/risk/incidents/{id}/acknowledge` | POST | `post_acknowledge_incident` | L398 | `risk.acknowledge_incident` | `FPO_ADMIN` |
| `/api/v1/risk/incidents/{id}/resolve` | POST | `post_resolve_incident` | L406 | `risk.resolve_incident` | `FPO_ADMIN` |
| `/api/v1/recovery/plans/generate` | POST | `post_generate_recovery_plan` | L416 | `recovery.generate_recovery_plan` | `FPO_ADMIN` |
| `/api/v1/recovery/plans/{id}` | GET | `get_single_recovery_plan` | L425 | `recovery.get_recovery_plan` | `FPO_ADMIN`, `BUYER` |
| `/api/v1/recovery/plans` | GET | `get_all_recovery_plans` | L432 | `recovery.list_recovery_plans` | `FPO_ADMIN`, `BUYER` |
| `/api/v1/recovery/plans/{id}/buyer-confirm` | POST | `post_confirm_recovery_by_buyer` | L440 | `recovery.confirm_recovery_by_buyer` | `BUYER` |
| `/api/v1/recovery/plans/{id}/approve` | POST | `post_approve_recovery_plan` | L448 | `recovery.approve_recovery_plan` | `FPO_ADMIN` |
| `/api/v1/settlements/generate` | POST | `post_generate_settlement` | L458 | `settlement.generate_settlement` | `FPO_ADMIN` |
| `/api/v1/settlements/{id}` | GET | `get_single_settlement` | L467 | `settlement.get_settlement` | `FPO_ADMIN`, `BUYER`, `FARMER` |
| `/api/v1/settlements` | GET | `get_all_settlements` | L474 | `settlement.list_settlements` | `FPO_ADMIN`, `BUYER`, `FARMER` |
| `/api/v1/settlements/{id}/payments` | POST | `post_record_payment` | L482 | `settlement.record_payment` | `BUYER` |
| `/api/v1/settlements/{id}/report-payment` | POST | `post_report_payment` | L492 | `settlement.report_payment` | `BUYER` |
| `/api/v1/settlements/{id}/payments/{pid}/verify` | POST | `post_verify_payment` | L502 | `settlement.verify_payment` | `FPO_ADMIN` |
| `/api/v1/movements` | GET | `get_all_movements` | L514 | `inventory.record_movement` | `FPO_ADMIN` |
| `/api/v1/lots/{id}/movements` | GET | `get_lot_movements` | L520 | `inventory.record_movement` | `FPO_ADMIN`, `FARMER` |
| `/api/v1/overview/farmer` | GET | `get_farmer_overview_route` | L529 | `overview.get_farmer_overview` | `FARMER` |
| `/api/v1/overview/buyer` | GET | `get_buyer_overview_route` | L536 | `overview.get_buyer_overview` | `BUYER` |
| `/api/v1/overview/driver` | GET | `get_driver_overview_route` | L543 | `overview.get_driver_overview` | `DRIVER` |
| `/api/v1/overview/fpo` | GET | `get_fpo_overview_route` | L550 | `overview.get_fpo_overview` | `FPO_ADMIN` |
| `/api/v1/sync/reconcile` | POST | `post_reconcile_sync` | L558 | `sync.reconcile_offline_command` | Any authenticated actor |
| `/api/v1/export/data` | GET | `get_export_data` | L569 | Store Dump | `FPO_ADMIN` |
| `/api/v1/lots/receipt` | POST | `post_lot_receipt` | L583 | `inventory.receive_inventory_lot` | `FPO_ADMIN` |
| `/api/v1/lots/{id}` | GET | `get_single_lot` | L593 | `inventory.get_inventory_lot` | `FPO_ADMIN`, `FARMER` |
| `/api/v1/lots` | GET | `get_all_lots` | L600 | `inventory.list_inventory_lots` | `FPO_ADMIN` |
| `/api/v1/lots/{id}/split` | POST | `post_lot_split` | L607 | `inventory.split_inventory_lot` | `FPO_ADMIN` |
| `/api/v1/lots/merge` | POST | `post_lot_merge` | L616 | `inventory.merge_inventory_lots` | `FPO_ADMIN` |
| `/api/v1/lots/{id}/grade` | POST | `post_lot_grade` | L624 | `inventory.adjust_lot_grade` | `FPO_ADMIN` |

---

## 4. Services & Domain Logic Implementation Map

| File Path | Function / Class Name | Line Ref | Component | Runtime Role |
|---|---|---|---|---|
| `gramsetu/core.py` | `Settings` | L25 | Bootstrap | Global configuration, environment variables, feature flags |
| `gramsetu/core.py` | `Role` (Enum) | L17 | Identity / Auth | Stakeholder roles: `FARMER`, `FPO_ADMIN`, `BUYER`, `DRIVER`, `SYSTEM` |
| `gramsetu/core.py` | `DEV_ACTORS` | L67 | Identity / Auth | Development mock actor map (12 static actors) |
| `gramsetu/security/identity.py` | `DevIdentityAdapter` | L31 | Identity / Auth | Evaluates `X-Dev-Actor` header in dev mode |
| `gramsetu/security/identity.py` | `JwtIdentityAdapter` | L65 | Identity / Auth | Verifies signed HMAC-SHA256 JWT tokens |
| `gramsetu/store.py` | `InMemoryStore` | L35 | Persistence | In-memory CRUD with copy-on-write deep-copies |
| `gramsetu/store.py` | `ProcessWriterLock` | L86 | Concurrency | OS file lock preventing multi-process split-brain writes |
| `gramsetu/store.py` | `TransactionCoordinator` | L140 | Persistence | Snapshot writing (`tempfile` + `fsync` + `replace`) |
| `gramsetu/algorithms.py` | `haversine_distance_km` | L14 | Logistics | Great-circle distance between coordinate pairs |
| `gramsetu/algorithms.py` | `OfflineRoadGraphProvider` | L89 | Logistics | In-memory Dijkstra shortest path solver |
| `gramsetu/algorithms.py` | `optimize_recovery_allocation` | L245 | Recovery | Greedy / branch-and-bound candidate requirement allocator |
| `gramsetu/services/supply.py` | `create_harvest_forecast` | L10 | Farmer Supply | Validates & records farmer harvest forecast |
| `gramsetu/services/procurement.py` | `create_buyer_requirement` | L28 | Buyer Demand | Records buyer purchase demand with price ceilings |
| `gramsetu/services/procurement.py` | `compute_demand_gap` | L97 | Market / Demand | Aggregates demand vs harvest forecasts (Arithmetic sum) |
| `gramsetu/services/procurement.py` | `create_commitment` | L177 | CommitGuard | Atomically allocates uncommitted physical stock to buyer |
| `gramsetu/services/procurement.py` | `cancel_commitment` | L290 | CommitGuard | Releases reserved stock back to eligible physical pool |
| `gramsetu/services/inventory.py` | `receive_inventory_lot` | L65 | BatchTrace | Creates physical lot upon warehouse receipt |
| `gramsetu/services/inventory.py` | `split_inventory_lot` | L165 | BatchTrace | Divides lot with strict mass conservation |
| `gramsetu/services/inventory.py` | `merge_inventory_lots` | L260 | BatchTrace | Combines identical crop/grade lots with mass conservation |
| `gramsetu/services/inventory.py` | `adjust_lot_grade` | L350 | BatchTrace | Adjusts lot quality grade with auditable movement |
| `gramsetu/services/logistics.py` | `register_vehicle` | L26 | Logistics | Registers transport vehicle to FPO fleet |
| `gramsetu/services/logistics.py` | `create_shipment` | L77 | Logistics | Binds vehicle, driver, and commitment into active shipment |
| `gramsetu/services/logistics.py` | `record_pickup` | L134 | Logistics | Transitions shipment to `IN_TRANSIT` |
| `gramsetu/services/logistics.py` | `record_delivery` | L202 | Logistics | Records accepted/rejected mass; transitions lot to `DELIVERED` |
| `gramsetu/services/risk.py` | `scan_risk_incidents` | L33 | RiskWatch | Scans for shelf-life expiry, delivery rejections, shortfalls |
| `gramsetu/services/recovery.py` | `generate_recovery_plan` | L45 | RecoveryOpt | Invokes `optimize_recovery_allocation` for distressed produce |
| `gramsetu/services/settlement.py` | `generate_settlement` | L29 | SettleTrack | Computes `gross - deductions = net_payable` for accepted mass |
| `gramsetu/services/settlement.py` | `record_payment` | L100 | SettleTrack | Direct buyer payment recording with balance update |
| `gramsetu/services/settlement.py` | `report_payment` | L186 | SettleTrack | Self-reported buyer payment (pending FPO verification) |
| `gramsetu/services/settlement.py` | `verify_payment` | L263 | SettleTrack | FPO verification of reported payment against proof |
| `gramsetu/adapters/evidence.py` | `EvidenceManager` | L35 | Audit / Evidence | Computes SHA-256 digests of weighbridge slips and UTR slips |
| `gramsetu/workers.py` | `LocalEventDispatcher` | L12 | Event Sourcing | In-process cursor-based durable event processor |

---

## 5. Machine Learning, Training & Inference Discovery

### Critical Finding: ZERO Machine Learning Models in Repository
A thorough search across all files, extensions (`.pkl`, `.joblib`, `.onnx`, `.pt`, `.h5`), and AST import trees confirms:
1. **No ML Frameworks Installed or Imported**: There are **zero** references to `scikit-learn`, `PyTorch`, `TensorFlow`, `LightGBM`, `XGBoost`, `CatBoost`, `Statsmodels`, or `Prophet` in `pyproject.toml` or `gramsetu/`.
2. **No Model Training Scripts**: There are no training pipelines, loss functions, validation splits, or hyperparameter configs.
3. **No Stored Model Artifacts**: No serialised weights or model binaries exist anywhere in the repository.
4. **"AI" Components are Rule-Based Algorithms**:
   - `DemandSync`: Implemented as an exact arithmetic difference: $\text{Deficit} = \sum\text{Demand} - \sum\text{Forecast}$.
   - `RiskWatch`: Implemented as a set of static `if-else` heuristic rules checking shelf-life days and delivery rejection mass.
   - `RecoveryOpt`: Implemented as a deterministic branch-and-bound / greedy knapsack algorithm in `gramsetu/algorithms.py`.
5. **Missing `MarketIntelligenceService`**: The price forecasting model referenced in `ARCHITECTURE.md` (Component B) does not exist in code. In `data_dictionary.csv`, the table `price_forecasts` is declared with 10 columns, but has **0 records** in `gramsetu_all_records.csv` and has no corresponding backend service.

---

## 6. Dataset Directories & Persisted Assets

The repository contains two distinct dataset structures:

### Structure A: Legacy GramSetu v2.2 Consolidated Package (Root)
- `gramsetu_all_records.csv`: **8,321 rows** across **42 tables** stored in a denormalized schema (`table_name`, `record_id`, `data_class`, `record_source_url`, `record_json`).
  - `SYNTHETIC_TEST_FIXTURE`: 8,174 rows (98.23%).
  - `THIRD_PARTY_ADMIN_REFERENCE`: 84 rows (1.01%).
  - `SECONDARY_PRICE_REFERENCE`: 63 rows (0.76%).
- `data_dictionary.csv`: **463 attribute definitions** across **44 tables**. Two tables (`market_arrivals` and `price_forecasts`) exist in the dictionary but have 0 records in `gramsetu_all_records.csv`.
- `correction_change_log.csv`: **1,408 records** documenting modifications made to synthetic timestamps and delivery ETAs during a prior validation run.
- `independent_validation.json`: Summary metadata recording `verdict: "PASS_INTERNAL_STRUCTURE_ONLY"`.

### Structure B: Canonical Data Ecosystem (`data/`)
- `data/verified/`: 12 verified reference CSV files (97 rows).
- `data/operator_confirmed/`: 4 operational master registries (12 rows).
- `data/derived/`: 2 analytical summary CSV files (8 rows).
- `data/synthetic_test/`: 3 isolated test fixture CSV files (6 rows).
- `data/quarantine/`: 0 files.
- `data/verified_canonical_bundle.json`: Structured snapshot export of verified and operator confirmed entities.
- `INGESTION_PIPELINE/manifest.json`: SHA-256 cryptographic manifests for all 16 canonical CSV files.

---

## 7. Configuration & Environment Variables

Defined in `gramsetu/core.py` (`Settings` class):
- `ENVIRONMENT`: `development` | `staging` | `production` (default: `development`)
- `APP_NAME`: `GramSetu AI Backend`
- `APP_VERSION`: `2.0.0`
- `SNAPSHOT_PATH`: Optional path to persistent JSON snapshot.
- `LOCK_FILE_PATH`: Path to single-writer lock file (default: `gramsetu.lock`).
- `DEV_AUTH_ENABLED`: Boolean enabling `X-Dev-Actor` header authentication (default: `True` in dev).
- `JWT_SECRET_KEY`: HMAC secret for token verification.
- `JWT_ALGORITHM`: `HS256`.
- `MAX_RECOVERY_CANDIDATES`: Optimizer pool ceiling (default: `200`).
- `RECOVERY_TIME_BUDGET_MS`: Optimizer execution timeout (default: `200.0` ms).

---

## 8. Test Suite Organization

Total **27 test files** across 4 directories:
1. `tests/`: 15 core functional contract tests (F0–F13) + `conftest.py` (128 passing tests).
2. `tests/hardening/`: 6 hardening tests (concurrency, process locking, adversarial route verification).
3. `tests/validation/`: 4 gate validation test suites.
4. `VALIDATION_TESTS/`: 2 data engineering quality suites:
   - `test_data_quality_10_layers.py`: 10 automated layer tests.
   - `test_data_scenarios.py`: 5 operational scenario tests (A through E).

---

## 9. Architectural Blockers & Disconnected Assets Summary

1. **Disconnected Dataset Package**: `gramsetu_all_records.csv` (8,321 records) is completely unread by the backend runtime.
2. **Missing Market Intelligence Module**: No service or API exists to ingest, serve, or forecast APMC prices.
3. **Empty Cold Boot**: Server startup without an explicit snapshot starts with 0 records in all collections.
4. **Synthetic Saturation**: 98.23% of records in the v2.2 baseline are synthetic simulation records, unsuitable for real-world dispatch or banking execution.
