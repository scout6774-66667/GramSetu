from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
from gramsetu.schemas import RecoveryPlanResponse
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.services.recovery import (
    generate_recovery_plan,
    confirm_recovery_by_buyer,
    approve_recovery_plan,
    get_recovery_plan,
    list_recovery_plans,
)

router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.post("/plans/generate", response_model=RecoveryPlanResponse, status_code=201)
async def post_generate_recovery(
    incident_id: str,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return generate_recovery_plan(store, coordinator, actor, incident_id)


@router.get("/plans/{plan_id}", response_model=RecoveryPlanResponse)
async def get_single_recovery_plan(
    plan_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_recovery_plan(store, actor, plan_id)


@router.get("/plans", response_model=List[RecoveryPlanResponse])
async def get_all_recovery_plans(
    fpo_id: Optional[str] = None,
    status: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_recovery_plans(store, actor, fpo_id=fpo_id, status=status)


@router.post("/plans/{plan_id}/buyer-confirm", response_model=RecoveryPlanResponse)
async def post_buyer_confirm_recovery(
    plan_id: str,
    actor: DevActor = Depends(require_roles(Role.BUYER, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return confirm_recovery_by_buyer(store, coordinator, actor, plan_id)


@router.post("/plans/{plan_id}/approve", response_model=RecoveryPlanResponse)
async def post_approve_recovery(
    plan_id: str,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return approve_recovery_plan(store, coordinator, actor, plan_id)
