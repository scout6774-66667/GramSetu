"""GramSetu AI Market Intelligence and Wholesale Price Forecasting Service.

Connects normalized mandi prices and validated ML time-series models to DemandSync,
strictly adhering to feature gating, temporal causality, and production safety locks.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from gramsetu.core import Settings, Environment, DevActor, Role, GramSetuError
from gramsetu.store import InMemoryStore
from gramsetu.schemas import MarketForecastResponse
from gramsetu.pipeline import predict_one, read_normalized, DataGateError


class ForecastingUnavailableError(GramSetuError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=503, error_code="FORECASTING_UNAVAILABLE", details=details)


class ProvenanceRefusalError(GramSetuError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=403, error_code="PROVENANCE_REFUSAL", details=details)


def get_market_price_forecast(
    store: InMemoryStore,
    settings: Settings,
    actor: DevActor,
    market_id: str,
    commodity_id: str,
    variety: str = "NOT_REPORTED",
    grade: str = "NOT_REPORTED",
    target_date: Optional[str] = None,
) -> MarketForecastResponse:
    """Provide single-step wholesale price forecast for market x commodity x variety x grade.

    - Feature Gating: Refuses with UNAVAILABLE_FEATURE_DISABLED when disabled.
    - Production Gate: Refuses with REFUSED_UNVERIFIED_PROVENANCE in production unless
      independently reviewed and approved.
    - Missing Model: Returns UNAVAILABLE_NO_TRAINED_MODEL when artifact is missing or incomplete.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    t_date = target_date or (date.today() + timedelta(days=1)).isoformat()

    base_kwargs = {
        "market_id": market_id,
        "commodity_id": commodity_id,
        "variety": variety,
        "grade": grade,
        "forecast_target_date": t_date,
        "forecast_issue_timestamp_utc": now_utc,
        "price_unit": "INR/quintal",
        "predicted_modal_price_inr_quintal": None,
        "feature_availability": {
            "lag_1": "UNAVAILABLE",
            "lag_7": "UNAVAILABLE",
            "lag_14": "UNAVAILABLE",
            "lag_28": "UNAVAILABLE",
            "market_arrivals": "UNAVAILABLE_AWAITING_SOURCE",
            "historical_weather": "UNAVAILABLE_AWAITING_SOURCE",
        },
    }

    # 1. Feature Gate Enforcement
    if not settings.PHASE4_FORECASTING_ENABLED:
        return MarketForecastResponse(
            status="UNAVAILABLE_FEATURE_DISABLED",
            operational_notice=(
                "Phase 4 Market Price Forecasting is DISABLED by system configuration "
                "(PHASE4_FORECASTING_ENABLED=False). Set PHASE4_FORECASTING_ENABLED=True to activate."
            ),
            **base_kwargs,
        )

    # 2. Production Safety Lock
    is_prod = settings.ENVIRONMENT == Environment.PRODUCTION or "prod" in str(settings.ENVIRONMENT).lower()
    if is_prod and not settings.ALLOW_RESEARCH_EVALUATION:
        return MarketForecastResponse(
            status="REFUSED_UNVERIFIED_PROVENANCE",
            operational_notice=(
                "Production safety refusal: Market price forecasting models based on unverified secondary "
                "or experimental data cannot be served in production environment without certified operator sign-off."
            ),
            **base_kwargs,
        )

    # 3. Model Artifact Availability Check
    model_path_str = settings.PHASE4_MODEL_ARTIFACT_PATH
    if not model_path_str or not Path(model_path_str).exists():
        # Check store unavailable marker
        status_marker = store.get_item("items", "price_forecasts_status")
        msg = status_marker.get("message", "Model artifact unavailable.") if status_marker else "No model artifact configured."
        return MarketForecastResponse(
            status="UNAVAILABLE_NO_TRAINED_MODEL",
            operational_notice=f"Forecasting model unavailable: {msg}",
            **base_kwargs,
        )

    try:
        model_artifact = json.loads(Path(model_path_str).read_text(encoding="utf-8"))
    except Exception as e:
        return MarketForecastResponse(
            status="UNAVAILABLE_CORRUPTED_MODEL_ARTIFACT",
            operational_notice=f"Failed to load model artifact: {e}",
            **base_kwargs,
        )

    # If artifact explicitly indicates UNAVAILABLE (e.g. training gate failure)
    if model_artifact.get("status") == "UNAVAILABLE":
        return MarketForecastResponse(
            status="UNAVAILABLE_TRAINING_GATES_FAILED",
            operational_notice=f"Model training gates failed: {model_artifact.get('reason', 'UNKNOWN')}",
            **base_kwargs,
        )

    # 4. History Data Availability Check
    data_path_str = settings.PHASE4_NORMALIZED_DATA_PATH
    if not data_path_str or not Path(data_path_str).exists():
        return MarketForecastResponse(
            status="UNAVAILABLE_HISTORICAL_DATA_MISSING",
            operational_notice="Normalized historical market price data missing for lag feature computation.",
            **base_kwargs,
        )

    try:
        history_rows = read_normalized(data_path_str)
    except Exception as e:
        return MarketForecastResponse(
            status="UNAVAILABLE_INVALID_HISTORY_DATA",
            operational_notice=f"Historical data validation failed: {e}",
            **base_kwargs,
        )

    # 5. Predict single step
    group = (market_id, commodity_id, variety, grade)
    try:
        req_d = date.fromisoformat(t_date)
        res = predict_one(model_artifact, history_rows, group, req_d)
        
        feature_status = {
            "lag_1": "AVAILABLE",
            "lag_7": "AVAILABLE",
            "lag_14": "AVAILABLE",
            "lag_28": "AVAILABLE",
            "rolling_mean_7": "AVAILABLE",
            "rolling_std_7": "AVAILABLE",
            "market_arrivals": "UNAVAILABLE_AWAITING_SOURCE",
            "historical_weather": "UNAVAILABLE_AWAITING_SOURCE",
        }

        return MarketForecastResponse(
            status="PREDICTED_RESEARCH_ONLY",
            market_id=market_id,
            commodity_id=commodity_id,
            variety=variety,
            grade=grade,
            forecast_target_date=t_date,
            forecast_issue_timestamp_utc=now_utc,
            price_unit="INR/quintal",
            predicted_modal_price_inr_quintal=res["predicted_modal_price_inr_quintal"],
            model_version=model_artifact.get("schema_version", "phase4.1"),
            training_dataset_sha256=model_artifact.get("dataset_sha256"),
            source_review_tier=model_artifact.get("deployment_scope"),
            feature_availability=feature_status,
            operational_notice="Inference completed for research evaluation.",
        )
    except DataGateError as e:
        return MarketForecastResponse(
            status="UNAVAILABLE_INSUFFICIENT_LAGS",
            operational_notice=f"Inference blocked by data gate: {e}",
            **base_kwargs,
        )
    except Exception as e:
        return MarketForecastResponse(
            status="UNAVAILABLE_PREDICTION_ERROR",
            operational_notice=f"Unexpected prediction error: {e}",
            **base_kwargs,
        )
