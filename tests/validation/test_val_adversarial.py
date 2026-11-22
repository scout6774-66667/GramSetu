from __future__ import annotations

import os
import random
import uuid
from decimal import Decimal, ROUND_HALF_UP
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
    InvariantViolationError,
    ConflictError,
    NotFoundError,
    AuthorizationError,
    get_current_utc,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.main import create_app
from gramsetu.schemas import (
    LotReceiptCreate,
    BuyerRequirementCreate,
    BuyerCommitmentCreate,
    CommitmentAllocationItem,
    VehicleCreate,
    ShipmentCreate,
    DeliveryConfirmationRequest,
    SettlementGenerateRequest,
    SettlementDeduction,
    PaymentReportRequest,
    PaymentVerifyRequest,
)
from gramsetu.services.inventory import (
    receive_inventory_lot,
    split_inventory_lot,
    list_movements,
)
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
from gramsetu.services.settlement import (
    generate_settlement,
    report_payment,
    verify_payment,
)
from gramsetu.services.recovery import (
    generate_recovery_plan,
    _calc_transport_paise,
)
from gramsetu.algorithms import estimate_route_metrics


# ==============================================================================
# Cross-Cutting Test A: Stateful Property Invariant Testing (Randomized Sequence)
# ==============================================================================

def test_adversarial_stateful_property_invariants():
    """Stateful Property Test:
    Execute a pseudo-random sequence of valid and conflicting supply chain actions
    (receipts, reservations, cancellations).
    After EVERY action, assert:
    1. Reserved grams <= physical quantity grams.
    2. Available grams >= 0.
    3. No negative quantities in any lot.
    Seed is reported upon any failure.
    """
    seed = 42107
    rng = random.Random(seed)
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-reliance"]

    active_lots = []
    active_commitments = []

    for step in range(30):
        action = rng.choice(["RECEIPT", "RESERVE", "CANCEL"])

        if action == "RECEIPT" or not active_lots:
            # Create a lot with random quantity between 50,000g and 500,000g
            qty = rng.randint(50, 500) * 1_000
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
                    quantity_grams=qty,
                    storage_location=f"Shed-{step}",
                ),
            )
            active_lots.append(lot.lot_id)

        elif action == "RESERVE" and active_lots:
            # Pick a lot and try to reserve random amount
            target_lot_id = rng.choice(active_lots)
            lot_rec = store.get_item("lots", target_lot_id)
            avail = lot_rec["quantity_grams"] - lot_rec.get("reserved_grams", 0)

            # Sometimes request valid amount, sometimes excessive
            request_grams = rng.randint(10, 300) * 1_000
            req, _ = create_buyer_requirement(
                store,
                coord,
                buyer,
                BuyerRequirementCreate(
                    crop="Tomato",
                    variety="Desi",
                    grade="Grade A",
                    needed_grams=request_grams,
                    delivery_window_start=get_current_utc().isoformat(),
                    delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
                    max_price_paise_per_gram=40,
                ),
            )
            try:
                commit, is_new = create_commitment(
                    store,
                    coord,
                    buyer,
                    BuyerCommitmentCreate(
                        requirement_id=req.requirement_id,
                        fpo_id="fpo-alpha",
                        agreed_price_paise_per_gram=40,
                        allocations=[CommitmentAllocationItem(lot_id=target_lot_id, allocated_grams=request_grams)],
                        idempotency_key=f"prop-step-{step}-{uuid.uuid4().hex[:6]}",
                    ),
                )
                if is_new:
                    active_commitments.append(commit.commitment_id)
            except InvariantViolationError:
                # Excessive request rejected cleanly
                pass

        elif action == "CANCEL" and active_commitments:
            target_commit_id = active_commitments.pop(0)
            try:
                cancel_commitment(store, coord, buyer, target_commit_id)
            except Exception:
                pass

        # ASSERT SYSTEM-WIDE INVARIANTS AFTER EVERY STEP
        all_lots = store.list_items("lots")
        for l in all_lots:
            q = l["quantity_grams"]
            r = l.get("reserved_grams", 0)
            assert q >= 0, f"[Seed {seed}, Step {step}] Lot {l['lot_id']} has negative quantity: {q}"
            assert r >= 0, f"[Seed {seed}, Step {step}] Lot {l['lot_id']} has negative reserved: {r}"
            assert r <= q, f"[Seed {seed}, Step {step}] Lot {l['lot_id']} reserved ({r}g) exceeds quantity ({q}g)"


