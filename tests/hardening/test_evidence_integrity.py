from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import (
    DEV_ACTOR_HEADER,
    ConflictError,
    InvariantViolationError,
    Role,
    DevActor,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import VerificationStatus
from gramsetu.adapters.evidence import EvidenceManager, compute_payload_digest


def test_r5_tamper_evident_payload_digest_validation():
    """R5 INTEGRITY: SHA-256 payload digest guarantees that any modification
    to amount, timestamp, or reference is immediately flagged as tampered.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    actor = DevActor(actor_id="buyer-reliance", role=Role.BUYER, name="Reliance Buyer")

    payload = {"utr": "AXIS12345678", "amount_paise": 500_000, "payer_vpa": "reliance@icici"}
    digest = compute_payload_digest(payload)
    assert len(digest) == 64

    # Valid registration succeeds
    record = EvidenceManager.register_payment_evidence(
        store=store,
        coordinator=coord,
        actor=actor,
        reference_number="AXIS12345678",
        amount_paise=500_000,
        raw_payload=payload,
        expected_digest=digest,
    )
    assert record.payload_digest == digest
    assert record.verification_status == VerificationStatus.REPORTED

    # Tampered payload with altered amount fails integrity verification
    tampered_payload = {"utr": "AXIS12345678", "amount_paise": 999_999, "payer_vpa": "reliance@icici"}
    with pytest.raises(InvariantViolationError, match="Tampered payment payload"):
        EvidenceManager.register_payment_evidence(
            store=store,
            coordinator=coord,
            actor=actor,
            reference_number="AXIS12345679",
            amount_paise=999_999,
            raw_payload=tampered_payload,
            expected_digest=digest,  # Passing original digest against modified payload
        )

    coord.close()


def test_r5_duplicate_payment_reference_replay_prevention():
    """R5 REPLAY DEFENSE: Replay of an identical payment reference MUST be rejected with ConflictError."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    actor = DevActor(actor_id="buyer-reliance", role=Role.BUYER, name="Reliance Buyer")

    ref = "HDFC-NEFT-998877"
    payload = {"ref": ref, "amount_paise": 250_000}

    # First registration
    EvidenceManager.register_payment_evidence(
        store=store,
        coordinator=coord,
        actor=actor,
        reference_number=ref,
        amount_paise=250_000,
        raw_payload=payload,
    )

    # Duplicate replay MUST raise ConflictError
    with pytest.raises(ConflictError, match="Duplicate payment evidence replay"):
        EvidenceManager.register_payment_evidence(
            store=store,
            coordinator=coord,
            actor=actor,
            reference_number=ref,
            amount_paise=250_000,
            raw_payload=payload,
        )

    coord.close()


def test_r5_honest_evidence_lifecycle_state_transitions():
    """R5 PROVENANCE LIFECYCLE:
    1. Initial registration: REPORTED.
    2. Operator verification: OPERATOR_CONFIRMED.
    3. Cryptographic bank token verification: EXTERNALLY_VERIFIED.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    actor_buyer = DevActor(actor_id="buyer-reliance", role=Role.BUYER, name="Reliance Buyer")
    actor_fpo = DevActor(actor_id="fpo-admin-alpha", role=Role.FPO_ADMIN, name="Alpha FPO Admin")

    ref = "SBI-IMPS-443322"
    record = EvidenceManager.register_payment_evidence(
        store=store,
        coordinator=coord,
        actor=actor_buyer,
        reference_number=ref,
        amount_paise=100_000,
        raw_payload={"ref": ref, "amount": 100_000},
    )
    assert record.verification_status == VerificationStatus.REPORTED

    # 1. Human operator confirms credit advice -> OPERATOR_CONFIRMED
    confirmed = EvidenceManager.confirm_evidence(
        store=store,
        coordinator=coord,
        actor=actor_fpo,
        evidence_id=record.evidence_id,
        external_confirmation_token=None,
    )
    assert confirmed.verification_status == VerificationStatus.OPERATOR_CONFIRMED
    assert confirmed.verifier_identity == "fpo-admin-alpha"

    # 2. Cryptographic bank token confirms -> EXTERNALLY_VERIFIED
    ext_verified = EvidenceManager.confirm_evidence(
        store=store,
        coordinator=coord,
        actor=actor_fpo,
        evidence_id=record.evidence_id,
        external_confirmation_token="CRYPTO_BANK_SIG_RSA2048_9988AABB",
    )
    assert ext_verified.verification_status == VerificationStatus.EXTERNALLY_VERIFIED

    coord.close()


def test_r5_weighbridge_iot_evidence_with_calibration():
    """R5 PHYSICAL PROVENANCE: Weighbridge scale receipts preserve calibration metadata
    and reject duplicated scale tickets.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    actor_driver = DevActor(actor_id="driver-1", role=Role.DRIVER, name="Driver Jagdish")

    ticket = "WB-NASHIK-2026-0042"
    scale_data = {
        "gross_grams": 12_500_000,
        "tare_grams": 4_500_000,
        "net_grams": 8_000_000,
        "scale_model": "AveryWeightronix-Z400",
    }
    cert = "LEGAL_METROLOGY_CERT_MH_2026_99"

    record = EvidenceManager.register_weighbridge_evidence(
        store=store,
        coordinator=coord,
        actor=actor_driver,
        ticket_number=ticket,
        net_grams=8_000_000,
        raw_scale_data=scale_data,
        scale_calibration_cert=cert,
    )

    assert record.raw_reference == ticket
    assert record.quantity_or_amount == 8_000_000
    assert record.unit_or_currency == "GRAMS"
    assert record.calibration_metadata == cert
    assert record.verification_status == VerificationStatus.OPERATOR_CONFIRMED

    # Replay protection on physical weighbridge ticket
    with pytest.raises(ConflictError, match="Duplicate weighbridge ticket replay"):
        EvidenceManager.register_weighbridge_evidence(
            store=store,
            coordinator=coord,
            actor=actor_driver,
            ticket_number=ticket,
            net_grams=8_000_000,
            raw_scale_data=scale_data,
            scale_calibration_cert=cert,
        )

    coord.close()


def test_r5_settlement_evidence_flow_via_api():
    """R5 API WORKFLOW INTEGRATION:
    Buyer reports payment on settlement -> evidence registered with SHA-256 digest.
    Duplicate reference rejected with 409.
    FPO Admin verifies payment -> payment elevated to OPERATOR_CONFIRMED.
    """
    app = create_app()
    client = TestClient(app)

    # 1. Setup prerequisite: Receive lot, create requirement, commitment, vehicle, shipment, and deliver
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Soybean",
            "grade": "A",
            "quantity_grams": 1_000_000,
            "storage_location": "Silo-1",
        },
    )
    assert res_lot.status_code == 201
    lot_id = res_lot.json()["lot_id"]

    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Soybean",
            "grade": "A",
            "needed_grams": 1_000_000,
            "max_price_paise_per_gram": 35,
            "delivery_window_start": "2026-12-01T00:00:00Z",
            "delivery_window_end": "2026-12-15T00:00:00Z",
        },
    )
    assert res_req.status_code == 201
    req_id = res_req.json()["requirement_id"]

    res_commit = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 35,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 1_000_000}],
        },
    )
    assert res_commit.status_code == 201
    commit_id = res_commit.json()["commitment_id"]

    res_veh = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "fpo_id": "fpo-alpha",
            "driver_id": "driver-1",
            "capacity_grams": 2_000_000,
            "vehicle_type": "TRUCK_4T",
        },
    )
    assert res_veh.status_code == 201
    veh_id = res_veh.json()["vehicle_id"]

    res_ship = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"},
    )
    assert res_ship.status_code == 201
    ship_id = res_ship.json()["shipment_id"]

    client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 1_000_000, "rejected_grams": 0, "loss_grams": 0},
    )

    # Generate settlement
    res_set = client.post(
        "/api/v1/settlements/generate",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"shipment_id": ship_id, "deductions": []},
    )
    assert res_set.status_code == 201
    set_id = res_set.json()["settlement_id"]

    # 2. Buyer reports payment with reference
    res_report = client.post(
        f"/api/v1/settlements/{set_id}/report-payment",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "amount_paise": 35_000_000,
            "payment_method": "RTGS",
            "reference_number": "RTGS-MUM-2026-8877",
            "evidence_note": "Bank UTR RTGS-MUM-2026-8877 confirmed by treasury",
        },
    )
    assert res_report.status_code == 200
    set_data = res_report.json()
    assert len(set_data["payments"]) == 1
    payment = set_data["payments"][0]
    payment_id = payment["payment_id"]
    assert payment["verification_status"] == "REPORTED"
    assert payment["payload_digest"] is not None
    assert len(payment["payload_digest"]) == 64

    # 3. Duplicate payment report with identical reference MUST return 409 Conflict
    res_dup = client.post(
        f"/api/v1/settlements/{set_id}/report-payment",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "amount_paise": 35_000_000,
            "payment_method": "RTGS",
            "reference_number": "RTGS-MUM-2026-8877",
            "evidence_note": "Attempted replay of same RTGS reference",
        },
    )
    assert res_dup.status_code == 409

    # 4. FPO admin verifies reported payment
    res_ver = client.post(
        f"/api/v1/settlements/{set_id}/payments/{payment_id}/verify",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"verification_note": "Reconciled with FPO State Bank passbook entry"},
    )
    assert res_ver.status_code == 200
    ver_data = res_ver.json()
    assert ver_data["status"] == "SETTLED"
    assert ver_data["remaining_balance_paise"] == 0
    verified_payment = ver_data["payments"][0]
    assert verified_payment["verification_status"] == "OPERATOR_CONFIRMED"
    assert verified_payment["verified"] is True

    app.state.coordinator.close()
