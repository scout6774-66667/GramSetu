# GramSetu AI — Performance & Scaling Benchmark Report

## 1. Executive Summary
This report documents the performance, latency distribution (p50, p95, p99), and throughput limits of the hardened GramSetu AI backend prototype. All measurements were collected on Windows 11 Enterprise using Python 3.11.9, running against the actual repository algorithms and atomic JSON persistence coordinator via `scripts/benchmark_hardening.py`.

---

## 2. Benchmark Environment & Methodology
- **Platform**: Windows 11 Enterprise (win32, x86_64)
- **Runtime**: Python 3.11.9, FastAPI 0.141.1, Pydantic 2.13.5
- **Storage**: Zero external database. In-memory dictionary state with atomic JSON file persistence (`write() + fsync() + os.replace()`).
- **Locking**: Exclusive OS process lock (`ProcessWriterLock` via `msvcrt.locking` on Windows).
- **Execution Script**: `scripts/benchmark_hardening.py`
- **Output Artifact**: `docs/hardening/benchmark_metrics.json`

---

## 3. Workload Scaling Results

### Tier 1: Small Workload (10 Farmers, 8 Buyers, 5 Shipments)
- Total Store Objects: 23 objects
- Snapshot Size: 6.1 KB
- Write Latency (Atomic disk fsync):
  - p50: **1.32 ms**
  - p95: **1.52 ms**
  - p99: **1.52 ms**
- Read Latency (In-memory lookup):
  - p50: **0.0035 ms** (3.5 microseconds)
  - p95: **0.0114 ms**
- Cold Restart Reconstruction (Snapshot parse & hydrate):
  - p50: **0.30 ms**
- Practical Throughput Limit: **~760 writes/second**

---

### Tier 2: Medium Workload (100 Farmers, 20 Buyers, 30 Shipments)
- Total Store Objects: 150 objects
- Snapshot Size: 38.7 KB
- Write Latency (Atomic disk fsync):
  - p50: **1.99 ms**
  - p95: **2.88 ms**
  - p99: **3.49 ms**
- Read Latency (In-memory lookup):
  - p50: **0.0030 ms**
  - p95: **0.0035 ms**
- Cold Restart Reconstruction (Snapshot parse & hydrate):
  - p50: **0.76 ms**
- Practical Throughput Limit: **~501 writes/second**

---

### Tier 3: Large Workload (1,000 Farmers, 100 Buyers, 200 Shipments)
- Total Store Objects: 1,300 objects
- Snapshot Size: 335.0 KB
- Write Latency (Atomic disk fsync):
  - p50: **8.15 ms**
  - p95: **51.72 ms**
  - p99: **65.98 ms**
- Read Latency (In-memory lookup):
  - p50: **0.0032 ms** (3.2 microseconds)
  - p95: **0.0042 ms**
- Cold Restart Reconstruction (Snapshot parse & hydrate):
  - p50: **6.14 ms**
- Practical Throughput Limit: **~123 writes/second**

---

## 4. Algorithm & Engine Latencies

### Recovery Optimizer Candidate Pool Scaling
Tested across 50 iterations with net-margin evaluation, positive filter, and 4-tuple deterministic tie-breaking:

| Candidate Count | p50 Runtime (ms) | p95 Runtime (ms) | p99 Runtime (ms) | Solved Status |
|---|---|---|---|---|
| **8 candidates** | 0.0078 | 0.0205 | 1.3883 | `OPTIMAL_PROVEN` |
| **16 candidates** | 0.0141 | 0.0188 | 0.0205 | `OPTIMAL_PROVEN` |
| **32 candidates** | 0.0281 | 0.0318 | 0.0747 | `OPTIMAL_PROVEN` |
| **64 candidates** | 0.0549 | 0.0626 | 0.0733 | `OPTIMAL_PROVEN` |

### Logistics Road Graph Dijkstra Routing
Tested across 500 shortest-duration path queries over the 7-node rural network:
- p50: **0.0044 ms** (4.4 microseconds)
- p95: **0.0064 ms**
- p99: **0.0104 ms**

---

## 5. Architectural Ceiling & Transition Analysis
1. **Linear Degradation on Full-State Snapshots**:
   Notice that while in-memory read latency remains completely flat (~3 microseconds) across all tiers, transaction write latency increases from 1.32 ms (p50) at 10 farmers to 8.15 ms (p50) and 65.98 ms (p99) at 1,000 farmers. This is the direct cost of serializing the entire 335 KB JSON document on every committed transaction and calling `os.fsync()`.
2. **Database Transition Point**:
   - For rural FPO deployments operating with $\le$ 1,000 farmers and 200 daily shipments, the database-free prototype achieves **123 writes/sec** and sub-10ms p50 latency, easily satisfying rural operational requirements.
   - If an FPO cluster scales beyond **5,000 active physical lots** (~1.5 MB state file) or requires more than **50 concurrent writes/second**, transitioning from full JSON snapshots to an embedded WAL database (such as SQLite with WAL mode) or PostgreSQL is architecturally mandatory to avoid fsync latency spikes.
