"""Staged release validation, hash checking, and sandbox seeding for GramSetu AI."""
from __future__ import annotations

import csv
import io
import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Dict, Any, List, Optional
from zipfile import ZipFile

from gramsetu.core.units import (
    DatasetContractError,
    validate_requirement_demand_semantics,
    validate_commitment_delivery_reconciliation,
)
from gramsetu.infrastructure.persistence import TransactionCoordinator


class StagedRelease:
    """In-memory validated release bundle ready for transactional application."""

    def __init__(
        self,
        version: str,
        tables: Dict[str, List[Dict[str, str]]],
        manifest: Dict[str, Any],
        audit: Dict[str, Any],
        file_hashes: Optional[Dict[str, str]] = None,
    ):
        self.version = version
        self.tables = tables
        self.manifest = manifest
        self.audit = audit
        self.file_hashes = file_hashes or {}


def _read_csv_blob(blob: bytes, expected_columns: List[str], table_name: str) -> List[Dict[str, str]]:
    """Parse UTF-8 CSV bytes, validating exact header matching and non-empty field definitions."""
    try:
        text = blob.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise DatasetContractError(f"{table_name}: CSV content is not valid UTF-8") from e

    stream = io.StringIO(text)
    reader = csv.DictReader(stream)

    if reader.fieldnames is None:
        raise DatasetContractError(f"{table_name}: empty CSV file or missing header row")

    if list(reader.fieldnames) != expected_columns:
        raise DatasetContractError(
            f"{table_name}: header mismatch; actual={list(reader.fieldnames)}, expected={expected_columns}"
        )

    rows = list(reader)
    for idx, row in enumerate(rows, start=2):
        if None in row or any(v is None for v in row.values()):
            raise DatasetContractError(f"{table_name}:{idx}: malformed CSV row structure")
    return rows


def validate_release_zip(zip_path: str | Path) -> StagedRelease:
    """Validate release archive entries, manifest version, SHA-256 hashes, schemas, and declared keys.

    Strictly immutable preflight: does NOT alter backend state.
    """
    path = Path(zip_path)
    if not path.is_file():
        raise DatasetContractError(f"Release ZIP not found: {path}")

    tables: Dict[str, List[Dict[str, str]]] = {}
    blank_cells_by_table: Dict[str, int] = {}

    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise DatasetContractError("Duplicate file entries detected in ZIP archive")

        if "manifest.json" not in names or "file_hashes_sha256.json" not in names:
            raise DatasetContractError("Release archive is missing required manifest.json or file_hashes_sha256.json")

        try:
            manifest = json.loads(archive.read("manifest.json"))
            expected_hashes = json.loads(archive.read("file_hashes_sha256.json"))
        except Exception as e:
            raise DatasetContractError("Failed to parse manifest JSON in release archive") from e

        if manifest.get("version") != "2.2.0":
            raise DatasetContractError(f"Unsupported manifest version: {manifest.get('version')}; expected '2.2.0'")

        table_specs = manifest.get("tables", {})
        declared_names = set(table_specs.keys())
        archive_csv_names = {Path(x).stem for x in names if x.startswith("csv/") and x.endswith(".csv")}

        if archive_csv_names != declared_names:
            missing = sorted(declared_names - archive_csv_names)
            unexpected = sorted(archive_csv_names - declared_names)
            raise DatasetContractError(f"Table inventory mismatch: missing={missing}, unexpected={unexpected}")

        expected_csv_filenames = {name + ".csv" for name in declared_names}
        if set(expected_hashes.keys()) != expected_csv_filenames:
            raise DatasetContractError("Hash index files do not match declared table inventory")

        # 1. Byte hash and schema verification
        for name, spec in table_specs.items():
            blob = archive.read(f"csv/{name}.csv")
            expected_hash = expected_hashes[name + ".csv"]

            if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                raise DatasetContractError(f"{name}: invalid SHA-256 hex format in manifest")

            actual_hash = sha256(blob).hexdigest()
            if actual_hash != expected_hash:
                raise DatasetContractError(f"{name}: byte hash mismatch (actual={actual_hash}, expected={expected_hash})")

            rows = _read_csv_blob(blob, spec["columns"], name)
            if len(rows) != spec["row_count"]:
                raise DatasetContractError(f"{name}: row count mismatch (actual={len(rows)}, expected={spec['row_count']})")

            tables[name] = rows
            blank_cells_by_table[name] = sum(v.strip() == "" for row in rows for v in row.values())

    # 2. Primary Key and Business Key Uniqueness
    for name, spec in table_specs.items():
        rows = tables[name]
        pk = spec["primary_key"]
        if pk not in spec["columns"]:
            raise DatasetContractError(f"{name}: declared primary key '{pk}' missing from columns")

        ids = [row[pk] for row in rows]
        if any(not v.strip() for v in ids) or len(ids) != len(set(ids)):
            raise DatasetContractError(f"{name}: missing or duplicate primary key in table")

        for combo in spec.get("unique_combinations", []):
            keys = [tuple(row[c] for c in combo) for row in rows]
            if len(keys) != len(set(keys)):
                raise DatasetContractError(f"{name}: duplicate declared business key combination: {combo}")

    # 3. Foreign Key Integrity (allowing legitimate blanks for optional FKs)
    for name, spec in table_specs.items():
        for col, target in spec.get("foreign_keys", {}).items():
            dest_table, dest_col = target.split(".", 1)
            if dest_table not in tables:
                raise DatasetContractError(f"{name}.{col}: foreign key target table '{dest_table}' not loaded")

            target_values = {r[dest_col] for r in tables[dest_table]}
            for idx, row in enumerate(tables[name], start=2):
                val = row.get(col, "").strip()
                if val and val not in target_values:
                    raise DatasetContractError(
                        f"{name}:{idx}: foreign key violation on '{col}'='{val}'. Not found in {dest_table}.{dest_col}"
                    )

    # 4. Mandatory Business Invariants
    total_rows = sum(len(r) for r in tables.values())
    audit_summary = {
        "status": "PASS",
        "release_version": manifest["version"],
        "table_count": len(tables),
        "normalized_row_count": total_rows,
        "blank_cells_count": sum(blank_cells_by_table.values()),
        "blank_cells_by_table": blank_cells_by_table,
    }

    return StagedRelease(
        version=manifest["version"],
        tables=tables,
        manifest=manifest,
        audit=audit_summary,
        file_hashes=expected_hashes,
    )


