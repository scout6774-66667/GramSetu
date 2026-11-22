# GramSetu AI — Pre-Flight Baseline Audit (R0)
**Audit Date**: 2026-11-17T19:07:00+05:30  
**Environment**: Windows 11 Enterprise (AMD64), Python 3.11.9  
**Git Status**: Not a git repository (standalone project directory)  
**Baseline Test Suite**: 92 passed, 1 warning in 5.21s  

---

## 1. Runtime & Environment Inventory

- **Operating System**: Windows 11 Enterprise (10.0.26100)
- **Python**: 3.11.9 (`C:\Users\ABIR SAHA\AppData\Local\Programs\Python\Python311\python.exe`)
- **Key Installed Packages**:
  - `fastapi == 0.141.1`
  - `pydantic == 2.13.5`
  - `uvicorn == 0.52.4`
  - `pytest == 9.1.1`
  - `starlette == 1.6.0`
- **Application Factory**: `gramsetu.main:create_app()`
- **Registered Endpoints**: 55 operational endpoints under `/api/v1/` and documentation routes (`/health`, `/docs`, `/openapi.json`, `/redoc`)
- **Forbidden Database / Broker Scan**:
  - SQLite, PostgreSQL, MySQL, MongoDB, Redis, Celery: **None detected**.
  - Single-process in-memory store with atomic JSON snapshot files (`data/state.json`).

---

## 2. Source Code Fingerprint Baseline (SHA-256)

```
da6cdc8349b47ded  gramsetu/algorithms.py
9c69681e8f75a48e  gramsetu/core.py
088a238786d3acce  gramsetu/main.py
7ca480a9d3e29476  gramsetu/schemas.py
44b308600f65165e  gramsetu/services/events.py
19034e789d9f3017  gramsetu/services/inventory.py
91053b11e1374154  gramsetu/services/logistics.py
81ccd8f7d8ea808a  gramsetu/services/overview.py
8f913106a5429456  gramsetu/services/procurement.py
5f9f6983592d2079  gramsetu/services/recovery.py
1ac7c02fe67fcbe0  gramsetu/services/risk.py
3014187a9706a848  gramsetu/services/settlement.py
ea84d681f76305a3  gramsetu/services/supply.py
88317287b6cc7b97  gramsetu/services/sync.py
f0c9c38c6f603a00  gramsetu/store.py
cd2f2599444ff68c  gramsetu/workers.py
```

---

## 3. Initial Test Suite Execution Evidence

- **Command**: `python -m pytest -q`
- **Exit Status**: 0 (Clean pass)
- **Output**:
  ```
  92 passed, 1 warning in 5.21s
  ```
- **Test Composition**:
  - 58 baseline regression tests in `tests/test_*.py`
  - 34 independent validation tests in `tests/validation/test_val_*.py`
  - 0 failed, 0 skipped.

---

## 4. Known Hardening Targets (R1 - R5)

1. **R1**: `RecoveryOpt` candidate bounding (`[:8]`) truncation creates potential sub-optimality when $>8$ buyers exist. Need formal branch-and-bound / combinatorial optimizer with provable optimality flags.
2. **R2**: `TransactionCoordinator` relies on in-memory `threading.RLock`, which is not multi-process safe. Need OS-level exclusive process file lock (`msvcrt` on Windows / `fcntl` on Unix) to prevent multi-worker startup collisions.
3. **R3**: Identity verification uses development `X-Dev-Actor`. Need production-ready pluggable JWT identity adapter with cryptographic verification, algorithm pinning, and fail-closed security.
4. **R4**: Logistics assumes straight-line Haversine and constant 40 km/h speed. Need `TravelMatrixProvider` with directed road network graph, road restrictions, weight limits, and Dijkstra shortest path search.
5. **R5**: Financial payments and weighbridge records lack cryptographic provenance and tamper-evident digests. Need `PaymentEvidenceProvider` and `WeightEvidenceProvider` with distinct trust states (`REPORTED`, `OPERATOR_CONFIRMED`, `EXTERNALLY_VERIFIED`).
