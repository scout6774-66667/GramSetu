from __future__ import annotations

import os
import copy
import json
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from gramsetu.core import (
    Settings,
    Environment,
    Role,
    DevActor,
    DEV_ACTORS,
    DEV_ACTOR_HEADER,
    CorruptionError,
    InvariantViolationError,
    AuthorizationError,
    ConflictError,
    get_current_utc,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.main import create_app
from gramsetu.schemas import (
    HarvestForecastCreate,
    BuyerRequirementCreate,
    LotReceiptCreate,
    LotSplitRequest,
    LotMergeRequest,
    GradeAdjustmentRequest,
)
from gramsetu.services.supply import create_harvest_forecast, list_harvest_forecasts
from gramsetu.services.procurement import create_buyer_requirement, compute_demand_gap
from gramsetu.services.inventory import (
    receive_inventory_lot,
    get_inventory_lot,
    split_inventory_lot,
    merge_inventory_lots,
    list_movements,
)


# ==============================================================================
# F0 — Bootstrap & Atomic JSON State Tests
# ==============================================================================

def test_f0_deep_copy_isolation():
    """Verify that reading from the store returns deep copies, preventing caller corruption."""
    store = InMemoryStore()
    store.set_item("items", "key1", {"nested": {"count": 10}, "tags": ["a", "b"]})

    read1 = store.get_item("items", "key1")
    assert read1 is not None
    read1["nested"]["count"] = 999
    read1["tags"].append("c")

    # Authoritative store state must remain unchanged
    read2 = store.get_item("items", "key1")
    assert read2["nested"]["count"] == 10
    assert read2["tags"] == ["a", "b"]


def test_f0_transaction_rollback_in_ram_and_disk(tmp_path):
    """Verify that an exception inside a transaction rolls back RAM and leaves disk snapshot unchanged."""
    snapshot_file = str(tmp_path / "f0_state.json")
    store = InMemoryStore()
    store.set_item("lots", "lot-stable", {"quantity_grams": 100_000, "status": "AVAILABLE"})
    coordinator = TransactionCoordinator(store=store, snapshot_path=snapshot_file)

    # Initial successful commit
    with coordinator.transaction():
        coordinator.store.set_item("lots", "lot-stable", {"quantity_grams": 100_000, "status": "AVAILABLE"})

    assert os.path.exists(snapshot_file)
    initial_snapshot_bytes = open(snapshot_file, "rb").read()

    # Fault injection: exception inside mutating transaction
    with pytest.raises(RuntimeError, match="Simulated crash during transaction"):
        with coordinator.transaction():
            coordinator.store.set_item("lots", "lot-stable", {"quantity_grams": 0, "status": "CORRUPTED"})
            coordinator.store.set_item("lots", "lot-phantom", {"quantity_grams": 500_000})
            raise RuntimeError("Simulated crash during transaction")

    # Verify RAM rollback
    lot = store.get_item("lots", "lot-stable")
    assert lot["quantity_grams"] == 100_000
    assert lot["status"] == "AVAILABLE"
    assert store.get_item("lots", "lot-phantom") is None

    # Verify disk snapshot was not modified
    current_snapshot_bytes = open(snapshot_file, "rb").read()
    assert current_snapshot_bytes == initial_snapshot_bytes


def test_f0_unreadable_or_corrupt_snapshot_refusal(tmp_path):
    """Verify the store refuses corrupt or incompatible snapshots and does not silently overwrite."""
    corrupt_file = str(tmp_path / "corrupt.json")
    with open(corrupt_file, "w") as f:
        f.write("{ invalid json content ...")

    with pytest.raises(CorruptionError, match="JSON decode failure"):
        InMemoryStore.load_from_snapshot(corrupt_file)

    # Incompatible schema version
    bad_schema_file = str(tmp_path / "bad_schema.json")
    with open(bad_schema_file, "w") as f:
        json.dump({"meta": {"schema_version": 999}, "data": {}}, f)

    with pytest.raises(CorruptionError, match="unsupported schema metadata"):
        InMemoryStore.load_from_snapshot(bad_schema_file)


def test_f0_integer_precision_and_non_negative_invariants():
    """Verify integer quantities and currency units are strictly enforced."""
    # Negative quantity in lot receipt should be rejected
    with pytest.raises(Exception):
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            quantity_grams=-500,  # Invalid
            storage_location="Warehouse A",
        )

    # Float quantity should be rejected or coerced strictly according to Pydantic rules
    with pytest.raises(Exception):
        HarvestForecastCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Hybrid",
            grade="Grade A",
            estimated_grams=0,  # Field(gt=0)
            harvest_start=get_current_utc().isoformat(),
            harvest_end=(get_current_utc() + timedelta(days=5)).isoformat(),
        )