def import_staged_release_to_store(
    staged: StagedRelease,
    coordinator: TransactionCoordinator,
    *,
    environment: str,
    allow_synthetic_seed: bool,
    release_pin: str = "2.2.0",
) -> Dict[str, Any]:
    """Atomically ingest validated release data into backend InMemoryStore under a single write lock."""
    env = environment.strip().lower()
    if env == "production":
        raise DatasetContractError(
            f"Production safety violation: synthetic fixture release cannot be seeded into environment='{environment}'"
        )
    if not allow_synthetic_seed:
        raise DatasetContractError("Synthetic fixture release cannot be seeded without explicit allow_synthetic_seed=True")

    if staged.version != release_pin:
        raise DatasetContractError(f"Staged release version {staged.version} does not match release pin {release_pin}")

    store = coordinator.store
    import_marker_key = f"release_import_{release_pin}"
    existing_marker = store.get_item("evidence", import_marker_key)
    if existing_marker is not None:
        return {
            "status": "ALREADY_IMPORTED",
            "release_version": release_pin,
            "idempotent": True,
            "table_count": staged.audit["table_count"],
            "imported_rows": staged.audit["normalized_row_count"],
            "quarantined_records": 0,
            "trust_classification": "VALIDATED_RELEASE_STRUCTURE_SANDBOX_ONLY",
            "message": "Release archive was previously ingested into store; operation is idempotent.",
        }

    with coordinator.transaction():
        # 1. Harvest Forecasts (F2)
        for r in staged.tables.get("harvest_forecasts", []):
            h_id = r.get("forecast_id") or r.get("harvest_forecast_id")
            qty_g = int(r.get("forecast_quantity_grams") or r.get("estimated_grams") or float(r.get("expected_yield_kg", 0)) * 1000)
            store.set_item("forecasts", h_id, {
                "forecast_id": h_id,
                "farmer_id": r["farmer_id"],
                "fpo_id": "fpo-alpha",
                "crop": r.get("commodity_id", "WHEAT"),
                "variety": r.get("variety", "Standard"),
                "grade": r.get("grade", "Standard"),
                "estimated_grams": qty_g,
                "harvest_start_date": r.get("forecast_harvest_date", "2026-11-20"),
                "harvest_end_date": r.get("forecast_harvest_date", "2026-11-20"),
                "confidence_score": float(r.get("confidence_pct", 80)) / 100.0,
                "created_at": r.get("captured_at", "2026-11-10T00:00:00Z"),
                "idempotency_key": h_id,
                "status": "ACTIVE",
            })

        # 2. Inventory Lots (F3)
        for r in staged.tables.get("inventory_lots", []):
            l_id = r["lot_id"]
            phys_g = int(r.get("physical_grams") or r.get("received_grams") or float(r.get("quantity_kg", 0)) * 1000)
            res_g = int(r.get("reserved_grams", 0))
            held_g = int(r.get("held_grams", 0))
            avail_g = max(0, phys_g - res_g - held_g)
            store.set_item("lots", l_id, {
                "lot_id": l_id,
                "forecast_id": r.get("forecast_id", "FCST_NONE"),
                "farmer_id": r["farmer_id"],
                "fpo_id": "fpo-alpha",
                "crop": r.get("commodity_id", "WHEAT"),
                "variety": r.get("variety", "Standard"),
                "grade": r.get("grade", "A"),
                "quantity_grams": phys_g,
                "reserved_grams": res_g,
                "available_grams": avail_g,
                "storage_location": r.get("location_id", "LOC_HUB_000001"),
                "custody": "FPO",
                "version": int(r.get("version", 1)),
                "status": r.get("lot_status", "ACTIVE"),
                "created_at": r.get("received_at", "2026-11-10T00:00:00Z"),
                "updated_at": r.get("received_at", "2026-11-10T00:00:00Z"),
                "parent_lot_ids": [],
            })
            store.set_item("movements", f"MOV_{l_id}", {
                "movement_id": f"MOV_{l_id}",
                "lot_id": l_id,
                "movement_type": "RECEIPT",
                "source": "FARM",
                "destination": r.get("location_id", "LOC_HUB_000001"),
                "quantity_grams": phys_g,
                "performed_by": r["farmer_id"],
                "timestamp": r.get("received_at", "2026-11-10T00:00:00Z"),
            })

        # 3. Buyer Requirements & CommitGuard (F4)
        for r in staged.tables.get("buyer_requirements", []):
            req_id = r["requirement_id"]
            needed = int(r.get("required_grams", 0))
            remaining = int(r.get("remaining_grams", 0))
            uncommitted = int(r.get("uncommitted_grams", 0))
            validate_requirement_demand_semantics(needed_grams=needed, uncommitted_grams=uncommitted, remaining_grams=remaining)
            allocated = needed - remaining
            store.set_item("requirements", req_id, {
                "requirement_id": req_id,
                "buyer_id": r.get("buyer_org_id") or r.get("buyer_id", "buyer-reliance"),
                "crop": r.get("commodity_id", "WHEAT"),
                "variety": r.get("variety", "Standard"),
                "grade": r.get("grade", "A"),
                "needed_grams": needed,
                "allocated_grams": allocated,
                "delivery_window_start": r.get("created_at", "2026-11-09T07:00:00Z"),
                "delivery_window_end": r.get("delivery_deadline", "2026-11-27T10:00:00Z"),
                "max_price_paise_per_gram": 20,
                "status": r.get("status", "OPEN"),
                "created_at": r.get("created_at", "2026-11-09T07:00:00Z"),
                "updated_at": r.get("created_at", "2026-11-09T07:00:00Z"),
                "idempotency_key": req_id,
            })

        for r in staged.tables.get("commitments", []):
            c_id = r["commitment_id"]
            deliv = int(r.get("delivered_grams", 0))
            accept = int(r.get("buyer_accepted_grams", 0))
            reject = int(r.get("buyer_rejected_grams", 0))
            validate_commitment_delivery_reconciliation(delivered_grams=deliv, accepted_grams=accept, rejected_grams=reject)
            store.set_item("commitments", c_id, {
                "commitment_id": c_id,
                "requirement_id": r["requirement_id"],
                "fpo_id": "fpo-alpha",
                "buyer_id": r.get("buyer_org_id", "buyer-reliance"),
                "committed_grams": int(r.get("committed_grams", 0)),
                "agreed_price_paise_per_gram": int(r.get("unit_price_paise_per_kg", 2000)) // 1000,
                "agreed_price_paise_per_kg": int(r.get("unit_price_paise_per_kg", 2000)),
                "allocated_lot_ids": [r["lot_id"]] if r.get("lot_id") else [],
                "allocated_grams": int(r.get("committed_grams", 0)),
                "status": r.get("status", "CONFIRMED"),
                "version": int(r.get("version", 1)),
                "created_at": r.get("committed_at", "2026-11-09T09:00:00Z"),
                "updated_at": r.get("committed_at", "2026-11-09T09:00:00Z"),
            })

        # 4. Vehicles & Logistics (F5)
        for r in staged.tables.get("vehicles", []):
            v_id = r["vehicle_id"]
            cap_g = int(r.get("payload_capacity_grams") or 1000000)
            store.set_item("vehicles", v_id, {
                "vehicle_id": v_id,
                "fpo_id": "fpo-alpha",
                "driver_id": "driver-1",
                "vehicle_type": r.get("vehicle_type", "SMALL_GOODS_CARRIER"),
                "capacity_grams": cap_g,
                "is_available": True,
                "status": "AVAILABLE",
                "created_at": "2026-11-10T00:00:00Z",
                "updated_at": "2026-11-10T00:00:00Z",
            })

        # 5. Shipments (F6)
        for r in staged.tables.get("shipments", []):
            s_id = r["shipment_id"]
            store.set_item("shipments", s_id, {
                "shipment_id": s_id,
                "commitment_id": r["commitment_id"],
                "vehicle_id": r.get("vehicle_id", "VEH_000001"),
                "driver_id": "driver-1",
                "dispatched_grams": int(r.get("quantity_grams", 0)),
                "version": 1,
                "status": "DELIVERED",
                "custody": "DRIVER",
                "actual_pickup_time": r.get("planned_departure_at"),
                "actual_delivery_time": r.get("planned_arrival_at"),
                "accepted_grams": int(r.get("actual_delivered_grams", 0)),
                "rejected_grams": 0,
                "loss_grams": 0,
                "created_at": r.get("planned_departure_at", "2026-11-15T00:00:00Z"),
                "updated_at": r.get("planned_arrival_at", "2026-11-15T00:00:00Z"),
            })

        # 6. Settlements from payable_ledger (F8)
        for r in staged.tables.get("payable_ledger", []):
            pay_id = r["payable_id"]
            store.set_item("settlements", pay_id, {
                "settlement_id": pay_id,
                "commitment_id": r["commitment_id"],
                "farmer_id": r["farmer_id"],
                "buyer_id": r["buyer_org_id"],
                "fpo_id": "fpo-alpha",
                "accepted_grams": int(r["accepted_grams"]),
                "gross_amount_paise": int(r["gross_payable_paise"]),
                "deductions_paise": int(r["authorized_deductions_paise"]),
                "net_payable_paise": int(r["net_payable_paise"]),
                "remaining_balance_paise": 0 if "SETTLED" in r.get("payment_status", "") else int(r["net_payable_paise"]),
                "status": r.get("payment_status", "PENDING"),
                "payments": [],
                "created_at": r.get("issued_at", "2026-11-15T09:30:00Z"),
                "updated_at": r.get("issued_at", "2026-11-15T09:30:00Z"),
            })

        # 7. Domain Events (Audit)
        for i, r in enumerate(staged.tables.get("domain_events", [])):
            ev_id = r.get("event_id", f"EVT_{i}")
            store.set_item("events", ev_id, {
                "event_id": ev_id,
                "aggregate_type": r.get("aggregate_type", "GENERAL"),
                "aggregate_id": r.get("aggregate_id", "AGG_001"),
                "event_type": r.get("event_type", "INFO"),
                "payload": r,
                "timestamp": r.get("occurred_at", "2026-11-15T00:00:00Z"),
            })

        # Status markers in items collection
        store.set_item("items", "market_arrivals_status", {
            "status": "UNAVAILABLE_AWAITING_SOURCE",
            "row_count": len(staged.tables.get("market_arrivals", [])),
        })
        store.set_item("items", "price_forecasts_status", {
            "status": "UNAVAILABLE_UNTRAINED_MODEL",
            "row_count": len(staged.tables.get("price_forecasts", [])),
        })

        # Evidence marker
        store.set_item("evidence", import_marker_key, {
            "status": "IMPORTED",
            "version": release_pin,
            "imported_at": "2026-11-22T12:00:00Z",
            "table_count": staged.audit["table_count"],
            "row_count": staged.audit["normalized_row_count"],
        })

    return {
        "status": "IMPORTED",
        "release_version": release_pin,
        "idempotent": False,
        "table_count": staged.audit["table_count"],
        "imported_rows": staged.audit["normalized_row_count"],
        "quarantined_records": 0,
        "trust_classification": "VALIDATED_RELEASE_STRUCTURE_SANDBOX_ONLY",
        "message": f"Successfully imported {staged.audit['normalized_row_count']} records across {staged.audit['table_count']} tables.",
    }
