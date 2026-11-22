# GramSetu AI — Payment Settlement Evidence & Banking Audit

**Audit Date:** 2026-11-22  
**Audit Scope:** SettleTrack Ledger, Payment Evidence, Bank UTR Verification  
**Audited Datasets:** `payable_ledger.csv` (32 rows), `payment_evidence.csv` (16 rows), `payment_transactions.csv` (22 rows)  
**Evaluator:** Principal Banking Integration & SRE Audit Engineer  
**Verdict:** `BANKING_UNVERIFIED / PRODUCTION_BLOCKED`

---

## 1. Executive Summary

GramSetu AI’s settlement service (`gramsetu/services/settlement.py`) handles financial settlement calculations between agricultural buyers, Farmer Producer Organizations (FPOs), and smallholder farmers.

A comprehensive forensic audit of all payment-related datasets and backend settlement endpoints reveals that:
1. **100% of financial settlement records are simulated:** All 32 rows in `payable_ledger.csv` and all 22 rows in `payment_transactions.csv` have `simulation_flag: True`.
2. **Payment Evidence is Synthetic:** All 16 rows in `payment_evidence.csv` are marked with provider `SYNTHETIC_BANK_CALLBACK`.
3. **No Two-Way Bank Gateway Verification:** In development mode, the `record_payment` and `report_payment` endpoints accept arbitrary user-supplied Unique Transaction Reference (UTR) strings without verifying beneficiary credit confirmation via bank APIs or NPCI settlement rails.

Deploying this settlement logic to real-world commercial operations would leave the platform vulnerable to payment fraud, repudiation, and phantom settlements.

---

## 2. Settlement Unit Contract & Invariant Audit

The backend correctly implements the Phase 3 unit contracts and financial invariants:
- **Integer Paise Representation:** All money amounts are stored and calculated as integer paise (e.g. ₹25.00 = 2,500 paise), avoiding floating-point rounding drift.
- **Half-Up Rounding Invariant:** Gross payable calculations enforce exact integer half-up rounding:
  $$\text{gross\_paise} = \left\lfloor \frac{\text{accepted\_grams} \times \text{unit\_price\_paise\_per\_kg} + 500}{1000} \right\rfloor$$
- **Conservation of Delivery Mass:** Settlement is strictly blocked unless delivery inspection is fully reconciled:
  $$\text{delivered\_grams} = \text{accepted\_grams} + \text{rejected\_grams} + \text{loss\_grams}$$
  $$\text{pending\_inspection\_grams} = 0$$
- **Net Payable Balance Invariant:**
  $$\text{net\_payable\_paise} = \text{gross\_payable\_paise} - \text{authorized\_deductions\_paise}$$
  $$\text{remaining\_balance\_paise} = \max(0, \text{net\_payable\_paise} - \text{verified\_paid\_paise})$$

All mathematical calculations in `gramsetu/units.py` and `gramsetu/services/settlement.py` strictly satisfy these mathematical properties.

---

## 3. Banking Fraud & Non-Repudiation Vulnerabilities

```
+-----------------------------------------------------------------------------+
| SETTLEMENT FRAUD VECTOR UNDER UNVERIFIED UTRs                               |
+-----------------------------------------------------------------------------+
|                                                                             |
|  1. Buyer claims payment by entering fictitious string:                      |
|     UTR: "UTR_SBI_998877665544"                                             |
|                                                                             |
|  2. Current Mock Backend:                                                   |
|     -> Accepts UTR string without checking bank ledger                      |
|     -> Marks settlement status as "PAID" / "SETTLED"                        |
|                                                                             |
|  3. Farmer Reality:                                                         |
|     -> Zero funds credited to farmer bank account                           |
|     -> Produce already consumed / irreversibly transferred                  |
|     -> Disastrous counterparty credit loss for FPO                          |
+-----------------------------------------------------------------------------+
```

Without cryptographic confirmation from an authorized banking institution or payment aggregator:
1. **Fictitious UTR Submission:** A malicious buyer can enter an invented 12-digit or 16-digit alphanumeric UTR string.
2. **Timing Asynchrony:** Even when a legitimate UTR is initiated, NEFT/RTGS payments can bounce or be rejected due to account name mismatches or freeze orders. Marking a transaction settled before receiving an authenticated bank credit confirmation is an unmitigated credit risk.
3. **Lack of Cryptographic Webhook Signing:** Development endpoints do not verify webhook payload signatures (HMAC-SHA256), leaving them vulnerable to spoofing.

---

## 4. Production Banking Integration Architecture (Phase 6)

To transition SettleTrack from sandbox research to production operation, the following technical safeguards must be integrated:

1. **Corporate Open Banking Webhook Gateway:**
   - Partner with an authorized commercial bank (e.g., State Bank of India, ICICI Bank, or HDFC Bank) or an RBI-licensed payment aggregator.
   - Enforce asymmetric cryptographic signature verification (Ed25519 or HMAC-SHA256 with rotating webhook secrets) on all incoming settlement notifications.

2. **Beneficiary Account Credit Confirmation:**
   - Transitions to `SETTLED` status must require a signed callback containing:
     - `bank_reference_id`
     - `beneficiary_account_hash`
     - `cleared_amount_paise`
     - `bank_settlement_timestamp_utc`
     - `clearing_status: "SUCCESS_CREDITED"`

3. **Current Phase 5 Verdict:**
   - Feature Gate: **`PRODUCTION_BLOCKED`**
   - Readiness Check: `two_way_bank_settlement_verified: False`
   - Data Notice: `"bank payments are unverified self-reported references; NOT CERTIFIED FOR BANKING SETTLEMENT."`
