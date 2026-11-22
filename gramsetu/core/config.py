"""Configuration and environment definitions for GramSetu AI."""
from __future__ import annotations

from enum import Enum
from typing import Optional, List
from datetime import datetime, timezone
import os
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
    TRANSPORTER = "TRANSPORTER"
    STORAGE_OPERATOR = "STORAGE_OPERATOR"
    ADMIN = "ADMIN"
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

    # PostgreSQL & PostGIS Configuration
    DATABASE_URL: Optional[str] = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "gramsetu_db"
    POSTGRES_USER: str = "gramsetu_user"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SCHEMA: str = "public"
    POSTGIS_ENABLED: bool = True
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    def get_database_url(self) -> str:
        """Resolve database connection URL from explicit URL or individual components."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        env_url = os.environ.get("DATABASE_URL")
        if env_url:
            return env_url
        user = os.environ.get("POSTGRES_USER", self.POSTGRES_USER)
        pwd = os.environ.get("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        host = os.environ.get("POSTGRES_HOST", self.POSTGRES_HOST)
        port = os.environ.get("POSTGRES_PORT", str(self.POSTGRES_PORT))
        db = os.environ.get("POSTGRES_DB", self.POSTGRES_DB)
        auth = f"{user}:{pwd}" if pwd else user
        return f"postgresql://{auth}@{host}:{port}/{db}"


def get_current_utc() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)
