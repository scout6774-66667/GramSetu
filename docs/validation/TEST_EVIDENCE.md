# GramSetu AI — Test Execution Evidence & Reproducibility Log
**Validation Timestamp**: 2026-11-17T14:40:00+05:30 | **Platform**: Windows (win32) | **Python**: 3.11.9

---

## 1. Environment & Hardware Baseline

- **Operating System**: Windows 11 Enterprise (x86_64)
- **Python Version**: `Python 3.11.9 (tags/v3.11.9:de5405b, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]`
- **Core Runtime Dependencies**:
  - `fastapi == 0.141.1`
  - `pydantic == 2.13.5`
  - `pydantic_core == 2.46.5`
  - `uvicorn == 0.52.4`
  - `pytest == 9.1.1`
  - `starlette == 1.6.0`
- **Forbidden Storage Scan**:
  - `sqlite3`: NOT imported in domain services.
  - `sqlalchemy`: NOT imported in domain services.
  - `redis`: NOT imported in domain services.
  - `celery`: NOT imported in domain services.
  - `psycopg2`: NOT imported in domain services.
  - Result: **CLEAN (Zero forbidden external databases or brokers)**.
- **Specification Blocker Noted**: `docs/ENGINEERING_LOOP_PROMPT.md` is referenced in the audit prompt but not present on disk. All requirements are authoritative from `docs/FEATURE_CONTRACTS.md`, `docs/ARCHITECTURE.md`, and session prompt constraints.

---

## 2. Source Code Fingerprints (SHA-256)

```
30c5db09eed7031c  docs/ARCHITECTURE.md
cb2f6c27ce5b7c2f  docs/FEATURE_CONTRACTS.md
096506755ddfeecd  docs/IMPLEMENTATION_PROGRESS.md
99ccda99dd5b270d  gramsetu/__init__.py
da6cdc8349b47ded  gramsetu/algorithms.py
9c69681e8f75a48e  gramsetu/core.py (pre-repair) -> patched for VAL-001
088a238786d3acce  gramsetu/main.py
7ca480a9d3e29476  gramsetu/schemas.py
44b308600f65165e  gramsetu/services/events.py
19034e789d9f3017  gramsetu/services/inventory.py (pre-repair) -> patched for VAL-004
91053b11e1374154  gramsetu/services/logistics.py
81ccd8f7d8ea808a  gramsetu/services/overview.py
8f913106a5429456  gramsetu/services/procurement.py
5f9f6983592d2079  gramsetu/services/recovery.py (pre-repair) -> patched for VAL-002, VAL-003
1ac7c02fe67fcbe0  gramsetu/services/risk.py
3014187a9706a848  gramsetu/services/settlement.py
ea84d681f76305a3  gramsetu/services/supply.py
88317287b6cc7b97  gramsetu/services/sync.py
f0c9c38c6f603a00  gramsetu/store.py
cd2f2599444ff68c  gramsetu/workers.py
```

---

## 3. Test Execution Logs

### A. Baseline Regression Suite
- **Command**: `python -m pytest -q tests/`
- **Exit Code**: `0`
- **Output**:
  ```
  ..........................................................               [100%]
  58 passed, 1 warning in 3.13s
  ```

### B. Independent Validation Suite
- **Command**: `python -m pytest -q tests/validation/`
- **Exit Code**: `0`
- **Output**:
  ```
  ..................................                                       [100%]
  34 passed, 1 warning in 0.29s
  ```
- **Breakdown**:
  - `test_val_f0_f3.py`: 11 passed (F0, F1, F2, F3)
  - `test_val_f4_f7.py`: 11 passed (F4, F5, F6, F7)
  - `test_val_f8_f13.py`: 6 passed (F8, F9, F10, F11, F12)
  - `test_val_adversarial.py`: 6 passed (Stateful Property, Financial Oracle Fuzz, Fault Injection, Access Matrix, Metamorphic, Truthfulness)

### C. Combined Full Suite Verification
- **Command**: `python -m pytest -q`
- **Exit Code**: `0`
- **Duration**: `3.07s`
- **Total Tests Executed**: **92 passed, 0 failed, 1 warning**.

---

## 4. Randomized Test Reproducibility Parameters

1. **Stateful Property Test (`test_adversarial_stateful_property_invariants`)**:
   - Random Generator: `random.Random(seed=42107)`
   - Steps: 30 sequential multi-actor operations
   - Checked Invariants: $\text{reserved} \le \text{physical}$, $\text{available} \ge 0$, no negative mass
   - Outcome: **PASS (100% invariant adherence)**.
2. **Financial Oracle Fuzz Test (`test_adversarial_financial_oracle_fuzz`)**:
   - Random Generator: `random.Random(seed=999)`
   - Iterations: 50 randomized quantity/price/deduction combinations
   - Compared Against: `Decimal.quantize(Decimal('1'), rounding=ROUND_HALF_UP)`
   - Outcome: **PASS (0 discrepancies)**.
