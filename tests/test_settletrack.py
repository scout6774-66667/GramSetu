from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def setup_delivered_shipment(client):
    now = datetime.now(timezone.utc)

    # 1. Register vehicle
    res_v = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 500_000},
    )
    veh_id = res_v.json()["vehicle_id"]

    # 2. Receive lot: 500,000 g
    res_l = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Banana",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": "Ripening-1",
        },
    )
    lot_id = res_l.json()["lot_id"]

    # 3. Create requirement & commitment at 25 paise/g
    res_r = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Banana",
            "grade": "A",
            "needed_grams": 500_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 30,
        },
    )
    req_id = res_r.json()["requirement_id"]

    res_c = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 25,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 500_000}],
        },
    )
    commit_id = res_c.json()["commitment_id"]

    # 4. Create shipment, pickup, deliver with 400,000 g accepted (100,000 g rejected)
    res_s = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"},
    )
    ship_id = res_s.json()["shipment_id"]

    client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 400_000, "rejected_grams": 100_000, "loss_grams": 0},
    )

    return ship_id


def test_settlement_generation_from_accepted_quantity_only():
    app = create_app()
    client = TestClient(app)
    ship_id = setup_delivered_shipment(client)

    # Generate settlement with transport deduction of 50,000 paise
    payload = {
        "shipment_id": ship_id,
        "deductions": [
            {"deduction_type": "TRANSPORT", "amount_paise": 50_000, "reason": "Standard haulage fee"}
        ],
    }
    res = client.post("/api/v1/settlements/generate", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}, json=payload)
    assert res.status_code == 201
    settle = res.json()

    # 400,000 g accepted * 25 paise/g = 10,000,000 paise gross
    # 10,000,000 - 50,000 = 9,950,000 paise net payable
    assert settle["accepted_grams"] == 400_000
    assert settle["gross_amount_paise"] == 10_000_000
    assert settle["total_deductions_paise"] == 50_000
    assert settle["net_payable_paise"] == 9_950_000
    assert settle["paid_amount_paise"] == 0
    assert settle["remaining_balance_paise"] == 9_950_000
    assert settle["status"] == "PENDING"


def test_zero_payable_immediately_settled():
    app = create_app()
    client = TestClient(app)
    now = datetime.now(timezone.utc)

    # Setup zero accepted shipment directly in store
    with app.state.coordinator.transaction():
        app.state.store.set_item(
            "shipments",
            "ship-zero",
            {
                "shipment_id": "ship-zero",
                "commitment_id": "com-zero",
                "vehicle_id": "veh-1",
                "driver_id": "driver-1",
                "dispatched_grams": 100_000,
                "status": "DELIVERED",
                "accepted_grams": 0,
                "rejected_grams": 100_000,
                "loss_grams": 0,
            },
        )
        app.state.store.set_item(
            "commitments",
            "com-zero",
            {
                "commitment_id": "com-zero",
                "fpo_id": "fpo-alpha",
                "buyer_id": "buyer-reliance",
                "agreed_price_paise_per_gram": 30,
                "allocations": [{"lot_id": "lot-1", "allocated_grams": 100_000}],
            },
        )
        app.state.store.set_item(
            "lots",
            "lot-1",
            {"lot_id": "lot-1", "fpo_id": "fpo-alpha", "farmer_id": "farmer-1"},
        )

    res = client.post(
        "/api/v1/settlements/generate",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"shipment_id": "ship-zero", "deductions": []},
    )
    assert res.status_code == 201
    settle = res.json()
    assert settle["net_payable_paise"] == 0
    assert settle["status"] == "SETTLED"  # Zero payable is settled, never overdue debt!


def test_partial_payment_and_overpayment_rejection():
    app = create_app()
    client = TestClient(app)
    ship_id = setup_delivered_shipment(client)

    res_gen = client.post(
        "/api/v1/settlements/generate",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"shipment_id": ship_id, "deductions": []},
    )
    settle_id = res_gen.json()["settlement_id"]
    net_payable = res_gen.json()["net_payable_paise"]  # 10,000,000 paise

    # 1. Partial payment: 4,000,000 paise
    res_pay1 = client.post(
        f"/api/v1/settlements/{settle_id}/payments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "amount_paise": 4_000_000,
            "payment_method": "NEFT",
            "reference_number": "UTR-10001",
        },
    )
    assert res_pay1.status_code == 200
    p1 = res_pay1.json()
    assert p1["paid_amount_paise"] == 4_000_000
    assert p1["remaining_balance_paise"] == 6_000_000
    assert p1["status"] == "PARTIALLY_PAID"

    # 2. Overpayment attempt: remaining is 6m, attempting 7m -> 400
    res_overpay = client.post(
        f"/api/v1/settlements/{settle_id}/payments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "amount_paise": 7_000_000,
            "payment_method": "NEFT",
            "reference_number": "UTR-10002",
        },
    )
    assert res_overpay.status_code == 400
    assert res_overpay.json()["error"] == "INVARIANT_VIOLATION"

    # 3. Duplicate reference attempt -> 409
    res_dup = client.post(
        f"/api/v1/settlements/{settle_id}/payments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "amount_paise": 1_000_000,
            "payment_method": "NEFT",
            "reference_number": "UTR-10001",  # Duplicate!
        },
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["error"] == "CONFLICT"


def test_payment_report_and_verification_flow():
    app = create_app()
    client = TestClient(app)
    ship_id = setup_delivered_shipment(client)

    res_gen = client.post(
        "/api/v1/settlements/generate",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"shipment_id": ship_id, "deductions": []},
    )
    settle_id = res_gen.json()["settlement_id"]
    net_payable = res_gen.json()["net_payable_paise"]

    # 1. Buyer reports payment (does NOT mark as verified, balance unchanged)
    res_rep = client.post(
        f"/api/v1/settlements/{settle_id}/report-payment",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "amount_paise": net_payable,
            "payment_method": "RTGS",
            "reference_number": "UTR-REPORT-777",
            "evidence_note": "Bank transfer slip uploaded to portal",
        },
    )
    assert res_rep.status_code == 200
    rep_data = res_rep.json()
    assert rep_data["status"] == "PAID_REPORTED"
    assert rep_data["paid_amount_paise"] == 0  # Still 0 until verified!
    assert rep_data["remaining_balance_paise"] == net_payable
    pay_id = rep_data["payments"][0]["payment_id"]
    assert rep_data["payments"][0]["verified"] is False

    # 2. Farmer or Buyer cannot verify payment (must be FPO admin or system)
    res_bad_ver = client.post(
        f"/api/v1/settlements/{settle_id}/payments/{pay_id}/verify",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
    )
    assert res_bad_ver.status_code == 403

    # 3. FPO admin verifies payment
    res_ver = client.post(
        f"/api/v1/settlements/{settle_id}/payments/{pay_id}/verify",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"verification_note": "Credit verified in Bank statement"},
    )
    assert res_ver.status_code == 200
    ver_data = res_ver.json()
    assert ver_data["status"] == "SETTLED"
    assert ver_data["paid_amount_paise"] == net_payable
    assert ver_data["remaining_balance_paise"] == 0
    assert ver_data["payments"][0]["verified"] is True
    assert ver_data["payments"][0]["verified_by"] == "fpo-admin-alpha"

