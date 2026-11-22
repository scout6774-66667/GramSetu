# 11 — REFACTOR CHANGELOG

## GramSetu AI — Structural Engineering Changelog
**Author:** Principal Software Architect & Release Engineer  
**Date:** 2026-11-22  
**Target Milestone:** Engineering Hardening & Repository Modularization  
**Git Branch:** `refactor/architecture-pipeline-hardening`

---

## 1. Summary of Changes

### 1.1 Structural De-duplication & Pruning
- **Removed Massive Duplicate:** Replaced 19,615 lines of duplicate code in root-level [pipeline.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/pipeline.py) with a 2-line backward-compatible facade re-exporting `from gramsetu.pipeline import *`.
- **Baseline CSV Preservation:** Extracted all 44 original tables from `GramSetu_All_Corrected_CSV_v2_2.zip` into [baseline_original/csv/](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/baseline_original/csv/) for immutable baseline auditing.

### 1.2 Core Domain Modularization (`gramsetu/core/`)
- Created [gramsetu/core/config.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/core/config.py): Pydantic `Settings`, `Environment`, `Role`, and UTC timestamp utilities.
- Created [gramsetu/core/exceptions.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/core/exceptions.py): Unified exception hierarchy (`GramSetuError`, `CorruptionError`, `DomainValidationError`, `ProcessLockError`, etc.).
- Created [gramsetu/core/security.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/core/security.py): `DevActor`, role enforcement decorators, JWT verification, and scoping guards.
- Created [gramsetu/core/units.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/core/units.py): Exact integer arithmetic, half-up rounding, and mass balance validators.
- Installed backward-compatible facades at [gramsetu/core.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/core.py) and [gramsetu/units.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/units.py).

### 1.3 Infrastructure & Persistence (`gramsetu/infrastructure/`)
- Created [gramsetu/infrastructure/persistence.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/infrastructure/persistence.py):
  - `InMemoryStore`: RAM dictionary partition, deep-copy isolation, schema validation.
  - `ProcessWriterLock`: Cross-platform OS single-writer locking (`msvcrt` on Windows, `fcntl` on POSIX).
  - `TransactionCoordinator`: Copy-on-write ACID transactions with automatic rollback and atomic `.tmp` $\to$ `fsync` $\to$ `os.replace` snapshot durability. Added `close()` lifecycle cleanup.
- Installed backward-compatible facade at [gramsetu/store.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/store.py).

### 1.4 API Monolith Decomposition (`gramsetu/api/` & `gramsetu/main.py`)
- Created [gramsetu/api/deps.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/api/deps.py): FastAPI dependency providers (`get_store`, `get_coordinator`, `get_app_settings`).
- Created [gramsetu/api/v1/router.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/api/v1/router.py) and 13 domain routers under `gramsetu/api/v1/`:
  - `auth.py`, `demand.py`, `commitments.py`, `inventory.py`, `logistics.py`, `risk.py`, `recovery.py`, `settlements.py`, `overview.py`, `sync.py`, `system.py`, `admin.py`, `market.py`.
- Refactored [gramsetu/main.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/main.py): Reduced from 673 lines to 110 lines of clean application factory with middleware and exception handling.

### 1.5 Optimization, Ingestion, & ML Packages
- Created [gramsetu/optimization/](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/optimization/) (`routing.py`, `recovery.py`). Facade at [gramsetu/algorithms.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/algorithms.py).
- Created [gramsetu/ingestion/](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/ingestion/) (`staging.py`, `acquisition.py`). Facade at [gramsetu/release.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/release.py) and [gramsetu/acquisition.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/acquisition.py).
- Created [gramsetu/ml/](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/ml/) (`pipeline.py`). Facade at [gramsetu/pipeline.py](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/pipeline.py).
- Created [gramsetu/readiness/](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/gramsetu/readiness/) (`health.py`).

### 1.6 CI/CD Quality Automation
- Created [.github/workflows/gramsetu-ci.yml](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/.github/workflows/gramsetu-ci.yml): 9-stage principal engineering automated quality gate.
