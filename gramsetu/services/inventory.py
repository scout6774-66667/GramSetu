from __future__ import annotations

import uuid
from typing import List, Optional
from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    NotFoundError,
    InvariantViolationError,
    get_current_utc,
    verify_organization_access,
)
from gramsetu.schemas import (
    LotReceiptCreate,
    InventoryLotResponse,
    LotSplitRequest,
    LotSplitResponse,
    LotMergeRequest,
    LotMergeResponse,
    GradeAdjustmentRequest,
    InventoryMovementResponse,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator


def _to_lot_response(data: dict) -> InventoryLotResponse:
    q = data.get("quantity_grams", 0)
    r = data.get("reserved_grams", 0)
    avail = max(0, q - r) if data.get("status") == "AVAILABLE" else 0
    clean = {k: v for k, v in data.items() if k in InventoryLotResponse.model_fields}
    clean["available_grams"] = avail
    return InventoryLotResponse(**clean)


def record_movement(
    coordinator: TransactionCoordinator,
    lot_id: str,
    movement_type: str,
    quantity_grams: int,
    source_custody: str,
    dest_custody: str,
    recorded_by: str,
    source_location: Optional[str] = None,
    dest_location: Optional[str] = None,
) -> dict:
    """Record an auditable inventory movement record in the store."""
    mov_id = f"mov-{uuid.uuid4().hex[:10]}"
    record = {
        "movement_id": mov_id,
        "lot_id": lot_id,
        "movement_type": movement_type,
        "quantity_grams": quantity_grams,
        "source_location": source_location,
        "dest_location": dest_location,
        "source_custody": source_custody,
        "dest_custody": dest_custody,
        "recorded_by": recorded_by,
        "created_at": get_current_utc().isoformat(),
    }
    coordinator.store.set_item("movements", mov_id, record)
    return record


def receive_inventory_lot(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: LotReceiptCreate,
) -> InventoryLotResponse:
    """Record verified receipt of produce from a farmer into FPO warehouse inventory."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins or system engine can record physical produce receipt.")

    verify_organization_access(actor, payload.fpo_id)

    if payload.quantity_grams <= 0:
        raise InvariantViolationError("Receipt quantity must be strictly greater than 0 grams.")

    lot_id = f"lot-{uuid.uuid4().hex[:10]}"
    now = get_current_utc().isoformat()

    record = {
        "lot_id": lot_id,
        "fpo_id": payload.fpo_id,
        "farmer_id": payload.farmer_id,
        "crop": payload.crop,
        "variety": payload.variety,
        "grade": payload.grade,
        "quantity_grams": payload.quantity_grams,
        "reserved_grams": 0,
        "storage_location": payload.storage_location,
        "custody": "FPO_WAREHOUSE",
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "parent_lot_ids": [],
        "status": "AVAILABLE",
    }

    with coordinator.transaction():
        coordinator.store.set_item("lots", lot_id, record)
        record_movement(
            coordinator,
            lot_id=lot_id,
            movement_type="RECEIPT",
            quantity_grams=payload.quantity_grams,
            source_custody="FARMER",
            dest_custody="FPO_WAREHOUSE",
            recorded_by=actor.actor_id,
            source_location=None,
            dest_location=payload.storage_location,
        )

    return _to_lot_response(record)


def get_inventory_lot(
    store: InMemoryStore,
    actor: DevActor,
    lot_id: str,
) -> InventoryLotResponse:
    """Fetch an inventory lot with access verification."""
    data = store.get_item("lots", lot_id)
    if not data:
        raise NotFoundError(f"Inventory lot '{lot_id}' not found.")

    if actor.role == Role.FPO_ADMIN:
        verify_organization_access(actor, data["fpo_id"])
    elif actor.role == Role.FARMER:
        if actor.actor_id != data.get("farmer_id"):
            raise AuthorizationError("Farmers can only view their own delivered lots.")

    return _to_lot_response(data)


def list_inventory_lots(
    store: InMemoryStore,
    actor: DevActor,
    fpo_id: Optional[str] = None,
    crop: Optional[str] = None,
    grade: Optional[str] = None,
    status: Optional[str] = None,
) -> List[InventoryLotResponse]:
    """List inventory lots scoped by actor permissions."""
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.FPO_ADMIN and item.get("fpo_id") != actor.organization_id:
            return False
        if actor.role == Role.FARMER and item.get("farmer_id") != actor.actor_id:
            return False
        if fpo_id and item.get("fpo_id") != fpo_id:
            return False
        if crop and item.get("crop", "").lower() != crop.lower():
            return False
        if grade and item.get("grade", "").upper() != grade.upper():
            return False
        if status and item.get("status", "").upper() != status.upper():
            return False
        return True

    items = store.list_items("lots", filter_fn)
    return [_to_lot_response(item) for item in items]


def split_inventory_lot(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    parent_lot_id: str,
    payload: LotSplitRequest,
) -> LotSplitResponse:
    """Split an unreserved lot into multiple child lots with mass conservation."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins can split inventory lots.")

    with coordinator.transaction():
        parent = coordinator.store.get_item("lots", parent_lot_id)
        if not parent:
            raise NotFoundError(f"Parent lot '{parent_lot_id}' not found.")

        verify_organization_access(actor, parent["fpo_id"])

        if parent.get("status") != "AVAILABLE":
            raise InvariantViolationError(f"Cannot split lot with status '{parent.get('status')}'.")
        if parent.get("reserved_grams", 0) > 0:
            raise InvariantViolationError(
                f"Cannot split lot with active reservations ({parent['reserved_grams']}g reserved)."
            )

        total_child_grams = sum(p.quantity_grams for p in payload.child_portions)
        if total_child_grams != parent["quantity_grams"]:
            raise InvariantViolationError(
                f"Mass conservation violation: sum of child portions ({total_child_grams}g) "
                f"does not equal parent quantity ({parent['quantity_grams']}g)."
            )

        now = get_current_utc().isoformat()

        orig_parent_qty = parent["quantity_grams"]
        # Update parent lot: consumed by split
        parent["status"] = "SPLIT"
        parent["quantity_grams"] = 0
        parent["reserved_grams"] = 0
        parent["updated_at"] = now
        parent["version"] += 1
        coordinator.store.set_item("lots", parent_lot_id, parent)
        record_movement(
            coordinator,
            lot_id=parent_lot_id,
            movement_type="SPLIT_OUT",
            quantity_grams=orig_parent_qty,
            source_custody=parent.get("custody", "FPO_WAREHOUSE"),
            dest_custody="SPLIT",
            recorded_by=actor.actor_id,
            source_location=parent.get("storage_location"),
            dest_location=None,
        )

        # Create child lots
        child_responses: List[InventoryLotResponse] = []
        for portion in payload.child_portions:
            child_id = f"lot-{uuid.uuid4().hex[:10]}"
            child_record = {
                "lot_id": child_id,
                "fpo_id": parent["fpo_id"],
                "farmer_id": parent["farmer_id"],
                "crop": parent["crop"],
                "variety": parent.get("variety"),
                "grade": parent["grade"],
                "quantity_grams": portion.quantity_grams,
                "reserved_grams": 0,
                "storage_location": portion.storage_location,
                "custody": parent.get("custody", "FPO_WAREHOUSE"),
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "parent_lot_ids": [parent_lot_id],
                "status": "AVAILABLE",
            }
            coordinator.store.set_item("lots", child_id, child_record)
            record_movement(
                coordinator,
                lot_id=child_id,
                movement_type="SPLIT_IN",
                quantity_grams=portion.quantity_grams,
                source_custody="SPLIT",
                dest_custody="FPO_WAREHOUSE",
                recorded_by=actor.actor_id,
                source_location=None,
                dest_location=portion.storage_location,
            )
            child_responses.append(_to_lot_response(child_record))

    return LotSplitResponse(
        parent_lot=_to_lot_response(parent),
        child_lots=child_responses,
    )


