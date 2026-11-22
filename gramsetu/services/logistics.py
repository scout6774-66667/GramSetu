from __future__ import annotations

import uuid
from typing import List, Optional
from gramsetu.algorithms import get_default_road_network, OfflineRoadGraphProvider
from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    NotFoundError,
    InvariantViolationError,
    get_current_utc,
    verify_organization_access,
    verify_driver_assignment,
)
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
from gramsetu.services.inventory import record_movement


def register_vehicle(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: VehicleCreate,
) -> VehicleResponse:
    """Register a rural transport vehicle into the fleet."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins or system engine can register logistics vehicles.")

    verify_organization_access(actor, payload.fpo_id)

    veh_id = f"veh-{uuid.uuid4().hex[:10]}"
    now = get_current_utc().isoformat()

    record = {
        "vehicle_id": veh_id,
        "fpo_id": payload.fpo_id,
        "driver_id": payload.driver_id,
        "capacity_grams": payload.capacity_grams,
        "vehicle_type": payload.vehicle_type,
        "is_available": True,
        "created_at": now,
    }

    with coordinator.transaction():
        coordinator.store.set_item("vehicles", veh_id, record)

    return VehicleResponse(**record)


def list_vehicles(
    store: InMemoryStore,
    actor: DevActor,
    fpo_id: Optional[str] = None,
    is_available: Optional[bool] = None,
) -> List[VehicleResponse]:
    """List fleet vehicles scoped by actor."""
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.FPO_ADMIN and item.get("fpo_id") != actor.organization_id:
            return False
        if fpo_id and item.get("fpo_id") != fpo_id:
            return False
        if is_available is not None and item.get("is_available") != is_available:
            return False
        return True

    items = store.list_items("vehicles", filter_fn)
    return [VehicleResponse(**item) for item in items]


def create_shipment(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: ShipmentCreate,
) -> ShipmentResponse:
    """Plan a shipment assigning a confirmed commitment to an available vehicle."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins or system engine can create shipment plans.")

    with coordinator.transaction():
        commit = coordinator.store.get_item("commitments", payload.commitment_id)
        if not commit:
            raise NotFoundError(f"Commitment '{payload.commitment_id}' not found.")
        verify_organization_access(actor, commit["fpo_id"])

        if commit.get("status") != "CONFIRMED":
            raise InvariantViolationError(
                f"Cannot create shipment for commitment with status '{commit.get('status')}' (expected CONFIRMED)."
            )

        veh = coordinator.store.get_item("vehicles", payload.vehicle_id)
        if not veh:
            raise NotFoundError(f"Vehicle '{payload.vehicle_id}' not found.")
        if not veh.get("is_available", True):
            raise InvariantViolationError(f"Vehicle '{payload.vehicle_id}' is currently unavailable.")

        if veh.get("capacity_grams", 0) < commit["committed_grams"]:
            raise InvariantViolationError(
                f"Vehicle capacity ({veh.get('capacity_grams')}g) cannot accommodate shipment payload ({commit['committed_grams']}g)."
            )

        ship_id = f"ship-{uuid.uuid4().hex[:10]}"
        now = get_current_utc().isoformat()

        record = {
            "shipment_id": ship_id,
            "commitment_id": commit["commitment_id"],
            "vehicle_id": veh["vehicle_id"],
            "driver_id": payload.driver_id,
            "dispatched_grams": commit["committed_grams"],
            "version": 1,
            "status": "PLANNED",
            "custody": "SCHEDULED",
            "actual_pickup_time": None,
            "actual_delivery_time": None,
            "accepted_grams": None,
            "rejected_grams": None,
            "loss_grams": None,
            "created_at": now,
            "updated_at": now,
        }
        coordinator.store.set_item("shipments", ship_id, record)

    return ShipmentResponse(**record)


