import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def setup_offline_shipment(client):
    now = datetime.now(timezone.utc)

    # 1. Register vehicle
    client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 500_000},
    )
    # 2. Receive lot
    res_l = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Mango",
            "grade": "A",
            "quantity_grams": 400_000,
            "storage_location": "Shed-1",
        },
    )
    lot_id = res_l.json()["lot_id"]

    # 3. Create requirement & commitment
    res_r = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Mango",
            "grade": "A",
            "needed_grams": 400_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 60,
        },
    )
    req_id = res_r.json()["requirement_id"]

    res_c = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 55,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 400_000}],
        },
    )
    commit_id = res_c.json()["commitment_id"]

    # 4. Planned shipment
    vehicles = client.app.state.store.list_items("vehicles")
    veh_id = vehicles[0]["vehicle_id"]
    res_s = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"},
    )
    return res_s.json()["shipment_id"]


def test_offline_driver_pickup_applied_and_replayed():
    app = create_app()
    client = TestClient(app)
    ship_id = setup_offline_shipment(client)

    cmd_id = str(uuid.uuid4())
    envelope = {
        "command_id": cmd_id,
        "actor_id": "driver-1",
        "device_id": "device-mobile-001",
        "command_type": "DRIVER_PICKUP_OBSERVATION",
        "resource_type": "shipment",
        "resource_id": ship_id,
        "expected_version": 1,
        "client_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"action": "pickup"},
    }

    # 1. First sync -> APPLIED
    res1 = client.post("/api/v1/sync/reconcile", headers={DEV_ACTOR_HEADER: "driver-1"}, json=envelope)
    assert res1.status_code == 200
    r1 = res1.json()
    assert r1["status"] == "APPLIED"

    # Verify server shipment is now PICKED_UP
    ship = client.get(f"/api/v1/shipments/{ship_id}", headers={DEV_ACTOR_HEADER: "driver-1"}).json()
    assert ship["status"] == "PICKED_UP"

    # 2. Idempotent replay of exact same command envelope -> REPLAYED
    res2 = client.post("/api/v1/sync/reconcile", headers={DEV_ACTOR_HEADER: "driver-1"}, json=envelope)
    assert res2.status_code == 200
    assert res2.json()["status"] == "REPLAYED"


def test_stale_offline_command_conflict_rejected():
    app = create_app()
    client = TestClient(app)
    ship_id = setup_offline_shipment(client)

    # First pickup already happened on server
    client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})

    # Now a stale offline command arrives claiming expected_version == 1
    envelope = {
        "command_id": str(uuid.uuid4()),
        "actor_id": "driver-1",
        "device_id": "device-mobile-old",
        "command_type": "DRIVER_PICKUP_OBSERVATION",
        "resource_type": "shipment",
        "resource_id": ship_id,
        "expected_version": 1,  # Stale!
        "client_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"action": "pickup"},
    }
    res = client.post("/api/v1/sync/reconcile", headers={DEV_ACTOR_HEADER: "driver-1"}, json=envelope)
    assert res.status_code == 409
    data = res.json()
    assert data["status"] == "CONFLICT_REJECTED"
    assert data["current_server_state"]["status"] == "PICKED_UP"


def test_unauthorized_offline_commercial_action_rejected():
    app = create_app()
    client = TestClient(app)

    # Attempt to do an offline payment confirmation
    envelope = {
        "command_id": str(uuid.uuid4()),
        "actor_id": "buyer-reliance",
        "device_id": "device-buyer-99",
        "command_type": "BUYER_OFFLINE_PAYMENT",  # Disallowed offline!
        "resource_type": "settlement",
        "resource_id": "set-100",
        "expected_version": 1,
        "client_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"amount_paise": 100_000},
    }
    res = client.post("/api/v1/sync/reconcile", headers={DEV_ACTOR_HEADER: "buyer-reliance"}, json=envelope)
    assert res.status_code == 400
    assert res.json()["error"] == "INVARIANT_VIOLATION"
