from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from gramsetu.core import DevActor, Role, get_current_actor, require_roles, verify_organization_access
from gramsetu.schemas import (
    HarvestForecastCreate,
    HarvestForecastResponse,
    BuyerRequirementCreate,
    BuyerRequirementResponse,
    DemandGapAnalysis,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.api.deps import get_store, get_coordinator
from gramsetu.services.supply import create_harvest_forecast, list_harvest_forecasts
from gramsetu.services.procurement import (
    create_buyer_requirement,
    list_buyer_requirements,
    compute_demand_gap,
)

router = APIRouter(tags=["demand"])


@router.post("/forecasts", response_model=HarvestForecastResponse)
async def post_forecast(
    payload: HarvestForecastCreate,
    actor: DevActor = Depends(require_roles(Role.FARMER, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    forecast, was_created = create_harvest_forecast(store, coordinator, actor, payload)
    status_code = 201 if was_created else 200
    return JSONResponse(status_code=status_code, content=forecast.model_dump(mode="json"))


@router.get("/forecasts", response_model=List[HarvestForecastResponse])
async def get_forecasts(
    crop: Optional[str] = None,
    grade: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_harvest_forecasts(store, actor, crop=crop, grade=grade)


@router.post("/requirements", response_model=BuyerRequirementResponse)
async def post_requirement(
    payload: BuyerRequirementCreate,
    actor: DevActor = Depends(require_roles(Role.BUYER, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
):
    requirement, was_created = create_buyer_requirement(store, coordinator, actor, payload)
    status_code = 201 if was_created else 200
    return JSONResponse(status_code=status_code, content=requirement.model_dump(mode="json"))


@router.get("/requirements", response_model=List[BuyerRequirementResponse])
async def get_requirements(
    crop: Optional[str] = None,
    grade: Optional[str] = None,
    status: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return list_buyer_requirements(store, actor, crop=crop, grade=grade, status=status)


@router.get("/demand-gap", response_model=List[DemandGapAnalysis])
@router.get("/demand-gaps", response_model=List[DemandGapAnalysis])
async def get_demand_gap(
    fpo_id: str,
    crop: Optional[str] = None,
    grade: Optional[str] = None,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
):
    verify_organization_access(actor, fpo_id)
    return compute_demand_gap(store, fpo_id, crop=crop, grade=grade)
