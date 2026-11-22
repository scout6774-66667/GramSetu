# GramSetu AI — Single-Writer Durability & Crash Recovery Report

## 1. Executive Summary
The GramSetu AI system adheres strictly to the Zero-Database architectural invariant: in-memory state coordination with atomic JSON snapshotting. However, Phase 1 relied solely on a Python `threading.RLock`, which is completely blind to multi-process concurrency. If multiple Uvicorn worker processes or CLI processes opened the same `data/state.json`, interleaved writes would destroy state integrity without warning.

Phase 2 implemented genuine OS-level exclusive process locking, verified cold restart durability, and guaranteed fail-closed behavior on corrupted snapshots.

---

## 2. Implementation Details

### OS-Level Exclusive Process Locking (`gramsetu/store.py`)
`ProcessWriterLock` enforces exclusive single-writer ownership:
- **Windows Implementation**:
  - Uses `kernel32.CreateFileW` with flags `GENERIC_READ | GENERIC_WRITE (0xC0000000)`, sharing flags `FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE (7)`, and `OPEN_ALWAYS (4)`.
  - Applies non-blocking lock via `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)`.
  - Sharing mode `7` ensures that upon process termination or directory cleanup, temporary test directories can be unlinked without `WinError 32 PermissionError`.
- **POSIX Implementation**:
  - Uses `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)`.
- **Fail-Fast Semantics**:
  - If another process holds the lock, initialization aborts immediately with `ProcessLockError(CONCURRENT_WRITER_COLLISION)`, before reading or writing any files.
- **Graceful Shutdown**:
  - Releases lock on `.close()` and registers an `atexit` cleanup handler.

### Atomic JSON Snapshotting
Snapshot persistence uses the three-step POSIX/Windows atomic sequence:
1. Serialize state to temporary file `${snapshot_path}.tmp`.
2. Flush and force disk sync: `f.flush()` followed by `os.fsync(f.fileno())`.
3. Atomic filesystem rename: `os.replace(tmp_path, snapshot_path)`.

---

## 3. Crash Recovery & Durability Verification
1. **Dual Coordinator Lockout**:
   - `test_process_writer_lock_prevents_dual_coordinators`: Spawning a second coordinator pointing to an active lockfile immediately raises `ProcessLockError`.
2. **Cold Restart Reconstruction**:
   - `test_atomic_snapshot_cold_restart_reconstruction`: App commits records, coordinator cleanly exits, second instance starts from snapshot file and reconstructs identical in-memory dictionaries.
3. **Corrupt Snapshot Safety**:
   - `test_corrupt_snapshot_fails_closed_without_silent_reset`: If snapshot JSON contains syntax errors, truncated bytes, or missing schema headers, `load_from_snapshot()` raises `CorruptionError(STATE_CORRUPTION)` and refuses to overwrite the corrupted file with an empty state.

---

## 4. Empirical Durability Benchmarks
From `scripts/benchmark_hardening.py`:

| Workload Tier | Object Count | Snapshot File Size | Write Latency with fsync (p50) | Cold Restart Load Time (p50) |
|---|---|---|---|---|
| **Small** (10 farmers) | 23 | 6.1 KB | 1.32 ms | 0.30 ms |
| **Medium** (100 farmers) | 150 | 38.7 KB | 1.99 ms | 0.76 ms |
| **Large** (1,000 farmers) | 1,300 | 335.0 KB | 8.15 ms (p95: 51.7 ms) | 6.14 ms |

### Practical Single-Writer Throughput Bounds
- **Small workloads**: ~760 sustained commits/second.
- **Medium workloads**: ~501 sustained commits/second.
- **Large workloads**: ~123 sustained commits/second (dominated by 335 KB full-state serialization and disk fsync on Windows).
- **Scale Ceiling Boundary**: When state exceeds ~5,000 objects (~2 MB JSON) or concurrent write demands exceed 50 writes/sec, transitioning from full-state JSON snapshots to an embedded append-only SQLite/WAL or client-server PostgreSQL becomes necessary.

---

## 5. Verification Verdict
- Test suite: `tests/hardening/test_process_writer_lock.py` (3 tests passed).
- Gate status: **GATE R2 — PASS**.
