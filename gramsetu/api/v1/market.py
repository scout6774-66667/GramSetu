from __future__ import annotations

from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, Query

from gramsetu.core import DevActor, Settings, get_current_actor
from gramsetu.schemas import (
    MarketForecastResponse,
    MarketPricesQueryResponse,
    NetEarningsEstimateRequest,
    NetEarningsEstimateResponse,
)
from gramsetu.store import InMemoryStore
from gramsetu.api.deps import get_store, get_app_settings
from gramsetu.services.market import get_market_price_forecast
from gramsetu.services.market_intel import (
    query_market_prices,
    estimate_net_farmer_earnings,
    list_pilot_mandis,
)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/prices", response_model=MarketPricesQueryResponse)
async def api_get_market_prices(
    commodity: Optional[str] = Query(None),
    market_id: Optional[str] = Query(None),
    store: InMemoryStore = Depends(get_store),
):
    """Query market prices with explicit disclosure of dataset restrictions and empty states."""
    return query_market_prices(store, commodity=commodity, market_id=market_id)


@router.get("/mandis", response_model=List[Dict[str, str]])
async def api_list_mandis():
    """List supported pilot mandis in West Bengal."""
    return list_pilot_mandis()


@router.post("/estimate-earnings", response_model=NetEarningsEstimateResponse)
async def api_estimate_net_earnings(payload: NetEarningsEstimateRequest):
    """Estimate net farmer earnings without fabricating verified prices."""
    return estimate_net_farmer_earnings(payload)


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
