# GramSetu AI — Performance, Reliability & Scalability Report
**Benchmark Date**: 2026-11-17 | **Hardware**: Intel/AMD x86_64, Windows 11 Enterprise | **Python**: 3.11.9

---

## 1. Latency & Throughput Profile

Measured across 1,000 in-memory read operations, 500 route metric estimates, and 100 atomic copy-on-write snapshot operations:

| Operation Type | Dataset Size | p50 Latency | p95 Latency | p99 Latency | Engineering SLA | Compliance Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **In-Memory Store Item Read** | 1,000 Lots | **0.0016 ms** | **0.0018 ms** | **0.0028 ms** | $< 1.0\text{ ms}$ | **EXCEEDED (550x headroom)** |
| **Route & Capacity Estimator** | 500 Queries | **0.0016 ms** | **0.0020 ms** | **0.0102 ms** | $< 10.0\text{ ms}$ | **EXCEEDED (5000x headroom)** |
| **Atomic Snapshot Persistence** | 1,000 entities (79.9 KB) | **7.81 ms** | **8.56 ms** | **18.12 ms** | $< 50.0\text{ ms}$ | **COMPLIANT** |
| **Recovery Optimizer Execution** | 8 Candidates | **0.0084 ms** | **0.0112 ms** | **0.0165 ms** | $< 20.0\text{ ms}$ | **EXCEEDED** |

---

## 2. Resource Utilization & Growth Characterization

### Snapshot File Scaling
- **100 Entities**: $\approx 7.2\text{ KB}$ JSON payload ($\approx 4.5\text{ ms}$ fsync duration)
- **1,000 Entities**: $\approx 79.9\text{ KB}$ JSON payload ($\approx 8.5\text{ ms}$ fsync duration)
- **5,000 Entities**: $\approx 412.0\text{ KB}$ JSON payload ($\approx 32.0\text{ ms}$ fsync duration)

### Memory Footprint
- Single Uvicorn process memory: $\approx 42\text{ MB}$ baseline RSS at startup.
- Peak memory under 5,000 simulated domain objects: $\approx 64\text{ MB}$ RSS.

---

## 3. Algorithm Bounds & Known Limitations

1. **Recovery Optimizer Candidate Bounding**:
   - To guarantee sub-millisecond API response times and bounded memory usage, `RecoveryOpt` caps the evaluated buyer requirement pool to at most **8 candidates** (`bounded_reqs = valid_reqs[:8]`).
   - *Limitation*: In scenarios where $> 8$ open requirements exist for the same crop and grade, taking the first 8 could exclude a higher-paying 9th buyer unless requirements are pre-sorted by net price. In production, pre-filtering by offered price is recommended.
2. **Single-Worker Concurrency Limit**:
   - Memory store locking (`threading.RLock`) protects multi-threaded operations within a single process.
   - *Limitation*: Running multiple Uvicorn workers (`--workers > 1`) will cause independent memory states and disk write conflicts, as file replacement lacks cross-process locking. Maximum 1 worker is supported.
3. **Logistics Road Estimation**:
   - Haversine distance uses great-circle spherical geometry, assuming an average speed of 40 km/h.
   - *Limitation*: Does not account for road topology, ferry crossings, monsoon washouts, or vehicle weight-restricted bridges. Suitable only as a provisional planning estimator.
