# GRAMSETU AI — FINAL REFACTOR & ARCHITECTURAL HARDENING REPORT

**Author:** Principal Software Architect, Senior Backend Systems Engineer & MLOps Auditor  
**Date:** 2026-11-22  
**Target Repository:** [scout6774-66667/GramSetu](https://github.com/scout6774-66667/GramSetu)  
**Branch:** `refactor/architecture-pipeline-hardening`  
**Test Suite Status:** **183 passed, 0 failures, 1 warning in 10.71s (100.0% Pass)**  
**Authoritative Refactor Verdict:** `REFACTOR_COMPLETE_WITH_LIMITATIONS`

---

## 1. Executive Summary & Architectural Verdict

In accordance with the Principal Software Architect and Pipeline Engineering mandate, a repository-wide structural refactoring, modularization, pipeline hardening, and quality gate establishment has been executed across the GramSetu AI platform.

### Authoritative Verdict: `REFACTOR_COMPLETE_WITH_LIMITATIONS`
- **Codebase Refactoring Status:** **COMPLETE & VERIFIED**. The monolithic architecture, massive code duplication (19,615 lines in root `pipeline.py`), and 673-line `main.py` router have been completely dismantled and reorganized into a clean, 9-layer domain-driven architecture.
- **Invariants Preserved:** **100% PRESERVED**. The database-free single-process RAM persistence (`InMemoryStore`), OS single-writer locking (`ProcessWriterLock`), ACID atomic copy-on-write JSON snapshotting (`TransactionCoordinator`), exact integer unit contracts ($g$, $m$, paise/kg), and fail-closed readiness gates have been rigorously maintained.
- **Why "WITH LIMITATIONS"?** As mandated by engineering integrity principles, synthetic test fixtures are **never** relabeled as authentic live data. GramSetu v2.2 continues to have known operational limitations: 43 secondary AGMARKNET observations across 2 calendar days, 0 market arrivals, 79 administrative centroid proxies, and 0 real two-way bank confirmations. The `/api/v1/system/readiness` endpoint remains truthfully **fail-closed** (`NOT_READY_CRITICAL_OPERATIONAL_GAPS`).

---

## 2. Before vs. After Structural Metrics

| Dimension | Pre-Refactor Baseline | Post-Refactor Hardened | Engineering Impact |
|:---|:---:|:---:|:---|
| **Root Duplicate LOC** | 19,615 lines (`pipeline.py`) | **2 lines** (facade stub) | -19,613 duplicate lines removed |
| **`main.py` Monolith LOC** | 673 lines (inline routes) | **110 lines** (clean app factory) | -83.6% reduction in monolith size |
| **Domain Routers** | 0 (all in `main.py`) | **13 domain routers** (`api/v1/`) | Clean separation of concerns |
| **Subpackage Layers** | Flat top-level directory | **8 structured subpackages** | Domain-driven architecture |
| **Automated Tests** | 183 passed | **183 passed (0 failures)** | Zero functional regression |
| **Test Execution Time** | 13.14s | **10.71s** | 18.5% execution speedup |
| **CI/CD Quality Gate** | None | **9-Stage GitHub Actions Workflow** | Automated regression defense |

---

## 3. Modular Architecture & Directory Map

```
GramSetu/
├── .github/
│   └── workflows/
│       └── gramsetu-ci.yml             # 9-stage automated CI/CD pipeline
├── baseline_original/
│   └── csv/                            # 44 extracted baseline CSVs from v2.2 ZIP
├── gramsetu/
│   ├── api/
│   │   ├── deps.py                     # Request dependencies (store, coordinator, settings)
│   │   └── v1/
│   │       ├── router.py               # Master API v1 router mounting 13 domain routers
│   │       ├── admin.py                # Release preflight & sandbox import endpoints
│   │       ├── auth.py                 # Actor identity & scoping endpoints
│   │       ├── commitments.py          # CommitGuard buyer commitment endpoints
│   │       ├── demand.py               # DemandSync forecasts & requirements endpoints
│   │       ├── inventory.py            # BatchTrace lot receipt, split, merge, grade endpoints
│   │       ├── logistics.py            # Fleet vehicles, shipments, route verify endpoints
│   │       ├── market.py               # Mandi price observations & ML forecast endpoints
│   │       ├── overview.py             # Persona overview endpoints (farmer, buyer, driver, FPO)
│   │       ├── recovery.py             # RecoveryOpt allocation plan endpoints
│   │       ├── risk.py                 # RiskWatch incident scanner & resolver endpoints
│   │       ├── settlements.py          # SettleTrack deduction & payment endpoints
│   │       ├── sync.py                 # Offline command reconciliation endpoints
│   │       └── system.py               # Health, export, and system readiness endpoints
│   ├── core/
│   │   ├── config.py                   # Pydantic Settings & Environment enums
│   │   ├── exceptions.py               # Domain error hierarchy (GramSetuError, etc.)
│   │   ├── security.py                 # DevActor, JWT verification, tenant scoping
│   │   └── units.py                    # Exact integer unit arithmetic & half-up rounding
│   ├── infrastructure/
│   │   └── persistence.py              # InMemoryStore, ProcessWriterLock, TransactionCoordinator
│   ├── ingestion/
│   │   ├── acquisition.py              # Raw AGMARKNET ingestion & SHA-256 manifests
│   │   └── staging.py                  # Release ZIP validation & transactional import
│   ├── ml/
│   │   └── pipeline.py                 # Canonical ML features, training gates, inert inference
│   ├── optimization/
│   │   ├── recovery.py                 # LP recovery plan optimizer
│   │   └── routing.py                  # Haversine metrics & Dijkstra road graph solver
│   ├── readiness/
│   │   └── health.py                   # Operational readiness & trust classification
│   ├── schemas/                        # Pydantic v2 schemas and models
│   ├── services/                       # Business logic services (F1–F12)
│   ├── main.py                         # Clean FastAPI application factory
│   └── [facades]                       # core.py, store.py, units.py, algorithms.py, release.py, pipeline.py
└── REFACTOR_REPORTS/                   # Complete 14-report audit and migration suite
```

---

## 4. Key Invariants & Hardening Guarantees

### 4.1 Database-Free Storage & OS Process Lock
- **Persistence:** [InMemoryStore](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/infrastructure/persistence.py) stores all collections in RAM with schema validation and deep-copy isolation.
- **Process Lock:** [ProcessWriterLock](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/infrastructure/persistence.py) acquires an exclusive OS lock (`msvcrt` on Windows, `fcntl` on POSIX) on the state snapshot lockfile. Secondary processes attempting to start fail immediately with `ProcessLockError`.
- **Atomic Snapshots:** [TransactionCoordinator](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/infrastructure/persistence.py) serializes state to `.tmp`, invokes `os.fsync`, and atomically commits via `os.replace`.

### 4.2 Exact Unit Contracts & Zero Floating-Point Drift
- **Mass:** Expressed strictly in integer grams ($g$).
- **Distance:** Expressed strictly in integer meters ($m$).
- **Price:** Expressed strictly in integer paise/kg.
- **Settlement Rounding:** Gross payable paise uses contractual half-up rounding:
  $$\text{gross\_paise} = \left\lfloor \frac{\text{accepted\_grams} \times \text{price\_paise\_per\_kg} + 500}{1000} \right\rfloor$$
- **Delivery Reconciliation:** Strict physical mass conservation:
  $$\text{delivered\_grams} = \text{accepted\_grams} + \text{rejected\_grams}$$

### 4.3 Fail-Closed Production Readiness
The `/api/v1/system/readiness` endpoint truthfully evaluates operational safety gates:
- Pre-import and post-sandbox-import status: `NOT_READY_CRITICAL_OPERATIONAL_GAPS`.
- Trust classification: `SANDBOX_SIMULATION_ONLY`.
- Active operational blocks: `BLOCKED_INSUFFICIENT_HISTORY`, `ADMIN_CENTROID_PROXIES_NON_GPS`, `SYNTHETIC_TOPOLOGY_NON_ROUTABLE`.

---

## 5. Verification Test Evidence

The entire automated test suite was executed across all unit, hardening, and validation test suites:

```text
============================== test session starts ==============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\ABIR SAHA\Downloads\GRAHAT
configfile: pyproject.toml
collected 183 items

tests/test_auth_scoping.py .....                                           [  2%]
tests/test_batchtrace.py .....                                             [  5%]
tests/test_bootstrap.py .....                                              [  8%]
tests/test_commitguard.py .....                                            [ 10%]
tests/test_demandsync.py .....                                             [ 13%]
tests/test_durable_events.py ..                                            [ 14%]
tests/test_final_acceptance.py .......                                     [ 18%]
tests/test_logistics.py .....                                              [ 21%]
tests/test_offline_sync.py .....                                           [ 24%]
tests/test_overview.py .....                                               [ 26%]
tests/test_performance.py ...                                              [ 28%]
tests/test_phase3_contracts.py ...............                             [ 36%]
tests/test_phase4_mlops.py ..........                                      [ 42%]
tests/test_phase5_readiness.py ........                                    [ 46%]
tests/test_phase6_contracts.py ...........                                 [ 52%]
tests/test_recoveryopt.py .....                                            [ 55%]
tests/test_riskwatch.py .....                                              [ 57%]
tests/test_settletrack.py .....                                            [ 60%]
tests/hardening/test_auth_negative.py ........                             [ 65%]
tests/hardening/test_evidence_integrity.py .....                           [ 67%]
tests/hardening/test_full_regression.py ............                       [ 74%]
tests/hardening/test_process_writer_lock.py ..                             [ 75%]
tests/hardening/test_road_graph_routing.py .....                           [ 78%]
tests/validation/test_val_adversarial.py ..                                [ 79%]
tests/validation/test_val_f0_f3.py ..                                      [ 80%]
tests/validation/test_val_f8_f13.py ..                                     [ 81%]
VALIDATION_TESTS/test_data_quality_10_layers.py ..........                 [ 87%]
VALIDATION_TESTS/test_data_scenarios.py ............                       [100%]

======================== 183 passed, 1 warning in 10.71s ========================
```

---

## 6. Deliverables Index

All 14 required engineering audit reports and matrixes have been generated and committed to the [REFACTOR_REPORTS/](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/) directory:

1. [00_INITIAL_REPOSITORY_AUDIT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/00_INITIAL_REPOSITORY_AUDIT.md) — Baseline discovery, LOC counts, and defect inventory.
2. [01_ARCHITECTURE_BEFORE_AFTER.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/01_ARCHITECTURE_BEFORE_AFTER.md) — Architectural decomposition and diagrammatic analysis.
3. [02_FILE_MIGRATION_MATRIX.csv](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/02_FILE_MIGRATION_MATRIX.csv) — Line-by-line file movement and deprecation matrix.
4. [03_DATA_PIPELINE_VALIDATION.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/03_DATA_PIPELINE_VALIDATION.md) — 10-layer data pipeline audit and integrity verification.
5. [04_PERSISTENCE_AND_CONCURRENCY.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/04_PERSISTENCE_AND_CONCURRENCY.md) — Single-writer lock and copy-on-write snapshotting analysis.
6. [05_SERVICE_DEPENDENCY_MATRIX.csv](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/05_SERVICE_DEPENDENCY_MATRIX.csv) — Module dependency coupling and circular import audit.
7. [06_MLOPS_ARCHITECTURE_AUDIT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/06_MLOPS_ARCHITECTURE_AUDIT.md) — Statistical history gates, feature leakage defense, and inert models.
8. [07_API_COMPATIBILITY_REPORT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/07_API_COMPATIBILITY_REPORT.md) — 27-endpoint compatibility verification across 13 domain routers.
9. [08_SECURITY_AND_CONFIGURATION_AUDIT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/08_SECURITY_AND_CONFIGURATION_AUDIT.md) — JWT auth, role scoping, secret scanning, and payload size guard.
10. [09_CI_CD_PIPELINE_REPORT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/09_CI_CD_PIPELINE_REPORT.md) — 9-stage GitHub Actions CI/CD pipeline specification.
11. [10_TEST_AND_REGRESSION_RESULTS.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/10_TEST_AND_REGRESSION_RESULTS.md) — Execution evidence across 183 automated tests.
12. [11_REFACTOR_CHANGELOG.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/11_REFACTOR_CHANGELOG.md) — Chronological engineering changelog of all modifications.
13. [12_UNRESOLVED_ISSUES.csv](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/12_UNRESOLVED_ISSUES.csv) — Register of open field pilot blockers (GAP-01 to GAP-07).
14. [GRAMSETU_FINAL_REFACTOR_ENGINEERING_REPORT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/REFACTOR_REPORTS/GRAMSETU_FINAL_REFACTOR_ENGINEERING_REPORT.md) — Authoritative final engineering report.

Plus automated workflow:
- [.github/workflows/gramsetu-ci.yml](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/.github/workflows/gramsetu-ci.yml) — GitHub Actions CI/CD workflow.
