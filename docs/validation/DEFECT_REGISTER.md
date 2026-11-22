# GramSetu AI — Defect Register
**Assessment Mode**: `AUDIT_AND_REPAIR` | **Total Defects Logged**: 4 | **Fixed**: 4 | **Open**: 0

---

## Defect Summary

| Defect ID | Feature | Severity | Component | Summary | Status |
| :---: | :---: | :---: | :--- | :--- | :---: |
| **VAL-001** | F1 | **P1 / BLOCKER** | `gramsetu/core.py` | `X-Dev-Actor` accepted in `Environment.PRODUCTION` without authentication failure | **FIXED** |
| **VAL-002** | F7 | **P1 / BLOCKER** | `gramsetu/services/recovery.py` | Negative net-return candidates permitted and recommended in recovery plans | **FIXED** |
| **VAL-003** | F7 | **P1 / BLOCKER** | `gramsetu/services/recovery.py` | Defaulting/cancelling buyer was not excluded from recovery candidates | **FIXED** |
| **VAL-004** | F3 | **P0 / STOP** | `gramsetu/services/inventory.py` | Consumed parent/source lots retained quantity grams upon split and merge | **FIXED** |

---

## Detailed Defect Entries

### VAL-001: Dev Actor Header Accepted in Production Environment
- **Feature**: F1 — Identity / Authorization
- **Severity**: P1 / BLOCKER
- **Impacted Components**: `gramsetu/core.py::get_current_actor`
- **Impacted Apps**: All 4 frontend applications (security boundary)
- **Reproduction**:
  ```python
  app = create_app(Settings(ENVIRONMENT=Environment.PRODUCTION))
  client = TestClient(app)
  resp = client.get("/api/v1/forecasts", headers={"X-Dev-Actor": "fpo-admin-alpha"})
  assert resp.status_code == 401  # Failed: returned 200 OK
  ```
- **Root Cause Hypothesis**: `get_current_actor` inspected `request.headers` and matched `actor_id in DEV_ACTORS` without checking if `request.app.state.settings.ENVIRONMENT == Environment.PRODUCTION`.
- **Minimal Correct Fix**:
  In `gramsetu/core.py`: check `app_settings.settings.ENVIRONMENT == Environment.PRODUCTION`. If so, raise `GramSetuError(status_code=401, error_code="UNAUTHORIZED", message="Production authentication error: X-Dev-Actor test adapter is prohibited in production.")`.
- **Regression Test**: `tests/validation/test_val_f0_f3.py::test_f1_production_environment_fails_closed_against_x_dev_actor`
- **Result**: **FIXED & VERIFIED**.

---

### VAL-002: Negative Net-Return Candidates Permitted in Recovery Plans
- **Feature**: F7 — RecoveryOpt
- **Severity**: P1 / BLOCKER
- **Impacted Components**: `gramsetu/services/recovery.py::generate_recovery_plan`
- **Impacted Apps**: FPO Control Tower, Buyer App
- **Reproduction**:
  ```python
  # Lot of 1,000g; buyer offers 10 paise/g -> gross = 10,000 paise.
  # Transport cost to buyer-local is 75,000 paise -> net return = -65,000 paise.
  plan = generate_recovery_plan(store, coord, admin, inc_id)
  assert plan.status == "NO_FEASIBLE_OPTION"  # Failed: returned RECOMMENDED
  ```
- **Root Cause Hypothesis**: Candidate evaluation calculated `net = gross - transport` but did not filter candidates where `net <= 0`. As a result, loss-making alternatives were presented as recommended recovery plans.
- **Minimal Correct Fix**:
  In `gramsetu/services/recovery.py`: added `if net <= 0: continue`. If all candidates are non-positive, `candidates` is empty, yielding `status = "NO_FEASIBLE_OPTION"` and `recommended_candidate = None`.
- **Regression Test**: `tests/validation/test_val_f4_f7.py::test_f7_recovery_negative_net_return_rejected`
- **Result**: **FIXED & VERIFIED**.

---

### VAL-003: Original Defaulting Buyer Not Excluded From Recovery Search
- **Feature**: F7 — RecoveryOpt
- **Severity**: P1 / BLOCKER
- **Impacted Components**: `gramsetu/services/recovery.py::generate_recovery_plan`
- **Impacted Apps**: FPO Control Tower
- **Reproduction**:
  ```python
  # Buyer Reliance cancels commitment com-1; incident inc-cancel-1 created.
  plan = generate_recovery_plan(store, coord, admin, "inc-cancel-1")
  assert "buyer-reliance" not in [c.buyer_id for c in plan.candidates]  # Failed: Reliance included
  ```
- **Root Cause Hypothesis**: `generate_recovery_plan` fetched all open requirements matching crop and grade without inspecting the underlying commitment or shipment to identify the defaulting buyer who triggered the cancellation.
- **Minimal Correct Fix**:
  In `gramsetu/services/recovery.py`: extract `cancelled_buyer_id` from the affected commitment/shipment and skip requirements where `r.get("buyer_id") == cancelled_buyer_id`.
- **Regression Test**: `tests/validation/test_val_f4_f7.py::test_f7_recovery_original_cancelled_buyer_excluded`
- **Result**: **FIXED & VERIFIED**.

---

### VAL-004: Split and Merged Source Lots Retained Quantity Grams (Produce Duplication)
- **Feature**: F3 — BatchTrace / Inventory Ledger
- **Severity**: P0 / STOP
- **Impacted Components**: `gramsetu/services/inventory.py::split_inventory_lot`, `merge_inventory_lots`
- **Impacted Apps**: Farmer App, FPO Control Tower
- **Reproduction**:
  ```python
  # Lot of 1,000,000g split into 400,000g and 600,000g.
  parent = store.get_item("lots", parent_id)
  assert parent["quantity_grams"] == 0  # Failed: returned 1,000,000g
  ```
- **Root Cause Hypothesis**: `split_inventory_lot` set `parent["status"] = "SPLIT"` and `merge_inventory_lots` set `source["status"] = "MERGED"`, but neither zeroed out `quantity_grams` or `reserved_grams` on the retired records. This allowed physical mass to be counted twice when inspecting lot entities.
- **Minimal Correct Fix**:
  In `gramsetu/services/inventory.py`:
  - When splitting: set `parent["quantity_grams"] = 0` and `parent["reserved_grams"] = 0`.
  - When merging: set each `s["quantity_grams"] = 0` and `s["reserved_grams"] = 0`.
- **Regression Test**: `tests/validation/test_val_f0_f3.py::test_f3_split_and_merge_mass_conservation`
- **Result**: **FIXED & VERIFIED**.
