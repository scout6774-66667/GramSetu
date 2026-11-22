from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def setup_overview_scenario(client):
    now = datetime.now(timezone.utc)

    # 1. Farmer 1 creates forecast
    client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Guava",
            "grade": "A",
            "estimated_grams": 200_000,
            "harvest_start_date": (now + timedelta(days=2)).isoformat(),
            "harvest_end_date": (now + timedelta(days=6)).isoformat(),
        },
    )

    # 2. FPO receives lot from Farmer 1: 300,000 g
    res_l = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Guava",
            "grade": "A",
            "quantity_grams": 300_000,
            "storage_location": "Bay-G1",
        },
    )
    lot_id = res_l.json()["lot_id"]

    # 3. Buyer Reliance creates requirement: 300,000 g
    res_r = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Guava",
            "grade": "A",
            "needed_grams": 300_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 50,
        },
    )
    req_id = res_r.json()["requirement_id"]

    # 4. Commitment: 150,000 g (half of lot reserved)
    client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 45,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 150_000}],
        },
    )

    # 5. Vehicle for driver-1
    client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 500_000},
    )


def test_four_app_views():
    app = create_app()
    client = TestClient(app)
    setup_overview_scenario(client)

    # 1. Farmer Overview
    res_f = client.get("/api/v1/overview/farmer", headers={DEV_ACTOR_HEADER: "farmer-1"})
    assert res_f.status_code == 200
    f_data = res_f.json()
    assert f_data["farmer_id"] == "farmer-1"
    assert f_data["active_forecasts_count"] == 1
    assert f_data["active_forecasts_grams"] == 200_000
    assert f_data["delivered_lots_count"] == 1
    assert f_data["delivered_grams"] == 300_000
    assert "as_of" in f_data

    # 2. Buyer Overview
    res_b = client.get("/api/v1/overview/buyer", headers={DEV_ACTOR_HEADER: "buyer-reliance"})
    assert res_b.status_code == 200
    b_data = res_b.json()
    assert b_data["buyer_id"] == "buyer-reliance"
    assert b_data["open_requirements_count"] == 1
    assert b_data["active_commitments_count"] == 1
    assert b_data["active_committed_grams"] == 150_000

    # 3. Driver Overview
    res_d = client.get("/api/v1/overview/driver", headers={DEV_ACTOR_HEADER: "driver-1"})
    assert res_d.status_code == 200
    d_data = res_d.json()
    assert d_data["driver_id"] == "driver-1"
    assert d_data["assigned_vehicle_id"] is not None

    # 4. FPO Overview
    res_fpo = client.get("/api/v1/overview/fpo?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_fpo.status_code == 200
    fpo_data = res_fpo.json()
    assert fpo_data["fpo_id"] == "fpo-alpha"
    assert fpo_data["total_physical_stock_grams"] == 300_000
    assert fpo_data["total_reserved_stock_grams"] == 150_000
    assert fpo_data["total_available_stock_grams"] == 150_000


def test_cross_tenant_overview_forbidden():
    app = create_app()
    client = TestClient(app)
    setup_overview_scenario(client)

    # Farmer attempting to access FPO overview
    res1 = client.get("/api/v1/overview/fpo?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "farmer-1"})
    assert res1.status_code == 403

    # FPO Beta admin attempting to access FPO Alpha overview
    res2 = client.get("/api/v1/overview/fpo?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-beta"})
    assert res2.status_code == 403