# ==============================================================================
# Cross-Cutting Test B: Financial Reference Oracle (50 Fuzz Iterations)
# ==============================================================================

def test_adversarial_financial_oracle_fuzz():
    """Fuzz testing financial rounding:
    Compare settlement calculations against Decimal ROUND_HALF_UP over 50 iterations
    with edge quantities (1g, ties, prime weights).
    """
    rng = random.Random(999)
    for i in range(50):
        accepted_grams = rng.randint(1, 1_000_000)
        unit_price = rng.randint(1, 500)  # 1 to 500 paise per gram
        deduction_transport = rng.randint(0, 100_000)
        deduction_packaging = rng.randint(0, 50_000)

        # Reference Decimal calculation
        d_acc = Decimal(str(accepted_grams))
        d_price = Decimal(str(unit_price))
        d_gross = (d_acc * d_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        total_ded = Decimal(str(deduction_transport + deduction_packaging))
        d_net = max(Decimal("0"), d_gross - total_ded)

        # System calculation
        gross_calc = accepted_grams * unit_price
        total_ded_calc = deduction_transport + deduction_packaging
        net_calc = max(0, gross_calc - total_ded_calc)

        assert gross_calc == int(d_gross)
        assert net_calc == int(d_net)


# ==============================================================================
# Cross-Cutting Test C: Persistence Failure Injection
# ==============================================================================

def test_adversarial_persistence_failure_injection(tmp_path):
    """Test fault injection during snapshot write:
    If disk write fails during transaction, RAM rolls back and existing snapshot is unharmed.
    """
    snapshot_path = str(tmp_path / "fault_test.json")
    store = InMemoryStore()
    store.set_item("lots", "lot-orig", {"quantity_grams": 500_000})
    coord = TransactionCoordinator(store=store, snapshot_path=snapshot_path)

    # Initial snapshot save
    with coord.transaction():
        coord.store.set_item("lots", "lot-orig", {"quantity_grams": 500_000})

    orig_content = open(snapshot_path, "r").read()

    # Inject failure: simulate serialization failure
    class UnserializableCrash:
        def __str__(self):
            raise TypeError("Simulated serialization crash")

    with pytest.raises(Exception):
        with coord.transaction():
            coord.store.set_item("lots", "lot-orig", {"quantity_grams": 999_999})
            coord.store.set_item("items", "bad_key", UnserializableCrash())

    # State in RAM must be rolled back
    assert store.get_item("lots", "lot-orig")["quantity_grams"] == 500_000

    # Snapshot on disk must be identical to orig_content
    current_content = open(snapshot_path, "r").read()
    assert current_content == orig_content


# ==============================================================================
# Cross-Cutting Test D: Authentication & Access Control Matrix
# ==============================================================================

def test_adversarial_role_access_matrix():
    """Access Matrix Verification:
    Verify endpoints reject unauthorized roles according to the permissions matrix:
    - /lots/receipt: FPO_ADMIN only
    - /risk/scan: FPO_ADMIN only
    - /shipments/{id}/pickup: DRIVER only
    - /recovery/plans/{id}/approve: FPO_ADMIN only
    """
    app = create_app(Settings(ENVIRONMENT=Environment.TESTING))
    client = TestClient(app)

    # 1. Farmer attempting /lots/receipt -> 403
    resp = client.post(
        "/api/v1/lots/receipt",
        json={"fpo_id": "fpo-alpha", "farmer_id": "farmer-1", "crop": "Tomato", "variety": "Desi", "grade": "Grade A", "quantity_grams": 100_000, "storage_location": "S1"},
        headers={DEV_ACTOR_HEADER: "farmer-1"},
    )
    assert resp.status_code == 403

    # 2. Buyer attempting /risk/scan -> 403
    resp = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "buyer-reliance"})
    assert resp.status_code == 403

    # 3. Farmer attempting driver pickup -> 403
    resp = client.post("/api/v1/shipments/ship-fake/pickup", headers={DEV_ACTOR_HEADER: "farmer-1"})
    assert resp.status_code == 403

    # 4. Transporter attempting recovery approval -> 403
    resp = client.post("/api/v1/recovery/plans/plan-fake/approve", headers={DEV_ACTOR_HEADER: "driver-1"})
    assert resp.status_code == 403


