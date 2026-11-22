"""Configuration and environment definitions for GramSetu AI."""
from __future__ import annotations

from enum import Enum
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Role(str, Enum):
    FARMER = "FARMER"
    FPO_ADMIN = "FPO_ADMIN"
    BUYER = "BUYER"
    DRIVER = "DRIVER"
    SYSTEM = "SYSTEM"


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    APP_NAME: str = "GramSetu AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Environment = Environment.TESTING
    SNAPSHOT_PATH: Optional[str] = None
    MAX_REQUEST_SIZE_BYTES: int = 1_048_576  # 1 MB
    MAX_RECOVERY_CANDIDATES: int = 8
    SINGLE_WRITER_ENFORCED: bool = True
    AUTH_MODE: str = "auto"  # "auto", "jwt", or "dev"
    JWT_SECRET_KEY: str = "gramsetu-dev-insecure-secret-key-32b"
    JWT_ALGORITHMS: List[str] = ["HS256"]
    JWT_ISSUER: str = "gramsetu-auth"
    JWT_AUDIENCE: str = "gramsetu-api"
    ALLOW_SYNTHETIC_SEED: bool = False
    RELEASE_PIN: str = "2.2.0"
    RELEASE_ARCHIVE_PATH: str = "GramSetu_All_Corrected_CSV_v2_2.zip"
    PHASE4_FORECASTING_ENABLED: bool = False
    PHASE4_MODEL_ARTIFACT_PATH: Optional[str] = None
    PHASE4_NORMALIZED_DATA_PATH: Optional[str] = "contracts/market_prices_normalized.csv"
    PHASE4_APPROVAL_PATH: Optional[str] = None
    ALLOW_RESEARCH_EVALUATION: bool = False


def get_current_utc() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)
