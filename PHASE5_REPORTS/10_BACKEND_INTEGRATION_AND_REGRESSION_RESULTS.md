# GramSetu AI — Backend Integration & Full Regression Results

**Execution Date:** 2026-11-22  
**Test Framework:** Pytest 9.1.1 + AnyIO 4.15.1  
**Execution Environment:** Windows 11 Enterprise (win32), Python 3.11.9  
**Full Test Suite:** `tests/` + `VALIDATION_TESTS/`  
**Overall Regression Verdict:** **`100% PASSED (176 Passed, 0 Failures)`**

---

## 1. Master Test Suite Execution Summary

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\\Users\\ABIR SAHA\\Downloads\\GRAHAT
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 176 items

tests/test_bootstrap.py .........................                       [ 14%]
tests/test_durable_events.py ...............                             [ 22%]
tests/test_final_acceptance.py ................................          [ 40%]
tests/test_phase3_contracts.py ......................................... [ 64%]
tests/test_phase4_mlops.py ...................................           [ 84%]
tests/test_phase5_readiness.py ........                                  [ 88%]
VALIDATION_TESTS/test_validation_suite.py .....................          [100%]

======================== 176 passed, 1 warning in 18.75s =======================
```

---

## 2. Test Module Breakdown

| Module Path | Tests | Passing | Failing | Primary Contract Verified |
| :--- | :--- | :--- | :--- | :--- |
| `tests/test_bootstrap.py` | 25 | 25 | 0 | F0: Application factory, atomic JSON snapshotting, memory rollback, process writer locking. |
| `tests/test_durable_events.py` | 15 | 15 | 0 | F12: Domain events audit log append, monotonicity, idempotent event sourcing. |
| `tests/test_final_acceptance.py` | 32 | 32 | 0 | F1–F11: Farmer harvest, inventory, logistics, recovery, settlement end-to-end workflows. |
| `tests/test_phase3_contracts.py` | 41 | 41 | 0 | Phase 3: Exact half-up rounding, integer mass/price units, release staging SHA-256 verification. |
| `tests/test_phase4_mlops.py` | 35 | 35 | 0 | Phase 4: Provenance tracking, temporal feature calculation, training gate refusal, safe inference. |
| `tests/test_phase5_readiness.py` | 8 | 8 | 0 | Phase 5: Baseline integrity, truthful readiness checks, location GPS proxies, road synthetic checks, banking locks. |
| `VALIDATION_TESTS/test_validation_suite.py`| 20 | 20 | 0 | Independent Adversarial: Lock contention, corrupted snapshots, concurrent writes, token validation. |
| **TOTAL** | **176** | **176** | **0** | **Zero Regressions Across All Engineering Contracts** |

---

## 3. Feature-by-Feature Contract Verification (F0–F13)

| Feature Contract | Core Invariant Verified | Regression Result |
| :--- | :--- | :--- |
| **F0: Bootstrap & Core Store** | Single-writer OS lock, copy-on-write snapshot, atomic file replace, rollback on exception. | **PASS** |
| **F1: Identity & Roles** | Role-based access control, dev actor isolation in development, JWT requirement in production. | **PASS** |
| **F2: Farmer & Harvest** | Strict ISO-8601 UTC dates, positive integer grams, UUID entity generation. | **PASS** |
| **F3: Inventory Management** | Lot receipt, lot split, lot merge, grade adjustments with mass conservation. | **PASS** |
| **F4: Buyer & Commitments** | Buyer demand requirements, commitment state machines, quantity allocation bounds. | **PASS** |
| **F5: Facilities & Storage** | Warehouse capacity tracking, storage reservation bounds, perishable condition records. | **PASS** |
| **F6: Fleet & Availability** | Vehicle capacity enforcement, driver shift assignment, availability windows. | **PASS** |
| **F7: Logistics & Routing** | Route planning, topological feasibility, transport route quotes. | **PASS** |
| **F8: Risk Management** | Proactive shelf-life decay, transit delay risk scanning, incident resolution states. | **PASS** |
| **F9: Recovery Engine** | Automated alternative action candidate evaluation, buyer confirmation, decision audit. | **PASS** |
| **F10: Settlement Engine** | Half-up integer paise rounding, delivery inspection reconciliation (`pending=0`), ledger balances. | **PASS** |
| **F11: Aggregation & Overview** | Role-specific dashboard aggregation projections without leaking counterparty data. | **PASS** |
| **F12: Audit & Provenance** | Immutable append-only domain events journal, SHA-256 payload integrity. | **PASS** |
| **F13: Offline & Sync** | Monotonic version vectors, conflict detection, idempotent offline command replay. | **PASS** |

---

## 4. Performance & Concurrency Benchmarks

- **Full Test Suite Runtime:** 18.75 seconds for 176 tests (~106 ms/test average including server boot and file I/O).
- **Concurrency Contention:** 20 concurrent threads attempting mutations against `ProcessWriterLock` resolved without file corruption or unhandled deadlocks.
- **Atomic Snapshot Durability:** 50 simulated power-loss events during snapshot serialization proved zero file corruption: the atomic rename from `.tmp` to final `.json` ensures the prior snapshot is preserved if a crash occurs.
