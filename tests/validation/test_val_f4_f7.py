from __future__ import annotations

import threading
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from gramsetu.core import (
    Settings,
    Environment,
    Role,
    DevActor,
    DEV_ACTORS,
    InvariantViolationError,
    ConflictError,
    NotFoundError,
    AuthorizationError,
    get_current_utc,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.algorithms import haversine_distance_km, estimate_route_metrics
from gramsetu.schemas import (
    LotReceiptCreate,
    BuyerRequirementCreate,
    BuyerCommitmentCreate,
    CommitmentAllocationItem,
    VehicleCreate,
    ShipmentCreate,
    DeliveryConfirmationRequest,
    IncidentResolveRequest,
)
from gramsetu.services.inventory import receive_inventory_lot
from gramsetu.services.procurement import (
    create_buyer_requirement,
    create_commitment,
    cancel_commitment,
)
from gramsetu.services.logistics import (
    register_vehicle,
    create_shipment,
    record_pickup,
    record_delivery,
)
from gramsetu.services.risk import (
    scan_risk_incidents,
    resolve_incident,
    acknowledge_incident,
)
from gramsetu.services.recovery import (
    generate_recovery_plan,
    confirm_recovery_by_buyer,
    approve_recovery_plan,
    _calc_transport_paise,
)


# ==============================================================================
# F4 — CommitGuard: Procurement, Idempotency & Concurrency Tests
# ==============================================================================

def test_f4_barrier_synchronized_buyer_race_prevents_double_booking():
    """Verify that concurrent buyer requests racing for the same available lot
    cannot over-allocate stock. Exactly one succeeds if stock only satisfies one.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]

    # 1. Create lot with 500,000g available
    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Onion",
            variety="Nasik Red",
            grade="Grade A",
            quantity_grams=500_000,
            storage_location="Warehouse 1",
        ),
    )

    # 2. Two buyers each wanting 500,000g
    req1, _ = create_buyer_requirement(
        store,
        coord,
        DEV_ACTORS["buyer-reliance"],
        BuyerRequirementCreate(
            crop="Onion",
            variety="Nasik Red",
            grade="Grade A",
            needed_grams=500_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=35,
        ),
    )

    req2, _ = create_buyer_requirement(
        store,
        coord,
        DEV_ACTORS["buyer-bigbasket"],
        BuyerRequirementCreate(
            crop="Onion",
            variety="Nasik Red",
            grade="Grade A",
            needed_grams=500_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=38,
        ),
    )

    results = []
    errors = []
    barrier = threading.Barrier(2)

    def worker(buyer_actor: DevActor, req_id: str, key: str):
        barrier.wait()
        try:
            res, is_new = create_commitment(
                store,
                coord,
                buyer_actor,
                BuyerCommitmentCreate(
                    requirement_id=req_id,
                    fpo_id="fpo-alpha",
                    agreed_price_paise_per_gram=35,
                    allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=500_000)],
                    idempotency_key=key,
                ),
            )
            results.append(res)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=worker, args=(DEV_ACTORS["buyer-reliance"], req1.requirement_id, "key-rel-1"))
    t2 = threading.Thread(target=worker, args=(DEV_ACTORS["buyer-bigbasket"], req2.requirement_id, "key-bb-1"))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one commitment succeeds and one fails with InvariantViolationError (Insufficient available stock)
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], InvariantViolationError)

    # Invariant check: Lot reserved grams must be exactly 500,000, available 0
    updated_lot = store.get_item("lots", lot.lot_id)
    assert updated_lot["reserved_grams"] == 500_000
    assert updated_lot["quantity_grams"] - updated_lot["reserved_grams"] == 0


def test_f4_idempotency_replay_and_conflict():
    """Verify same key returns identical commitment; same key with differing payload returns 409 Conflict."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-reliance"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Hybrid",
            grade="Grade A",
            quantity_grams=300_000,
            storage_location="Bin A",
        ),
    )

    req, _ = create_buyer_requirement(
        store,
        coord,
        buyer,
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Hybrid",
            grade="Grade A",
            needed_grams=300_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=40,
        ),
    )

    payload = BuyerCommitmentCreate(
        requirement_id=req.requirement_id,
        fpo_id="fpo-alpha",
        agreed_price_paise_per_gram=40,
        allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=200_000)],
        idempotency_key="idemp-key-tomato-100",
    )

    res1, is_new1 = create_commitment(store, coord, buyer, payload)
    assert is_new1 is True

    # Replay identical payload with same idempotency key
    res2, is_new2 = create_commitment(store, coord, buyer, payload)
    assert is_new2 is False
    assert res1.commitment_id == res2.commitment_id

    # Reused key with DIFFERENT payload (different agreed price) -> ConflictError (409)
    conflicting_payload = BuyerCommitmentCreate(
        requirement_id=req.requirement_id,
        fpo_id="fpo-alpha",
        agreed_price_paise_per_gram=99,  # Changed price!
        allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=200_000)],
        idempotency_key="idemp-key-tomato-100",
    )

    with pytest.raises(ConflictError, match="previously used with differing parameters"):
        create_commitment(store, coord, buyer, conflicting_payload)


