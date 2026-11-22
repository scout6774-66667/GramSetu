from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def setup_risk_data(client):
    now = datetime.now(timezone.utc)

    # 1. Register vehicle
    res_veh = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 500_000},
    )
    veh_id = res_veh.json()["vehicle_id"]

    # 2. Receive lot: Tomato 500,000 g
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Tomato",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": "Bay-1",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    # 3. Create requirement & commitment
    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Tomato",
            "grade": "A",
            "needed_grams": 500_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 40,
        },
    )
    req_id = res_req.json()["requirement_id"]

    res_commit = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 38,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 500_000}],
        },
    )
    commit_id = res_commit.json()["commitment_id"]

    # 4. Dispatch and deliver with 50,000 g rejected, 10,000 g loss
    res_ship = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"},
    )
    ship_id = res_ship.json()["shipment_id"]

    client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 440_000, "rejected_grams": 50_000, "loss_grams": 10_000},
    )

    return lot_id, commit_id, ship_id


def test_scan_detects_rejections_and_shortages():
    app = create_app()
    client = TestClient(app)
    lot_id, commit_id, ship_id = setup_risk_data(client)

    # Run scan
    res_scan = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_scan.status_code == 200
    incidents = res_scan.json()
    assert len(incidents) >= 2

    types = [inc["incident_type"] for inc in incidents]
    assert "QUALITY_REJECTION" in types
    assert "SHORT_DELIVERY" in types

    rejection = next(inc for inc in incidents if inc["incident_type"] == "QUALITY_REJECTION")
    assert rejection["affected_grams"] == 50_000
    assert rejection["status"] == "OPEN"


def test_deduplication_prevents_alert_storms():
    app = create_app()
    client = TestClient(app)
    lot_id, commit_id, ship_id = setup_risk_data(client)

    # Scan 1
    res1 = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    count1 = len(res1.json())

    # Scan 2 (repeated scan)
    res2 = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    count2 = len(res2.json())

    assert count1 == count2, "Repeated scans must deduplicate and not inflate incident count"


def test_incident_lifecycle():
    app = create_app()
    client = TestClient(app)
    lot_id, commit_id, ship_id = setup_risk_data(client)

    res_scan = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    inc_id = res_scan.json()[0]["incident_id"]

    # 1. Acknowledge
    res_ack = client.post(f"/api/v1/risk/incidents/{inc_id}/acknowledge", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_ack.status_code == 200
    assert res_ack.json()["status"] == "ACKNOWLEDGED"

    # 2. Resolve with empty note -> rejected
    res_bad_res = client.post(
        f"/api/v1/risk/incidents/{inc_id}/resolve",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"resolution_note": ""},
    )
    assert res_bad_res.status_code == 422 or res_bad_res.status_code == 400

    # 3. Resolve with verifiable note
    res_good_res = client.post(
        f"/api/v1/risk/incidents/{inc_id}/resolve",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"resolution_note": "Produce composted and claim deducted from farmer receipt"},
    )
    assert res_good_res.status_code == 200
    assert res_good_res.json()["status"] == "RESOLVED"
