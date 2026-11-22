# GramSetu AI — Phase 3 Architecture & Baseline Specification
**Milestone:** Dataset-to-Backend Integration and Unit Contract Hardening  
**Dataset Baseline:** GramSetu v2.2.0 (`GramSetu_All_Corrected_CSV_v2_2.zip`)  
**Release Pin:** `2.2.0`  
**Execution Timestamp:** 2026-11-22T02:54:00+05:30  

---

## 1. Zero-Database Architecture & Runtime Invariants

GramSetu AI is engineered strictly as a **database-free, single-process, highly resilient agricultural supply chain platform**.

### Core Storage & Concurrency Guarantees
1. **In-Memory Primary State (`InMemoryStore`)**:
   - All operational domain entities (`forecasts`, `requirements`, `lots`, `movements`, `commitments`, `vehicles`, `shipments`, `settlements`, `incidents`, `recovery_plans`, `events`) reside in memory as high-performance structured Python dictionaries.
   - Deep-copy read isolation: All read operations (`get_item`, `list_items`) return deep copies to prevent external mutations from corrupting internal store memory.
2. **Atomic Copy-on-Write Snapshotting**:
   - Persistence is achieved via atomic JSON snapshots written to disk.
   - Write protocol: Write to temporary file (`.tmp`) -> force OS cache flush (`os.fsync`) -> atomic file rename (`os.replace`).
   - Zero partially written, torn, or corrupted snapshots can ever replace the durable snapshot file.
3. **Transaction Coordinator & Concurrency Protection (`TransactionCoordinator`)**:
   - Atomic transactions with automatic rollback: In-memory store state is snapshotted in memory prior to yielding to the transaction context. If any exception occurs during processing, in-memory state is restored instantly to the pre-transaction baseline and snapshot disk writes are aborted.
   - Single-writer synchronization: Thread reentrancy is governed by `threading.RLock()`.
   - OS-level multi-process lock (`ProcessWriterLock` via `portalocker` / file-locking): Guarantees that only a single operating system process can write to the persistent snapshot path at any given time.
4. **Architectural Prohibitions**:
   - Zero SQL engines (PostgreSQL, SQLite, MySQL, MariaDB, Oracle).
   - Zero Object-Relational Mappers (SQLAlchemy, Tortoise, Peewee).
   - Zero external key-value caches or message brokers (Redis, Memcached, Celery, RabbitMQ, Kafka).
   - Zero distributed microservices: GramSetu AI executes entirely as a self-contained monolith.

---

## 2. Physical & Logical Store Separation: Sandbox vs Production

A foundational requirement of Phase 3 is ensuring that **synthetic fixture datasets can never contaminate a live production agricultural deployment**.

```
+-----------------------------------------------------------------------------------+
|                            API REQUEST / CLI INVOCATION                           |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
                         +---------------------------------+
                         |  Environment Gatekeeper Check   |
                         +----------------+----------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
      ENVIRONMENT == "production"                       ENVIRONMENT == "sandbox" / "testing"
                |                                                   |
                v                                                   v
+-------------------------------+               +---------------------------------------+
|  FAIL-CLOSED PRODUCTION GATE  |               |  ALLOW_SYNTHETIC_SEED == True Check   |
|                               |               +-------------------+-------------------+
|  Rejects ANY synthetic seed   |                                   |
|  attempt with HTTP 403.       |                  +----------------+----------------+
|  Zero fixture rows imported.  |                  |                                 |
+-------------------------------+             SEED DENIED                       SEED GRANTED
                                           (ALLOW_SYNTHETIC_SEED=False)      (ALLOW_SYNTHETIC_SEED=True)
                                                   |                                 |
                                                   v                                 v
                                    +------------------------------+ +-------------------------------+
                                    | 403 Forbidden / Denied       | | Staged SHA-256 Byte Hash      |
                                    | Fixture seed flag disabled.  | | & Schema Verification         |
                                    +------------------------------+ +---------------+---------------+
                                                                                     |
                                                                                     v
                                                                     +-------------------------------+
                                                                     | Atomic Multi-Table Import     |
                                                                     | 8,321 Records Loaded to RAM   |
                                                                     | Explicit Unavailable Markers  |
                                                                     +-------------------------------+
```

### Safety Contracts Enforced
1. **Production Gating**:
   - When `ENVIRONMENT=production`, all attempts to invoke `POST /api/v1/admin/import/sandbox-release` or seed synthetic fixtures fail immediately with `403 FORBIDDEN`.
   - Overriding `ALLOW_SYNTHETIC_SEED=True` is explicitly rejected if `ENVIRONMENT=production`.
2. **Explicit Opt-in in Sandbox**:
   - In `sandbox`, `development`, or `testing` environments, synthetic seeding is only permitted when `ALLOW_SYNTHETIC_SEED=True` is explicitly configured.
3. **Data Provenance Labelling**:
   - All records seeded from the release package carry release markers and audit metadata in `store.set_item("evidence", ...)` with `trust_classification="VALIDATED_RELEASE_STRUCTURE_SANDBOX_ONLY"`.

---

## 3. Dataset Baseline Inventory (v2.2.0)

- **Source Archive**: `GramSetu_All_Corrected_CSV_v2_2.zip`
- **Release Version**: `2.2.0`
- **Normalized Tables**: 44 CSV files under `csv/`
- **Total Records**: 8,321 records
- **Data Dictionary & Manifest**: Verified against `manifest.json` and `file_hashes_sha256.json`.
- **Preflight Compatibility**: Fully verified and compliant with standalone `gramsetu_phase3_adapter.py`.