def merge_inventory_lots(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: LotMergeRequest,
) -> LotMergeResponse:
    """Merge multiple compatible lots into a consolidated lot with mass conservation."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins can merge inventory lots.")

    with coordinator.transaction():
        sources = []
        for s_id in payload.source_lot_ids:
            lot = coordinator.store.get_item("lots", s_id)
            if not lot:
                raise NotFoundError(f"Source lot '{s_id}' not found.")
            verify_organization_access(actor, lot["fpo_id"])
            if lot.get("status") != "AVAILABLE":
                raise InvariantViolationError(f"Source lot '{s_id}' is not AVAILABLE (status: {lot.get('status')}).")
            if lot.get("reserved_grams", 0) > 0:
                raise InvariantViolationError(f"Source lot '{s_id}' has active reservations.")
            sources.append(lot)

        first = sources[0]
        for s in sources[1:]:
            if s["crop"] != first["crop"] or s["grade"] != first["grade"] or s["fpo_id"] != first["fpo_id"]:
                raise InvariantViolationError("All merged source lots must have identical crop, grade, and FPO.")

        total_grams = sum(s["quantity_grams"] for s in sources)
        now = get_current_utc().isoformat()

        # Retire source lots: consumed by merge
        for s in sources:
            orig_s_qty = s["quantity_grams"]
            s["status"] = "MERGED"
            s["quantity_grams"] = 0
            s["reserved_grams"] = 0
            s["updated_at"] = now
            s["version"] += 1
            coordinator.store.set_item("lots", s["lot_id"], s)
            record_movement(
                coordinator,
                lot_id=s["lot_id"],
                movement_type="MERGE_OUT",
                quantity_grams=orig_s_qty,
                source_custody="FPO_WAREHOUSE",
                dest_custody="MERGED",
                recorded_by=actor.actor_id,
                source_location=s.get("storage_location"),
                dest_location=None,
            )

        # Create consolidated lot
        merged_id = f"lot-{uuid.uuid4().hex[:10]}"
        merged_record = {
            "lot_id": merged_id,
            "fpo_id": first["fpo_id"],
            "farmer_id": "COMMINGLED_FPO",
            "crop": first["crop"],
            "variety": first.get("variety"),
            "grade": first["grade"],
            "quantity_grams": total_grams,
            "reserved_grams": 0,
            "storage_location": payload.target_storage_location,
            "custody": "FPO_WAREHOUSE",
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "parent_lot_ids": sorted(payload.source_lot_ids),
            "status": "AVAILABLE",
        }
        coordinator.store.set_item("lots", merged_id, merged_record)
        record_movement(
            coordinator,
            lot_id=merged_id,
            movement_type="MERGE_IN",
            quantity_grams=total_grams,
            source_custody="MERGED",
            dest_custody="FPO_WAREHOUSE",
            recorded_by=actor.actor_id,
            source_location=None,
            dest_location=payload.target_storage_location,
        )

    return LotMergeResponse(
        merged_lot=_to_lot_response(merged_record),
        retired_lot_ids=payload.source_lot_ids,
    )


def adjust_lot_grade(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    lot_id: str,
    payload: GradeAdjustmentRequest,
) -> InventoryLotResponse:
    """Adjust the quality grade of an inventory lot with audit log."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins can re-grade inventory lots.")

    with coordinator.transaction():
        lot = coordinator.store.get_item("lots", lot_id)
        if not lot:
            raise NotFoundError(f"Lot '{lot_id}' not found.")
        verify_organization_access(actor, lot["fpo_id"])
        if lot.get("status") != "AVAILABLE":
            raise InvariantViolationError("Cannot adjust grade of non-available lot.")
        if lot.get("reserved_grams", 0) > 0:
            raise InvariantViolationError("Cannot adjust grade of lot with active reservations.")

        now = get_current_utc().isoformat()
        old_grade = lot["grade"]
        lot["grade"] = payload.new_grade
        lot["updated_at"] = now
        lot["version"] += 1
        coordinator.store.set_item("lots", lot_id, lot)
        record_movement(
            coordinator,
            lot_id=lot_id,
            movement_type="REGRADE",
            quantity_grams=lot["quantity_grams"],
            source_custody=lot.get("custody", "FPO_WAREHOUSE"),
            dest_custody=lot.get("custody", "FPO_WAREHOUSE"),
            recorded_by=actor.actor_id,
            source_location=lot.get("storage_location"),
            dest_location=f"Regraded from {old_grade} to {payload.new_grade}: {payload.reason}",
        )

    return _to_lot_response(lot)


def list_movements(
    store: InMemoryStore,
    actor: DevActor,
    lot_id: Optional[str] = None,
) -> List[InventoryMovementResponse]:
    """List auditable inventory movement ledger entries."""
    def filter_fn(item: dict) -> bool:
        if lot_id and item.get("lot_id") != lot_id:
            return False
        return True

    items = store.list_items("movements", filter_fn)
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return [InventoryMovementResponse(**item) for item in items]