def record_pickup(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    shipment_id: str,
) -> ShipmentResponse:
    """Record physical pickup, transfer warehouse custody to driver, and decrement physical stock."""
    with coordinator.transaction():
        ship = coordinator.store.get_item("shipments", shipment_id)
        if not ship:
            raise NotFoundError(f"Shipment '{shipment_id}' not found.")

        verify_driver_assignment(actor, ship["driver_id"])

        if ship.get("status") != "PLANNED":
            raise InvariantViolationError(
                f"Cannot pick up shipment with status '{ship.get('status')}' (expected PLANNED)."
            )

        commit = coordinator.store.get_item("commitments", ship["commitment_id"])
        if not commit:
            raise NotFoundError(f"Commitment '{ship['commitment_id']}' not found.")

        now = get_current_utc().isoformat()

        # Decrement warehouse stock: mass has physically left the warehouse
        for alloc in commit.get("allocations", []):
            lot = coordinator.store.get_item("lots", alloc["lot_id"])
            if lot:
                lot["quantity_grams"] = max(0, lot.get("quantity_grams", 0) - alloc["allocated_grams"])
                lot["reserved_grams"] = max(0, lot.get("reserved_grams", 0) - alloc["allocated_grams"])
                lot["version"] += 1
                lot["updated_at"] = now
                coordinator.store.set_item("lots", lot["lot_id"], lot)
                record_movement(
                    coordinator,
                    lot_id=lot["lot_id"],
                    movement_type="PICKUP",
                    quantity_grams=alloc["allocated_grams"],
                    source_custody="FPO_WAREHOUSE",
                    dest_custody="DRIVER_CUSTODY",
                    recorded_by=actor.actor_id,
                    source_location=lot.get("storage_location"),
                    dest_location=f"VEHICLE:{ship['vehicle_id']}",
                )

        # Update vehicle status
        veh = coordinator.store.get_item("vehicles", ship["vehicle_id"])
        if veh:
            veh["is_available"] = False
            coordinator.store.set_item("vehicles", veh["vehicle_id"], veh)

        # Update commitment
        commit["status"] = "DISPATCHED"
        commit["updated_at"] = now
        coordinator.store.set_item("commitments", commit["commitment_id"], commit)

        # Update shipment
        ship["status"] = "PICKED_UP"
        ship["custody"] = "DRIVER_CUSTODY"
        ship["version"] = ship.get("version", 1) + 1
        ship["actual_pickup_time"] = now
        ship["updated_at"] = now
        coordinator.store.set_item("shipments", shipment_id, ship)

    return ShipmentResponse(**ship)


