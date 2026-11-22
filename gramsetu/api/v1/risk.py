from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, Role, get_current_actor, require_roles
from gramsetu.schemas import (
    RiskIncidentResponse,
    IncidentResolveRequest,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.services.risk import (
    scan_risk_incidents,
    acknowledge_incident,
    resolve_incident,
    list_incidents,
)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/scan", response_model=List[RiskIncidentResponse])
async def post_risk_scan(
    fpo_id: str,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return scan_risk_incidents(store, coordinator, actor, fpo_id)


@router.get("/incidents", response_model=List[RiskIncidentResponse])
async def get_all_incidents(
    fpo_id: Optional[str] = None,
    status: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_incidents(store, actor, fpo_id=fpo_id, status=status)


@router.post("/incidents/{incident_id}/acknowledge", response_model=RiskIncidentResponse)
async def post_acknowledge_incident(
    incident_id: str,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return acknowledge_incident(store, coordinator, actor, incident_id)


@router.post("/incidents/{incident_id}/resolve", response_model=RiskIncidentResponse)
async def post_resolve_incident(
    incident_id: str,
    payload: IncidentResolveRequest,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    return resolve_incident(store, coordinator, actor, incident_id, payload)
