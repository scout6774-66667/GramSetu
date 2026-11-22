# GramSetu AI — Hardening Risk Matrix (R0 - R7)
**Status**: IN_PROGRESS | **Review Cycle**: Phase 2 Engineering Hardening

---

## 1. Risk Evaluation & Impact Mapping

| Risk ID | Domain / Feature | Severity | Problem Statement | Affected Components | Mitigation & Target Architecture |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **R1** | F7 RecoveryOpt | **P1 / BLOCKER** | Silent 8-candidate truncation (`[:8]`) may miss optimal recovery buyers when $>8$ candidates exist. | `gramsetu/algorithms.py`, `gramsetu/services/recovery.py` | Implement complete branch-and-bound / combinatorial optimizer with explicit optimality statuses (`OPTIMAL_PROVEN`, `FEASIBLE_NOT_PROVEN_OPTIMAL`, `NO_POSITIVE_NET_OPTION`). |
| **R2** | F0 / Store Durability | **P1 / BLOCKER** | In-process `threading.RLock` is not multiprocess-safe; dual Uvicorn worker starts could corrupt state. | `gramsetu/store.py`, `gramsetu/main.py` | Add OS-enforced exclusive process file lock (`msvcrt` on Windows, `fcntl` on Linux) to fail startup immediately if a second writer starts. |
| **R3** | F1 Identity & Auth | **P1 / BLOCKER** | Only development mock header `X-Dev-Actor` exists; no production token verification adapter. | `gramsetu/core.py`, `gramsetu/security/` | Implement pluggable `IdentityAdapter` with `JwtIdentityAdapter` verifying signature, pinned algorithms, audience, expiry, and tenant claims. |
| **R4** | F5 Logistics | **P2 / MAJOR** | Pure Haversine distance with 40 km/h constant speed ignores road topologies, closures, and load limits. | `gramsetu/algorithms.py`, `gramsetu/services/logistics.py` | Define `TravelMatrixProvider` interface; implement directed graph with Dijkstra search, bridge/seasonal closures, weight limits, and route statuses. |
| **R5** | F8 SettleTrack | **P1 / BLOCKER** | Payments and weighbridge records lack tamper-evident provenance digests and distinct trust levels. | `gramsetu/services/settlement.py`, `gramsetu/schemas.py` | Introduce SHA-256 payload digests, immutable evidence records, and distinct status tiers (`REPORTED`, `OPERATOR_CONFIRMED`, `EXTERNALLY_VERIFIED`). |
| **R6** | F12 Performance & Scaling | **P2 / MAJOR** | Need benchmark evidence under realistic multi-tenant loads (100–1,000 farmers, 20–100 buyers). | `scripts/benchmark_hardening.py` | Implement end-to-end multi-tenant stress benchmark measuring p50/p95/p99 across dataset tiers. |
| **R7** | F13 Final Acceptance | **P0 / CRITICAL** | Risk of regressions across the 14 core features and 4 application user journeys during hardening. | All modules | Execute full 12-scenario regression suite with randomized seeds and isolated stores. |
