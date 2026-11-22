"""GramSetu v2.2 read-only dataset release validator and explicit unit adapter.

This does not integrate with a FastAPI repository or mutate application state.
It only validates/stages a GramSetu release ZIP for a later sandbox-only import.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from typing import Any
from zipfile import ZipFile


class DatasetContractError(ValueError):
    """Release was rejected due to a contract or integrity violation."""


@dataclass(frozen=True)
class ReleaseBundle:
    version: str
    tables: dict[str, list[dict[str, str]]]
    manifest: dict[str, Any]
    audit: dict[str, Any]

    def stage_for_sandbox(self, *, environment: str, explicit_opt_in: bool) -> dict[str, list[dict[str, str]]]:
        """Return a defensively copied staging view; do not touch live state."""
        if environment.strip().lower() not in {'sandbox', 'test', 'development'} or not explicit_opt_in:
            raise DatasetContractError('Synthetic fixtures cannot be seeded without explicit sandbox-only opt-in')
        return {name: [dict(row) for row in rows] for name, rows in self.tables.items()}


def _csv_rows(blob: bytes, expected_columns: list[str], name: str) -> list[dict[str, str]]:
    try:
        text = blob.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError as e:
        raise DatasetContractError(f'{name}: invalid UTF-8') from e
    rd = csv.DictReader(io.StringIO(text, newline=''))
    header = rd.fieldnames or []
    if len(header) != len(set(header)) or header != expected_columns:
        raise DatasetContractError(f'{name}: header mismatch; actual={header}, expected={expected_columns}')
    rows = list(rd)
    for i, row in enumerate(rows, start=2):
        if None in row or any(v is None for v in row.values()):
            raise DatasetContractError(f'{name}:{i}: malformed CSV row')
    return rows


def load_v22_release(zip_path: str | Path) -> ReleaseBundle:
    """Validate release hashes, schema, declared keys, references, and row counts.

    Does not assert external authenticity or operating safety.
    """
    tables: dict[str, list[dict[str, str]]] = {}
    blank_by_table: dict[str, int] = {}
    with ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise DatasetContractError('Duplicate entries in ZIP archive')
        manifest = json.loads(archive.read('manifest.json'))
        expected_hashes = json.loads(archive.read('file_hashes_sha256.json'))
        table_specs = manifest['tables']
        declared_names = set(table_specs)
        files = {Path(x).stem for x in names if x.startswith('csv/') and x.endswith('.csv')}
        if files != declared_names:
            raise DatasetContractError(f'Table inventory mismatch: missing={sorted(declared_names-files)}, unexpected={sorted(files-declared_names)}')
        if manifest.get('version') != '2.2.0':
            raise DatasetContractError('Unexpected manifest version; review migration before using')
        if set(expected_hashes) != {name + '.csv' for name in declared_names}:
            raise DatasetContractError('Hash index differs from table inventory')
        for name, spec in table_specs.items():
            blob = archive.read(f'csv/{name}.csv')
            expected_hash = expected_hashes[name + '.csv']
            if not re.fullmatch(r'[0-9a-f]{64}', expected_hash) or sha256(blob).hexdigest() != expected_hash:
                raise DatasetContractError(f'{name}: byte hash differs from release manifest')
            rows = _csv_rows(blob, spec['columns'], name)
            if len(rows) != spec['row_count']:
                raise DatasetContractError(f'{name}: count={len(rows)} expected={spec["row_count"]}')
            tables[name] = rows
            blank_by_table[name] = sum(v.strip() == '' for row in rows for v in row.values())

    # Uniqueness: real PK and declared natural/composite keys only.
    for name, spec in table_specs.items():
        rows = tables[name]
        pk = spec['primary_key']
        if pk not in spec['columns']:
            raise DatasetContractError(f'{name}: missing declared primary key column {pk}')
        ids = [row[pk] for row in rows]
        if any(not v.strip() for v in ids) or len(ids) != len(set(ids)):
            raise DatasetContractError(f'{name}: missing or duplicate primary key')
        for columns in spec.get('unique_combinations', []):
            keys = [tuple(row[c] for c in columns) for row in rows]
            if len(keys) != len(set(keys)):
                raise DatasetContractError(f'{name}: duplicate business key {columns}')

    # FK integrity, blanks allowed for legitimately optional FK references.
    for name, spec in table_specs.items():
        for col, target in spec.get('foreign_keys', {}).items():
            dest_table, dest_col = target.split('.', 1)
            if dest_table not in tables:
                raise DatasetContractError(f'{name}.{col}: unknown FK target {target}')
            targets = {row[dest_col] for row in tables[dest_table]}
            bad = [row[col] for row in tables[name] if row[col].strip() and row[col] not in targets]
            if bad:
                raise DatasetContractError(f'{name}.{col}: {len(bad)} broken references to {target}')

    # Key business invariants within the source release (not proof of physical authenticity).
    for row in tables['market_prices']:
        values = [Decimal(row[k]) for k in ('min_price_inr_quintal','modal_price_inr_quintal','max_price_inr_quintal')]
        if not (Decimal(0) <= values[0] <= values[1] <= values[2]):
            raise DatasetContractError(f'Price ordering incorrect for {row["price_observation_id"]}')
    for row in tables['inventory_lots']:
        phys = int(row['physical_grams']); reserved = int(row['reserved_grams'])
        held = int(row['held_grams'])
        if not (0 <= reserved <= phys and 0 <= held <= phys and reserved + held <= phys):
            raise DatasetContractError(f'Invalid lot quantity state: {row["lot_id"]}')
    for row in tables['commitments']:
        delivered=int(row['delivered_grams']); accepted=int(row['buyer_accepted_grams']); rejected=int(row['buyer_rejected_grams'])
        if delivered != accepted + rejected:
            raise DatasetContractError(f'Delivery acceptance mismatch: {row["commitment_id"]}')

    risk = {
        'source_backed_administrative_reference_points': len(tables.get('geography_reference_points', [])),
        'secondary_market_price_records': len(tables.get('market_prices', [])),
        'physical_site_coordinates_verified': sum(r.get('site_coordinate_verified') == 'True' for r in tables.get('locations', [])),
        'simulated_road_edges': sum(r.get('simulation_flag') == 'True' for r in tables.get('road_edges', [])),
        'market_arrival_rows': len(tables.get('market_arrivals', [])),
        'price_forecast_rows': len(tables.get('price_forecasts', [])),
        'simulated_operational_records_present': any(
            r.get('simulation_flag') == 'True'
            for name, rows in tables.items() if name not in {'geography_reference_points','market_prices'}
            for r in rows
        ),
    }
    audit = {
        'release_version': manifest['version'],
        'table_count': len(tables),
        'normalized_row_count': sum(map(len, tables.values())),
        'hashes_valid': True,
        'schemas_valid': True,
        'declared_keys_valid': True,
        'declared_foreign_keys_valid': True,
        'blank_cells_by_table': blank_by_table,
        'sandbox_fixture_readiness': 'STRUCTURAL_PASS_READ_ONLY',
        'live_production_data_readiness': 'BLOCKED_REAL_SOURCE_EVIDENCE_AND_OPERATIONAL_FEEDS',
        'backend_ingestion_integration': 'NOT_TESTED_BACKEND_REPOSITORY_NOT_PROVIDED',
        'ml_training_validation': 'NOT_TESTED_BACKEND_REPOSITORY_NOT_PROVIDED',
        'risk_facts': risk,
    }
    return ReleaseBundle(manifest['version'], tables, manifest, audit)


def _decimal(value: str | int | Decimal) -> Decimal:
    try:
        v = Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise DatasetContractError(f'Invalid numeric value: {value!r}') from e
    if not v.is_finite() or v < 0:
        raise DatasetContractError(f'Invalid nonnegative numeric value: {value!r}')
    return v


def exact_integer(value: Decimal, name: str) -> int:
    if value != value.to_integral_value():
        raise DatasetContractError(f'{name} is fractional in canonical integer units; manual review required')
    return int(value)


def mass_to_grams(value: str | int | Decimal, *, source_unit: str) -> int:
    multipliers = {'kg': Decimal(1000), 'g': Decimal(1)}
    if source_unit not in multipliers:
        raise DatasetContractError(f'Unsupported mass source_unit={source_unit}; explicit mapping required')
    return exact_integer(_decimal(value)*multipliers[source_unit], 'grams')


def distance_to_meters(value: str | int | Decimal, *, source_unit: str) -> int:
    multipliers = {'km': Decimal(1000), 'm': Decimal(1)}
    if source_unit not in multipliers:
        raise DatasetContractError(f'Unsupported distance source_unit={source_unit}; explicit mapping required')
    return exact_integer(_decimal(value)*multipliers[source_unit], 'meters')


def price_to_paise_per_kg(value: str | int | Decimal, *, source_unit: str) -> int:
    multipliers = {
        'INR/kg': Decimal(100),
        'INR/quintal': Decimal(1),
        'paise/kg': Decimal(1),
    }
    if source_unit not in multipliers:
        raise DatasetContractError(f'Unsupported price source_unit={source_unit}; explicit mapping required')
    return exact_integer(_decimal(value)*multipliers[source_unit], 'paise/kg')


def payable_paise(accepted_grams: int, price_paise_per_kg: int) -> Decimal:
    """Return exact payable paise before contractual rounding, not a rounded settlement."""
    if accepted_grams < 0 or price_paise_per_kg < 0:
        raise DatasetContractError('Negative payable inputs')
    return Decimal(accepted_grams) * Decimal(price_paise_per_kg) / Decimal(1000)


def main() -> None:
    parser=argparse.ArgumentParser(description='Audit GramSetu v2.2 synthetic release safely')
    parser.add_argument('dataset_zip', type=Path)
    parser.add_argument('--report', type=Path, default=Path('phase3_dataset_preflight.json'))
    args=parser.parse_args()
    bundle=load_v22_release(args.dataset_zip)
    args.report.write_text(json.dumps(bundle.audit, indent=2), encoding='utf-8')
    print(f'Validated {bundle.audit["table_count"]} tables, {bundle.audit["normalized_row_count"]} rows')
    print(f'Production readiness: {bundle.audit["live_production_data_readiness"]}')
    print(f'Report: {args.report}')


if __name__=='__main__':
    main()
