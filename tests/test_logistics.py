from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def setup_logistics_scenario(client):
    now = datetime.now(timezone.utc)

    # 1. Register vehicle for driver-1 (capacity 600,000 g)
    res_veh = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "fpo_id": "fpo-alpha",
            "driver_id": "driver-1",
            "capacity_grams": 600_000,
            "vehicle_type": "Tata Ace",
        },
    )
    veh_id = res_veh.json()["vehicle_id"]

    # 2. Receive lot: 500,000 g Grade A Apple
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Apple",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": "ColdStorage-1",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    # 3. Create requirement: 500,000 g
    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Apple",
            "grade": "A",
            "needed_grams": 500_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 80,
        },
    )
    req_id = res_req.json()["requirement_id"]

    # 4. Create commitment
    res_commit = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 75,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 500_000}],
        },
    )
    commit_id = res_commit.json()["commitment_id"]

    return veh_id, lot_id, commit_id


def test_vehicle_overload_rejection():
    app = create_app()
    client = TestClient(app)
    veh_id, lot_id, commit_id = setup_logistics_scenario(client)

    # Register small vehicle (capacity only 200,000 g)
    res_small_veh = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "fpo_id": "fpo-alpha",
            "driver_id": "driver-2",
            "capacity_grams": 200_000,
            "vehicle_type": "Auto",
        },
    )
    small_veh_id = res_small_veh.json()["vehicle_id"]

    # Attempt to schedule 500,000 g commitment onto 200,000 g vehicle
    res_ship = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "commitment_id": commit_id,
            "vehicle_id": small_veh_id,
            "driver_id": "driver-2",
        },
    )
    assert res_ship.status_code == 400
    assert res_ship.json()["error"] == "INVARIANT_VIOLATION"


def test_shipment_lifecycle_and_custody_conservation():
    app = create_app()
    client = TestClient(app)
    veh_id, lot_id, commit_id = setup_logistics_scenario(client)

    # 1. Create planned shipment
    res_ship = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "commitment_id": commit_id,
            "vehicle_id": veh_id,
            "driver_id": "driver-1",
        },
    )
    assert res_ship.status_code == 201
    ship = res_ship.json()
    ship_id = ship["shipment_id"]
    assert ship["status"] == "PLANNED"
    assert ship["custody"] == "SCHEDULED"

    # 2. Unauthorized driver pickup attempt (driver-2 cannot pick up driver-1 shipment)
    res_unauth = client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-2"})
    assert res_unauth.status_code == 403

    # 3. Authorized driver-1 records pickup
    res_pickup = client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    assert res_pickup.status_code == 200
    picked = res_pickup.json()
    assert picked["status"] == "PICKED_UP"
    assert picked["custody"] == "DRIVER_CUSTODY"
    assert picked["dispatched_grams"] == 500_000

    # Warehouse physical stock for lot must now be decremented (500k -> 0)
    lot_after = client.get(f"/api/v1/lots/{lot_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()
    assert lot_after["quantity_grams"] == 0
    assert lot_after["reserved_grams"] == 0

    # 4. Delivery with non-conserving sum rejected (450k + 20k != 500k)
    res_bad_del = client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 450_000, "rejected_grams": 20_000, "loss_grams": 0},
    )
    assert res_bad_del.status_code == 400
    assert res_bad_del.json()["error"] == "INVARIANT_VIOLATION"

    # 5. Delivery with conservation: 480k accepted, 15k rejected, 5k loss = 500k
    res_del = client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 480_000, "rejected_grams": 15_000, "loss_grams": 5_000},
    )
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data["status"] == "DELIVERED"
    assert del_data["custody"] == "BUYER_ACCEPTED"
    assert del_data["accepted_grams"] == 480_000
    assert del_data["rejected_grams"] == 15_000
    assert del_data["loss_grams"] == 5_000


def test_route_capacity_algorithm():
    from gramsetu.algorithms import estimate_route_metrics

    # Test within capacity
    metrics = estimate_route_metrics(
        origin_lat=28.6139,
        origin_lon=77.2090,  # Delhi
        dest_lat=28.4595,
        dest_lon=77.0266,   # Gurgaon
        payload_grams=400_000,
        vehicle_capacity_grams=500_000,
    )
    assert metrics["is_feasible"] is True
    assert metrics["distance_km"] > 0
    assert metrics["utilization_percent"] == 80.0
    assert metrics["estimated_cost_paise"] > 0

    # Test exceeding capacity
    overload_metrics = estimate_route_metrics(
        origin_lat=28.6139,
        origin_lon=77.2090,
        dest_lat=28.4595,
        dest_lon=77.0266,
        payload_grams=600_000,
        vehicle_capacity_grams=500_000,
    )
    assert overload_metrics["is_feasible"] is False
    assert overload_metrics["utilization_percent"] == 120.0
