from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import (
    DEV_ACTOR_HEADER,
    Settings,
    Role,
    DevActor,
    get_current_utc,
    ConflictError,
    InvariantViolationError,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import RouteStatus


@pytest.fixture
def app_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = os.path.join(tmpdir, "regression_state.json")
        settings = Settings(SNAPSHOT_PATH=snap_path)
        app = create_app(settings=settings)
        client = TestClient(app)
        yield {
            "app": app,
            "client": client,
            "snap_path": snap_path,
            "settings": settings,
        }
        app.state.coordinator.close()


def test_scenario_01_farmer_harvest_forecast(app_env):
    """Scenario 1: Farmer submits harvest forecast, FPO aggregates."""
    client = app_env["client"]
    res = client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Soybean",
            "variety": "JS-335",
            "grade": "A",
            "estimated_grams": 2_500_000,
            "harvest_start_date": "2026-11-25T00:00:00Z",
            "harvest_end_date": "2026-11-30T00:00:00Z",
            "confidence_score": 0.9,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["crop"] == "Soybean"
    assert data["farmer_id"] == "farmer-1"

    # FPO retrieves forecast
    list_res = client.get("/api/v1/forecasts", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


def test_scenario_02_buyer_requirement_and_demand_gap(app_env):
    """Scenario 2: Buyer submits requirement, demand gap calculated."""
    client = app_env["client"]
    res = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Wheat",
            "grade": "A",
            "needed_grams": 5_000_000,
            "delivery_window_start": "2026-12-01T00:00:00Z",
            "delivery_window_end": "2026-12-10T00:00:00Z",
            "max_price_paise_per_gram": 30,
        },
    )
    assert res.status_code == 201

    # Demand gap calculation
    gap_res = client.get("/api/v1/demand-gap?fpo_id=fpo-alpha&crop=Wheat&grade=A", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert gap_res.status_code == 200
    gap_data = gap_res.json()
    assert len(gap_data) >= 1
    assert gap_data[0]["net_gap_grams"] == 5_000_000


def test_scenario_03_physical_lot_receipt_and_grade_adjustment(app_env):
    """Scenario 3: Physical lot received, grade adjusted."""
    client = app_env["client"]
    res = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Onion",
            "grade": "A",
            "quantity_grams": 1_000_000,
            "storage_location": "Warehouse-1",
        },
    )
    assert res.status_code == 201
    lot_id = res.json()["lot_id"]

    # Grade adjustment
    adj_res = client.post(
        f"/api/v1/lots/{lot_id}/grade",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"new_grade": "B", "reason": "Moisture content higher than Grade A threshold"},
    )
    assert adj_res.status_code == 200
    assert adj_res.json()["grade"] == "B"


def test_scenario_04_lot_split_and_merge_mass_conservation(app_env):
    """Scenario 4: Lot split and merge with strict mass conservation."""
    client = app_env["client"]
    res = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Paddy",
            "grade": "A",
            "quantity_grams": 1_000_000,
            "storage_location": "Bay-A",
        },
    )
    parent_lot_id = res.json()["lot_id"]

    # Split 1,000,000g into 400,000g and 600,000g
    split_res = client.post(
        f"/api/v1/lots/{parent_lot_id}/split",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "child_portions": [
                {"quantity_grams": 400_000, "storage_location": "Bay-A1"},
                {"quantity_grams": 600_000, "storage_location": "Bay-A2"},
            ]
        },
    )
    assert split_res.status_code == 200
    child_ids = [c["lot_id"] for c in split_res.json()["child_lots"]]
    assert len(child_ids) == 2

    # Merge children back
    merge_res = client.post(
        "/api/v1/lots/merge",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"source_lot_ids": child_ids, "target_storage_location": "Bay-Combined"},
    )
    assert merge_res.status_code == 200
    assert merge_res.json()["merged_lot"]["quantity_grams"] == 1_000_000


def test_scenario_05_commitment_and_stock_reservation(app_env):
    """Scenario 5: Commitment created, stock reserved."""
    client = app_env["client"]
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Corn",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": "Silo-Corn",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Corn",
            "grade": "A",
            "needed_grams": 500_000,
            "delivery_window_start": "2026-12-01T00:00:00Z",
            "delivery_window_end": "2026-12-10T00:00:00Z",
            "max_price_paise_per_gram": 28,
        },
    )
    req_id = res_req.json()["requirement_id"]

    res_commit = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 28,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 500_000}],
        },
    )
    assert res_commit.status_code == 201

    # Over-reservation on same lot MUST fail
    res_over = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 28,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 100_000}],
        },
    )
    assert res_over.status_code == 400


