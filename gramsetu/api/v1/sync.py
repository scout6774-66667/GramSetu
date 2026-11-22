from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from gramsetu.core import DevActor, get_current_actor
from gramsetu.schemas import OfflineCommandEnvelope, ReconciliationResponse
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.services.sync import reconcile_offline_command

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/reconcile", response_model=ReconciliationResponse)
async def post_reconcile_command(
    envelope: OfflineCommandEnvelope,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    result, status_code = reconcile_offline_command(store, coordinator, actor, envelope)
    return JSONResponse(status_code=status_code, content=result.model_dump(mode="json"))
