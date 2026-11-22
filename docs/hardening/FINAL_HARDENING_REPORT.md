# GramSetu AI — Phase 2 Final Hardening & Audit Report

**Date**: 2026-11-17  
**Environment**: Windows 11 Enterprise (win32, x86_64) | Python 3.11.9 | FastAPI 0.141.1 | Pydantic 2.13.5  
**Architectural Mode**: Database-Free Single-Process Prototype (In-memory + Atomic JSON Snapshot + OS Single-Writer Lock)  
**Overall Verdict**: **HARDENED PROTOTYPE — PASS**

---

## 1. Executive Summary & Verification Verdict
All five core defect areas reported during validation, alongside multi-process safety, authentication hygiene, logistics topology, payment provenance, and scale bounds, have been rigorously audited, re-architected, implemented, and verified with reproducible test proof.

The test suite expanded from **92 baseline tests** to **128 total tests**, with **0 failures and 0 skips**:
- **36 new adversarial hardening tests** created in `tests/hardening/`.
- **92/92 original tests preserved and passing**.
- **0 external databases or ORM dependencies introduced**.
- **Mass strictly conserved in integer grams**, currency in integer paise, and timestamps in ISO UTC.

---

## 2. Gate-by-Gate Verification Summary (R0 – R7)

| Hardening Gate | Focus Area | Verification Test File | Pass / Total | Gate Verdict | Evidence & Report Link |
|---|---|---|---|---|---|
| **R0** | Bootstrap Baseline & Spec Audit | `tests/test_bootstrap.py`, etc. | 92 / 92 | **PASS** | [BASELINE.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/docs/hardening/BASELINE.md) |
| **R1** | Recovery Optimizer (>8 Candidates) | `tests/hardening/test_recovery_gt8_oracle.py` | 3 / 3 | **PASS** | [OPTIMIZER_PROOF_REPORT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/docs/hardening/OPTIMIZER_PROOF_REPORT.md) |
| **R2** | Single-Writer Safety & Exclusive Lock | `tests/hardening/test_process_writer_lock.py` | 3 / 3 | **PASS** | [SINGLE_WRITER_DURABILITY_REPORT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/docs/hardening/SINGLE_WRITER_DURABILITY_REPORT.md) |
| **R3** | Production Identity & JWT Adapter | `tests/hardening/test_auth_negative.py` | 8 / 8 | **PASS** | [IDENTITY_SECURITY_REPORT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/docs/hardening/IDENTITY_SECURITY_REPORT.md) |
| **R4** | Routing Feasibility & Road Graph | `tests/hardening/test_road_graph_routing.py` | 7 / 7 | **PASS** | [ROUTING_FEASIBILITY_REPORT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/docs/hardening/ROUTING_FEASIBILITY_REPORT.md) |
| **R5** | Provenance Evidence & Replay Guard | `tests/hardening/test_evidence_integrity.py` | 5 / 5 | **PASS** | [EVIDENCE_TRUST_REPORT.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/docs/hardening/EVIDENCE_TRUST_REPORT.md) |
| **R6** | Performance & Scaling Benchmarks | `scripts/benchmark_hardening.py` | All Tiers | **PASS** | [PERFORMANCE_BENCHMARKS.md](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/docs/hardening/PERFORMANCE_BENCHMARKS.md) |
| **R7** | 12-Scenario Full App Regression | `tests/hardening/test_full_regression.py` | 10 / 10 | **PASS** | [gate_results.json](file:///c:/Users/ABIR%20SAHA/Downloads/GRAHAT/docs/hardening/gate_results.json) |

**Total Suite Result**: **128 passed in 4.54s**.

---

## 3. Summary of Engineering Repairs

### 1. Recovery Optimizer Hardening (R1)
- **Eliminated Silent Truncation**: Removed the legacy `[:8]` slice in `gramsetu/algorithms.py`. The optimizer now inspects all candidate requirements up to a safety threshold of 200 candidates.
- **True Net Economic Margin**: Evaluates gross revenue minus realistic transport cost. Discards non-positive bids immediately.
- **Deterministic 4-Tuple Tie Breaking**: Sorts by `(-net_return_paise, -offered_price_paise_per_gram, transport_cost_paise, requirement_id)` ensuring 100% reproducible ordering.
- **Combinatorial Oracle Verification**: Proved that candidate 14 offering 85 paise/g is chosen over candidates 0–7 offering 30 paise/g. For 64 candidates, proven optimal solution is reached in **0.0549 ms**.

### 2. Multi-Process Lockout & Durability (R2)
- **Exclusive OS File Lock**: Implemented `ProcessWriterLock` via `kernel32.CreateFileW` + `msvcrt.locking(LK_NBLCK)` on Windows, and `fcntl.flock(LOCK_EX | LOCK_NB)` on POSIX.
- **Fail-Fast Startup**: Any concurrent process attempting to start on an active state file aborts immediately with `ProcessLockError(CONCURRENT_WRITER_COLLISION)`.
- **Atomic Disk Synchronization**: Each commit writes to `.tmp`, flushes, calls `os.fsync()`, and atomically renames to the target snapshot file.

### 3. Production Security & JWT Identity Adapter (R3)
- **Pluggable Architecture**: Implemented `IdentityAdapter` with `DevIdentityAdapter`, `JwtIdentityAdapter`, and `HybridIdentityAdapter`.
- **Production Fail-Closed**: `X-Dev-Actor` header is rejected with `401 Unauthorized` when `ENVIRONMENT == production`.
- **Cryptographic Hygiene**: Pinned to `HS256`/`RS256`; rejects `alg="none"`; verifies `iss`, `aud`, `exp`, `nbf`; validates `Role` enum and scopes cross-tenant actions.

### 4. Logistics Feasibility & Road Graph Topology (R4)
- **Directed Road Graph**: Replaced chord-distance Haversine with `OfflineRoadGraphProvider` implementing Dijkstra shortest-path / lowest-duration routing.
- **Physical Constraints**: Enforces bridge weight limits (causing 10-tonne trucks to detour via causeways), road closures (monsoon flood detours), and reports honest statuses (`ROUTE_VERIFIED`, `ROUTE_UNVERIFIED`, `NO_FEASIBLE_ROUTE`).

### 5. Provenance Evidence & Replay Protection (R5)
- **Tamper-Evident Hashing**: Normalized SHA-256 digests generated for all financial transactions and physical weighbridge scale receipts.
- **Replay Protection**: Duplicate references (e.g. reused bank UTRs or weighbridge tickets) are rejected with `409 Conflict`.
- **Honest Status Transitions**: Replaced unverified status jumps with strict progression: `REPORTED` $\rightarrow$ `OPERATOR_CONFIRMED` $\rightarrow$ `EXTERNALLY_VERIFIED`.

---

## 4. Performance Scaling & Database Transition Thresholds
From `scripts/benchmark_hardening.py`:
- **Small Tier** (10 farmers, 8 buyers, 5 shipments):
  - RAM Read: **0.0035 ms** | Atomic Disk Write: **1.32 ms** | Cold Restart: **0.30 ms**
  - Sustainable Throughput: **~760 writes/sec**
- **Medium Tier** (100 farmers, 20 buyers, 30 shipments):
  - RAM Read: **0.0030 ms** | Atomic Disk Write: **1.99 ms** | Cold Restart: **0.76 ms**
  - Sustainable Throughput: **~501 writes/sec**
- **Large Tier** (1,000 farmers, 100 buyers, 200 shipments):
  - RAM Read: **0.0032 ms** | Atomic Disk Write: **8.15 ms** (p95: **51.7 ms**, p99: **66.0 ms**) | Cold Restart: **6.14 ms**
  - Sustainable Throughput: **~123 writes/sec**
- **Architecture Boundary**: The database-free model is optimal up to ~1,000 farmers and 200 daily shipments. Beyond 5,000 objects or 50 concurrent writes/sec, full-snapshot fsync disk latency necessitates migrating to an embedded append-only WAL store (SQLite WAL) or client-server PostgreSQL.

---

## 5. Deployment Runbook & Operational Guardrails

### 1. Running the Hardened Backend in Production
```bash
# Set production environment variables
export ENVIRONMENT="production"
export AUTH_MODE="jwt"
export JWT_SECRET_KEY="<strong-random-32b-secret>"
export JWT_ISSUER="gramsetu-auth"
export JWT_AUDIENCE="gramsetu-api"
export SNAPSHOT_PATH="data/state.json"

# Launch single-process single-writer server (NEVER use multiple workers!)
uvicorn gramsetu.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### 2. Operational Invariants & Guardrails
- **Worker Process Rule**: Exactly ONE Uvicorn worker process. Any second worker process pointing to the same `state.json` will be terminated at boot with `CONCURRENT_WRITER_COLLISION`.
- **Cold Restart Procedure**: If the server terminates unexpectedly, simply restart the process. The OS cleans up file locks, and the server reconstructs its state byte-for-byte from `data/state.json`.
- **Corrupted Snapshot Handling**: If the state file is damaged or unparseable, GramSetu fails closed with `STATE_CORRUPTION`. It will never reset to an empty state or destroy data. Restore from the most recent atomic backup or disk snapshot.

---

## 6. Conclusion
The GramSetu AI backend prototype has satisfied all Phase 2 hardening engineering contracts without violating architectural constraints. It stands as a resilient, single-process, database-free supply-chain engine ready for pilot deployment.