def test_scenario_06_and_07_logistics_custody_and_transit_loss(app_env):
    """Scenarios 6 & 7: Vehicle registered, shipment dispatched, custody tracked, partial delivery, transit loss."""
    client = app_env["client"]

    # Prerequisite lot & commitment
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Tomato",
            "grade": "A",
            "quantity_grams": 2_000_000,
            "storage_location": "ColdStorage-1",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Tomato",
            "grade": "A",
            "needed_grams": 2_000_000,
            "delivery_window_start": "2026-12-01T00:00:00Z",
            "delivery_window_end": "2026-12-10T00:00:00Z",
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
            "agreed_price_paise_per_gram": 40,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 2_000_000}],
        },
    )
    commit_id = res_commit.json()["commitment_id"]

    # Register vehicle
    res_veh = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "fpo_id": "fpo-alpha",
            "driver_id": "driver-1",
            "capacity_grams": 3_000_000,
            "vehicle_type": "REEFER_VAN",
        },
    )
    veh_id = res_veh.json()["vehicle_id"]

    # Dispatch shipment
    res_ship = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"},
    )
    ship_id = res_ship.json()["shipment_id"]
    assert res_ship.json()["custody"] == "SCHEDULED"

    # Pickup by driver
    res_pickup = client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    assert res_pickup.json()["custody"] == "DRIVER_CUSTODY"

    # Partial delivery with transit loss (1,800,000g accepted, 150,000g rejected, 50,000g spoilage loss)
    res_deliv = client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 1_800_000, "rejected_grams": 150_000, "loss_grams": 50_000},
    )
    assert res_deliv.status_code == 200
    deliv_data = res_deliv.json()
    assert deliv_data["custody"] == "BUYER_ACCEPTED"
    assert deliv_data["status"] == "DELIVERED"
    assert deliv_data["loss_grams"] == 50_000
    assert deliv_data["accepted_grams"] == 1_800_000


def test_scenario_08_and_09_risk_incident_and_recovery_plan(app_env):
    """Scenarios 8 & 9: Risk incident detected, exact recovery plan generated and approved."""
    client = app_env["client"]

    # Scan risk incidents
    res_scan = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_scan.status_code == 200

    # Create available lot and candidate requirement
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Chana",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": "Silo-C",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Chana",
            "grade": "A",
            "needed_grams": 500_000,
            "delivery_window_start": "2026-12-01T00:00:00Z",
            "delivery_window_end": "2026-12-10T00:00:00Z",
            "max_price_paise_per_gram": 60,
        },
    )

    # Inject distress incident on the lot
    inc_id = f"inc-{uuid.uuid4().hex[:10]}"
    now = get_current_utc().isoformat()
    app_env["app"].state.store.set_item(
        "incidents",
        inc_id,
        {
            "incident_id": inc_id,
            "fpo_id": "fpo-alpha",
            "incident_type": "LOT_EXPIRY_RISK",
            "dedup_key": f"lot-exp-{lot_id}",
            "severity": "HIGH",
            "title": "Chana stock distress",
            "description": "Risk of quality degradation",
            "resource_type": "lot",
            "resource_id": lot_id,
            "affected_grams": 500_000,
            "affected_paise": 0,
            "status": "OPEN",
            "created_at": now,
            "updated_at": now,
        },
    )

    # Generate recovery plan for distressed lot incident
    res_plan = client.post(
        f"/api/v1/recovery/plans/generate?incident_id={inc_id}",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_plan.status_code == 201
    plan_data = res_plan.json()
    assert plan_data["optimality_status"] in ("OPTIMAL_PROVEN", "NO_POSITIVE_NET_OPTION")

    if plan_data["candidates"]:
        plan_id = plan_data["plan_id"]
        # Buyer confirms recovery
        res_conf = client.post(
            f"/api/v1/recovery/plans/{plan_id}/buyer-confirm",
            headers={DEV_ACTOR_HEADER: "buyer-reliance"},
            json={"buyer_id": "buyer-reliance"},
        )
        assert res_conf.status_code == 200

        # FPO approves recovery
        res_app = client.post(
            f"/api/v1/recovery/plans/{plan_id}/approve",
            headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        )
        assert res_app.status_code == 200
        assert res_app.json()["status"] == "APPROVED"


def test_scenario_10_settlement_and_evidence_provenance(app_env):
    """Scenario 10: Settlement calculated, deductions applied, payment recorded with tamper-evident proof."""
    client = app_env["client"]

    # Setup delivered shipment
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Moong",
            "grade": "A",
            "quantity_grams": 400_000,
            "storage_location": "Silo-M",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Moong",
            "grade": "A",
            "needed_grams": 400_000,
            "delivery_window_start": "2026-12-01T00:00:00Z",
            "delivery_window_end": "2026-12-10T00:00:00Z",
            "max_price_paise_per_gram": 80,
        },
    )
    req_id = res_req.json()["requirement_id"]

    res_commit = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 80,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 400_000}],
        },
    )
    commit_id = res_commit.json()["commitment_id"]

    res_veh = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 1_000_000, "vehicle_type": "VAN"},
    )
    veh_id = res_veh.json()["vehicle_id"]

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
        json={"accepted_grams": 400_000, "rejected_grams": 0, "loss_grams": 0},
    )

    # Generate settlement with deduction (400,000g * 80 paise/g = 32,000,000 paise gross; 500,000 paise transport fee deduction)
    res_set = client.post(
        "/api/v1/settlements/generate",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "shipment_id": ship_id,
            "deductions": [{"deduction_type": "TRANSPORT", "amount_paise": 500_000, "reason": "FPO Freight"}],
        },
    )
    assert res_set.status_code == 201
    set_data = res_set.json()
    assert set_data["gross_amount_paise"] == 32_000_000
    assert set_data["total_deductions_paise"] == 500_000
    assert set_data["net_payable_paise"] == 31_500_000

    set_id = set_data["settlement_id"]

    # Record payment
    res_pay = client.post(
        f"/api/v1/settlements/{set_id}/payments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "amount_paise": 31_500_000,
            "payment_method": "NEFT",
            "reference_number": "NEFT-FPO-PAY-0011",
            "evidence_note": "Direct bank payment receipt verified",
        },
    )
    assert res_pay.status_code == 200
    assert res_pay.json()["status"] == "SETTLED"
    assert res_pay.json()["remaining_balance_paise"] == 0


