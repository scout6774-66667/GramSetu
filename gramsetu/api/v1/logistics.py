from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
from gramsetu.schemas import (
    VehicleCreate,
    VehicleResponse,
    ShipmentCreate,
    ShipmentResponse,
    DeliveryConfirmationRequest,
    RouteVerificationRequest,
    RouteVerificationResponse,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.services.logistics import (
    register_vehicle,
    list_vehicles,
    create_shipment,
    record_pickup,
    record_delivery,
    get_shipment,
    list_shipments,
    plan_and_verify_route,
)

router = APIRouter(tags=["logistics"])


@router.post("/vehicles", response_model=VehicleResponse, status_code=201)
async def post_vehicle(
    payload: VehicleCreate,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return register_vehicle(store, coordinator, actor, payload)


@router.get("/vehicles", response_model=List[VehicleResponse])
async def get_all_vehicles(
    fpo_id: Optional[str] = None,
    is_available: Optional[bool] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_vehicles(store, actor, fpo_id=fpo_id, is_available=is_available)


@router.post("/shipments", response_model=ShipmentResponse, status_code=201)
async def post_shipment(
    payload: ShipmentCreate,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return create_shipment(store, coordinator, actor, payload)


@router.get("/shipments/{shipment_id}", response_model=ShipmentResponse)
async def get_single_shipment(
    shipment_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_shipment(store, actor, shipment_id)


@router.get("/shipments", response_model=List[ShipmentResponse])
async def get_all_shipments(
    fpo_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    status: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_shipments(store, actor, fpo_id=fpo_id, driver_id=driver_id, status=status)


@router.post("/shipments/{shipment_id}/pickup", response_model=ShipmentResponse)
async def post_pickup(
    shipment_id: str,
    actor: DevActor = Depends(require_roles(Role.DRIVER, Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return record_pickup(store, coordinator, actor, shipment_id)


@router.post("/shipments/{shipment_id}/delivery", response_model=ShipmentResponse)
async def post_delivery(
    shipment_id: str,
    payload: DeliveryConfirmationRequest,
    actor: DevActor = Depends(require_roles(Role.DRIVER, Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return record_delivery(store, coordinator, actor, shipment_id, payload)


@router.post("/logistics/routes/verify", response_model=RouteVerificationResponse)
async def verify_logistics_route(
    payload: RouteVerificationRequest,
    actor: DevActor = Depends(get_current_actor),
):
    return plan_and_verify_route(payload)
