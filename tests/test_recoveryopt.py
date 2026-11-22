from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def setup_recovery_scenario(client):
    now = datetime.now(timezone.utc)

    # 1. Receive lot: 400,000 g Grade A Tomato at FPO Alpha
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Tomato",
            "grade": "A",
            "quantity_grams": 400_000,
            "storage_location": "Silo-A1",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    # 2. Setup an aging risk incident for this lot
    res_scan = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})

    # Create dummy incident directly for test if none generated
    inc_payload = {
        "incident_id": "inc-test-aging",
        "fpo_id": "fpo-alpha",
        "incident_type": "AGING_RISK",
        "dedup_key": f"AGING_RISK:{lot_id}",
        "severity": "HIGH",
        "title": "Perishable Aging Risk",
        "description": "Stock at risk",
        "resource_type": "lot",
        "resource_id": lot_id,
        "affected_grams": 400_000,
        "status": "OPEN",
    }
    client.app.state.store.set_item("incidents", "inc-test-aging", inc_payload)

    # 3. Create two candidate buyer requirements:
    # Buyer 1 (Reliance): Price 40 paise/g, but far away (high transport)
    client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Tomato",
            "grade": "A",
            "needed_grams": 400_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 40,
        },
    )

    # Buyer 2 (Local): Price 38 paise/g, local trader (low transport)
    client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-local"},
        json={
            "crop": "Tomato",
            "grade": "A",
            "needed_grams": 400_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 38,
        },
    )

    return lot_id, "inc-test-aging"


def test_generate_recovery_plan_and_net_return_ranking():
    app = create_app()
    client = TestClient(app)
    lot_id, inc_id = setup_recovery_scenario(client)

    res_plan = client.post(f"/api/v1/recovery/plans/generate?incident_id={inc_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_plan.status_code == 201
    plan = res_plan.json()
    assert plan["status"] == "RECOMMENDED"
    assert len(plan["candidates"]) >= 2
    assert "RECOMMENDATION ONLY" in plan["disclaimer"]
    assert plan["recommended_candidate"] is not None


def test_approval_requires_buyer_confirmation_first():
    app = create_app()
    client = TestClient(app)
    lot_id, inc_id = setup_recovery_scenario(client)

    res_plan = client.post(f"/api/v1/recovery/plans/generate?incident_id={inc_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    plan_id = res_plan.json()["plan_id"]

    # FPO admin attempts to approve without buyer confirmation -> 400
    res_bad_appr = client.post(f"/api/v1/recovery/plans/{plan_id}/approve", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_bad_appr.status_code == 400
    assert res_bad_appr.json()["error"] == "INVARIANT_VIOLATION"


def test_safe_approval_end_to_end():
    app = create_app()
    client = TestClient(app)
    lot_id, inc_id = setup_recovery_scenario(client)

    res_plan = client.post(f"/api/v1/recovery/plans/generate?incident_id={inc_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    plan = res_plan.json()
    plan_id = plan["plan_id"]
    rec_buyer = plan["recommended_candidate"]["buyer_id"]

    # 1. Buyer confirms
    res_conf = client.post(f"/api/v1/recovery/plans/{plan_id}/buyer-confirm", headers={DEV_ACTOR_HEADER: rec_buyer})
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "CONFIRMED_BY_BUYER"

    # 2. FPO Approves
    res_appr = client.post(f"/api/v1/recovery/plans/{plan_id}/approve", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "APPROVED"

    # 3. Verify lot is now reserved
    lot = client.get(f"/api/v1/lots/{lot_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()
    assert lot["reserved_grams"] == 400_000
    assert lot["available_grams"] == 0

    # 4. Verify incident resolved
    inc = client.app.state.store.get_item("incidents", inc_id)
    assert inc["status"] == "RESOLVED"
