"""GramSetu AI Market Intelligence and Net Farmer Earnings Service (Module 4).

Provides:
- Market comparison architecture with honest data availability indicators.
- Respects blocked dataset restrictions:
  - market_prices.csv
  - market_arrivals.csv
  - official_crosswalk_approvals.csv
  - Historical market price panel
  Returns truthful structured disclosures rather than fabricating prices or arrivals.
- Net farmer earnings estimator:
  Net Returns = (Benchmark Modal Price * Quantity) - (Estimated Transit + Mandi Handling Deductions).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any

from gramsetu.store import InMemoryStore
from gramsetu.schemas import (
    MarketPriceRecord,
    MarketPricesQueryResponse,
    NetEarningsEstimateRequest,
    NetEarningsEstimateResponse,
)

# Reference mandis in West Bengal pilot territory
PILOT_MANDIS: List[Dict[str, str]] = [
    {"market_id": "MKT_BURDWAN", "market_name": "Burdwan (Purba Bardhaman APMC)", "district": "Purba Bardhaman", "state": "West Bengal"},
    {"market_id": "MKT_KALNA", "market_name": "Kalna Sub-Market Yard", "district": "Purba Bardhaman", "state": "West Bengal"},
    {"market_id": "MKT_MEMARI", "market_name": "Memari Regulated Market", "district": "Purba Bardhaman", "state": "West Bengal"},
    {"market_id": "MKT_KATWA", "market_name": "Katwa APMC Yard", "district": "Purba Bardhaman", "state": "West Bengal"},
    {"market_id": "MKT_DURGAPUR", "market_name": "Durgapur Municipal Wholesale Mandi", "district": "Paschim Bardhaman", "state": "West Bengal"},
    {"market_id": "MKT_KOLKATA", "market_name": "Kolkata Central Wholesale Terminal", "district": "Kolkata", "state": "West Bengal"},
]

# Benchmark secondary modal prices (paise per gram) for indicative estimation ONLY when official feed blocked
BENCHMARK_PAISE_PER_GRAM: Dict[str, int] = {
    "potato": 14,      # ~₹1,400 / quintal
    "rice": 22,        # ~₹2,200 / quintal
    "paddy": 22,
    "rice (paddy)": 22,
    "tomato": 18,      # ~₹1,800 / quintal
    "mustard": 52,     # ~₹5,200 / quintal
    "onion": 24,       # ~₹2,400 / quintal
    "jute": 48,        # ~₹4,800 / quintal
    "raw jute": 48,
    "soybean": 46,
    "wheat": 24,
    "pomegranate": 95,
}


def list_pilot_mandis() -> List[Dict[str, str]]:
    """Return list of supported pilot mandis in West Bengal."""
    return list(PILOT_MANDIS)


def query_market_prices(
    store: InMemoryStore,
    commodity: Optional[str] = None,
    market_id: Optional[str] = None,
) -> MarketPricesQueryResponse:
    """Query available market prices with explicit disclosure of dataset limitations."""
    # Check if any authentic or secondary price records exist in store evidence or items
    stored_prices = store.list_items("items", lambda it: it.get("entity_type") == "market_price")
    records: List[MarketPriceRecord] = []

    for p in stored_prices:
        if commodity and p.get("commodity_name", "").lower() != commodity.lower():
            continue
        if market_id and p.get("market_id") != market_id:
            continue

        p_modal = int(p.get("modal_price_paise_per_gram", 0))
        p_min = int(p.get("min_price_paise_per_gram", p_modal))
        p_max = int(p.get("max_price_paise_per_gram", p_modal))

        records.append(
            MarketPriceRecord(
                observation_id=p.get("observation_id", "OBS-SEC-01"),
                market_id=p.get("market_id", "MKT_BURDWAN"),
                market_name=p.get("market_name", "Burdwan APMC"),
                commodity_id=p.get("commodity_id", "COM_POTATO"),
                commodity_name=p.get("commodity_name", "Potato"),
                variety=p.get("variety", "Jyoti"),
                grade=p.get("grade", "A"),
                price_date=p.get("price_date", "2026-11-17"),
                min_price_paise_per_gram=p_min,
                modal_price_paise_per_gram=p_modal,
                max_price_paise_per_gram=p_max,
                min_price_rs_quintal=round(p_min * 100.0, 2),
                modal_price_rs_quintal=round(p_modal * 100.0, 2),
                max_price_rs_quintal=round(p_max * 100.0, 2),
                source_tier="SECONDARY_REPUBLISHED",
                data_authenticity="UNVERIFIED_SECONDARY_BASELINE_ONLY",
            )
        )

    data_status = "PARTIAL_SECONDARY_ONLY" if records else "BLOCKED_UNVERIFIED_BASELINE"

    return MarketPricesQueryResponse(
        query_commodity=commodity,
        query_market=market_id,
        data_status=data_status,
        total_records=len(records),
        records=records,
        supported_mandis=PILOT_MANDIS,
    )


def estimate_net_farmer_earnings(
    payload: NetEarningsEstimateRequest,
) -> NetEarningsEstimateResponse:
    """Calculate indicative net farmer earnings without fabricating verified prices."""
    crop_lower = payload.crop.strip().lower()
    benchmark_price = BENCHMARK_PAISE_PER_GRAM.get(crop_lower)

    q_grams = payload.quantity_grams
    q_quintals = round(q_grams / 100_000.0, 4)
    q_tonnes = q_grams / 1_000_000.0

    # Transport estimation: standard rural freight model ₹3.50/tonne-km -> 350 paise / tonne-km
    # Min base charge ₹300 (30,000 paise)
    transit_rate_paise_per_tonne_km = 350
    dist_km = max(5.0, payload.distance_km)
    transport_cost = max(30_000, int(dist_km * q_tonnes * transit_rate_paise_per_tonne_km))

    # Mandi handling / loading deduction: approx 15 paise / kg -> 0.015 paise / g
    handling_deductions = int(q_grams * 0.015)

    if benchmark_price is not None:
        gross_revenue = q_grams * benchmark_price
        net_earnings = max(0, gross_revenue - (transport_cost + handling_deductions))
        net_inr = round(net_earnings / 100.0, 2)
        price_status = "INDICATIVE_SECONDARY_BENCHMARK_UNVERIFIED"
    else:
        gross_revenue = None
        net_earnings = None
        net_inr = None
        price_status = "NO_BENCHMARK_PRICE_AVAILABLE"

    disclaimers = [
        "RESTRICTED DATASET NOTICE: Verified Agmarknet / APMC real-time daily price panel is unpopulated.",
        "Indicative modal price uses secondary historical benchmarks for West Bengal pilot planning only.",
        "Transport deductions assume ₹3.50/t-km on unverified rural road network.",
    ]

    disclaimer_str = (
        "CALCULATED ESTIMATE: Net earnings are indicative estimates for farmer planning. "
        "Actual payouts depend on physical quality inspection, agreed buyer commitments, and verified transit expenses."
    )

    return NetEarningsEstimateResponse(
        crop=payload.crop,
        quantity_grams=q_grams,
        quantity_quintals=q_quintals,
        benchmark_modal_price_paise_per_gram=benchmark_price,
        estimated_gross_paise=gross_revenue,
        estimated_transport_cost_paise=transport_cost,
        estimated_mandi_cess_paise=handling_deductions,
        estimated_net_farmer_earnings_paise=net_earnings,
        estimated_net_farmer_earnings_inr=net_inr,
        price_source_status=price_status,
        disclaimers=disclaimers,
        disclaimer=disclaimer_str,
    )