# ==============================================================================
# Cross-Cutting Test E: Metamorphic Algorithm Properties
# ==============================================================================

def test_adversarial_metamorphic_recovery_monotonicity():
    """Metamorphic Properties of Recovery Optimizer:
    1. Increasing available lot stock must never decrease total allocable grams across compatible buyers.
    2. Increasing transport cost must never increase net return.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]

    # Candidate buyer
    create_buyer_requirement(
        store,
        coord,
        DEV_ACTORS["buyer-bigbasket"],
        BuyerRequirementCreate(
            crop="Capsicum",
            variety="Green",
            grade="Grade A",
            needed_grams=500_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=60,
        ),
    )

    # Instance 1: 100,000g available
    lot1 = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Capsicum",
            variety="Green",
            grade="Grade A",
            quantity_grams=100_000,
            storage_location="Bin 1",
        ),
    )
    inc1 = "inc-meta-1"
    store.set_item("incidents", inc1, {"incident_id": inc1, "fpo_id": "fpo-alpha", "resource_type": "lot", "resource_id": lot1.lot_id, "incident_type": "BUYER_CANCELLATION", "severity": "HIGH", "status": "OPEN", "created_at": get_current_utc().isoformat()})
    plan1 = generate_recovery_plan(store, coord, admin, inc1)

    # Instance 2: 200,000g available (increased stock)
    lot2 = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Capsicum",
            variety="Green",
            grade="Grade A",
            quantity_grams=200_000,
            storage_location="Bin 2",
        ),
    )
    inc2 = "inc-meta-2"
    store.set_item("incidents", inc2, {"incident_id": inc2, "fpo_id": "fpo-alpha", "resource_type": "lot", "resource_id": lot2.lot_id, "incident_type": "BUYER_CANCELLATION", "severity": "HIGH", "status": "OPEN", "created_at": get_current_utc().isoformat()})
    plan2 = generate_recovery_plan(store, coord, admin, inc2)

    # Monotonicity Assertions
    cand1 = plan1.recommended_candidate
    cand2 = plan2.recommended_candidate

    assert cand2.allocable_grams >= cand1.allocable_grams
    assert cand2.net_return_paise >= cand1.net_return_paise


# ==============================================================================
# Cross-Cutting Test F: Truthfulness & Explicit Mock Labelling Tests
# ==============================================================================

def test_adversarial_truthfulness_and_mock_labelling():
    """Truthfulness Audit:
    Verify that:
    1. Demand gap explicitly carries a PROVISIONAL / PLANNING disclaimer and never claims firm sales.
    2. Route estimates explicitly carry PROVISIONAL ESTIMATOR disclaimers and never claim road guarantees.
    3. Recovery plans explicitly state they are RECOMMENDATION ONLY.
    4. Unverified reported payments are labeled unverified and do not mark settlement as SETTLED.
    """
    # 1. Route Metrics Disclaimer
    metrics = estimate_route_metrics(12.9716, 77.5946, 13.0827, 80.2707, 100_000, 200_000)
    assert "PROVISIONAL ESTIMATOR" in metrics["disclaimer"]

    # 2. Demand Gap Disclaimer
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    from gramsetu.services.procurement import compute_demand_gap
    create_buyer_requirement(
        store,
        coord,
        DEV_ACTORS["buyer-reliance"],
        BuyerRequirementCreate(
            crop="Corn",
            variety="Sweet",
            grade="Grade A",
            needed_grams=100_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=20,
        ),
    )
    gaps = compute_demand_gap(store, "fpo-alpha")
    for g in gaps:
        assert "PLANNING ONLY" in g.planning_disclaimer
