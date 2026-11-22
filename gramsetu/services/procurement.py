from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    InvariantViolationError,
    get_current_utc,
    verify_organization_access,
    verify_buyer_access,
)
from gramsetu.schemas import (
    BuyerRequirementCreate,
    BuyerRequirementResponse,
    DemandGapAnalysis,
    BuyerCommitmentCreate,
    BuyerCommitmentResponse,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator


def create_buyer_requirement(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: BuyerRequirementCreate,
) -> Tuple[BuyerRequirementResponse, bool]:
    """Create a new buyer requirement idempotently. Returns (requirement, was_created)."""
    if actor.role not in (Role.BUYER, Role.SYSTEM):
        raise AuthorizationError("Only registered buyers or system engine can record demand requirements.")

    buyer_id = actor.actor_id

    # Idempotency check
    if payload.idempotency_key:
        existing = store.list_items(
            "requirements",
            lambda item: item.get("buyer_id") == buyer_id and item.get("idempotency_key") == payload.idempotency_key,
        )
        if existing:
            return BuyerRequirementResponse(**existing[0]), False

    req_id = f"req-{uuid.uuid4().hex[:10]}"
    now = get_current_utc()

    record = {
        "requirement_id": req_id,
        "buyer_id": buyer_id,
        "crop": payload.crop,
        "variety": payload.variety,
        "grade": payload.grade,
        "needed_grams": payload.needed_grams,
        "allocated_grams": 0,
        "delivery_window_start": payload.delivery_window_start.isoformat(),
        "delivery_window_end": payload.delivery_window_end.isoformat(),
        "max_price_paise_per_gram": payload.max_price_paise_per_gram,
        "created_at": now.isoformat(),
        "idempotency_key": payload.idempotency_key,
        "status": "OPEN",
    }

    with coordinator.transaction():
        coordinator.store.set_item("requirements", req_id, record)

    return BuyerRequirementResponse(**record), True


def list_buyer_requirements(
    store: InMemoryStore,
    actor: DevActor,
    crop: Optional[str] = None,
    grade: Optional[str] = None,
    status: Optional[str] = None,
) -> List[BuyerRequirementResponse]:
    """List requirements scoped by actor."""
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.BUYER and item.get("buyer_id") != actor.actor_id:
            return False
        if crop and item.get("crop", "").lower() != crop.lower():
            return False
        if grade and item.get("grade", "").upper() != grade.upper():
            return False
        if status and item.get("status", "").upper() != status.upper():
            return False
        return True

    items = store.list_items("requirements", filter_fn)
    return [BuyerRequirementResponse(**item) for item in items]


def compute_demand_gap(
    store: InMemoryStore,
    fpo_id: str,
    crop: Optional[str] = None,
    grade: Optional[str] = None,
    as_of: Optional[datetime] = None,
) -> List[DemandGapAnalysis]:
    """Compute planning demand-gap analysis by comparing active requirements vs forecasts."""
    current_time = as_of or get_current_utc()

    # Active forecasts for FPO
    forecasts = store.list_items(
        "forecasts",
        lambda item: item.get("fpo_id") == fpo_id and item.get("status") == "ACTIVE",
    )

    # Active buyer requirements (not expired as of current_time)
    def active_req(item: dict) -> bool:
        if item.get("status") != "OPEN":
            return False
        end_str = item.get("delivery_window_end")
        if end_str:
            end_dt = datetime.fromisoformat(end_str)
            if end_dt < current_time:
                return False
        return True

    requirements = store.list_items("requirements", active_req)

    # Group keys: (crop, grade)
    groups: Dict[Tuple[str, str], Dict[str, int]] = {}

    for req in requirements:
        c = req.get("crop", "")
        g = req.get("grade", "")
        if crop and c.lower() != crop.lower():
            continue
        if grade and g.upper() != grade.upper():
            continue
        key = (c, g)
        if key not in groups:
            groups[key] = {"demand": 0, "forecast": 0}
        remaining_demand = req.get("needed_grams", 0) - req.get("allocated_grams", 0)
        groups[key]["demand"] += max(0, remaining_demand)

    for fc in forecasts:
        c = fc.get("crop", "")
        g = fc.get("grade", "")
        if crop and c.lower() != crop.lower():
            continue
        if grade and g.upper() != grade.upper():
            continue
        key = (c, g)
        if key not in groups:
            groups[key] = {"demand": 0, "forecast": 0}
        groups[key]["forecast"] += fc.get("estimated_grams", 0)

    results: List[DemandGapAnalysis] = []
    for (c, g), counts in groups.items():
        demand = counts["demand"]
        forecast = counts["forecast"]
        net_gap = demand - forecast
        coverage = round(forecast / demand, 2) if demand > 0 else (1.0 if forecast > 0 else 0.0)

        results.append(
            DemandGapAnalysis(
                fpo_id=fpo_id,
                crop=c,
                grade=g,
                total_demand_grams=demand,
                total_forecast_grams=forecast,
                net_gap_grams=net_gap,
                coverage_ratio=coverage,
                as_of=current_time,
            )
        )

    return sorted(results, key=lambda x: (x.crop, x.grade))


def create_commitment(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: BuyerCommitmentCreate,
) -> Tuple[BuyerCommitmentResponse, bool]:
    """Atomically commit inventory lots against an open buyer requirement."""
    if actor.role not in (Role.BUYER, Role.SYSTEM):
        raise AuthorizationError("Only buyers or system engine can create procurement commitments.")

    now = get_current_utc()

    # Idempotency check
    if payload.idempotency_key:
        existing = store.list_items(
            "commitments",
            lambda item: item.get("idempotency_key") == payload.idempotency_key,
        )
        if existing:
            c = existing[0]
            # Check payload equivalence
            same_req = c.get("requirement_id") == payload.requirement_id
            same_price = c.get("agreed_price_paise_per_gram") == payload.agreed_price_paise_per_gram
            allocs_sum = sum(a["allocated_grams"] for a in c.get("allocations", []))
            payload_sum = sum(a.allocated_grams for a in payload.allocations)
            if same_req and same_price and allocs_sum == payload_sum:
                return BuyerCommitmentResponse(**c), False
            else:
                raise ConflictError(
                    f"Idempotency key '{payload.idempotency_key}' was previously used with differing parameters."
                )

    with coordinator.transaction():
        req = coordinator.store.get_item("requirements", payload.requirement_id)
        if not req:
            raise NotFoundError(f"Buyer requirement '{payload.requirement_id}' not found.")
        verify_buyer_access(actor, req["buyer_id"])

        if req.get("status") != "OPEN":
            raise InvariantViolationError(f"Requirement is not OPEN (status: {req.get('status')}).")

        # Expiry check
        end_str = req.get("delivery_window_end")
        if end_str and datetime.fromisoformat(end_str) < now:
            raise InvariantViolationError(f"Requirement delivery window ended at {end_str}; cannot commit.")

        total_requested = sum(a.allocated_grams for a in payload.allocations)
        rem_demand = req["needed_grams"] - req.get("allocated_grams", 0)
        if total_requested > rem_demand:
            raise InvariantViolationError(
                f"Requested commitment ({total_requested}g) exceeds remaining unfilled demand ({rem_demand}g)."
            )

        # Validate all lots
        lots_to_update = []
        for alloc in payload.allocations:
            lot = coordinator.store.get_item("lots", alloc.lot_id)
            if not lot:
                raise NotFoundError(f"Inventory lot '{alloc.lot_id}' not found.")
            if lot.get("fpo_id") != payload.fpo_id:
                raise InvariantViolationError(
                    f"Lot '{alloc.lot_id}' belongs to FPO '{lot.get('fpo_id')}', expected '{payload.fpo_id}'."
                )
            if lot.get("crop", "").lower() != req.get("crop", "").lower():
                raise InvariantViolationError(f"Crop mismatch: lot is {lot.get('crop')}, req is {req.get('crop')}.")
            if lot.get("grade", "").upper() != req.get("grade", "").upper():
                raise InvariantViolationError(f"Grade mismatch: lot is {lot.get('grade')}, req is {req.get('grade')}.")
            if lot.get("status") != "AVAILABLE":
                raise InvariantViolationError(f"Lot '{alloc.lot_id}' is not AVAILABLE (status: {lot.get('status')}).")

            available = lot["quantity_grams"] - lot.get("reserved_grams", 0)
            if alloc.allocated_grams > available:
                raise InvariantViolationError(
                    f"Insufficient available stock in lot '{alloc.lot_id}': requested {alloc.allocated_grams}g, available {available}g."
                )

            lot["reserved_grams"] = lot.get("reserved_grams", 0) + alloc.allocated_grams
            lot["version"] += 1
            lot["updated_at"] = now.isoformat()
            lots_to_update.append(lot)

        # Apply lot updates
        for lot in lots_to_update:
            coordinator.store.set_item("lots", lot["lot_id"], lot)

        # Update requirement
        req["allocated_grams"] = req.get("allocated_grams", 0) + total_requested
        if req["allocated_grams"] >= req["needed_grams"]:
            req["status"] = "FULFILLED"
        req["updated_at"] = now.isoformat()
        coordinator.store.set_item("requirements", req["requirement_id"], req)

        # Save commitment
        commit_id = f"com-{uuid.uuid4().hex[:10]}"
        commit_record = {
            "commitment_id": commit_id,
            "requirement_id": req["requirement_id"],
            "buyer_id": req["buyer_id"],
            "fpo_id": payload.fpo_id,
            "crop": req["crop"],
            "grade": req["grade"],
            "agreed_price_paise_per_gram": payload.agreed_price_paise_per_gram,
            "committed_grams": total_requested,
            "allocations": [a.model_dump() for a in payload.allocations],
            "created_at": now.isoformat(),
            "idempotency_key": payload.idempotency_key,
            "status": "CONFIRMED",
        }
        coordinator.store.set_item("commitments", commit_id, commit_record)

    return BuyerCommitmentResponse(**commit_record), True


def cancel_commitment(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    commitment_id: str,
) -> BuyerCommitmentResponse:
    """Cancel a commitment pre-pickup and release reserved inventory atomically."""
    with coordinator.transaction():
        commit = coordinator.store.get_item("commitments", commitment_id)
        if not commit:
            raise NotFoundError(f"Commitment '{commitment_id}' not found.")

        if actor.role == Role.BUYER:
            verify_buyer_access(actor, commit["buyer_id"])
        elif actor.role == Role.FPO_ADMIN:
            verify_organization_access(actor, commit["fpo_id"])

        if commit.get("status") in ("DISPATCHED", "DELIVERED"):
            raise InvariantViolationError(
                f"Cannot cancel commitment with status '{commit.get('status')}' pre-pickup. Produces have left warehouse."
            )
        if commit.get("status") == "CANCELLED":
            return BuyerCommitmentResponse(**commit)

        now = get_current_utc().isoformat()

        # Release lot reservations
        for alloc in commit.get("allocations", []):
            lot = coordinator.store.get_item("lots", alloc["lot_id"])
            if lot:
                lot["reserved_grams"] = max(0, lot.get("reserved_grams", 0) - alloc["allocated_grams"])
                lot["version"] += 1
                lot["updated_at"] = now
                coordinator.store.set_item("lots", lot["lot_id"], lot)

        # Release requirement allocation
        req = coordinator.store.get_item("requirements", commit["requirement_id"])
        if req:
            req["allocated_grams"] = max(0, req.get("allocated_grams", 0) - commit["committed_grams"])
            if req.get("status") == "FULFILLED":
                req["status"] = "OPEN"
            req["updated_at"] = now
            coordinator.store.set_item("requirements", req["requirement_id"], req)

        commit["status"] = "CANCELLED"
        commit["updated_at"] = now
        coordinator.store.set_item("commitments", commitment_id, commit)

    return BuyerCommitmentResponse(**commit)


def get_commitment(
    store: InMemoryStore,
    actor: DevActor,
    commitment_id: str,
) -> BuyerCommitmentResponse:
    """Fetch commitment with actor scoping."""
    commit = store.get_item("commitments", commitment_id)
    if not commit:
        raise NotFoundError(f"Commitment '{commitment_id}' not found.")
    if actor.role == Role.BUYER:
        verify_buyer_access(actor, commit["buyer_id"])
    elif actor.role == Role.FPO_ADMIN:
        verify_organization_access(actor, commit["fpo_id"])
    return BuyerCommitmentResponse(**commit)


def list_commitments(
    store: InMemoryStore,
    actor: DevActor,
    fpo_id: Optional[str] = None,
    buyer_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[BuyerCommitmentResponse]:
    """List commitments scoped by actor."""
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.BUYER and item.get("buyer_id") != actor.actor_id:
            return False
        if actor.role == Role.FPO_ADMIN and item.get("fpo_id") != actor.organization_id:
            return False
        if fpo_id and item.get("fpo_id") != fpo_id:
            return False
        if buyer_id and item.get("buyer_id") != buyer_id:
            return False
        if status and item.get("status", "").upper() != status.upper():
            return False
        return True

    items = store.list_items("commitments", filter_fn)
    return [BuyerCommitmentResponse(**item) for item in items]