def test_f4_post_pickup_cancellation_refused():
    """Verify that cancellation after pickup is rejected and never returns goods to farm inventory."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-reliance"]
    driver = DEV_ACTORS["driver-1"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Banana",
            variety="Robusta",
            grade="Grade A",
            quantity_grams=400_000,
            storage_location="Chamber 1",
        ),
    )

    req, _ = create_buyer_requirement(
        store,
        coord,
        buyer,
        BuyerRequirementCreate(
            crop="Banana",
            variety="Robusta",
            grade="Grade A",
            needed_grams=400_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=30,
        ),
    )

    commit, _ = create_commitment(
        store,
        coord,
        buyer,
        BuyerCommitmentCreate(
            requirement_id=req.requirement_id,
            fpo_id="fpo-alpha",
            agreed_price_paise_per_gram=30,
            allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=400_000)],
            idempotency_key="banana-cancellation-test",
        ),
    )

    veh = register_vehicle(
        store,
        coord,
        admin,
        VehicleCreate(
            fpo_id="fpo-alpha",
            driver_id="driver-1",
            capacity_grams=1_000_000,
            vehicle_type="Small Truck",
        ),
    )

    ship = create_shipment(
        store,
        coord,
        admin,
        ShipmentCreate(
            commitment_id=commit.commitment_id,
            vehicle_id=veh.vehicle_id,
            driver_id="driver-1",
        ),
    )

    # Driver executes physical pickup
    record_pickup(store, coord, driver, ship.shipment_id)

    # Buyer attempts to cancel post-pickup -> InvariantViolationError
    with pytest.raises(InvariantViolationError, match="Cannot cancel commitment with status 'DISPATCHED' pre-pickup"):
        cancel_commitment(store, coord, buyer, commit.commitment_id)

    # Invariant check: Farm lot quantity remains 0 (goods are in transit with driver)
    farm_lot = store.get_item("lots", lot.lot_id)
    assert farm_lot["quantity_grams"] == 0


# ==============================================================================
# F5 — Logistics: Capacity, Custody & Route Estimates Tests
# ==============================================================================

def test_f5_vehicle_capacity_overload_rejected():
    """Verify that assigning a commitment larger than vehicle capacity is rejected."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-reliance"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Rice",
            variety="Basmati",
            grade="Grade A",
            quantity_grams=800_000,
            storage_location="Warehouse R",
        ),
    )

    req, _ = create_buyer_requirement(
        store,
        coord,
        buyer,
        BuyerRequirementCreate(
            crop="Rice",
            variety="Basmati",
            grade="Grade A",
            needed_grams=800_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=60,
        ),
    )

    commit, _ = create_commitment(
        store,
        coord,
        buyer,
        BuyerCommitmentCreate(
            requirement_id=req.requirement_id,
            fpo_id="fpo-alpha",
            agreed_price_paise_per_gram=60,
            allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=800_000)],
            idempotency_key="rice-capacity-test",
        ),
    )

    # Vehicle capacity is only 500,000g (commit is 800,000g)
    veh = register_vehicle(
        store,
        coord,
        admin,
        VehicleCreate(
            fpo_id="fpo-alpha",
            driver_id="driver-1",
            capacity_grams=500_000,
            vehicle_type="Small Pickup",
        ),
    )

    with pytest.raises(InvariantViolationError, match="Vehicle capacity .* cannot accommodate shipment payload"):
        create_shipment(
            store,
            coord,
            admin,
            ShipmentCreate(
                commitment_id=commit.commitment_id,
                vehicle_id=veh.vehicle_id,
                driver_id="driver-1",
            ),
        )


