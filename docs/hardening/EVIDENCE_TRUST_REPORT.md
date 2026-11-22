# GramSetu AI — Payment & Weighbridge Evidence Provenance Report

## 1. Executive Summary
In rural agricultural supply chains, payment disputes and weight discrepancy claims represent a primary source of economic friction and counterparty default. In the Phase 1 prototype, payments were recorded as plain dictionary fields without tamper-evident cryptographic digests or duplicate replay protection. Furthermore, mock and human-reported payments could be falsely marked as verified.

Phase 2 implemented the `ProvenanceEvidenceRecord` model and `EvidenceManager` (`gramsetu/adapters/evidence.py`), creating an immutable, tamper-evident audit ledger with strict state-transition invariants.

---

## 2. Evidence Architecture & Data Invariants

### The `ProvenanceEvidenceRecord` Model
```python
class ProvenanceEvidenceRecord(BaseSchema):
    evidence_id: str
    source_type: str  # BANK_API, WEIGHBRIDGE_IOT, OPERATOR_MANUAL, OFFLINE_SYNC
    source_identity: str
    raw_reference: str
    payload_digest: str  # 64-character SHA-256 hex digest
    quantity_or_amount: int  # Grams or Paise
    unit_or_currency: str  # "GRAMS" or "PAISE"
    verification_status: VerificationStatus
    verifier_identity: Optional[str] = None
    calibration_metadata: Optional[str] = None
    recorded_at: datetime
    verified_at: Optional[datetime] = None
```

### Honest Status Progression
The system guarantees the following state machine invariants:
1. **Initial Registration**: Always `REPORTED` (or `OPERATOR_CONFIRMED` only if verified by an authorized on-site physical operator with calibration seal).
2. **Never Falsely Elevated**: A payment or scale receipt is **never** marked as `EXTERNALLY_VERIFIED` unless accompanied by a verified external cryptographic signature (e.g. `CRYPTO_BANK_SIG_...` bank API webhook). Human confirmation elevates strictly to `OPERATOR_CONFIRMED`.
3. **Replay & Idempotency Protection**:
   - `raw_reference` (UTR number, NEFT ref, weighbridge ticket) is deduplicated across the evidence store.
   - Any attempt to reuse or replay a previously recorded reference raises `ConflictError(409)`.
4. **Tamper-Evident SHA-256 Digest**:
   - Transaction payloads (amount, payer, UTR, timestamp) are canonicalized (`json.dumps(..., sort_keys=True)`) and hashed via SHA-256.
   - Any alteration to the payload causes an immediate digest mismatch and raises `InvariantViolationError`.

---

## 3. Negative Security & Provenance Verification (`tests/hardening/test_evidence_integrity.py`)

Five verification scenarios were proven passing:
1. **Tamper-Evident Digest Verification**:
   - Modification of payload amount from 500,000 paise to 999,999 paise is caught; raises `InvariantViolationError("Tampered payment payload")`.
2. **Duplicate Payment Replay Prevention**:
   - Submitting duplicate reference `HDFC-NEFT-998877` raises `ConflictError("Duplicate payment evidence replay")`.
3. **Honest Lifecycle Transitions**:
   - Initial submission: `REPORTED`.
   - FPO Admin confirmation: transitions to `OPERATOR_CONFIRMED` with verifier identity recorded.
   - Bank cryptographic webhook: transitions to `EXTERNALLY_VERIFIED`.
4. **Physical Weighbridge Scale Provenance**:
   - IoT scale print records gross/tare/net grams and calibration certificate ID (`LEGAL_METROLOGY_CERT_MH_2026_99`). Replaying the same ticket number fails with `ConflictError`.
5. **Full API Settlement Evidence Lifecycle**:
   - Buyer reports payment via `POST /api/v1/settlements/{id}/report-payment`. Evidence record is created with SHA-256 digest and status `REPORTED`.
   - Buyer attempts duplicate report $\rightarrow$ rejected with 409 Conflict.
   - FPO Admin verifies payment via `POST /api/v1/settlements/{id}/payments/{pid}/verify` $\rightarrow$ payment elevated to `OPERATOR_CONFIRMED` and remaining balance reduced to 0 (`SETTLED`).

---

## 4. Verification Verdict
- Test suite: `tests/hardening/test_evidence_integrity.py` (5 tests passed).
- Gate status: **GATE R5 — PASS**.
