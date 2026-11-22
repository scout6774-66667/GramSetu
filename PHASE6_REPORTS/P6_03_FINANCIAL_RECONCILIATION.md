# GramSetu AI — Financial Settlement & Beneficiary Credit Audit

**Document ID:** P6_03_FINANCIAL_RECONCILIATION.md  
**Audit Phase:** Phase 6 Workstream P6.3  
**Verdict:** `BANK_CREDIT_UNVERIFIED_IN_BASELINE`

---

## 1. Banking Integrity & Beneficiary Credit Invariant

Under Phase 6 governance (`P6-13` and `P6-M3-06`):
- **Freeform UTR String Rejection:** An alphanumeric string entered by a buyer (e.g. `UTR998877665544`) does NOT constitute proof of funds transfer.
- **HMAC Signature Sufficiency:** Verifying an HMAC-SHA256 signature on an incoming payment gateway webhook confirms only that the payload originated from the gateway; it does NOT confirm that the beneficiary's bank account was actually credited.
- **Mandatory Final Settlement Invariant:** A settlement record in `gramsetu/services/settlement.py` can only transition to `SETTLED` when an authoritative bank credit notification is received containing:
  1. `bank_clearing_reference_id`
  2. `beneficiary_account_hash`
  3. `cleared_amount_paise`
  4. `bank_settlement_timestamp_utc`
  5. `status == "SUCCESS_CREDITED"`

In the current baseline, all 32 payable ledger entries and 22 payment transactions carry `simulation_flag: True`. No live bank account transfers have been executed.