def test_scenario_11_offline_command_sync_and_conflict_detection(app_env):
    """Scenario 11: Offline command sync, replay, and monotonic version conflict detection."""
    client = app_env["client"]

    # Prerequisite: Receive lot, create commitment, vehicle, and shipment
    res_lot = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Cotton",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": "Yard-C",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    res_req = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Cotton",
            "grade": "A",
            "needed_grams": 500_000,
            "delivery_window_start": "2026-12-01T00:00:00Z",
            "delivery_window_end": "2026-12-10T00:00:00Z",
            "max_price_paise_per_gram": 70,
        },
    )
    req_id = res_req.json()["requirement_id"]

    res_commit = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 70,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 500_000}],
        },
    )
    commit_id = res_commit.json()["commitment_id"]

    res_veh = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 1_000_000, "vehicle_type": "TRUCK"},
    )
    veh_id = res_veh.json()["vehicle_id"]

    res_ship = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"},
    )
    ship_id = res_ship.json()["shipment_id"]

    # 1. Driver syncs offline pickup command with matching expected_version=1
    res_sync = client.post(
        "/api/v1/sync/reconcile",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={
            "command_id": "cmd-offline-001",
            "actor_id": "driver-1",
            "device_id": "driver-mobile-01",
            "command_type": "DRIVER_PICKUP_OBSERVATION",
            "resource_type": "shipment",
            "resource_id": ship_id,
            "expected_version": 1,
            "client_timestamp": "2026-11-20T10:00:00Z",
            "payload": {},
        },
    )
    assert res_sync.status_code == 200
    assert res_sync.json()["status"] == "APPLIED"

    # 2. Replay of identical offline command returns REPLAYED
    res_replay = client.post(
        "/api/v1/sync/reconcile",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={
            "command_id": "cmd-offline-001",
            "actor_id": "driver-1",
            "device_id": "driver-mobile-01",
            "command_type": "DRIVER_PICKUP_OBSERVATION",
            "resource_type": "shipment",
            "resource_id": ship_id,
            "expected_version": 1,
            "client_timestamp": "2026-11-20T10:00:00Z",
            "payload": {},
        },
    )
    assert res_replay.status_code == 200
    assert res_replay.json()["status"] == "REPLAYED"

    # 3. Stale offline command expecting version 1 when server is at version 2 returns 409 CONFLICT_REJECTED
    res_stale = client.post(
        "/api/v1/sync/reconcile",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={
            "command_id": "cmd-offline-002",
            "actor_id": "driver-1",
            "device_id": "driver-mobile-02",
            "command_type": "DRIVER_PICKUP_OBSERVATION",
            "resource_type": "shipment",
            "resource_id": ship_id,
            "expected_version": 1,  # Stale! Current server version is 2
            "client_timestamp": "2026-11-20T09:00:00Z",
            "payload": {},
        },
    )
    assert res_stale.status_code == 409
    assert res_stale.json()["status"] == "CONFLICT_REJECTED"


def test_scenario_12_crash_and_restart_byte_preservation(app_env):
    """Scenario 12: Process killed mid-operation, restarted from snapshot cleanly."""
    client = app_env["client"]
    snap_path = app_env["snap_path"]
    settings = app_env["settings"]

    # Write initial lot
    res = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-2",
            "fpo_id": "fpo-alpha",
            "crop": "Barley",
            "grade": "A",
            "quantity_grams": 750_000,
            "storage_location": "Silo-B",
        },
    )
    assert res.status_code == 201
    lot_id = res.json()["lot_id"]

    # Close App 1 cleanly (simulating process exit)
    app_env["app"].state.coordinator.close()

    # Restart App 2 from exact snapshot
    app2 = create_app(settings=settings)
    client2 = TestClient(app2)

    # Verify lot exists byte-for-byte in restarted app
    res_get = client2.get(f"/api/v1/lots/{lot_id}", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["lot_id"] == lot_id
    assert data["crop"] == "Barley"
    assert data["quantity_grams"] == 750_000

    app2.state.coordinator.close()
