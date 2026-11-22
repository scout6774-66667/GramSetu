from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
from gramsetu.schemas import (
    SettlementGenerateRequest,
    PaymentCreateRequest,
    PaymentReportRequest,
    PaymentVerifyRequest,
    SettlementResponse,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.services.settlement import (
    generate_settlement,
    record_payment,
    report_payment,
    verify_payment,
    get_settlement,
    list_settlements,
)

router = APIRouter(prefix="/settlements", tags=["settlements"])


@router.post("/generate", response_model=SettlementResponse, status_code=201)
async def post_generate_settlement(
    payload: SettlementGenerateRequest,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return generate_settlement(store, coordinator, actor, payload)


@router.get("/{settlement_id}", response_model=SettlementResponse)
async def get_single_settlement(
    settlement_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_settlement(store, actor, settlement_id)


@router.get("", response_model=List[SettlementResponse])
async def get_all_settlements(
    fpo_id: Optional[str] = None,
    farmer_id: Optional[str] = None,
    buyer_id: Optional[str] = None,
    status: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_settlements(store, actor, fpo_id=fpo_id, farmer_id=farmer_id, buyer_id=buyer_id, status=status)


@router.post("/{settlement_id}/payments", response_model=SettlementResponse)
async def post_record_payment(
    settlement_id: str,
    payload: PaymentCreateRequest,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.BUYER, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return record_payment(store, coordinator, actor, settlement_id, payload)


@router.post("/{settlement_id}/report-payment", response_model=SettlementResponse)
async def post_report_payment(
    settlement_id: str,
    payload: PaymentReportRequest,
    actor: DevActor = Depends(require_roles(Role.BUYER, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return report_payment(store, coordinator, actor, settlement_id, payload)


@router.post("/{settlement_id}/payments/{payment_id}/verify", response_model=SettlementResponse)
async def post_verify_payment(
    settlement_id: str,
    payment_id: str,
    payload: Optional[PaymentVerifyRequest] = None,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return verify_payment(store, coordinator, actor, settlement_id, payment_id, payload)
