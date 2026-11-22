"""Transporter & Shared Transportation API Router (Module 6)."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import (
    TransporterCreate,
    TransporterResponse,
    TransportRequestCreate,
    TransportRequestResponse,
    SharedTransportGroupResponse,
)
from gramsetu.services.transport_mgmt import (
    register_transporter,
    list_transporters,
    create_transport_request,
    list_transport_requests,
    optimize_shared_transport_pooling,
)

router = APIRouter(tags=["transport"])


@router.post("/transporters", response_model=TransporterResponse, status_code=status.HTTP_201_CREATED)
async def api_register_transporter(
    payload: TransporterCreate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Register a new rural transport operator."""
    return register_transporter(store, coordinator, actor, payload)


@router.get("/transporters", response_model=List[TransporterResponse])
async def api_list_transporters(
    fpo_id: Optional[str] = Query(None),
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """List registered transporters."""
    return list_transporters(store, actor, fpo_id=fpo_id)


@router.post("/transport/requests", response_model=TransportRequestResponse, status_code=status.HTTP_201_CREATED)
async def api_create_transport_request(
    payload: TransportRequestCreate,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Farmer requests pickup transportation for produce."""
    return create_transport_request(store, coordinator, actor, payload)


@router.get("/transport/requests", response_model=List[TransportRequestResponse])
async def api_list_transport_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    farmer_id: Optional[str] = Query(None),
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """List transport requests with actor-scoping."""
    return list_transport_requests(store, actor, status=status_filter, farmer_id=farmer_id)


@router.post("/transport/optimize-shared", response_model=List[SharedTransportGroupResponse])
async def api_optimize_shared_transport(
    district: str = Query("Purba Bardhaman"),
    target_facility_id: str = Query("FAC-WH-01"),
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.TRANSPORTER)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    """Pool multiple pending transport requests into shared vehicle runs."""
    return optimize_shared_transport_pooling(store, coordinator, actor, district, target_facility_id)
