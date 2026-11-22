from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
from gramsetu.schemas import (
    BuyerCommitmentCreate,
    BuyerCommitmentResponse,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.services.procurement import (
    create_commitment,
    cancel_commitment,
    get_commitment,
    list_commitments,
)

router = APIRouter(prefix="/commitments", tags=["commitments"])


@router.post("", response_model=BuyerCommitmentResponse)
async def post_commitment(
    payload: BuyerCommitmentCreate,
    actor: DevActor = Depends(require_roles(Role.BUYER, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    commit, was_created = create_commitment(store, coordinator, actor, payload)
    status_code = 201 if was_created else 200
    return JSONResponse(status_code=status_code, content=commit.model_dump(mode="json"))


@router.get("/{commitment_id}", response_model=BuyerCommitmentResponse)
async def get_single_commitment(
    commitment_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_commitment(store, actor, commitment_id)


@router.get("", response_model=List[BuyerCommitmentResponse])
async def get_all_commitments(
    fpo_id: Optional[str] = None,
    buyer_id: Optional[str] = None,
    status: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_commitments(store, actor, fpo_id=fpo_id, buyer_id=buyer_id, status=status)


@router.post("/{commitment_id}/cancel", response_model=BuyerCommitmentResponse)
async def post_cancel_commitment(
    commitment_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return cancel_commitment(store, coordinator, actor, commitment_id)
