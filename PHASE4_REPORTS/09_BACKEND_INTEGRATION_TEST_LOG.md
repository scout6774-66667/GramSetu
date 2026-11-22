# GramSetu AI — Backend Integration Test Log & Evidence
**Document ID:** `P4-09-INTEGRATION-LOG`  
**Execution Environment:** Python 3.11.9, pytest 9.1.1, Windows 11 Enterprise  
**Full Test Command:** `python -m pytest tests/test_phase4_mlops.py -v`  
**Suite Status:** **10 passed, 0 failed, 1 warning in 3.08s**  

---

## 1. Phase 4 Test Execution Log

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\ABIR SAHA\Downloads\GRAHAT
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 10 items

tests/test_phase4_mlops.py::test_p4_01_v2_2_baseline_audit_gate_blocks_training PASSED [ 10%]
tests/test_phase4_mlops.py::test_p4_02_raw_ingest_with_quarantine_and_sha_tracking PASSED [ 20%]
tests/test_phase4_mlops.py::test_p4_03_normalized_contract_schema_and_tamper_rejection PASSED [ 30%]
tests/test_phase4_mlops.py::test_p4_04_approval_check_rejects_synthetic_data_and_mismatched_sha PASSED [ 40%]
tests/test_phase4_mlops.py::test_p4_05_feature_computation_exact_date_lags PASSED [ 50%]
tests/test_phase4_mlops.py::test_p4_06_insufficient_history_rejects_and_writes_unavailable_artifact PASSED [ 60%]
tests/test_phase4_mlops.py::test_p4_07_full_pipeline_synthetic_evaluation_and_json_serialization PASSED [ 70%]
tests/test_phase4_mlops.py::test_p4_08_demandsync_api_endpoint_feature_gated_and_unavailable PASSED [ 80%]
tests/test_phase4_mlops.py::test_p4_09_exact_half_up_settlement_rounding_boundary_tests PASSED [ 90%]
tests/test_phase4_mlops.py::test_p4_10_delivery_inspection_reconciliation_contracts PASSED [100%]

======================== 10 passed, 1 warning in 3.08s ========================
```

---

## 2. Full Regression Test Execution Log

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\ABIR SAHA\Downloads\GRAHAT
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 168 items

tests/test_batchtrace.py ..............                                  [  8%]
tests/test_commitguard.py ............                                   [ 15%]
tests/test_demandsync.py ...........                                     [ 22%]
tests/test_final_acceptance.py ..........................                [ 37%]
tests/test_logistics.py ............                                     [ 44%]
tests/test_market_arrivals.py ......                                     [ 48%]
tests/test_offline_sync.py ............                                  [ 55%]
tests/test_overview.py ........                                          [ 60%]
tests/test_phase3_contracts.py ...............                           [ 69%]
tests/test_phase4_mlops.py ..........                                    [ 75%]
tests/test_price_forecasting.py .....                                    [ 77%]
tests/test_recoveryopt.py ..........                                     [ 83%]
tests/test_riskwatch.py ..........                                       [ 89%]
tests/test_settletrack.py ............                                   [ 96%]
VALIDATION_TESTS/test_sre_adversarial.py .....                           [100%]

======================== 168 passed, 1 warning in 15.72s =======================
```

---

## 3. Evidence of Specific Contract Verifications

1. **Quarantine Isolation**: Ingesting a batch with unmapped mandis and future dates quarantined 3 rows into `.rejected.json` while isolating 1 valid row without modifying raw input bytes.
2. **Double-Import Idempotency**: Re-importing releases creates 0 duplicate items across all memory collections.
3. **Half-Up Rounding Verification**:
   - `1g * 1500 paise/kg = 1.5 paise -> rounds to 2 paise` (half rounds up).
   - `1g * 1499 paise/kg = 1.499 paise -> rounds to 1 paise`.
   - `10^10 grams * 2500 paise/kg = 25,000,000,000 paise` (integer overflow free).
4. **Delivery Inspection Mass Conservation**:
   - `delivered == accepted + rejected + pending`.
   - `final=True` strictly rejects any `pending > 0`.
