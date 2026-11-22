from __future__ import annotations

from typing import Optional
from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    get_current_utc,
    verify_organization_access,
)
from gramsetu.schemas import (
    FarmerOverviewResponse,
    BuyerOverviewResponse,
    DriverOverviewResponse,
    FpoOverviewResponse,
)
from gramsetu.store import InMemoryStore


def get_farmer_overview(store: InMemoryStore, actor: DevActor) -> FarmerOverviewResponse:
    """Provide scoped dashboard metrics for a farmer."""
    if actor.role not in (Role.FARMER, Role.SYSTEM):
        raise AuthorizationError("Only farmers or system engine can access farmer overview.")

    farmer_id = actor.actor_id
    now = get_current_utc()

    # Active forecasts
    forecasts = store.list_items("forecasts", lambda f: f.get("farmer_id") == farmer_id and f.get("status") == "ACTIVE")
    fc_count = len(forecasts)
    fc_grams = sum(f.get("estimated_grams", 0) for f in forecasts)

    # Delivered lots
    lots = store.list_items("lots", lambda l: l.get("farmer_id") == farmer_id)
    lots_count = len(lots)
    lots_grams = sum(l.get("quantity_grams", 0) for l in lots)

    # Settlements
    settlements = store.list_items("settlements", lambda s: s.get("farmer_id") == farmer_id)
    earned_paise = sum(s.get("paid_amount_paise", 0) for s in settlements)
    pending_paise = sum(s.get("remaining_balance_paise", 0) for s in settlements)

    return FarmerOverviewResponse(
        farmer_id=farmer_id,
        active_forecasts_count=fc_count,
        active_forecasts_grams=fc_grams,
        delivered_lots_count=lots_count,
        delivered_grams=lots_grams,
        total_earned_paise=earned_paise,
        pending_payout_paise=pending_paise,
        as_of=now,
    )


def get_buyer_overview(store: InMemoryStore, actor: DevActor) -> BuyerOverviewResponse:
    """Provide scoped dashboard metrics for an institutional buyer."""
    if actor.role not in (Role.BUYER, Role.SYSTEM):
        raise AuthorizationError("Only buyers or system engine can access buyer overview.")

    buyer_id = actor.actor_id
    now = get_current_utc()

    # Open requirements
    reqs = store.list_items("requirements", lambda r: r.get("buyer_id") == buyer_id and r.get("status") == "OPEN")
    req_count = len(reqs)
    needed_grams = sum(r.get("needed_grams", 0) - r.get("allocated_grams", 0) for r in reqs)

    # Active commitments
    commits = store.list_items("commitments", lambda c: c.get("buyer_id") == buyer_id and c.get("status") in ("CONFIRMED", "DISPATCHED"))
    commit_count = len(commits)
    committed_grams = sum(c.get("committed_grams", 0) for c in commits)

    # In-transit shipments
    c_ids = {c["commitment_id"] for c in commits}
    in_transit_count = len(
        store.list_items("shipments", lambda s: s.get("commitment_id") in c_ids and s.get("status") == "PICKED_UP")
    )

    # Settlements
    settlements = store.list_items("settlements", lambda s: s.get("buyer_id") == buyer_id)
    payable = sum(s.get("net_payable_paise", 0) for s in settlements)
    paid = sum(s.get("paid_amount_paise", 0) for s in settlements)
    outstanding = sum(s.get("remaining_balance_paise", 0) for s in settlements)

    return BuyerOverviewResponse(
        buyer_id=buyer_id,
        open_requirements_count=req_count,
        open_needed_grams=needed_grams,
        active_commitments_count=commit_count,
        active_committed_grams=committed_grams,
        in_transit_shipments_count=in_transit_count,
        total_payable_paise=payable,
        total_paid_paise=paid,
        outstanding_balance_paise=outstanding,
        as_of=now,
    )


def get_driver_overview(store: InMemoryStore, actor: DevActor) -> DriverOverviewResponse:
    """Provide scoped dashboard metrics for a transporter/driver."""
    if actor.role not in (Role.DRIVER, Role.SYSTEM):
        raise AuthorizationError("Only drivers or system engine can access driver overview.")

    driver_id = actor.actor_id
    now = get_current_utc()

    # Assigned vehicle
    vehicles = store.list_items("vehicles", lambda v: v.get("driver_id") == driver_id)
    veh_id = vehicles[0]["vehicle_id"] if vehicles else None

    # Shipments
    shipments = store.list_items("shipments", lambda s: s.get("driver_id") == driver_id)
    pending_pickups = sum(1 for s in shipments if s.get("status") == "PLANNED")
    active_deliveries = sum(1 for s in shipments if s.get("status") == "PICKED_UP")
    completed = sum(1 for s in shipments if s.get("status") == "DELIVERED")

    return DriverOverviewResponse(
        driver_id=driver_id,
        assigned_vehicle_id=veh_id,
        pending_pickups_count=pending_pickups,
        active_deliveries_count=active_deliveries,
        completed_trips_count=completed,
        as_of=now,
    )


def get_fpo_overview(store: InMemoryStore, actor: DevActor, fpo_id: str) -> FpoOverviewResponse:
    """Provide aggregate operational dashboard metrics for FPO administration."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins or system engine can access FPO overview.")

    verify_organization_access(actor, fpo_id)
    now = get_current_utc()

    # Lots (physical, available, reserved)
    lots = store.list_items("lots", lambda l: l.get("fpo_id") == fpo_id and l.get("status") == "AVAILABLE")
    phys_stock = sum(l.get("quantity_grams", 0) for l in lots)
    res_stock = sum(l.get("reserved_grams", 0) for l in lots)
    avail_stock = max(0, phys_stock - res_stock)

    # Incidents / At-risk lots
    incidents = store.list_items("incidents", lambda i: i.get("fpo_id") == fpo_id and i.get("status") in ("OPEN", "ACKNOWLEDGED"))
    at_risk_count = sum(1 for i in incidents if i.get("incident_type") == "AGING_RISK")

    # Unfulfilled commitments
    commits = store.list_items("commitments", lambda c: c.get("fpo_id") == fpo_id and c.get("status") == "CONFIRMED")
    unfulfilled_commits = len(commits)

    # Pending collections / shipments planned
    c_ids = {c["commitment_id"] for c in store.list_items("commitments", lambda c: c.get("fpo_id") == fpo_id)}
    pending_collections = len(
        store.list_items("shipments", lambda s: s.get("commitment_id") in c_ids and s.get("status") == "PLANNED")
    )

    # Settlements
    settlements = store.list_items("settlements", lambda s: s.get("fpo_id") == fpo_id)
    pending_settle_count = sum(1 for s in settlements if s.get("status") in ("PENDING", "PARTIALLY_PAID"))
    total_payable = sum(s.get("net_payable_paise", 0) for s in settlements)
    total_paid = sum(s.get("paid_amount_paise", 0) for s in settlements)

    return FpoOverviewResponse(
        fpo_id=fpo_id,
        total_physical_stock_grams=phys_stock,
        total_available_stock_grams=avail_stock,
        total_reserved_stock_grams=res_stock,
        at_risk_lots_count=at_risk_count,
        unfulfilled_commitments_count=unfulfilled_commits,
        pending_collections_count=pending_collections,
        pending_settlements_count=pending_settle_count,
        total_settlement_payable_paise=total_payable,
        total_settlement_paid_paise=total_paid,
        as_of=now,
    )