def record_delivery(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    shipment_id: str,
    payload: DeliveryConfirmationRequest,
) -> ShipmentResponse:
    """Record physical delivery with strict mass conservation: accepted + rejected + loss == dispatched."""
    with coordinator.transaction():
        ship = coordinator.store.get_item("shipments", shipment_id)
        if not ship:
            raise NotFoundError(f"Shipment '{shipment_id}' not found.")

        verify_driver_assignment(actor, ship["driver_id"])

        if ship.get("status") != "PICKED_UP":
            raise InvariantViolationError(
                f"Cannot record delivery for shipment with status '{ship.get('status')}' (expected PICKED_UP)."
            )

        total_delivery = payload.accepted_grams + payload.rejected_grams + payload.loss_grams
        if total_delivery != ship["dispatched_grams"]:
            raise InvariantViolationError(
                f"Delivery mass conservation violation: sum of accepted ({payload.accepted_grams}g), "
                f"rejected ({payload.rejected_grams}g), and loss ({payload.loss_grams}g) = {total_delivery}g "
                f"does not match dispatched quantity ({ship['dispatched_grams']}g)."
            )

        now = get_current_utc().isoformat()

        # Update vehicle availability
        veh = coordinator.store.get_item("vehicles", ship["vehicle_id"])
        if veh:
            veh["is_available"] = True
            coordinator.store.set_item("vehicles", veh["vehicle_id"], veh)

        # Update commitment
        commit = coordinator.store.get_item("commitments", ship["commitment_id"])
        if commit:
            commit["status"] = "DELIVERED"
            commit["updated_at"] = now
            coordinator.store.set_item("commitments", commit["commitment_id"], commit)

        # Update shipment
        ship["status"] = "DELIVERED"
        ship["custody"] = "BUYER_ACCEPTED"
        ship["version"] = ship.get("version", 2) + 1
        ship["actual_delivery_time"] = now
        ship["accepted_grams"] = payload.accepted_grams
        ship["rejected_grams"] = payload.rejected_grams
        ship["loss_grams"] = payload.loss_grams
        ship["updated_at"] = now
        coordinator.store.set_item("shipments", shipment_id, ship)

        record_movement(
            coordinator,
            lot_id=ship["commitment_id"],
            movement_type="DELIVERY",
            quantity_grams=payload.accepted_grams,
            source_custody="DRIVER_CUSTODY",
            dest_custody="BUYER_ACCEPTED",
            recorded_by=actor.actor_id,
            source_location=f"VEHICLE:{ship['vehicle_id']}",
            dest_location="BUYER_FACILITY",
        )
        if payload.rejected_grams > 0:
            record_movement(
                coordinator,
                lot_id=ship["commitment_id"],
                movement_type="REJECTION",
                quantity_grams=payload.rejected_grams,
                source_custody="DRIVER_CUSTODY",
                dest_custody="REJECTED",
                recorded_by=actor.actor_id,
                source_location=f"VEHICLE:{ship['vehicle_id']}",
                dest_location="DISPOSITION_PENDING",
            )
        if payload.loss_grams > 0:
            record_movement(
                coordinator,
                lot_id=ship["commitment_id"],
                movement_type="LOSS",
                quantity_grams=payload.loss_grams,
                source_custody="DRIVER_CUSTODY",
                dest_custody="LOST",
                recorded_by=actor.actor_id,
                source_location=f"VEHICLE:{ship['vehicle_id']}",
                dest_location=None,
            )

    return ShipmentResponse(**ship)


def get_shipment(store: InMemoryStore, actor: DevActor, shipment_id: str) -> ShipmentResponse:
    """Get shipment with actor scoping."""
    ship = store.get_item("shipments", shipment_id)
    if not ship:
        raise NotFoundError(f"Shipment '{shipment_id}' not found.")
    if actor.role == Role.DRIVER:
        verify_driver_assignment(actor, ship["driver_id"])
    return ShipmentResponse(**ship)


def list_shipments(
    store: InMemoryStore,
    actor: DevActor,
    fpo_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[ShipmentResponse]:
    """List shipments scoped by actor."""
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.DRIVER and item.get("driver_id") != actor.actor_id:
            return False
        if driver_id and item.get("driver_id") != driver_id:
            return False
        if status and item.get("status", "").upper() != status.upper():
            return False
        return True

    items = store.list_items("shipments", filter_fn)
    return [ShipmentResponse(**item) for item in items]


_DEFAULT_ROAD_GRAPH: Optional[OfflineRoadGraphProvider] = None


def get_active_road_network() -> OfflineRoadGraphProvider:
    global _DEFAULT_ROAD_GRAPH
    if _DEFAULT_ROAD_GRAPH is None:
        _DEFAULT_ROAD_GRAPH = get_default_road_network()
    return _DEFAULT_ROAD_GRAPH


def plan_and_verify_route(
    payload: RouteVerificationRequest,
    provider: Optional[OfflineRoadGraphProvider] = None,
) -> RouteVerificationResponse:
    """Plan and verify logistics route using deterministic offline road topology."""
    road_provider = provider or get_active_road_network()
    result = road_provider.get_route(
        origin_node=payload.origin,
        dest_node=payload.destination,
        vehicle_payload_grams=payload.payload_weight_grams,
    )
    return RouteVerificationResponse(**result)