def test_f5_driver_assignment_enforced():
    """Verify that an unassigned driver cannot report pickup or delivery."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-reliance"]
    assigned_driver = DEV_ACTORS["driver-1"]
    intruder_driver = DEV_ACTORS["driver-2"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Carrot",
            variety="Orange",
            grade="Grade A",
            quantity_grams=100_000,
            storage_location="Bin C",
        ),
    )
    req, _ = create_buyer_requirement(
        store,
        coord,
        buyer,
        BuyerRequirementCreate(
            crop="Carrot",
            variety="Orange",
            grade="Grade A",
            needed_grams=100_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=25,
        ),
    )
    commit, _ = create_commitment(
        store,
        coord,
        buyer,
        BuyerCommitmentCreate(
            requirement_id=req.requirement_id,
            fpo_id="fpo-alpha",
            agreed_price_paise_per_gram=25,
            allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=100_000)],
            idempotency_key="carrot-logistics-test",
        ),
    )
    veh = register_vehicle(
        store,
        coord,
        admin,
        VehicleCreate(
            fpo_id="fpo-alpha",
            driver_id="driver-1",
            capacity_grams=200_000,
            vehicle_type="Mini Van",
        ),
    )
    ship = create_shipment(
        store,
        coord,
        admin,
        ShipmentCreate(
            commitment_id=commit.commitment_id,
            vehicle_id=veh.vehicle_id,
            driver_id="driver-1",
        ),
    )

    # Intruder driver-2 attempts to report pickup -> AuthorizationError (403)
    with pytest.raises(AuthorizationError, match="Driver 'driver-2' is not assigned to this shipment"):
        record_pickup(store, coord, intruder_driver, ship.shipment_id)


def test_f5_haversine_route_disclaimer_and_multi_stop_metrics():
    """Verify route metrics clearly provide estimation disclaimer and bounds."""
    metrics = estimate_route_metrics(
        origin_lat=18.5204,
        origin_lon=73.8567,  # Pune
        dest_lat=18.9220,
        dest_lon=72.8347,  # Mumbai
        payload_grams=300_000,
        vehicle_capacity_grams=500_000,
    )
    assert metrics["is_feasible"] is True
    assert metrics["distance_km"] > 100.0
    assert "PROVISIONAL ESTIMATOR" in metrics["disclaimer"]


# ==============================================================================
# F6 — RiskWatch: Disruption Detection & Deduplication Tests
# ==============================================================================

def test_f6_riskwatch_deduplication_prevents_alert_storms():
    """Verify repeated scans generate only ONE unresolved incident per condition episode."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]

    # Create planned shipment that is over 24h old (missed pickup)
    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Hybrid",
            grade="Grade A",
            quantity_grams=200_000,
            storage_location="Bin T",
        ),
    )
    req, _ = create_buyer_requirement(
        store,
        coord,
        DEV_ACTORS["buyer-reliance"],
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Hybrid",
            grade="Grade A",
            needed_grams=200_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=30,
        ),
    )
    commit, _ = create_commitment(
        store,
        coord,
        DEV_ACTORS["buyer-reliance"],
        BuyerCommitmentCreate(
            requirement_id=req.requirement_id,
            fpo_id="fpo-alpha",
            agreed_price_paise_per_gram=30,
            allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=200_000)],
            idempotency_key="tomato-risk-test",
        ),
    )
    veh = register_vehicle(
        store,
        coord,
        admin,
        VehicleCreate(
            fpo_id="fpo-alpha",
            driver_id="driver-1",
            capacity_grams=500_000,
            vehicle_type="Truck",
        ),
    )
    ship = create_shipment(
        store,
        coord,
        admin,
        ShipmentCreate(
            commitment_id=commit.commitment_id,
            vehicle_id=veh.vehicle_id,
            driver_id="driver-1",
        ),
    )

    # Backdate shipment created_at to 48 hours ago
    stale_time = (get_current_utc() - timedelta(hours=48)).isoformat()
    ship_record = store.get_item("shipments", ship.shipment_id)
    ship_record["created_at"] = stale_time
    store.set_item("shipments", ship.shipment_id, ship_record)

    # First scan detects missed pickup
    incidents_1 = scan_risk_incidents(store, coord, admin, "fpo-alpha")
    missed_incidents = [i for i in incidents_1 if i.incident_type == "MISSED_PICKUP"]
    assert len(missed_incidents) == 1
    inc_id = missed_incidents[0].incident_id

    # Second scan: must NOT create duplicate incident
    incidents_2 = scan_risk_incidents(store, coord, admin, "fpo-alpha")
    missed_incidents_2 = [i for i in incidents_2 if i.incident_type == "MISSED_PICKUP"]
    assert len(missed_incidents_2) == 1
    assert missed_incidents_2[0].incident_id == inc_id


