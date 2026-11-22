# GramSetu AI — Phase 5 Baseline Environment & Security Audit

**Audit Timestamp:** 2026-11-22T10:48:00Z  
**Audit Phase:** Phase 5 (Authentic Source Integration & Field-Validation Readiness)  
**System Architecture:** Database-Free Single-Process FastAPI + In-Memory Store + Copy-on-Write Atomic JSON Snapshots  
**Overall Verdict:** `SANDBOX_RESEARCH_HARDENED / PRODUCTION_BLOCKED`

---

## 1. Execution Environment & Dependencies

| Component | Specification / Version | Verification State |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 Enterprise (64-bit, x86_64) | Active Workspace Environment |
| **Python Runtime** | Python 3.11.9 (`C:\Users\ABIR SAHA\AppData\Local\Programs\Python\Python311\python.exe`) | Verified Native Executable |
| **Web Framework** | FastAPI 0.115.x / Starlette 0.41.x | Verified Async ASGI Stack |
| **Data Validation** | Pydantic v2 (Strict Schema Validation, `extra="forbid"`) | Active Schema Boundary |
| **Test Runner** | Pytest 9.1.1 + AnyIO 4.15.1 | Full Suite: 176 Passed, 0 Failures |
| **Serialization** | Standard Library `json` + Atomic `tempfile` + `os.replace` + `os.fsync` | Single-Writer Hardened |
| **Concurrency Control**| Process-level OS File Locking (`ProcessWriterLock` via `msvcrt.locking`) | Verified Single-Writer |

---

## 2. Baseline Release Archive Integrity

- **Archive File:** `GramSetu_All_Corrected_CSV_v2_2.zip`
- **File Size:** 1,531,946 bytes (1.46 MB)
- **SHA-256 Checksum:** `03c5b81267ba2b9c0369f283786b7381e6acd56f18eff1b2ed18f1d344d6344c`
- **Manifest Version:** `2.2.0`
- **Declared Tables:** 44 normalized CSV tables
- **Declared Total Records:** 8,321 records
- **Hash Integrity Check:** 100% of the 44 CSV files exactly match their cryptographic SHA-256 entries in `file_hashes_sha256.json`.
- **Primary Key Uniqueness:** Verified across all 44 tables without collision.
- **Foreign Key Referential Integrity:** Verified across all tables; optional foreign keys handle legitimate blanks.

---

## 3. Database-Free Architectural Invariants

1. **Zero Database Engine:**
   - No relational database (PostgreSQL, MySQL, SQLite), NoSQL database (MongoDB), object-relational mapper (SQLAlchemy, Tortoise), caching server (Redis), or task queue broker (Celery, RabbitMQ) is installed, imported, or executed.
   - The runtime state is maintained exclusively in `InMemoryStore` inside single-process memory.

2. **Single-Writer Process Lock:**
   - Every mutating request and snapshot persistence operation acquires `ProcessWriterLock` backed by OS-level file locking (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX).
   - Multi-process write contention is prevented; lock acquisition failures return explicit `423 Locked` responses.

3. **Atomic Copy-on-Write Durability:**
   - Persistence is achieved via copy-on-write snapshotting: the store serializes its deep copy to a unique temporary file (`.tmp`), calls `os.fsync` on the file descriptor to force physical flush to disk, and executes atomic file replacement (`os.replace`).
   - If the process or OS crashes mid-write, the existing snapshot remains uncorrupted.

4. **Rollback on Exception:**
   - `TransactionCoordinator.mutate` executes mutations against a cloned deep copy of the collection dictionary. If a business logic exception or constraint validation fails, the mutation is abandoned, RAM remains completely untouched, and disk snapshots are not updated.

---

## 4. Security & Identity Boundary Audit

| Security Domain | Implementation Policy | Production Enforcement |
| :--- | :--- | :--- |
| **Development Authentication** | `X-Dev-Actor` header mapped to `DEV_ACTORS` dictionary | **Strictly Forbidden in Production**: Returns `401 Unauthorized` if attempted when `ENVIRONMENT=production`. |
| **Production Authentication** | Signed JWT Bearer tokens verified against `JWT_SECRET_KEY` with algorithm `HS256` | **Mandatory in Production**: Requires valid token containing `sub` (actor_id), `role`, and valid expiry `exp`. |
| **Release Seeding Protection** | Sandbox seed endpoint `POST /api/v1/admin/import/sandbox-release` | **Blocked in Production**: Requires `ALLOW_SYNTHETIC_SEED=True`. Returns `403 Forbidden` in production mode. |
| **Forecasting Safety Lock** | Predictive pricing endpoint `/api/v1/market/forecasts` | **Refused in Production**: Unreviewed research models cannot serve predictions in production mode (`403 Refused`). |
| **Data Schema Tampering** | Pydantic Request/Response DTOs | **Forbidden Extras**: All schemas enforce `model_config = ConfigDict(extra="forbid")` to prevent prototype pollution. |

---

## 5. Security Scan Findings & Verdict

- **Hardcoded Secret Scan:** Clean. No AWS, Google Cloud, banking API tokens, or production private keys found in repo.
- **SQL / Command Injection:** Zero risk. Zero SQL queries exist; shell commands are not invoked by runtime application logic.
- **Production Readiness State:** **`PRODUCTION_BLOCKED`**. While the code and infrastructure are hardened against concurrency bugs, corruption, and unauthorized access, the system cannot be deployed to real agricultural operations due to critical operational data gaps (unverified market feeds, centroid coordinates, synthetic road edges, and simulated bank settlements).
