"""Storage Facility & Spoilage Management API Router (Module 7)."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import (
    StorageFacilityCreate,
    StorageFacilityResponse,
    SpoilageRiskItem,
)
from gramsetu.services.storage import (
    register_storage_facility,
    list_storage_facilities,
    get_storage_facility,
    compute_facility_spoilage_risks,
)

router = APIRouter(prefix="/storage", tags=["storage"])


@router.post("/facilities", response_model=StorageFacilityResponse, status_code=status.HTTP_201_CREATED)
async def api_register_facility(
    payload: StorageFacilityCreate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Register a new storage silo, warehouse, or cold storage bay."""
    return register_storage_facility(store, coordinator, actor, payload)


@router.get("/facilities", response_model=List[StorageFacilityResponse])
async def api_list_facilities(
    fpo_id: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    store: InMemoryStore = Depends(get_store),
):
    """List storage facilities with current capacity utilization."""
    return list_storage_facilities(store, fpo_id=fpo_id, district=district)


@router.get("/facilities/{facility_id}", response_model=StorageFacilityResponse)
async def api_get_facility(
    facility_id: str,
    store: InMemoryStore = Depends(get_store),
):
    """Get single facility with utilization and sensor telemetry disclosure."""
    return get_storage_facility(store, facility_id)


@router.get("/spoilage-risks", response_model=List[SpoilageRiskItem])
async def api_get_spoilage_risks(
    fpo_id: str = Query("fpo-alpha"),
    store: InMemoryStore = Depends(get_store),
):
    """Evaluate spoilage risks across all active stored produce lots."""
    return compute_facility_spoilage_risks(store, fpo_id=fpo_id)
