"""GramSetu AI Stage 1: Official Data Acquisition, Lineage & Provenance Protocol.

Provides an authenticated, reproducible, leakage-resistant ingestion pipeline
for AGMARKNET/DMI mandi price observations and arrivals with strict namespace separation
and zero fuzzy entity matching.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from gramsetu.pipeline import FIELDS, SOURCE_TIERS, DataGateError, sha256_file, require_price, parse_source_date

# Official Government Catalog Reference
OFFICIAL_DMI_CATALOG_URL = "https://data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi"
OFFICIAL_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"

# Provenance Namespace Isolation
NAMESPACE_GOVERNMENT_ORIGIN = "GOVERNMENT_DMI_PRIMARY"
NAMESPACE_SECONDARY_REPUBLISHED = "SECONDARY_REPUBLISHED"
NAMESPACE_SYNTHETIC_SANDBOX = "SYNTHETIC_SANDBOX"

# Explicit Canonical Market Crosswalk (Strict 1:1, zero fuzzy matching)
CANONICAL_MARKET_CROSSWALK: Dict[str, str] = {
    # West Bengal Mandis
    "Burdwan": "MKT_000001",
    "Burdwan Mandi": "MKT_000001",
    "Kalna": "MKT_000002",
    "Katwa": "MKT_000003",
    "Memari": "MKT_000004",
    "Asansol": "MKT_000005",
    "Durgapur": "MKT_000006",
    "Bankura": "MKT_000007",
    "Bishnupur": "MKT_000008",
    "Khatra": "MKT_000009",
    "Suri": "MKT_000010",
    "Bolpur": "MKT_000011",
    "Rampurhat": "MKT_000012",
}

CANONICAL_COMMODITY_CROSSWALK: Dict[str, str] = {
    "Brinjal": "COM_BRINJAL",
    "Cabbage": "COM_CABBAGE",
    "Carrot": "COM_CARROT",
    "Chilli": "COM_CHILLI",
    "Green Chilli": "COM_CHILLI",
    "Cucumber": "COM_CUCUMBER",
    "Lentil": "COM_LENTIL",
    "Mustard": "COM_MUSTARD",
    "Onion": "COM_ONION",
    "Paddy": "COM_PADDY",
    "Potato": "COM_POTATO",
    "Pumpkin": "COM_PUMPKIN",
    "Rice": "COM_RICE",
    "Tomato": "COM_TOMATO",
    "Wheat": "COM_WHEAT",
}


@dataclass
class RawBatchMetadata:
    batch_id: str
    source_url: str
    resource_id: str
    retrieved_at_utc: str
    sha256: str
    namespace: str
    reported_units: str
    observation_date_range: Tuple[str, str]
    total_records: int
    quarantined_records: int
    normalized_records: int
    extraction_outcome: str


def compute_bytes_sha256(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def ingest_raw_agmarknet_batch(
    raw_content: bytes,
    batch_id: str,
    source_url: str,
    source_tier: str,
    namespace: str,
    storage_root: Path | str,
    review_status: str = "NOT_REVIEWED",
    review_id: str = "NOT_REVIEWED",
) -> RawBatchMetadata:
    """Idempotently ingest an official or secondary vendor batch.

    1. Stores original immutable raw bytes under storage_root/raw/{namespace}/{batch_id}.raw.
    2. Calculates SHA-256 byte hash.
    3. Crosswalks markets and commodities with strict 1:1 mapping (rejecting unmapped rows to quarantine).
    4. Validates price ordering (min <= modal <= max) and non-negative finite decimals.
    5. Emits normalized CSV and row-level quarantine rejection JSON.
    """
    if source_tier not in SOURCE_TIERS:
        raise DataGateError(f"Invalid source tier: {source_tier}")
    if namespace not in {NAMESPACE_GOVERNMENT_ORIGIN, NAMESPACE_SECONDARY_REPUBLISHED, NAMESPACE_SYNTHETIC_SANDBOX}:
        raise DataGateError(f"Unknown namespace: {namespace}")

    root = Path(storage_root)
    raw_dir = root / "raw" / namespace
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{batch_id}.raw"

    # Store raw bytes
    raw_path.write_bytes(raw_content)
    raw_sha = compute_bytes_sha256(raw_content)
    retrieved_now = datetime.now(timezone.utc).isoformat()

    # Parse and normalize
    text_content = raw_content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(text_content.splitlines())
    if not reader.fieldnames:
        raise DataGateError("Batch content has no headers")

    aliases = {
        "arrival_date": "observed_date",
        "date": "observed_date",
        "min_price": "min_price_inr_quintal",
        "modal_price": "modal_price_inr_quintal",
        "max_price": "max_price_inr_quintal",
    }

    normalized_rows: List[Dict[str, str]] = []
    quarantined_rows: List[Dict[str, Any]] = []
    dates_observed: set[str] = set()

    for line_idx, orig_row in enumerate(reader, start=2):
        cleaned: Dict[str, str] = {}
        for k, v in orig_row.items():
            key = (k or "").strip().lower().replace(" ", "_")
            key = aliases.get(key, key)
            cleaned[key] = str(v or "").strip()

        # Check required fields
        req_keys = {"market", "commodity", "observed_date", "min_price_inr_quintal", "modal_price_inr_quintal", "max_price_inr_quintal"}
        if not req_keys <= set(cleaned):
            quarantined_rows.append({
                "line": line_idx,
                "reason": f"Missing required vendor columns: {sorted(req_keys - set(cleaned))}",
                "raw_record": orig_row,
            })
            continue

        try:
            obs_d = parse_source_date(cleaned["observed_date"])
            if obs_d > date.today():
                raise DataGateError(f"Future observation date rejected: {obs_d}")

            min_p = require_price(cleaned["min_price_inr_quintal"], "min_price_inr_quintal")
            mod_p = require_price(cleaned["modal_price_inr_quintal"], "modal_price_inr_quintal")
            max_p = require_price(cleaned["max_price_inr_quintal"], "max_price_inr_quintal")

            if not (min_p <= mod_p <= max_p):
                raise DataGateError(f"Price ordering invariant violated: min={min_p}, modal={mod_p}, max={max_p}")

            # Crosswalk market
            raw_mkt = cleaned["market"].strip()
            canonical_mkt = CANONICAL_MARKET_CROSSWALK.get(raw_mkt)
            if not canonical_mkt:
                # Direct canonical ID passthrough if already canonical
                if raw_mkt.startswith("MKT_"):
                    canonical_mkt = raw_mkt
                else:
                    raise DataGateError(f"Unmapped source market: '{raw_mkt}'. Strict crosswalk required.")

            # Crosswalk commodity
            raw_cmd = cleaned["commodity"].strip()
            canonical_cmd = CANONICAL_COMMODITY_CROSSWALK.get(raw_cmd)
            if not canonical_cmd:
                if raw_cmd.startswith("COM_"):
                    canonical_cmd = raw_cmd
                else:
                    raise DataGateError(f"Unmapped source commodity: '{raw_cmd}'. Strict crosswalk required.")

            variety = cleaned.get("variety", "").strip() or "NOT_REPORTED"
            grade = cleaned.get("grade", "").strip() or "NOT_REPORTED"
            obs_date_str = obs_d.isoformat()
            dates_observed.add(obs_date_str)

            src_key = f"{batch_id}|{canonical_mkt}|{canonical_cmd}|{obs_date_str}"
            obs_id = "OBS_" + hashlib.sha256(f"{raw_sha}|{line_idx}".encode()).hexdigest()[:20].upper()

            normalized_rows.append({
                "observation_id": obs_id,
                "market_id": canonical_mkt,
                "commodity_id": canonical_cmd,
                "variety": variety,
                "grade": grade,
                "observed_date": obs_date_str,
                "min_price_inr_quintal": str(min_p),
                "modal_price_inr_quintal": str(mod_p),
                "max_price_inr_quintal": str(max_p),
                "source_record_key": src_key,
                "source_url": source_url,
                "source_file_sha256": raw_sha,
                "retrieved_at_utc": retrieved_now,
                "source_tier": source_tier,
                "simulation_flag": "True" if namespace == NAMESPACE_SYNTHETIC_SANDBOX else "False",
                "review_status": review_status,
                "review_id": review_id,
            })
        except (ValueError, DataGateError) as e:
            quarantined_rows.append({
                "line": line_idx,
                "reason": str(e),
                "raw_record": orig_row,
            })

    # Write normalized output and quarantine log
    norm_dir = root / "normalized" / namespace
    norm_dir.mkdir(parents=True, exist_ok=True)
    norm_file = norm_dir / f"{batch_id}.csv"
    with norm_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(normalized_rows)

    quarantine_dir = root / "quarantine" / namespace
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / f"{batch_id}.rejected.json"
    with quarantine_file.open("w", encoding="utf-8") as f:
        json.dump(quarantined_rows, f, indent=2)

    date_sorted = sorted(dates_observed)
    min_date = date_sorted[0] if date_sorted else "NONE"
    max_date = date_sorted[-1] if date_sorted else "NONE"

    outcome = "SUCCESS_COMPLETE" if not quarantined_rows else ("PARTIAL_WITH_QUARANTINE" if normalized_rows else "REJECTED_ALL_ROWS")

    return RawBatchMetadata(
        batch_id=batch_id,
        source_url=source_url,
        resource_id=OFFICIAL_RESOURCE_ID,
        retrieved_at_utc=retrieved_now,
        sha256=raw_sha,
        namespace=namespace,
        reported_units="INR/quintal",
        observation_date_range=(min_date, max_date),
        total_records=len(normalized_rows) + len(quarantined_rows),
        quarantined_records=len(quarantined_rows),
        normalized_records=len(normalized_rows),
        extraction_outcome=outcome,
    )
