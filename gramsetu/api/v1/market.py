from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, Settings, get_current_actor
from gramsetu.schemas import MarketForecastResponse
from gramsetu.store import InMemoryStore
from gramsetu.api.deps import get_store, get_app_settings
from gramsetu.services.market import get_market_price_forecast

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/forecasts", response_model=MarketForecastResponse)
async def get_market_forecast(
    market_id: str,
    commodity_id: str,
    variety: str = "NOT_REPORTED",
    grade: str = "NOT_REPORTED",
    target_date: Optional[str] = None,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
    cfg: Settings = Depends(get_app_settings),
):
    return get_market_price_forecast(
        store=store,
        settings=cfg,
        actor=actor,
        market_id=market_id,
        commodity_id=commodity_id,
        variety=variety,
        grade=grade,
        target_date=target_date,
    )
