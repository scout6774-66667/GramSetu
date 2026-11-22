"""Backward-compatible facade for gramsetu.acquisition."""
from __future__ import annotations

from gramsetu.ingestion.acquisition import (
    RawBatchMetadata,
    compute_bytes_sha256,
    ingest_raw_agmarknet_batch,
    OFFICIAL_DMI_CATALOG_URL,
    OFFICIAL_RESOURCE_ID,
    NAMESPACE_GOVERNMENT_ORIGIN,
    NAMESPACE_SECONDARY_REPUBLISHED,
    NAMESPACE_SYNTHETIC_SANDBOX,
    CANONICAL_MARKET_CROSSWALK,
    CANONICAL_COMMODITY_CROSSWALK,
)

__all__ = [
    "RawBatchMetadata",
    "compute_bytes_sha256",
    "ingest_raw_agmarknet_batch",
    "OFFICIAL_DMI_CATALOG_URL",
    "OFFICIAL_RESOURCE_ID",
    "NAMESPACE_GOVERNMENT_ORIGIN",
    "NAMESPACE_SECONDARY_REPUBLISHED",
    "NAMESPACE_SYNTHETIC_SANDBOX",
    "CANONICAL_MARKET_CROSSWALK",
    "CANONICAL_COMMODITY_CROSSWALK",
]
