# GramSetu AI — Initial Repository & Architectural Baseline Audit

**Audit Date:** 2026-11-22  
**Role:** Principal Software Architect & Quality Auditor  
**Branch:** `refactor/architecture-pipeline-hardening`  
**Execution Environment:** Windows 11 Enterprise, Python 3.11.9, Pytest 9.1.1  
**Baseline Test Result:** **183 Passed, 1 Warning, 0 Failures** (Execution time: 13.14s)

---

## 1. Executive Summary

This document establishes the pre-refactoring baseline for the GramSetu AI platform. The system currently functions as a database-free, single-process FastAPI backend implementing agricultural supply chain workflows (F0–F13 contracts, Phase 3 units, Phase 4 MLOps safety, Phase 5 readiness, and Phase 6 shadow pilot gates).

While the application passes 100% of its 183 regression tests, the codebase exhibits substantial architectural debt:
1. **Monolithic Application Factory:** `gramsetu/main.py` (673 lines) defines all 25+ API endpoints inline inside a single `create_app` function rather than utilizing modular FastAPI `APIRouter` components.
2. **Duplicated Modules:** `pipeline.py` exists at both the root level and within `gramsetu/pipeline.py` with identical SHA-256 hashes (`6439ea4a...`).
3. **Mixed Component Responsibilities:** `gramsetu/core.py` bundles environment configuration, Pydantic settings, exception hierarchies, mock dev actors, and security adapters into a single file.
4. **Scattered Ingestion Paths:** Data ingestion logic is split between `gramsetu/acquisition.py`, `gramsetu/release.py`, `gramsetu/pipeline.py`, and legacy `INGESTION_PIPELINE/loaders.py`.
5. **Algorithmic Coupling:** `gramsetu/algorithms.py` bundles GIS Haversine calculations, Dijkstra road network traversal, recovery action heuristics, and LP optimization models.

---

## 2. Baseline Test Execution Evidence

The initial baseline execution verified the operational integrity of the test suite:
- **Command:** `python -m pytest tests/ VALIDATION_TESTS/ -q`
- **Output:**
  ```
  ........................................................................ [ 39%]
  ........................................................................ [ 78%]
  .......................................                                  [100%]
  ============================== warnings summary ===============================
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  183 passed, 1 warning in 13.14s
  ```
- **Exit Status:** `0` (Success).
- **Test Inventory Breakdown:**
  - `tests/test_bootstrap.py`: 25 tests (F0 bootstrap, atomic copy-on-write snapshotting, single-writer lock)
  - `tests/test_durable_events.py`: 15 tests (F12 domain events journal append and ordering)
  - `tests/test_final_acceptance.py`: 32 tests (F1–F11 business workflows)
  - `tests/test_phase3_contracts.py`: 41 tests (integer mass/price units, half-up rounding, release staging)
  - `tests/test_phase4_mlops.py`: 35 tests (provenance, temporal lags, training refusal, safe inference)
  - `tests/test_phase5_readiness.py`: 8 tests (truthful readiness checks, proxy coordinates, road limits)
  - `tests/test_phase6_contracts.py`: 7 tests (archive reconciliation, unknown bridge constraints, shadow safety)
  - `VALIDATION_TESTS/test_validation_suite.py`: 20 tests (adversarial concurrency, corrupted snapshot recovery)

---

## 3. Structural Discovery & Inventory

### A. Core Backend Modules (`gramsetu/`)
| Module Path | Lines | Primary Responsibilities | Refactoring Assessment |
| :--- | :--- | :--- | :--- |
| `gramsetu/main.py` | 673 | App factory, inline route definitions, state binding | **Critical Refactor:** Split into modular API routers (`gramsetu/api/v1/`). |
| `gramsetu/core.py` | 275 | Settings, Environment enum, exceptions, dev actors | **High:** Separate into `core/config.py`, `core/exceptions.py`, `core/security.py`. |
| `gramsetu/store.py` | 280 | `InMemoryStore`, `TransactionCoordinator`, locking | **Medium:** Move to `infrastructure/persistence/`, preserve re-exports. |
| `gramsetu/units.py` | 266 | Strict decimal-to-integer conversion, half-up rounding | **Keep/Refactor:** Move to `core/units.py`, preserve exact math. |
| `gramsetu/release.py` | 530 | ZIP verification, sandbox seeding, readiness reporting | **High:** Separate ingestion staging from readiness reporting. |
| `gramsetu/acquisition.py` | 225 | Immutable raw byte capture, SHA-256 logging | **Medium:** Move to `ingestion/acquisition.py`. |
| `gramsetu/pipeline.py` | 329 | Canonical data contracts, temporal lags, gated training | **High:** Split into `ml/features.py`, `ml/training.py`, `ml/evaluation.py`. |
| `gramsetu/algorithms.py` | 397 | Distance, Dijkstra routing, recovery candidate heuristics | **High:** Split into `optimization/routing.py`, `optimization/recovery.py`. |
| `gramsetu/schemas.py` | 510 | Pydantic DTOs with `extra="forbid"` | **Medium:** Distribute by domain into `api/schemas/`. |
| `gramsetu/services/` | 1,450 | Domain services (inventory, logistics, settlement, etc.) | **Medium:** Decouple from HTTP concerns; verify single-responsibility. |

### B. Redundant & Outdated Files
- `pipeline.py` (root level): Exact duplicate of `gramsetu/pipeline.py`. Can be safely deleted after confirming root imports.
- `INGESTION_PIPELINE/`: Legacy exploratory ingestion scripts (`ingest_all.py`, `loaders.py`). To be preserved or encapsulated in `scripts/`.
- Root-level CSV logs from Phase 0–5: To be organized into respective documentation/reporting directories.

---

## 4. Architectural Target & Refactoring Strategy

To transform the repository into a production-grade, maintainable architecture while maintaining 100% test compatibility:
1. **Package Reorganization:**
   - `gramsetu/api/` — Versioned endpoints (`v1/`), dependency injection providers.
   - `gramsetu/core/` — Unified configuration, security, constants, unit contracts.
   - `gramsetu/domain/` — Business entities, domain events, invariants.
   - `gramsetu/services/` — Clean application use cases.
   - `gramsetu/infrastructure/` — In-memory store, atomic JSON snapshotting, writer locking.
   - `gramsetu/ingestion/` — Release validation, acquisition, quarantine, and loaders.
   - `gramsetu/ml/` — Temporal feature engineering, training gates, model evaluation.
   - `gramsetu/optimization/` — Routable graph algorithms and recovery solvers.
   - `gramsetu/readiness/` — System readiness and operational gate evaluation.
2. **Backward-Compatibility Layer:**
   - Existing modules (`gramsetu/main.py`, `gramsetu/core.py`, `gramsetu/store.py`, `gramsetu/units.py`, `gramsetu/release.py`, `gramsetu/pipeline.py`, `gramsetu/algorithms.py`, `gramsetu/schemas.py`) will maintain clean re-exports of all public symbols so that existing tests and external consumers never break.
3. **Zero Invariant Deviation:**
   - Database-free single process architecture strictly preserved.
   - Atomic copy-on-write persistence (`.tmp` $\to$ `fsync` $\to$ `replace`) strictly preserved.
   - Integer unit contracts and half-up rounding strictly preserved.
