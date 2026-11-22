from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
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
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.services.inventory import (
    receive_inventory_lot,
    get_inventory_lot,
    list_inventory_lots,
    split_inventory_lot,
    merge_inventory_lots,
    adjust_lot_grade,
    list_movements,
)

router = APIRouter(tags=["inventory"])


@router.get("/movements", response_model=List[InventoryMovementResponse])
async def get_movements(
    lot_id: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_movements(store, actor, lot_id=lot_id)


@router.get("/lots/{lot_id}/movements", response_model=List[InventoryMovementResponse])
async def get_lot_movements(
    lot_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_movements(store, actor, lot_id=lot_id)


@router.post("/lots/receipt", response_model=InventoryLotResponse, status_code=201)
async def post_lot_receipt(
    payload: LotReceiptCreate,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return receive_inventory_lot(store, coordinator, actor, payload)


@router.get("/lots/{lot_id}", response_model=InventoryLotResponse)
async def get_lot(
    lot_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_inventory_lot(store, actor, lot_id)


@router.get("/lots", response_model=List[InventoryLotResponse])
async def get_lots(
    fpo_id: Optional[str] = None,
    crop: Optional[str] = None,
    grade: Optional[str] = None,
    status: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_inventory_lots(store, actor, fpo_id=fpo_id, crop=crop, grade=grade, status=status)


@router.post("/lots/{lot_id}/split", response_model=LotSplitResponse)
async def post_split_lot(
    lot_id: str,
    payload: LotSplitRequest,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return split_inventory_lot(store, coordinator, actor, lot_id, payload)


@router.post("/lots/merge", response_model=LotMergeResponse)
async def post_merge_lots(
    payload: LotMergeRequest,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return merge_inventory_lots(store, coordinator, actor, payload)


@router.post("/lots/{lot_id}/grade", response_model=InventoryLotResponse)
async def post_adjust_grade(
    lot_id: str,
    payload: GradeAdjustmentRequest,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return adjust_lot_grade(store, coordinator, actor, lot_id, payload)