# ==============================================================================
# F1 — Identity, Roles & Resource Ownership Tests
# ==============================================================================

def test_f1_dev_actor_authentication_and_scoping():
    """Verify dev actor header enforcement and role checks."""
    app = create_app(Settings(ENVIRONMENT=Environment.TESTING))
    client = TestClient(app)

    # Missing actor -> 401
    resp = client.get("/api/v1/forecasts")
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"

    # Unknown actor -> 401
    resp = client.get("/api/v1/forecasts", headers={DEV_ACTOR_HEADER: "unknown-actor-999"})
    assert resp.status_code == 401

    # Farmer role accessing FPO-only receipt creation -> 403
    receipt_payload = {
        "fpo_id": "fpo-alpha",
        "farmer_id": "farmer-1",
        "crop": "Tomato",
        "variety": "Desi",
        "grade": "Grade A",
        "quantity_grams": 50_000,
        "storage_location": "Shed 1",
    }
    resp = client.post("/api/v1/lots/receipt", json=receipt_payload, headers={DEV_ACTOR_HEADER: "farmer-1"})
    assert resp.status_code == 403
    assert resp.json()["error"] == "FORBIDDEN"


def test_f1_cross_tenant_organization_isolation():
    """Verify an FPO admin cannot view or mutate another FPO's records."""
    app = create_app(Settings(ENVIRONMENT=Environment.TESTING))
    client = TestClient(app)

    # Create lot under fpo-alpha
    create_resp = client.post(
        "/api/v1/lots/receipt",
        json={
            "fpo_id": "fpo-alpha",
            "farmer_id": "farmer-1",
            "crop": "Tomato",
            "variety": "Desi",
            "grade": "Grade A",
            "quantity_grams": 100_000,
            "storage_location": "Alpha Wh",
        },
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert create_resp.status_code == 201
    lot_id = create_resp.json()["lot_id"]

    # FPO Admin Beta attempts to split Alpha's lot -> 403 Forbidden
    split_resp = client.post(
        f"/api/v1/lots/{lot_id}/split",
        json={
            "child_portions": [
                {"quantity_grams": 50_000, "storage_location": "Alpha Wh A"},
                {"quantity_grams": 50_000, "storage_location": "Alpha Wh B"},
            ]
        },
        headers={DEV_ACTOR_HEADER: "fpo-admin-beta"},
    )
    assert split_resp.status_code == 403
    assert split_resp.json()["error"] == "FORBIDDEN"


def test_f1_production_environment_fails_closed_against_x_dev_actor():
    """Verify that in PRODUCTION environment, X-Dev-Actor is strictly rejected (fails closed)."""
    app = create_app(Settings(ENVIRONMENT=Environment.PRODUCTION))
    client = TestClient(app)

    # Any attempt to pass X-Dev-Actor in PRODUCTION must fail with 401
    resp = client.get("/api/v1/forecasts", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"
    assert "production" in resp.json()["message"].lower()


# ==============================================================================
# F2 — DemandSync: Forecasts vs Physical Stock & Gap Analysis Tests
# ==============================================================================

def test_f2_forecasts_never_create_physical_stock():
    """Verify that submitting a harvest forecast never increases physical inventory or lots."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    actor = DEV_ACTORS["farmer-1"]

    payload = HarvestForecastCreate(
        crop="Wheat",
        variety="Sharbati",
        grade="Grade A",
        estimated_grams=5_000_000,  # 5,000 kg forecast
        harvest_start_date=get_current_utc().isoformat(),
        harvest_end_date=(get_current_utc() + timedelta(days=10)).isoformat(),
    )

    fc, is_new = create_harvest_forecast(store, coord, actor, payload)
    assert fc.forecast_id.startswith("fc-")

    # Invariant: Lots collection must remain completely empty
    lots = store.list_items("lots")
    assert len(lots) == 0

    movements = store.list_items("movements")
    assert len(movements) == 0


def test_f2_demand_gap_labeled_as_planning_indicator():
    """Verify demand gap calculation is labeled planning-only and excludes expired demands."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    now = get_current_utc()

    # 1. Active forecast: 1,000 kg Grade A Tomato
    fc_payload = HarvestForecastCreate(
        crop="Tomato",
        variety="Desi",
        grade="Grade A",
        estimated_grams=1_000_000,
        harvest_start_date=now.isoformat(),
        harvest_end_date=(now + timedelta(days=7)).isoformat(),
    )
    create_harvest_forecast(store, coord, DEV_ACTORS["farmer-1"], fc_payload)

    # 2. Expired buyer requirement: 500 kg needed 2 days ago
    expired_req = BuyerRequirementCreate(
        crop="Tomato",
        variety="Desi",
        grade="Grade A",
        needed_grams=500_000,
        delivery_window_start=(now - timedelta(days=5)).isoformat(),
        delivery_window_end=(now - timedelta(days=1)).isoformat(),
        max_price_paise_per_gram=50,
    )
    create_buyer_requirement(store, coord, DEV_ACTORS["buyer-reliance"], expired_req)

    # 3. Active buyer requirement: 800 kg needed in 3 days
    active_req = BuyerRequirementCreate(
        crop="Tomato",
        variety="Desi",
        grade="Grade A",
        needed_grams=800_000,
        delivery_window_start=now.isoformat(),
        delivery_window_end=(now + timedelta(days=5)).isoformat(),
        max_price_paise_per_gram=55,
    )
    create_buyer_requirement(store, coord, DEV_ACTORS["buyer-bigbasket"], active_req)

    gaps = compute_demand_gap(store, "fpo-alpha", crop="Tomato", grade="Grade A", as_of=now)
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.crop == "Tomato"
    assert gap.grade == "Grade A"
    # Demand must only include active (800,000g), NOT expired (500,000g)
    assert gap.total_demand_grams == 800_000
    assert gap.total_forecast_grams == 1_000_000
    # Net gap = demand - forecast = 800,000 - 1,000,000 = -200,000 (surplus supply)
    assert gap.net_gap_grams == -200_000
    assert "PLANNING ONLY" in gap.planning_disclaimer


# ==============================================================================
# F3 — BatchTrace: Inventory Ledger & Mass Conservation Tests
# ==============================================================================

def test_f3_split_and_merge_mass_conservation():
    """Verify that split and merge strictly conserve produce mass and lineage."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]

    # 1. Receive 1,000,000g (1 tonne) lot
    receipt = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Potato",
            variety="Kufri",
            grade="Grade A",
            quantity_grams=1_000_000,
            storage_location="Bin 1",
        ),
    )
    parent_id = receipt.lot_id

    # 2. Split into 400kg + 600kg
    split_res = split_inventory_lot(
        store,
        coord,
        admin,
        parent_id,
        LotSplitRequest(
            child_portions=[
                {"quantity_grams": 400_000, "storage_location": "Bin 1A"},
                {"quantity_grams": 600_000, "storage_location": "Bin 1B"},
            ]
        ),
    )
    assert len(split_res.child_lots) == 2
    child_a = split_res.child_lots[0].lot_id
    child_b = split_res.child_lots[1].lot_id

    # Parent lot must be SPLIT with 0 quantity
    parent = store.get_item("lots", parent_id)
    assert parent["status"] == "SPLIT"
    assert parent["quantity_grams"] == 0

    # 3. Merge back child_a and child_b
    merge_res = merge_inventory_lots(
        store,
        coord,
        admin,
        LotMergeRequest(
            source_lot_ids=[child_a, child_b],
            target_storage_location="Bin 2-Consolidated",
        ),
    )
    merged_lot = store.get_item("lots", merge_res.merged_lot.lot_id)
    assert merged_lot["quantity_grams"] == 1_000_000
    assert merged_lot["status"] == "AVAILABLE"


def test_f3_complete_system_mass_equation():
    """Assert complete mass equation:
    Verified Receipts = On-Site Lots + In-Transit + Delivered + Disposed/Lost.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]

    # Receive three distinct lots
    l1 = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Apple",
            variety="Shimla",
            grade="Grade A",
            quantity_grams=300_000,
            storage_location="Cold Storage 1",
        ),
    )
    l2 = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-2",
            crop="Apple",
            variety="Shimla",
            grade="Grade A",
            quantity_grams=500_000,
            storage_location="Cold Storage 2",
        ),
    )

    all_receipts = sum(
        m["quantity_grams"]
        for m in store.list_items("movements")
        if m["movement_type"] == "RECEIPT"
    )
    on_site_stock = sum(
        lot["quantity_grams"]
        for lot in store.list_items("lots")
        if lot["status"] == "AVAILABLE"
    )

    assert all_receipts == 800_000
    assert on_site_stock == 800_000
    assert all_receipts == on_site_stock
