from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def setup_requirement_and_lots(client):
    now = datetime.now(timezone.utc)

    # 1. Buyer requirement for 600,000 g Grade A Onion
    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Onion",
            "grade": "A",
            "needed_grams": 600_000,
            "delivery_window_start": (now + timedelta(days=1)).isoformat(),
            "delivery_window_end": (now + timedelta(days=10)).isoformat(),
            "max_price_paise_per_gram": 30,
        },
    )
    req_id = res_req.json()["requirement_id"]

    # 2. FPO receives two lots: 400k g and 300k g
    res_lot1 = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Onion",
            "grade": "A",
            "quantity_grams": 400_000,
            "storage_location": "Silo-O1",
        },
    )
    lot1_id = res_lot1.json()["lot_id"]

    res_lot2 = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-2",
            "fpo_id": "fpo-alpha",
            "crop": "Onion",
            "grade": "A",
            "quantity_grams": 300_000,
            "storage_location": "Silo-O2",
        },
    )
    lot2_id = res_lot2.json()["lot_id"]

    return req_id, lot1_id, lot2_id


def test_atomic_commitment_success_and_reservation():
    app = create_app()
    client = TestClient(app)
    req_id, lot1_id, lot2_id = setup_requirement_and_lots(client)

    # Commit 500,000 g (400k from lot1, 100k from lot2)
    payload = {
        "requirement_id": req_id,
        "fpo_id": "fpo-alpha",
        "agreed_price_paise_per_gram": 28,
        "allocations": [
            {"lot_id": lot1_id, "allocated_grams": 400_000},
            {"lot_id": lot2_id, "allocated_grams": 100_000},
        ],
        "idempotency_key": "commit-key-100",
    }
    res = client.post("/api/v1/commitments", headers={DEV_ACTOR_HEADER: "buyer-reliance"}, json=payload)
    assert res.status_code == 201
    commit_data = res.json()
    assert commit_data["committed_grams"] == 500_000
    assert commit_data["status"] == "CONFIRMED"

    # Verify Lot 1 is fully reserved (0 available)
    l1 = client.get(f"/api/v1/lots/{lot1_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()
    assert l1["reserved_grams"] == 400_000
    assert l1["available_grams"] == 0

    # Verify Lot 2 has 100k reserved, 200k available
    l2 = client.get(f"/api/v1/lots/{lot2_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()
    assert l2["reserved_grams"] == 100_000
    assert l2["available_grams"] == 200_000

    # Verify requirement has 500k allocated
    req = client.get("/api/v1/requirements", headers={DEV_ACTOR_HEADER: "buyer-reliance"}).json()[0]
    assert req["allocated_grams"] == 500_000


def test_double_booking_race_rejected():
    app = create_app()
    client = TestClient(app)
    req_id, lot1_id, lot2_id = setup_requirement_and_lots(client)

    # First commitment takes all 400k from lot1
    client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 28,
            "allocations": [{"lot_id": lot1_id, "allocated_grams": 400_000}],
        },
    )

    # Second commitment attempts to reserve 100k from lot1 (only 0 available!)
    res_bad = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 28,
            "allocations": [{"lot_id": lot1_id, "allocated_grams": 100_000}],
        },
    )
    assert res_bad.status_code == 400
    assert res_bad.json()["error"] == "INVARIANT_VIOLATION"


def test_same_idempotency_key_different_payload_conflict():
    app = create_app()
    client = TestClient(app)
    req_id, lot1_id, lot2_id = setup_requirement_and_lots(client)

    payload1 = {
        "requirement_id": req_id,
        "fpo_id": "fpo-alpha",
        "agreed_price_paise_per_gram": 28,
        "allocations": [{"lot_id": lot1_id, "allocated_grams": 200_000}],
        "idempotency_key": "idemp-safe-1",
    }
    res1 = client.post("/api/v1/commitments", headers={DEV_ACTOR_HEADER: "buyer-reliance"}, json=payload1)
    assert res1.status_code == 201

    # Exact replay returns 200
    res_replay = client.post("/api/v1/commitments", headers={DEV_ACTOR_HEADER: "buyer-reliance"}, json=payload1)
    assert res_replay.status_code == 200

    # Conflicting payload with same idempotency key returns 409
    payload_diff = dict(payload1)
    payload_diff["agreed_price_paise_per_gram"] = 35
    res_conflict = client.post("/api/v1/commitments", headers={DEV_ACTOR_HEADER: "buyer-reliance"}, json=payload_diff)
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error"] == "CONFLICT"


def test_cancellation_pre_pickup_releases_inventory():
    app = create_app()
    client = TestClient(app)
    req_id, lot1_id, lot2_id = setup_requirement_and_lots(client)

    res_commit = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 28,
            "allocations": [{"lot_id": lot1_id, "allocated_grams": 300_000}],
        },
    )
    commit_id = res_commit.json()["commitment_id"]

    # Cancel pre-pickup
    res_cancel = client.post(f"/api/v1/commitments/{commit_id}/cancel", headers={DEV_ACTOR_HEADER: "buyer-reliance"})
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # Lot 1 reserved_grams must be back to 0, available back to 400k
    l1 = client.get(f"/api/v1/lots/{lot1_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()
    assert l1["reserved_grams"] == 0
    assert l1["available_grams"] == 400_000

    # Requirement allocated_grams back to 0
    req = client.get("/api/v1/requirements", headers={DEV_ACTOR_HEADER: "buyer-reliance"}).json()[0]
    assert req["allocated_grams"] == 0
