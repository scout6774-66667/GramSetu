import os
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER, Settings
from gramsetu.store import InMemoryStore, TransactionCoordinator


def test_complete_end_to_end_happy_path():
    app = create_app()
    client = TestClient(app)
    now = datetime.now(timezone.utc)

    # 1. Farmer records forecast
    res_fc = client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Pomegranate",
            "grade": "A",
            "estimated_grams": 500_000,
            "harvest_start_date": (now + timedelta(days=1)).isoformat(),
            "harvest_end_date": (now + timedelta(days=5)).isoformat(),
        },
    )
    assert res_fc.status_code == 201

    # 2. FPO receives physical lot
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Pomegranate",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": "Bay-P1",
        },
    )
    assert res_lot.status_code == 201
    lot_id = res_lot.json()["lot_id"]

    # 3. Buyer creates requirement
    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Pomegranate",
            "grade": "A",
            "needed_grams": 500_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=6)).isoformat(),
            "max_price_paise_per_gram": 100,
        },
    )
    assert res_req.status_code == 201
    req_id = res_req.json()["requirement_id"]

    # 4. Buyer creates commitment
    res_com = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 95,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 500_000}],
        },
    )
    assert res_com.status_code == 201
    commit_id = res_com.json()["commitment_id"]

    # 5. FPO registers vehicle & plans shipment
    res_veh = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 600_000},
    )
    veh_id = res_veh.json()["vehicle_id"]

    res_ship = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"},
    )
    assert res_ship.status_code == 201
    ship_id = res_ship.json()["shipment_id"]

    # 6. Driver picks up -> warehouse stock decrements to 0
    res_pick = client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    assert res_pick.status_code == 200
    lot_post_pickup = client.get(f"/api/v1/lots/{lot_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()
    assert lot_post_pickup["quantity_grams"] == 0
    assert lot_post_pickup["reserved_grams"] == 0

    # 7. Driver delivers (100% accepted)
    res_del = client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 500_000, "rejected_grams": 0, "loss_grams": 0},
    )
    assert res_del.status_code == 200

    # 8. FPO generates settlement: 500k * 95 = 47,500,000 paise
    res_set = client.post(
        "/api/v1/settlements/generate",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"shipment_id": ship_id, "deductions": []},
    )
    assert res_set.status_code == 201
    settle_id = res_set.json()["settlement_id"]
    assert res_set.json()["net_payable_paise"] == 47_500_000

    # 9. Buyer pays in full
    res_pay = client.post(
        f"/api/v1/settlements/{settle_id}/payments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={"amount_paise": 47_500_000, "payment_method": "RTGS", "reference_number": "UTR-RTGS-9999"},
    )
    assert res_pay.status_code == 200
    assert res_pay.json()["status"] == "SETTLED"
    assert res_pay.json()["remaining_balance_paise"] == 0

    # 10. Farmer overview confirms earnings
    farmer_dash = client.get("/api/v1/overview/farmer", headers={DEV_ACTOR_HEADER: "farmer-1"}).json()
    assert farmer_dash["total_earned_paise"] == 47_500_000
    assert farmer_dash["pending_payout_paise"] == 0


def test_disruption_recovery_cross_feature_flow():
    app = create_app()
    client = TestClient(app)
    now = datetime.now(timezone.utc)

    # 1. Lot received
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Carrot",
            "grade": "A",
            "quantity_grams": 300_000,
            "storage_location": "Shed-C",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    # 2. Buyer 1 commits, then cancels
    res_req1 = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Carrot",
            "grade": "A",
            "needed_grams": 300_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 30,
        },
    )
    req1_id = res_req1.json()["requirement_id"]

    res_com1 = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req1_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 28,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 300_000}],
        },
    )
    com1_id = res_com1.json()["commitment_id"]

    # Cancel commitment
    client.post(f"/api/v1/commitments/{com1_id}/cancel", headers={DEV_ACTOR_HEADER: "buyer-reliance"})

    # 3. Risk scan detects CANCELLED_ORDER
    res_scan = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    incidents = res_scan.json()
    cancel_inc = next(i for i in incidents if i["incident_type"] == "CANCELLED_ORDER")

    # 4. Buyer 2 (BigBasket) has open requirement
    client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-bigbasket"},
        json={
            "crop": "Carrot",
            "grade": "A",
            "needed_grams": 300_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 29,
        },
    )

    # 5. RecoveryOpt generates plan
    res_plan = client.post(
        f"/api/v1/recovery/plans/generate?incident_id={cancel_inc['incident_id']}",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_plan.status_code == 201
    plan = res_plan.json()
    plan_id = plan["plan_id"]
    rec_buyer = plan["recommended_candidate"]["buyer_id"]
    assert rec_buyer in ("buyer-reliance", "buyer-bigbasket")

    # 6. Recommended buyer confirms
    res_conf = client.post(f"/api/v1/recovery/plans/{plan_id}/buyer-confirm", headers={DEV_ACTOR_HEADER: rec_buyer})
    assert res_conf.status_code == 200

    # 7. FPO Approves
    res_appr = client.post(f"/api/v1/recovery/plans/{plan_id}/approve", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "APPROVED"

    # Verify lot is re-reserved for BigBasket
    lot_after = client.get(f"/api/v1/lots/{lot_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()
    assert lot_after["reserved_grams"] == 300_000
    assert lot_after["available_grams"] == 0


def test_cold_restart_from_snapshot():
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = os.path.join(tmpdir, "gramsetu_snapshot.json")
        settings = Settings(SNAPSHOT_PATH=snap_path)

        # 1. Start App 1, create data
        app1 = create_app(settings=settings)
        client1 = TestClient(app1)

        client1.post(
            "/api/v1/lots/receipt",
            headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
            json={
                "farmer_id": "farmer-1",
                "fpo_id": "fpo-alpha",
                "crop": "Soybean",
                "grade": "A",
                "quantity_grams": 800_000,
                "storage_location": "Silo-S1",
            },
        )
        assert os.path.exists(snap_path)
        app1.state.coordinator.close()

        # 2. Cold restart: Start App 2 from exact same snapshot
        app2 = create_app(settings=settings)
        client2 = TestClient(app2)

        lots = client2.get("/api/v1/lots", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()
        assert len(lots) == 1
        assert lots[0]["crop"] == "Soybean"
        assert lots[0]["quantity_grams"] == 800_000
