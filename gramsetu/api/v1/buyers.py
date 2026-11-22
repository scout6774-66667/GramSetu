"""Buyer Management & Procurement Offers API Router (Modules 2 & 9)."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from gramsetu.core import DevActor, get_current_actor
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import (
    BuyerCreate,
    BuyerUpdate,
    BuyerResponse,
    ProcurementOfferCreate,
    ProcurementOfferResponse,
    BuyerOverviewResponse,
)
from gramsetu.services.buyer import (
    register_buyer,
    get_buyer_profile,
    update_buyer_profile,
    list_buyers,
    create_procurement_offer,
    list_procurement_offers,
    update_procurement_offer_status,
)
from gramsetu.services.overview import get_buyer_overview

router = APIRouter(tags=["buyers"])


@router.post("/buyers", response_model=BuyerResponse, status_code=status.HTTP_201_CREATED)
async def api_register_buyer(
    payload: BuyerCreate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Register a new buyer profile."""
    return register_buyer(store, coordinator, actor, payload)


@router.get("/buyers", response_model=List[BuyerResponse])
async def api_list_buyers(
    category: Optional[str] = Query(None),
    verified_only: bool = Query(False),
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """List buyers with optional category and verification filters."""
    return list_buyers(store, actor, category=category, verified_only=verified_only)


@router.get("/buyers/{buyer_id}", response_model=BuyerResponse)
async def api_get_buyer_profile(
    buyer_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """Get single buyer profile."""
    return get_buyer_profile(store, actor, buyer_id)


@router.put("/buyers/{buyer_id}", response_model=BuyerResponse)
async def api_update_buyer_profile(
    buyer_id: str,
    payload: BuyerUpdate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Update buyer preferences or contact information."""
    return update_buyer_profile(store, coordinator, actor, buyer_id, payload)


@router.get("/buyers/{buyer_id}/dashboard", response_model=BuyerOverviewResponse)
async def api_get_buyer_dashboard(
    buyer_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """Get dashboard overview for a buyer."""
    return get_buyer_overview(store, actor, buyer_id)


# --- Procurement Offers (Module 9) ---
@router.post("/procurement/offers", response_model=ProcurementOfferResponse, status_code=status.HTTP_201_CREATED)
async def api_create_procurement_offer(
    payload: ProcurementOfferCreate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Buyer posts a procurement offer on produce listing."""
    return create_procurement_offer(store, coordinator, actor, payload)


@router.get("/procurement/offers", response_model=List[ProcurementOfferResponse])
async def api_list_procurement_offers(
    listing_id: Optional[str] = Query(None),
    requirement_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """List procurement offers."""
    return list_procurement_offers(store, actor, listing_id=listing_id, requirement_id=requirement_id, status=status_filter)


@router.post("/procurement/offers/{offer_id}/accept", response_model=ProcurementOfferResponse)
async def api_accept_procurement_offer(
    offer_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Accept buyer procurement offer."""
    return update_procurement_offer_status(store, coordinator, actor, offer_id, action="ACCEPT")


@router.post("/procurement/offers/{offer_id}/reject", response_model=ProcurementOfferResponse)
async def api_reject_procurement_offer(
    offer_id: str,
    rejection_reason: Optional[str] = Query(None),
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Reject buyer procurement offer."""
    return update_procurement_offer_status(store, coordinator, actor, offer_id, action="REJECT", rejection_reason=rejection_reason)
