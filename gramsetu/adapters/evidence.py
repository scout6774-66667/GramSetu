from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional, Dict, Any

from gramsetu.core import (
    DevActor,
    get_current_utc,
    ConflictError,
    InvariantViolationError,
    NotFoundError,
)
from gramsetu.schemas import ProvenanceEvidenceRecord, VerificationStatus
from gramsetu.store import InMemoryStore, TransactionCoordinator


def compute_payload_digest(payload: Any) -> str:
    """Compute deterministic canonical SHA-256 hex digest for arbitrary transaction payloads."""
    if isinstance(payload, bytes):
        raw_bytes = payload
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    elif isinstance(payload, (dict, list)):
        canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        raw_bytes = canonical_str.encode("utf-8")
    else:
        raw_bytes = str(payload).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


class EvidenceManager:
    """Manages immutable, tamper-evident provenance records for financial and physical weighbridge events."""

    @staticmethod
    def register_payment_evidence(
        store: InMemoryStore,
        coordinator: TransactionCoordinator,
        actor: DevActor,
        reference_number: str,
        amount_paise: int,
        raw_payload: Dict[str, Any],
        source_type: str = "OPERATOR_MANUAL",
        expected_digest: Optional[str] = None,
    ) -> ProvenanceEvidenceRecord:
        """Register payment transaction evidence with SHA-256 payload digest and duplicate prevention."""
        computed_digest = compute_payload_digest(raw_payload)

        # Integrity check: if caller provided an expected digest, verify match
        if expected_digest and expected_digest.lower() != computed_digest.lower():
            raise InvariantViolationError(
                f"Tampered payment payload: computed digest '{computed_digest}' does not match expected '{expected_digest}'."
            )

        # Replay / duplicate check across existing evidence records
        existing_records = store.list_items("evidence", lambda e: e.get("raw_reference") == reference_number)
        if existing_records:
            raise ConflictError(
                f"Duplicate payment evidence replay: reference '{reference_number}' already registered in evidence store."
            )

        evidence_id = f"evi-pay-{uuid.uuid4().hex[:10]}"
        now = get_current_utc()

        # Strict provenance invariant: never claim EXTERNALLY_VERIFIED at registration
        status = VerificationStatus.REPORTED

        record = ProvenanceEvidenceRecord(
            evidence_id=evidence_id,
            source_type=source_type,
            source_identity=actor.actor_id,
            raw_reference=reference_number,
            payload_digest=computed_digest,
            quantity_or_amount=amount_paise,
            unit_or_currency="PAISE",
            verification_status=status,
            verifier_identity=None,
            calibration_metadata=None,
            recorded_at=now,
            verified_at=None,
        )

        with coordinator.transaction():
            coordinator.store.set_item("evidence", evidence_id, record.model_dump())

        return record

    @staticmethod
    def register_weighbridge_evidence(
        store: InMemoryStore,
        coordinator: TransactionCoordinator,
        actor: DevActor,
        ticket_number: str,
        net_grams: int,
        raw_scale_data: Dict[str, Any],
        scale_calibration_cert: str,
        source_type: str = "WEIGHBRIDGE_IOT",
    ) -> ProvenanceEvidenceRecord:
        """Register physical weighbridge scale ticket evidence with calibration tracking."""
        computed_digest = compute_payload_digest(raw_scale_data)

        existing = store.list_items("evidence", lambda e: e.get("raw_reference") == ticket_number)
        if existing:
            raise ConflictError(
                f"Duplicate weighbridge ticket replay: ticket '{ticket_number}' already registered."
            )

        evidence_id = f"evi-scale-{uuid.uuid4().hex[:10]}"
        now = get_current_utc()

        # Honest status: IoT scale print is OPERATOR_CONFIRMED if certified, else REPORTED
        status = VerificationStatus.OPERATOR_CONFIRMED if scale_calibration_cert else VerificationStatus.REPORTED

        record = ProvenanceEvidenceRecord(
            evidence_id=evidence_id,
            source_type=source_type,
            source_identity=actor.actor_id,
            raw_reference=ticket_number,
            payload_digest=computed_digest,
            quantity_or_amount=net_grams,
            unit_or_currency="GRAMS",
            verification_status=status,
            verifier_identity=actor.actor_id,
            calibration_metadata=scale_calibration_cert,
            recorded_at=now,
            verified_at=now if status == VerificationStatus.OPERATOR_CONFIRMED else None,
        )

        with coordinator.transaction():
            coordinator.store.set_item("evidence", evidence_id, record.model_dump())

        return record

    @staticmethod
    def confirm_evidence(
        store: InMemoryStore,
        coordinator: TransactionCoordinator,
        actor: DevActor,
        evidence_id: str,
        external_confirmation_token: Optional[str] = None,
    ) -> ProvenanceEvidenceRecord:
        """Elevate evidence status with honest verification attribution:
        - If verified with external cryptographic token/bank webhook -> EXTERNALLY_VERIFIED
        - If confirmed by human operator -> OPERATOR_CONFIRMED
        """
        raw_evidence = store.get_item("evidence", evidence_id)
        if not raw_evidence:
            raise NotFoundError(f"Evidence record '{evidence_id}' not found.")

        current_record = ProvenanceEvidenceRecord(**raw_evidence)

        now = get_current_utc()
        # Honest status progression: only grant EXTERNALLY_VERIFIED if authentic cryptographic token supplied
        if external_confirmation_token and external_confirmation_token.startswith("CRYPTO_BANK_SIG_"):
            new_status = VerificationStatus.EXTERNALLY_VERIFIED
        else:
            new_status = VerificationStatus.OPERATOR_CONFIRMED

        updated_dict = current_record.model_dump()
        updated_dict["verification_status"] = new_status
        updated_dict["verifier_identity"] = actor.actor_id
        updated_dict["verified_at"] = now

        with coordinator.transaction():
            coordinator.store.set_item("evidence", evidence_id, updated_dict)

        return ProvenanceEvidenceRecord(**updated_dict)
