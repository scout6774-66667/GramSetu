"""Produce Listings & Commodities API Router (Module 3)."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, Response

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import (
    ProduceListingCreate,
    ProduceListingUpdate,
    ProduceListingResponse,
    CommodityItem,
)
from gramsetu.services.farmer import (
    create_produce_listing,
    list_produce_listings,
    get_produce_listing,
    update_produce_listing,
    list_commodities,
)

router = APIRouter(tags=["listings"])


@router.get("/commodities", response_model=List[CommodityItem])
async def api_list_commodities():
    """List supported commodities and quality standards for the pilot."""
    return list_commodities()


@router.post("/listings", response_model=ProduceListingResponse)
async def api_create_listing(
    payload: ProduceListingCreate,
    response: Response,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Create a new farmer produce listing."""
    listing, was_created = create_produce_listing(store, coordinator, actor, payload)
    response.status_code = status.HTTP_201_CREATED if was_created else status.HTTP_200_OK
    return listing


@router.get("/listings", response_model=List[ProduceListingResponse])
async def api_list_listings(
    crop: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    status_filter: Optional[str] = Query("ACTIVE", alias="status"),
    farmer_id: Optional[str] = Query(None),
    store: InMemoryStore = Depends(get_store),
):
    """List available produce listings with optional filtering."""
    return list_produce_listings(store, crop=crop, grade=grade, status=status_filter, farmer_id=farmer_id)


@router.get("/listings/{listing_id}", response_model=ProduceListingResponse)
async def api_get_listing(
    listing_id: str,
    store: InMemoryStore = Depends(get_store),
):
    """Get single produce listing by ID."""
    return get_produce_listing(store, listing_id)


@router.put("/listings/{listing_id}", response_model=ProduceListingResponse)
async def api_update_listing(
    listing_id: str,
    payload: ProduceListingUpdate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Update listing price, quantity, or status."""
    return update_produce_listing(store, coordinator, actor, listing_id, payload)
