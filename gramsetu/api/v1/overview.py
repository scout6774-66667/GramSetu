from __future__ import annotations

from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, get_current_actor
from gramsetu.schemas import (
    FarmerOverviewResponse,
    BuyerOverviewResponse,
    DriverOverviewResponse,
    FpoOverviewResponse,
)
from gramsetu.store import InMemoryStore
from gramsetu.api.deps import get_store
from gramsetu.services.overview import (
    get_farmer_overview,
    get_buyer_overview,
    get_driver_overview,
    get_fpo_overview,
)

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/farmer", response_model=FarmerOverviewResponse)
async def get_overview_farmer(
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_farmer_overview(store, actor)


@router.get("/buyer", response_model=BuyerOverviewResponse)
async def get_overview_buyer(
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_buyer_overview(store, actor)


@router.get("/driver", response_model=DriverOverviewResponse)
async def get_overview_driver(
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_driver_overview(store, actor)


@router.get("/fpo", response_model=FpoOverviewResponse)
async def get_overview_fpo(
    fpo_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    return get_fpo_overview(store, actor, fpo_id)
