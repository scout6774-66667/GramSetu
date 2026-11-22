from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def test_forecast_creation_and_scoping():
    app = create_app()
    client = TestClient(app)

    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=2)).isoformat()
    end = (now + timedelta(days=10)).isoformat()

    # Farmer 1 creates forecast
    f1_payload = {
        "crop": "Tomato",
        "variety": "Desi",
        "grade": "A",
        "estimated_grams": 500_000,
        "harvest_start_date": start,
        "harvest_end_date": end,
        "confidence_score": 0.85,
        "idempotency_key": "f1-key-01",
    }
    res = client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json=f1_payload,
    )
    assert res.status_code == 201
    f1_data = res.json()
    assert f1_data["farmer_id"] == "farmer-1"
    assert f1_data["fpo_id"] == "fpo-alpha"
    assert f1_data["estimated_grams"] == 500_000

    # Farmer 2 creates forecast
    f2_payload = {
        "crop": "Tomato",
        "variety": "Desi",
        "grade": "A",
        "estimated_grams": 300_000,
        "harvest_start_date": start,
        "harvest_end_date": end,
        "confidence_score": 0.90,
    }
    res2 = client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-2"},
        json=f2_payload,
    )
    assert res2.status_code == 201

    # Farmer 1 lists forecasts -> sees only their own (1)
    res_list1 = client.get("/api/v1/forecasts", headers={DEV_ACTOR_HEADER: "farmer-1"})
    assert res_list1.status_code == 200
    assert len(res_list1.json()) == 1
    assert res_list1.json()[0]["farmer_id"] == "farmer-1"

    # FPO admin lists forecasts -> sees both (2)
    res_list_fpo = client.get("/api/v1/forecasts", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_list_fpo.status_code == 200
    assert len(res_list_fpo.json()) == 2


def test_forecast_never_creates_physical_lot():
    app = create_app()
    client = TestClient(app)
    now = datetime.now(timezone.utc)

    client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Wheat",
            "variety": "Sharbati",
            "grade": "A",
            "estimated_grams": 1_000_000,
            "harvest_start_date": (now + timedelta(days=1)).isoformat(),
            "harvest_end_date": (now + timedelta(days=5)).isoformat(),
        },
    )
    # Check physical store lots
    lots = app.state.store.list_items("lots")
    assert len(lots) == 0, "Forecast must never produce physical lots in inventory!"


def test_repeated_submission_idempotency():
    app = create_app()
    client = TestClient(app)
    now = datetime.now(timezone.utc)

    payload = {
        "crop": "Potato",
        "variety": "Kufri",
        "grade": "B",
        "estimated_grams": 200_000,
        "harvest_start_date": (now + timedelta(days=1)).isoformat(),
        "harvest_end_date": (now + timedelta(days=3)).isoformat(),
        "idempotency_key": "potato-unique-999",
    }
    res1 = client.post("/api/v1/forecasts", headers={DEV_ACTOR_HEADER: "farmer-1"}, json=payload)
    assert res1.status_code == 201
    id1 = res1.json()["forecast_id"]

    # Re-submit identical key
    res2 = client.post("/api/v1/forecasts", headers={DEV_ACTOR_HEADER: "farmer-1"}, json=payload)
    assert res2.status_code == 200
    assert res2.json()["forecast_id"] == id1


def test_crop_grade_gap_analysis_and_expiry():
    app = create_app()
    client = TestClient(app)
    now = datetime.now(timezone.utc)

    # Farmer adds Grade B Wheat (400,000 g)
    client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Wheat",
            "grade": "B",
            "estimated_grams": 400_000,
            "harvest_start_date": (now + timedelta(days=2)).isoformat(),
            "harvest_end_date": (now + timedelta(days=6)).isoformat(),
        },
    )

    # Buyer adds Grade A Wheat requirement (500,000 g)
    client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Wheat",
            "grade": "A",
            "needed_grams": 500_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=10)).isoformat(),
            "max_price_paise_per_gram": 35,
        },
    )

    # Gap analysis for Grade A: demand = 500k, forecast = 0 -> deficit of 500k
    res_gap_a = client.get(
        "/api/v1/demand-gap?fpo_id=fpo-alpha&crop=Wheat&grade=A",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_gap_a.status_code == 200
    gap_a = res_gap_a.json()[0]
    assert gap_a["total_demand_grams"] == 500_000
    assert gap_a["total_forecast_grams"] == 0
    assert gap_a["net_gap_grams"] == 500_000
    assert "PLANNING ONLY" in gap_a["planning_disclaimer"]

    # Gap analysis for Grade B: demand = 0, forecast = 400k -> surplus of 400k (net gap = -400k)
    res_gap_b = client.get(
        "/api/v1/demand-gap?fpo_id=fpo-alpha&crop=Wheat&grade=B",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_gap_b.status_code == 200
    gap_b = res_gap_b.json()[0]
    assert gap_b["total_demand_grams"] == 0
    assert gap_b["total_forecast_grams"] == 400_000
    assert gap_b["net_gap_grams"] == -400_000


def test_expired_requirement_excluded_from_gap():
    app = create_app()
    client = TestClient(app)
    now = datetime.now(timezone.utc)

    # Expired buyer requirement in the past
    client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Mustard",
            "grade": "A",
            "needed_grams": 100_000,
            "delivery_window_start": (now - timedelta(days=10)).isoformat(),
            "delivery_window_end": (now - timedelta(days=2)).isoformat(),
            "max_price_paise_per_gram": 50,
        },
    )

    res_gap = client.get(
        "/api/v1/demand-gap?fpo_id=fpo-alpha&crop=Mustard&grade=A",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_gap.status_code == 200
    data = res_gap.json()
    assert len(data) == 0 or data[0]["total_demand_grams"] == 0


def test_v1_path_alias_routes():
    app = create_app()
    client = TestClient(app)
    now = datetime.now(timezone.utc)

    # Test /v1/forecasts
    res = client.post(
        "/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Millet",
            "grade": "A",
            "estimated_grams": 100_000,
            "harvest_start_date": (now + timedelta(days=1)).isoformat(),
            "harvest_end_date": (now + timedelta(days=4)).isoformat(),
        },
    )
    assert res.status_code == 201

    # Test /v1/demand-gaps
    res_gap = client.get(
        "/v1/demand-gaps?fpo_id=fpo-alpha&crop=Millet&grade=A",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_gap.status_code == 200
    assert len(res_gap.json()) == 1
    assert res_gap.json()[0]["total_forecast_grams"] == 100_000

