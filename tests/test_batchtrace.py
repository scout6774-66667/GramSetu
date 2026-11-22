from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER


def test_receipt_creation_and_scoping():
    app = create_app()
    client = TestClient(app)

    payload = {
        "farmer_id": "farmer-1",
        "fpo_id": "fpo-alpha",
        "crop": "Tomato",
        "variety": "Desi",
        "grade": "A",
        "quantity_grams": 500_000,
        "storage_location": "Silo-A1",
    }

    # Wrong FPO admin cannot receive for Alpha
    res_bad = client.post("/api/v1/lots/receipt", headers={DEV_ACTOR_HEADER: "fpo-admin-beta"}, json=payload)
    assert res_bad.status_code == 403

    # Correct FPO admin can receive
    res_ok = client.post("/api/v1/lots/receipt", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}, json=payload)
    assert res_ok.status_code == 201
    lot = res_ok.json()
    assert lot["farmer_id"] == "farmer-1"
    assert lot["quantity_grams"] == 500_000
    assert lot["reserved_grams"] == 0
    assert lot["available_grams"] == 500_000
    assert lot["custody"] == "FPO_WAREHOUSE"
    assert lot["version"] == 1


def test_negative_quantity_rejection():
    app = create_app()
    client = TestClient(app)

    payload = {
        "farmer_id": "farmer-1",
        "fpo_id": "fpo-alpha",
        "crop": "Tomato",
        "grade": "A",
        "quantity_grams": -10_000,  # Negative!
        "storage_location": "Silo-A1",
    }
    res = client.post("/api/v1/lots/receipt", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}, json=payload)
    assert res.status_code == 422  # Pydantic validation rejection


def test_split_conservation_and_lineage():
    app = create_app()
    client = TestClient(app)

    # 1. Create parent lot (1,000,000 g)
    res_parent = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Wheat",
            "grade": "A",
            "quantity_grams": 1_000_000,
            "storage_location": "Bin-1",
        },
    )
    parent_id = res_parent.json()["lot_id"]

    # 2. Split into 600k and 400k
    res_split = client.post(
        f"/api/v1/lots/{parent_id}/split",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "child_portions": [
                {"quantity_grams": 600_000, "storage_location": "Bin-1A"},
                {"quantity_grams": 400_000, "storage_location": "Bin-1B"},
            ]
        },
    )
    assert res_split.status_code == 200
    children = res_split.json()["child_lots"]
    assert len(children) == 2
    assert sum(c["quantity_grams"] for c in children) == 1_000_000
    assert children[0]["parent_lot_ids"] == [parent_id]

    # Verify parent is now SPLIT and unavailable
    res_get_parent = client.get(f"/api/v1/lots/{parent_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_get_parent.json()["status"] == "SPLIT"
    assert res_get_parent.json()["available_grams"] == 0

    # 3. Test non-conserving split rejection (sum != parent)
    res_bad_split = client.post(
        f"/api/v1/lots/{children[0]['lot_id']}/split",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "child_portions": [
                {"quantity_grams": 300_000, "storage_location": "Bin-X"},
                {"quantity_grams": 200_000, "storage_location": "Bin-Y"},  # Sum 500k != 600k
            ]
        },
    )
    assert res_bad_split.status_code == 400
    assert res_bad_split.json()["error"] == "INVARIANT_VIOLATION"


def test_merge_conservation_and_compatibility():
    app = create_app()
    client = TestClient(app)

    # 1. Create two lots
    res1 = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Corn",
            "grade": "A",
            "quantity_grams": 300_000,
            "storage_location": "Bin-C1",
        },
    )
    id1 = res1.json()["lot_id"]

    res2 = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-2",
            "fpo_id": "fpo-alpha",
            "crop": "Corn",
            "grade": "A",
            "quantity_grams": 700_000,
            "storage_location": "Bin-C2",
        },
    )
    id2 = res2.json()["lot_id"]

    # 2. Merge lots
    res_merge = client.post(
        "/api/v1/lots/merge",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "source_lot_ids": [id1, id2],
            "target_storage_location": "Bin-C-Consolidated",
        },
    )
    assert res_merge.status_code == 200
    merged = res_merge.json()["merged_lot"]
    assert merged["quantity_grams"] == 1_000_000
    assert merged["crop"] == "Corn"
    assert merged["grade"] == "A"
    assert set(merged["parent_lot_ids"]) == {id1, id2}

    # Verify sources are marked MERGED
    assert client.get(f"/api/v1/lots/{id1}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()["status"] == "MERGED"
    assert client.get(f"/api/v1/lots/{id2}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}).json()["status"] == "MERGED"


def test_split_merge_blocked_when_reserved():
    app = create_app()
    coordinator = app.state.coordinator

    # Manually setup a lot with reserved_grams > 0
    with coordinator.transaction():
        coordinator.store.set_item(
            "lots",
            "lot-res-1",
            {
                "lot_id": "lot-res-1",
                "fpo_id": "fpo-alpha",
                "farmer_id": "farmer-1",
                "crop": "Rice",
                "grade": "A",
                "quantity_grams": 500_000,
                "reserved_grams": 100_000,
                "storage_location": "Silo-R",
                "custody": "FPO_WAREHOUSE",
                "version": 1,
                "created_at": "2026-11-17T00:00:00Z",
                "updated_at": "2026-11-17T00:00:00Z",
                "parent_lot_ids": [],
                "status": "AVAILABLE",
            },
        )

    client = TestClient(app)
    # Attempt split
    res = client.post(
        "/api/v1/lots/lot-res-1/split",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"child_portions": [{"quantity_grams": 250_000, "storage_location": "A"}, {"quantity_grams": 250_000, "storage_location": "B"}]},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "INVARIANT_VIOLATION"


def test_inventory_movement_ledger():
    app = create_app()
    client = TestClient(app)

    res_rcpt = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Barley",
            "grade": "A",
            "quantity_grams": 600_000,
            "storage_location": "Silo-B1",
        },
    )
    lot_id = res_rcpt.json()["lot_id"]

    # Check movements for this lot
    res_mov = client.get(f"/api/v1/lots/{lot_id}/movements", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_mov.status_code == 200
    movs = res_mov.json()
    assert len(movs) == 1
    assert movs[0]["movement_type"] == "RECEIPT"
    assert movs[0]["quantity_grams"] == 600_000
    assert movs[0]["dest_custody"] == "FPO_WAREHOUSE"

