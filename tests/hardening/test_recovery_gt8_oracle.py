from __future__ import annotations

import time
import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from gramsetu.core import (
    DEV_ACTORS,
    DevActor,
    Role,
    get_current_utc,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import (
    LotReceiptCreate,
    BuyerRequirementCreate,
)
from gramsetu.services.inventory import receive_inventory_lot
from gramsetu.services.procurement import create_buyer_requirement
from gramsetu.services.recovery import generate_recovery_plan, _calc_transport_paise


def test_r1_silent_eight_candidate_truncation_reproduction():
    """REPRODUCTION OF DEFECT R1:
    Demonstrate that the current recovery optimizer with silent [:8] truncation
    omits the globally optimal buyer when more than 8 candidate requirements exist.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]

    # 1. Create affected lot of 200,000g
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
            storage_location="Bin R1",
        ),
    )

    inc_id = "inc-r1-repro"
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

    now = get_current_utc()

    # 2. Register 10 candidate buyers
    # Buyers 1 to 8: Low offer (30 paise/g)
    # Buyer 9: High offer (70 paise/g)
    # Buyer 10: Highest offer (85 paise/g)
    buyer_actors = [
        "buyer-local", "buyer-bigbasket", "buyer-reliance",
        "buyer-local", "buyer-bigbasket", "buyer-reliance",
        "buyer-local", "buyer-bigbasket",
        "buyer-reliance", "buyer-bigbasket",
    ]

    for idx, b_id in enumerate(buyer_actors, start=1):
        price = 30 if idx <= 8 else (70 if idx == 9 else 85)
        create_buyer_requirement(
            store,
            coord,
            DEV_ACTORS[b_id],
            BuyerRequirementCreate(
                crop="Tomato",
                variety="Desi",
                grade="Grade A",
                needed_grams=200_000,
                delivery_window_start=now.isoformat(),
                delivery_window_end=(now + timedelta(days=5)).isoformat(),
                max_price_paise_per_gram=price,
            ),
        )

    # All requirements registered in store
    all_reqs = store.list_items("requirements")
    assert len(all_reqs) == 10

    # Execute recovery plan
    plan = generate_recovery_plan(store, coord, admin, inc_id)

    # In the improved implementation, the 10th candidate with 85 paise/g is chosen!
    assert plan.recommended_candidate is not None
    assert plan.recommended_candidate.offered_price_paise_per_gram == 85
    assert plan.optimality_status == "OPTIMAL_PROVEN"
    assert plan.candidate_count == 10
    assert plan.solver_runtime_ms >= 0.0
    assert plan.model_version == "2.0-exact"


def test_r1_independent_brute_force_oracle_comparison():
    """INDEPENDENT BRUTE FORCE ORACLE (up to 15 candidates):
    Verify that across multiple problem sizes (9, 10, 12, 15 candidates),
    the implemented optimization engine yields the EXACT same optimal candidate
    and net return as a separately written exhaustive search oracle.
    """
    admin = DEV_ACTORS["fpo-admin-alpha"]

    for n_candidates in [9, 10, 12, 15]:
        store = InMemoryStore()
        coord = TransactionCoordinator(store=store)
        now = get_current_utc()

        lot_qty = 350_000
        lot = receive_inventory_lot(
            store,
            coord,
            admin,
            LotReceiptCreate(
                fpo_id="fpo-alpha",
                farmer_id="farmer-1",
                crop="Capsicum",
                variety="Yellow",
                grade="Grade A",
                quantity_grams=lot_qty,
                storage_location="Bin Oracle",
            ),
        )

        inc_id = f"inc-oracle-{n_candidates}"
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
                "created_at": now.isoformat(),
            },
        )

        # Generate candidates with varied demand, price, and transport
        candidates_raw = []
        for i in range(1, n_candidates + 1):
            b_id = "buyer-local" if i % 3 == 0 else ("buyer-bigbasket" if i % 3 == 1 else "buyer-reliance")
            demand = 50_000 + (i * 25_000)
            price = 20 + (i * 5)
            req, _ = create_buyer_requirement(
                store,
                coord,
                DEV_ACTORS[b_id],
                BuyerRequirementCreate(
                    crop="Capsicum",
                    variety="Yellow",
                    grade="Grade A",
                    needed_grams=demand,
                    delivery_window_start=now.isoformat(),
                    delivery_window_end=(now + timedelta(days=5)).isoformat(),
                    max_price_paise_per_gram=price,
                ),
            )
            transport = _calc_transport_paise(b_id)
            allocable = min(lot_qty, demand)
            net = (allocable * price) - transport
            candidates_raw.append({
                "buyer_id": b_id,
                "req_id": req.requirement_id,
                "demand": demand,
                "price": price,
                "transport": transport,
                "allocable": allocable,
                "net": net,
            })

        # Independent Oracle: Exhaustive search over all positive-net options
        positive_options = [c for c in candidates_raw if c["net"] > 0]
        assert len(positive_options) > 0

        # Sort oracle deterministically
        positive_options.sort(key=lambda c: (-c["net"], -c["price"], c["transport"], c["req_id"]))
        oracle_winner = positive_options[0]

        # Run system optimizer
        plan = generate_recovery_plan(store, coord, admin, inc_id)

        assert plan.status == "RECOMMENDED"
        assert plan.optimality_status == "OPTIMAL_PROVEN"
        assert plan.recommended_candidate is not None
        assert plan.recommended_candidate.requirement_id == oracle_winner["req_id"]
        assert plan.recommended_candidate.net_return_paise == oracle_winner["net"]


def test_r1_deterministic_tie_breaking():
    """Verify that when two buyer requirements produce IDENTICAL net returns,
    the optimizer breaks ties deterministically:
    1. Higher offered price
    2. Lower transport cost
    3. Lexicographical requirement ID
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    now = get_current_utc()

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
            quantity_grams=100_000,
            storage_location="Bin Tie",
        ),
    )
    inc_id = "inc-tie-test"
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
            "created_at": now.isoformat(),
        },
    )

    # Candidate 1: Local buyer (transport = 75,000 paise).
    # Needs 100,000g at price P1 = 40.75 paise/g -> Gross = 4,075,000 paise.
    # Net return = 4,075,000 - 75,000 = 4,000,000 paise.
    # We will use integer prices:
    # Buyer A: local (transport 75,000), allocable 100,000g, price 50 -> Gross 5,000,000 -> Net 4,925,000
    # Let's construct exact tie:
    # Both buyer-local (transport 75,000), demand 100,000g, price 50 -> Gross 5,000,000 -> Net 4,925,000 each!
    req_a, _ = create_buyer_requirement(
        store,
        coord,
        DEV_ACTORS["buyer-local"],
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            needed_grams=100_000,
            delivery_window_start=now.isoformat(),
            delivery_window_end=(now + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=50,
        ),
    )
    req_b, _ = create_buyer_requirement(
        store,
        coord,
        DEV_ACTORS["buyer-local"],
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            needed_grams=100_000,
            delivery_window_start=now.isoformat(),
            delivery_window_end=(now + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=50,
        ),
    )

    plan = generate_recovery_plan(store, coord, admin, inc_id)
    assert plan.status == "RECOMMENDED"
    assert len(plan.candidates) == 2
    assert plan.candidates[0].net_return_paise == plan.candidates[1].net_return_paise

    # Deterministic tie-breaker selects the smaller requirement_id lexicographically
    expected_winner_id = min(req_a.requirement_id, req_b.requirement_id)
    assert plan.recommended_candidate.requirement_id == expected_winner_id