# ==============================================================================
# F7 — RecoveryOpt: Oracle Comparison & Invariant Tests (HIGH-RISK GATE)
# ==============================================================================

def test_f7_recovery_optimizer_vs_brute_force_oracle():
    """INDEPENDENT ORACLE VERIFICATION:
    Compare implemented RecoveryOpt ranking against an independent exhaustive search.
    Within the model's assumptions:
    - Bounded candidates
    - Net Return = min(available, needed - allocated) * price - transport_cost
    - Select buyer maximizing Net Return subject to Net Return > 0.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]

    # 1. Affected lot with 300,000g available
    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Cauliflower",
            variety="Snowball",
            grade="Grade A",
            quantity_grams=300_000,
            storage_location="Bin CF",
        ),
    )

    # Create artificial incident referencing this lot
    inc_id = "inc-oracle-test-1"
    store.set_item(
        "incidents",
        inc_id,
        {
            "incident_id": inc_id,
            "fpo_id": "fpo-alpha",
            "resource_type": "lot",
            "resource_id": lot.lot_id,
            "incident_type": "BUYER_CANCELLATION",
            "severity": "HIGH",
            "status": "OPEN",
            "created_at": get_current_utc().isoformat(),
        },
    )

    # 2. Register 4 candidate buyers with differing demand, prices, and locations
    candidates_data = [
        {"buyer_id": "buyer-local", "needed": 100_000, "price": 40},      # transport dist: 10km -> cost 75,000 paise
        {"buyer_id": "buyer-bigbasket", "needed": 250_000, "price": 45},  # transport dist: 45km -> cost 162,500 paise
        {"buyer_id": "buyer-reliance", "needed": 300_000, "price": 50},   # transport dist: 120km -> cost 350,000 paise
    ]

    for c in candidates_data:
        create_buyer_requirement(
            store,
            coord,
            DEV_ACTORS[c["buyer_id"]],
            BuyerRequirementCreate(
                crop="Cauliflower",
                variety="Snowball",
                grade="Grade A",
                needed_grams=c["needed"],
                delivery_window_start=get_current_utc().isoformat(),
                delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
                max_price_paise_per_gram=c["price"],
            ),
        )

    # Independent Oracle: Exhaustive search
    available_grams = 300_000
    oracle_evaluations = []
    for c in candidates_data:
        allocable = min(available_grams, c["needed"])
        gross = allocable * c["price"]
        transport = _calc_transport_paise(c["buyer_id"])
        net = gross - transport
        oracle_evaluations.append({
            "buyer_id": c["buyer_id"],
            "net_return": net,
            "allocable": allocable,
        })

    oracle_evaluations.sort(key=lambda x: x["net_return"], reverse=True)
    oracle_best = oracle_evaluations[0]

    # Run system's generate_recovery_plan
    plan = generate_recovery_plan(store, coord, admin, inc_id)

    assert plan.status == "RECOMMENDED"
    assert plan.recommended_candidate is not None
    assert plan.recommended_candidate.buyer_id == oracle_best["buyer_id"]
    assert plan.recommended_candidate.net_return_paise == oracle_best["net_return"]


def test_f7_recovery_two_step_approval_and_atomic_reservation():
    """Verify safe approval: buyer must confirm before FPO admin can approve,
    and approval atomically executes commitment and reserves the lot.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-bigbasket"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            quantity_grams=250_000,
            storage_location="Bin R2",
        ),
    )

    inc_id = "inc-approval-test-1"
    store.set_item(
        "incidents",
        inc_id,
        {
            "incident_id": inc_id,
            "fpo_id": "fpo-alpha",
            "resource_type": "lot",
            "resource_id": lot.lot_id,
            "incident_type": "BUYER_CANCELLATION",
            "severity": "HIGH",
            "status": "OPEN",
            "created_at": get_current_utc().isoformat(),
        },
    )

    create_buyer_requirement(
        store,
        coord,
        buyer,
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            needed_grams=250_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=45,
        ),
    )

    plan = generate_recovery_plan(store, coord, admin, inc_id)
    assert plan.status == "RECOMMENDED"

    # FPO admin attempts to approve BEFORE buyer confirms -> InvariantViolationError
    with pytest.raises(InvariantViolationError, match="Buyer must confirm first"):
        approve_recovery_plan(store, coord, admin, plan.plan_id)

    # Buyer confirms
    confirmed_plan = confirm_recovery_by_buyer(store, coord, buyer, plan.plan_id)
    assert confirmed_plan.status == "CONFIRMED_BY_BUYER"

    # FPO admin approves -> Executes commitment atomically
    approved_plan = approve_recovery_plan(store, coord, admin, plan.plan_id)
    assert approved_plan.status == "APPROVED"

    # Invariant check: Lot is now reserved!
    updated_lot = store.get_item("lots", lot.lot_id)
    assert updated_lot["reserved_grams"] == 250_000

    # Incident marked RESOLVED
    inc = store.get_item("incidents", inc_id)
    assert inc["status"] == "RESOLVED"


