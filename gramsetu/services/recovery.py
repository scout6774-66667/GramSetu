from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
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
    DEV_ACTORS,
)
from gramsetu.schemas import (
    RecoveryCandidate,
    RecoveryPlanResponse,
    BuyerCommitmentCreate,
    CommitmentAllocationItem,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.services.procurement import create_commitment
from gramsetu.algorithms import optimize_recovery_allocation


# Transport cost model heuristics for simulated buyers
BUYER_DISTANCE_KM = {
    "buyer-local": 10.0,
    "buyer-bigbasket": 45.0,
    "buyer-reliance": 120.0,
    "default": 30.0,
}


def _calc_transport_paise(buyer_id: str) -> int:
    dist = BUYER_DISTANCE_KM.get(buyer_id, BUYER_DISTANCE_KM["default"])
    base = 50_000
    per_km = 2_500
    return int(base + (dist * per_km))


def generate_recovery_plan(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    incident_id: str,
) -> RecoveryPlanResponse:
    """Evaluate disrupted or unreserved inventory, search up to 8 alternative buyer requirements, and rank net returns."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins or system engine can trigger recovery optimization.")

    inc = store.get_item("incidents", incident_id)
    if not inc:
        raise NotFoundError(f"Incident '{incident_id}' not found.")
    verify_organization_access(actor, inc["fpo_id"])

    # Locate affected lot and defaulting buyer (if triggered by buyer cancellation/rejection)
    cancelled_buyer_id: Optional[str] = None
    lot_id = inc.get("resource_id") if inc.get("resource_type") == "lot" else None
    if not lot_id and inc.get("resource_type") == "commitment":
        commit = store.get_item("commitments", inc["resource_id"])
        if commit:
            cancelled_buyer_id = commit.get("buyer_id")
            if commit.get("allocations"):
                lot_id = commit["allocations"][0]["lot_id"]
    elif not lot_id and inc.get("resource_type") == "shipment":
        ship = store.get_item("shipments", inc["resource_id"])
        if ship:
            commit = store.get_item("commitments", ship.get("commitment_id", ""))
            if commit:
                cancelled_buyer_id = commit.get("buyer_id")
                if commit.get("allocations"):
                    lot_id = commit["allocations"][0]["lot_id"]

    if not lot_id:
        raise NotFoundError("Could not identify affected inventory lot for recovery.")

    lot = store.get_item("lots", lot_id)
    if not lot:
        raise NotFoundError(f"Affected lot '{lot_id}' not found.")

    available_grams = lot["quantity_grams"] - lot.get("reserved_grams", 0)
    if available_grams <= 0:
        raise InvariantViolationError(f"Lot '{lot_id}' has 0 available grams for recovery.")

    now = get_current_utc()
    crop = lot["crop"]
    grade = lot["grade"]

    # Find matching open buyer requirements
    all_reqs = store.list_items(
        "requirements",
        lambda r: r.get("status") == "OPEN"
        and r.get("crop", "").lower() == crop.lower()
        and r.get("grade", "").upper() == grade.upper(),
    )

    # Filter out expired requirements and the original cancelled buyer
    valid_reqs = []
    for r in all_reqs:
        if cancelled_buyer_id and r.get("buyer_id") == cancelled_buyer_id:
            continue
        end_str = r.get("delivery_window_end")
        if end_str and datetime.fromisoformat(end_str) < now:
            continue
        rem_demand = r["needed_grams"] - r.get("allocated_grams", 0)
        if rem_demand > 0:
            valid_reqs.append(r)

    for r in valid_reqs:
        r["transport_cost_paise"] = _calc_transport_paise(r["buyer_id"])

    opt_result = optimize_recovery_allocation(
        available_grams=available_grams,
        candidate_requirements=valid_reqs,
        time_budget_ms=200.0,
    )

    candidates = [RecoveryCandidate(**c) for c in opt_result["ranked_candidates"]]
    recommended = RecoveryCandidate(**opt_result["recommended_candidate"]) if opt_result["recommended_candidate"] else None
    plan_id = f"plan-{uuid.uuid4().hex[:10]}"

    record = {
        "plan_id": plan_id,
        "incident_id": incident_id,
        "fpo_id": inc["fpo_id"],
        "lot_id": lot_id,
        "crop": crop,
        "grade": grade,
        "available_recovery_grams": available_grams,
        "candidates": [c.model_dump() for c in candidates],
        "recommended_candidate": recommended.model_dump() if recommended else None,
        "status": opt_result["status"],
        "optimality_status": opt_result["optimality_status"],
        "solver_runtime_ms": opt_result["solver_runtime_ms"],
        "candidate_count": opt_result["candidate_count"],
        "objective_value_paise": opt_result["objective_value_paise"],
        "model_version": opt_result["model_version"],
        "buyer_confirmed_at": None,
        "fpo_approved_at": None,
        "created_at": now.isoformat(),
        "disclaimer": (
            "RECOMMENDATION ONLY: AI recovery plans do not bind buyers or guarantee stock rescue "
            "until explicit buyer confirmation and FPO approval are executed."
        ),
    }

    with coordinator.transaction():
        coordinator.store.set_item("recovery_plans", plan_id, record)

    return RecoveryPlanResponse(**record)


def confirm_recovery_by_buyer(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    plan_id: str,
) -> RecoveryPlanResponse:
    """Alternative buyer confirms acceptance of recovery terms."""
    with coordinator.transaction():
        plan = coordinator.store.get_item("recovery_plans", plan_id)
        if not plan:
            raise NotFoundError(f"Recovery plan '{plan_id}' not found.")

        rec = plan.get("recommended_candidate")
        if not rec:
            raise InvariantViolationError("Cannot confirm plan with no feasible candidate.")

        verify_buyer_access(actor, rec["buyer_id"])

        if plan.get("status") != "RECOMMENDED":
            raise InvariantViolationError(f"Plan status is '{plan.get('status')}', expected RECOMMENDED.")

        now = get_current_utc().isoformat()
        plan["status"] = "CONFIRMED_BY_BUYER"
        plan["buyer_confirmed_at"] = now
        coordinator.store.set_item("recovery_plans", plan_id, plan)

    return RecoveryPlanResponse(**plan)


def approve_recovery_plan(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    plan_id: str,
) -> RecoveryPlanResponse:
    """FPO Admin approves buyer-confirmed recovery plan, executing atomic reservation commitment."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins can approve recovery plans.")

    with coordinator.transaction():
        plan = coordinator.store.get_item("recovery_plans", plan_id)
        if not plan:
            raise NotFoundError(f"Recovery plan '{plan_id}' not found.")

        verify_organization_access(actor, plan["fpo_id"])

        if plan.get("status") != "CONFIRMED_BY_BUYER":
            raise InvariantViolationError(
                f"Cannot approve recovery plan with status '{plan.get('status')}'. Buyer must confirm first."
            )

        rec = plan["recommended_candidate"]
        lot = coordinator.store.get_item("lots", plan["lot_id"])
        if not lot or lot.get("status") != "AVAILABLE":
            raise ConflictError("Stale recovery plan: underlying inventory lot is no longer AVAILABLE.")

        available = lot["quantity_grams"] - lot.get("reserved_grams", 0)
        if available < rec["allocable_grams"]:
            raise ConflictError(
                f"Stale recovery plan: lot available grams ({available}g) is less than required ({rec['allocable_grams']}g)."
            )

        # Execute atomic commitment
        buyer_actor = DEV_ACTORS.get(rec["buyer_id"], actor)
        commit_payload = BuyerCommitmentCreate(
            requirement_id=rec["requirement_id"],
            fpo_id=plan["fpo_id"],
            agreed_price_paise_per_gram=rec["offered_price_paise_per_gram"],
            allocations=[CommitmentAllocationItem(lot_id=plan["lot_id"], allocated_grams=rec["allocable_grams"])],
            idempotency_key=f"recovery-{plan_id}",
        )
        create_commitment(store, coordinator, buyer_actor, commit_payload)

        now = get_current_utc().isoformat()
        plan["status"] = "APPROVED"
        plan["fpo_approved_at"] = now
        coordinator.store.set_item("recovery_plans", plan_id, plan)

        # Mark incident resolved
        inc = coordinator.store.get_item("incidents", plan["incident_id"])
        if inc:
            inc["status"] = "RESOLVED"
            inc["resolution_note"] = f"Produce successfully re-routed and recovered under plan {plan_id}."
            inc["updated_at"] = now
            coordinator.store.set_item("incidents", inc["incident_id"], inc)

    return RecoveryPlanResponse(**plan)


def get_recovery_plan(store: InMemoryStore, actor: DevActor, plan_id: str) -> RecoveryPlanResponse:
    plan = store.get_item("recovery_plans", plan_id)
    if not plan:
        raise NotFoundError(f"Recovery plan '{plan_id}' not found.")
    return RecoveryPlanResponse(**plan)


def list_recovery_plans(
    store: InMemoryStore,
    actor: DevActor,
    fpo_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[RecoveryPlanResponse]:
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.FPO_ADMIN and item.get("fpo_id") != actor.organization_id:
            return False
        if fpo_id and item.get("fpo_id") != fpo_id:
            return False
        if status and item.get("status", "").upper() != status.upper():
            return False
        return True

    items = store.list_items("recovery_plans", filter_fn)
    return [RecoveryPlanResponse(**item) for item in items]
