"""Farmer Management API Router (Module 1)."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from gramsetu.core import DevActor, get_current_actor
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import (
    FarmerCreate,
    FarmerUpdate,
    FarmerResponse,
    FarmerOverviewResponse,
)
from gramsetu.services.farmer import (
    register_farmer,
    get_farmer_profile,
    update_farmer_profile,
    list_farmers,
)
from gramsetu.services.overview import get_farmer_overview

router = APIRouter(prefix="/farmers", tags=["farmers"])


@router.post("", response_model=FarmerResponse, status_code=status.HTTP_201_CREATED)
async def api_register_farmer(
    payload: FarmerCreate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Register a new farmer profile."""
    return register_farmer(store, coordinator, actor, payload)


@router.get("", response_model=List[FarmerResponse])
async def api_list_farmers(
    fpo_id: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """List registered farmers scoped by actor."""
    return list_farmers(store, actor, fpo_id=fpo_id, district=district)


@router.get("/{farmer_id}", response_model=FarmerResponse)
async def api_get_farmer_profile(
    farmer_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """Get single farmer profile."""
    return get_farmer_profile(store, actor, farmer_id)


@router.put("/{farmer_id}", response_model=FarmerResponse)
async def api_update_farmer_profile(
    farmer_id: str,
    payload: FarmerUpdate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Update farmer contact or landholding details."""
    return update_farmer_profile(store, coordinator, actor, farmer_id, payload)


@router.get("/{farmer_id}/dashboard", response_model=FarmerOverviewResponse)
async def api_get_farmer_dashboard(
    farmer_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """Get dashboard summary for a farmer."""
    return get_farmer_overview(store, actor, farmer_id)