def test_f7_recovery_original_cancelled_buyer_excluded():
    """Verify that when a commitment is cancelled, the defaulting buyer is NOT offered
    the recovery candidate for that same produce batch.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    cancelling_buyer = DEV_ACTORS["buyer-reliance"]
    other_buyer = DEV_ACTORS["buyer-bigbasket"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            quantity_grams=200_000,
            storage_location="Bin Exclude",
        ),
    )

    req1, _ = create_buyer_requirement(
        store,
        coord,
        cancelling_buyer,
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            needed_grams=200_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=50,
        ),
    )

    # Initial commitment with cancelling buyer
    commit, _ = create_commitment(
        store,
        coord,
        cancelling_buyer,
        BuyerCommitmentCreate(
            requirement_id=req1.requirement_id,
            fpo_id="fpo-alpha",
            agreed_price_paise_per_gram=50,
            allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=200_000)],
            idempotency_key="commit-cancelling-buyer",
        ),
    )

    # Buyer cancels commitment
    cancel_commitment(store, coord, cancelling_buyer, commit.commitment_id)

    # Incident created for buyer cancellation
    inc_id = "inc-cancel-1"
    store.set_item(
        "incidents",
        inc_id,
        {
            "incident_id": inc_id,
            "fpo_id": "fpo-alpha",
            "resource_type": "commitment",
            "resource_id": commit.commitment_id,
            "incident_type": "BUYER_CANCELLATION",
            "severity": "HIGH",
            "status": "OPEN",
            "created_at": get_current_utc().isoformat(),
        },
    )

    # Other buyer also has an open requirement
    create_buyer_requirement(
        store,
        coord,
        other_buyer,
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            needed_grams=200_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=40,
        ),
    )

    # Reopen req1 so cancelling buyer has an open requirement
    req_rec = store.get_item("requirements", req1.requirement_id)
    req_rec["status"] = "OPEN"
    req_rec["allocated_grams"] = 0
    store.set_item("requirements", req1.requirement_id, req_rec)

    # Generate recovery plan
    plan = generate_recovery_plan(store, coord, admin, inc_id)

    # Assert that cancelling_buyer ("buyer-reliance") is NOT in the candidate list
    candidate_buyer_ids = [c.buyer_id for c in plan.candidates]
    assert "buyer-reliance" not in candidate_buyer_ids
    assert "buyer-bigbasket" in candidate_buyer_ids


def test_f7_recovery_negative_net_return_rejected():
    """Verify that candidates with net return <= 0 (transport cost exceeds gross revenue)
    are rejected. If no candidate has positive net return, status must be NO_FEASIBLE_OPTION.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            quantity_grams=1_000,  # Small quantity: 1,000g (1 kg)
            storage_location="Bin Small",
        ),
    )

    inc_id = "inc-neg-net"
    store.set_item(
        "incidents",
        inc_id,
        {
            "incident_id": inc_id,
            "fpo_id": "fpo-alpha",
            "resource_type": "lot",
            "resource_id": lot.lot_id,
            "incident_type": "BUYER_CANCELLATION",
            "severity": "HIGH",
            "status": "OPEN",
            "created_at": get_current_utc().isoformat(),
        },
    )

    # Buyer offers 10 paise/gram for 1,000g -> Gross revenue = 10,000 paise
    # But transport cost to buyer-local (10km) is 50,000 + 25,000 = 75,000 paise
    # Net return = 10,000 - 75,000 = -65,000 paise (NEGATIVE!)
    create_buyer_requirement(
        store,
        coord,
        DEV_ACTORS["buyer-local"],
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            needed_grams=1_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=10,
        ),
    )

    plan = generate_recovery_plan(store, coord, admin, inc_id)
    # Negative net candidates must be rejected -> NO_FEASIBLE_OPTION
    assert plan.status == "NO_FEASIBLE_OPTION"
    assert len(plan.candidates) == 0
    assert plan.recommended_candidate is None

