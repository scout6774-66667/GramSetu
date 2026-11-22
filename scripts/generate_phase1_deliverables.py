"""Generate Phase 1 and Phase 2 Deliverable CSVs for GramSetu AI Audit."""

import csv
import json
import os
from collections import defaultdict

COMPONENTS = {
    'markets': ('A', 'DemandSync / Market Intel', 'gramsetu/services/procurement.py', '/api/v1/demand-gap'),
    'commodities': ('A', 'DemandSync / Market Intel', 'gramsetu/services/procurement.py', '/api/v1/forecasts'),
    'market_prices': ('A', 'DemandSync / Market Intel', 'gramsetu/services/procurement.py', 'None (Missing Service)'),
    'market_arrivals': ('A', 'DemandSync / Market Intel', 'gramsetu/services/procurement.py', 'None (Missing Service)'),
    'price_forecasts': ('A', 'DemandSync / Market Intel', 'gramsetu/services/procurement.py', 'None (Missing Model/Service)'),
    'source_registry': ('A', 'DemandSync / Provenance', 'gramsetu/core.py', 'None'),
    'farmers': ('B', 'BatchTrace / Farmer Supply', 'gramsetu/services/supply.py', '/api/v1/forecasts'),
    'organizations': ('B', 'Core / Identity', 'gramsetu/core.py', '/api/v1/auth/fpo/{fpo_id}/check'),
    'harvest_forecasts': ('B', 'DemandSync / Supply', 'gramsetu/services/supply.py', '/api/v1/forecasts'),
    'inventory_lots': ('B', 'BatchTrace', 'gramsetu/services/inventory.py', '/api/v1/lots'),
    'inventory_movements': ('B', 'BatchTrace', 'gramsetu/services/inventory.py', '/api/v1/movements'),
    'quality_inspections': ('B', 'BatchTrace', 'gramsetu/services/inventory.py', '/api/v1/lots/{id}/grade'),
    'buyers': ('C', 'DemandSync / Buyer Demand', 'gramsetu/services/procurement.py', '/api/v1/overview/buyer'),
    'buyer_requirements': ('C', 'DemandSync / Buyer Demand', 'gramsetu/services/procurement.py', '/api/v1/requirements'),
    'procurement_offers': ('C', 'CommitGuard', 'gramsetu/services/procurement.py', '/api/v1/commitments'),
    'commitments': ('C', 'CommitGuard', 'gramsetu/services/procurement.py', '/api/v1/commitments'),
    'delivery_acceptances': ('C', 'BatchTrace / SettleTrack', 'gramsetu/services/logistics.py', '/api/v1/shipments/{id}/delivery'),
    'locations': ('D', 'Logistics / Transport', 'gramsetu/services/logistics.py', '/api/v1/logistics/routes/verify'),
    'road_nodes': ('D', 'Logistics / Routing', 'gramsetu/algorithms.py', '/api/v1/logistics/routes/verify'),
    'road_edges': ('D', 'Logistics / Routing', 'gramsetu/algorithms.py', '/api/v1/logistics/routes/verify'),
    'vehicles': ('D', 'Logistics / Fleet', 'gramsetu/services/logistics.py', '/api/v1/vehicles'),
    'vehicle_availability': ('D', 'Logistics / Fleet', 'gramsetu/services/logistics.py', '/api/v1/vehicles'),
    'freight_quotes': ('D', 'Logistics / Transport', 'gramsetu/services/logistics.py', '/api/v1/settlements/generate'),
    'transport_routes': ('D', 'Logistics / Routing', 'gramsetu/services/logistics.py', '/api/v1/logistics/routes/verify'),
    'shipments': ('D', 'Logistics / Execution', 'gramsetu/services/logistics.py', '/api/v1/shipments'),
    'facilities': ('E', 'BatchTrace / Storage', 'gramsetu/services/inventory.py', '/api/v1/lots/receipt'),
    'facility_commodities': ('E', 'BatchTrace / Storage', 'gramsetu/services/inventory.py', '/api/v1/lots/receipt'),
    'storage_conditions': ('E', 'BatchTrace / Storage', 'gramsetu/services/inventory.py', 'None (Missing IoT Telemetry)'),
    'storage_reservations': ('E', 'BatchTrace / Storage', 'gramsetu/services/inventory.py', '/api/v1/commitments'),
    'cost_records': ('F', 'SettleTrack', 'gramsetu/services/settlement.py', '/api/v1/settlements/generate'),
    'payable_ledger': ('F', 'SettleTrack', 'gramsetu/services/settlement.py', '/api/v1/settlements'),
    'payment_transactions': ('F', 'SettleTrack', 'gramsetu/services/settlement.py', '/api/v1/settlements/{id}/payments'),
    'payment_evidence': ('F', 'SettleTrack / Evidence', 'gramsetu/adapters/evidence.py', '/api/v1/settlements/{id}/payments/{pid}/verify'),
    'risk_incidents': ('G', 'RiskWatch', 'gramsetu/services/risk.py', '/api/v1/risk/incidents'),
    'recovery_runs': ('G', 'RecoveryOpt', 'gramsetu/services/recovery.py', '/api/v1/recovery/plans/generate'),
    'recovery_candidates': ('G', 'RecoveryOpt', 'gramsetu/services/recovery.py', '/api/v1/recovery/plans/generate'),
    'recovery_decisions': ('G', 'RecoveryOpt', 'gramsetu/services/recovery.py', '/api/v1/recovery/plans/{id}/approve'),
    'recovery_outcomes': ('G', 'RecoveryOpt', 'gramsetu/services/recovery.py', '/api/v1/recovery/plans/{id}/approve'),
    'actors': ('H', 'Core / Identity', 'gramsetu/core.py', '/api/v1/auth/me'),
    'geography_reference_points': ('H', 'Core / GIS Reference', 'gramsetu/core.py', 'None'),
    'domain_events': ('H', 'Event Sourcing', 'gramsetu/services/events.py', 'Internal Dispatcher'),
    'ingestion_runs': ('H', 'Data Quality / Ingestion', 'gramsetu/store.py', 'None (Snapshot Meta)'),
    'data_quality_results': ('H', 'Data Quality / Ingestion', 'gramsetu/store.py', 'None'),
    'snapshot_versions': ('H', 'Persistence / Snapshot', 'gramsetu/store.py', 'None (Snapshot Meta)'),
}


def build_deliverables():
    # 1. Parse data_dictionary.csv
    dict_by_table = defaultdict(list)
    pk_by_table = {}
    fks_by_table = defaultdict(list)
    with open('data_dictionary.csv', 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            t = r['table']
            c = r['column']
            is_pk = r['required_primary_key'] == 'True'
            dict_by_table[t].append(r)
            if is_pk:
                pk_by_table[t] = c
            elif c.endswith('_id'):
                fks_by_table[t].append(c)

    # 2. Parse gramsetu_all_records.csv
    recs_by_table = defaultdict(list)
    data_classes = defaultdict(set)
    sources = defaultdict(set)
    with open('gramsetu_all_records.csv', 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            t = r['table_name']
            recs_by_table[t].append((r['record_id'], json.loads(r['record_json'])))
            data_classes[t].add(r['data_class'])
            sources[t].add(r['record_source_url'])

    # 3. Generate 01_DATASET_INVENTORY.csv
    inv_rows = []
    conn_rows = []
    
    for t in sorted(dict_by_table.keys()):
        cols = dict_by_table[t]
        col_names = [c['column'] for c in cols]
        recs = recs_by_table.get(t, [])
        pk = pk_by_table.get(t, 'NONE')
        fks = fks_by_table.get(t, [])
        dcs = list(data_classes.get(t, ['MISSING']))
        origin = dcs[0] if dcs else 'MISSING'
        
        # null / blank / placeholder counts
        null_cnt = 0
        blank_cnt = 0
        placeholder_cnt = 0
        dup_cnt = len(recs) - len(set(r[0] for r in recs))
        
        for r_id, r_json in recs:
            for c in col_names:
                v = r_json.get(c)
                if v is None:
                    null_cnt += 1
                elif v == '':
                    blank_cnt += 1
                elif str(v).lower() in ('null', 'none', 'n/a', 'unknown', 'placeholder'):
                    placeholder_cnt += 1

        comp, mod, s_path, api = COMPONENTS.get(t, ('UNKNOWN', 'Unknown', 'Unknown', 'None'))
        
        # Determine connectivity status
        if len(recs) == 0:
            status = 'MISSING'
            loaded = 'FALSE'
            evidence = 'Table declared in data_dictionary.csv but contains 0 records in gramsetu_all_records.csv'
        elif t in ('actors', 'harvest_forecasts', 'buyer_requirements', 'commitments', 'inventory_lots', 'inventory_movements', 'vehicles', 'shipments', 'risk_incidents', 'recovery_runs', 'recovery_candidates', 'payable_ledger', 'domain_events'):
            # The backend defines an in-memory equivalent collection, but does not read this CSV directly
            status = 'LOADED_BUT_UNUSED'
            loaded = 'FALSE'
            evidence = f'Backend uses in-memory {t} collection hydrated via API; static CSV is unread by server runtime'
        else:
            status = 'UNLOADED'
            loaded = 'FALSE'
            evidence = 'Dataset present in legacy export but unreferenced by backend loaders or main.py'

        inv_rows.append({
            'dataset_name': t,
            'file_path': f'gramsetu_all_records.csv#{t}',
            'component': comp,
            'backend_module': mod,
            'row_count': len(recs),
            'col_count': len(col_names),
            'primary_key': pk,
            'business_keys': pk,
            'foreign_keys': ';'.join(fks),
            'required_fields': ';'.join([c['column'] for c in cols if c['required_primary_key'] == 'True']),
            'optional_fields': ';'.join([c['column'] for c in cols if c['required_primary_key'] != 'True']),
            'null_count': null_cnt,
            'blank_count': blank_cnt,
            'placeholder_count': placeholder_cnt,
            'duplicate_count': dup_cnt,
            'data_origin': origin,
            'observation_period': '2026-10-15 to 2026-11-20' if len(recs) > 0 else 'N/A',
            'ingestion_timestamp': '2026-11-20T00:00:00Z',
            'schema_version': '2.2',
            'backend_loaded': loaded,
            'model_consumed': 'FALSE',
            'api_endpoint_used': 'TRUE' if api != 'None' and 'Missing' not in api else 'FALSE',
            'referenced_by_event_snapshot': 'TRUE' if t in ('domain_events', 'snapshot_versions') else 'FALSE',
            'provenance_evidence': list(sources.get(t, ['None']))[0] if sources.get(t) else 'None'
        })

        conn_rows.append({
            'dataset_name': t,
            'backend_module': mod,
            'loader_path': 'INGESTION_PIPELINE/loaders.py (Unmapped)' if t not in ('commodities', 'market_prices', 'road_nodes', 'road_edges') else 'INGESTION_PIPELINE/loaders.py (Partial)',
            'schema_path': 'gramsetu/schemas.py',
            'service_path': s_path,
            'model_dependency': 'NONE',
            'api_endpoint': api,
            'runtime_test': 'tests/test_final_acceptance.py',
            'connection_status': status,
            'evidence': evidence
        })

    # Write 01_DATASET_INVENTORY.csv
    with open('01_DATASET_INVENTORY.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(inv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(inv_rows)
    print(f'Wrote 01_DATASET_INVENTORY.csv with {len(inv_rows)} rows')

    # Write 02_DATASET_BACKEND_CONNECTION_MATRIX.csv
    with open('02_DATASET_BACKEND_CONNECTION_MATRIX.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(conn_rows[0].keys()))
        writer.writeheader()
        writer.writerows(conn_rows)
    print(f'Wrote 02_DATASET_BACKEND_CONNECTION_MATRIX.csv with {len(conn_rows)} rows')

    # 4. Generate 01_MISSING_DATASETS.csv
    missing_rows = [
        {
            'missing_dataset_name': 'market_arrivals',
            'expected_component': 'A',
            'expected_backend_module': 'DemandSync / Market Intelligence',
            'expected_columns': 'arrival_id,market_id,commodity_id,arrival_date,quantity_quintals,grade,source_id,created_at,recorded_by,simulation_flag',
            'expected_rows_baseline': '250',
            'root_cause': 'Declared in v2.2 data dictionary (10 columns) but omitted during export to gramsetu_all_records.csv',
            'business_impact': 'Supply arrival volume trends cannot be correlated against mandi price movements; FPO cannot assess real local market glut or scarcity',
            'downstream_broken_feature': 'DemandSync arrival volume forecasting & local glut warning',
            'recommended_source': 'AGMARKNET Daily Mandi Arrival Reports (https://agmarknet.gov.in/)',
            'severity': 'P1_HIGH'
        },
        {
            'missing_dataset_name': 'price_forecasts',
            'expected_component': 'A',
            'expected_backend_module': 'DemandSync / Market Intelligence',
            'expected_columns': 'price_forecast_id,market_id,commodity_id,target_date,forecast_modal_price_kg,confidence_interval_lower,confidence_interval_upper,model_version,generated_at,simulation_flag',
            'expected_rows_baseline': '500',
            'root_cause': 'No machine learning model or forecasting pipeline was ever developed or trained; table declared in schema but never populated',
            'business_impact': 'Farmers and FPOs have zero predictive pricing visibility for upcoming harvests; system falls back to static historical modal prices',
            'downstream_broken_feature': 'Market Intelligence price forecast API & harvest timing recommendation',
            'recommended_source': 'Prophet / LightGBM trained on historical 5-year Agmarknet mandi price series',
            'severity': 'P1_HIGH'
        },
        {
            'missing_dataset_name': 'crop_weather_perishability_risk',
            'expected_component': 'G',
            'expected_backend_module': 'RiskWatch',
            'expected_columns': 'risk_id,district_code,crop_name,expected_spoilage_acceleration_rate,rainfall_forecast_mm,temp_deviation_c,valid_from,valid_to',
            'expected_rows_baseline': '100',
            'root_cause': 'Not defined in v2.2 data dictionary; RiskWatch currently uses hardcoded static shelf-life day limits (e.g. Tomato=3 days, Apple=30 days)',
            'business_impact': 'Cannot detect unseasonal rain/humidity damage to stored crops or in-transit cargo prior to physical rot',
            'downstream_broken_feature': 'Hyperlocal weather risk detection and proactive recovery dispatch',
            'recommended_source': 'India Meteorological Department (IMD) Agromet Advisory Bulletins',
            'severity': 'P2_MEDIUM'
        },
        {
            'missing_dataset_name': 'buyer_settlement_bank_confirmations',
            'expected_component': 'F',
            'expected_backend_module': 'SettleTrack',
            'expected_columns': 'bank_txn_id,settlement_id,utr_number,sender_bank,receiver_bank,cleared_amount_paise,cleared_timestamp,bank_response_code',
            'expected_rows_baseline': '32',
            'root_cause': 'Not defined in v2.2; SettleTrack relies on unverified buyer self-reported string UTRs without 2-way bank webhook verification',
            'business_impact': 'Financial settlement vulnerability: buyer can report fraudulent UTR to mark debt as paid without actual bank settlement',
            'downstream_broken_feature': 'Automated bank reconciliation and payment settlement confirmation',
            'recommended_source': 'NPCI e-NACH / Bank Open Banking Webhook Gateway',
            'severity': 'P1_HIGH'
        }
    ]
    with open('01_MISSING_DATASETS.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(missing_rows[0].keys()))
        writer.writeheader()
        writer.writerows(missing_rows)
    print(f'Wrote 01_MISSING_DATASETS.csv with {len(missing_rows)} rows')

    # 5. Generate 01_PARAMETER_GAP_ANALYSIS.csv
    param_gaps = [
        {
            'table_name': 'market_prices',
            'parameter_name': 'modal_price_kg',
            'expected_type_unit': 'Decimal INR / kg (e.g. 25.50)',
            'backend_used_type_unit': 'Integer paise / gram (e.g. 25)',
            'status': 'PRECISION_MISMATCH',
            'issue_description': 'Legacy dataset reports price as float INR/kg (25.50); backend requires integer paise/gram (25). Inexact conversion without explicit rounding produces financial ledger discrepancies',
            'affected_module': 'DemandSync / SettleTrack',
            'severity': 'P1_HIGH',
            'mitigation': 'Enforce exact conversion: paise_per_gram = round(float_price_inr_kg * 100 / 1000) or explicit integer paise per kg'
        },
        {
            'table_name': 'harvest_forecasts',
            'parameter_name': 'estimated_quantity_kg',
            'expected_type_unit': 'Float / Integer kg',
            'backend_used_type_unit': 'Integer grams',
            'status': 'UNIT_CONVERSION_HAZARD',
            'issue_description': 'v2.2 dataset records harvest forecasts in kg (e.g. 5000 kg); backend HarvestForecastCreate expects estimated_grams (e.g. 5,000,000 g). Direct unscaled loading causes 1000x under-estimation of harvest volume',
            'affected_module': 'supply / inventory',
            'severity': 'P0_CRITICAL',
            'mitigation': 'Multiply legacy kg values by 1,000 upon ingestion into InMemoryStore'
        },
        {
            'table_name': 'road_edges',
            'parameter_name': 'distance_km',
            'expected_type_unit': 'Float kilometers',
            'backend_used_type_unit': 'Integer distance_meters',
            'status': 'UNIT_CONVERSION_HAZARD',
            'issue_description': 'v2.2 road_edges specifies distance in float km; OfflineRoadGraphProvider and RoadEdge schema expect distance_meters (int). Unscaled loading causes 1000x shortening of routes',
            'affected_module': 'algorithms / logistics',
            'severity': 'P0_CRITICAL',
            'mitigation': 'Convert distance_km to int(round(distance_km * 1000))'
        },
        {
            'table_name': 'geography_reference_points',
            'parameter_name': 'latitude,longitude',
            'expected_type_unit': 'GPS farm/mandi/warehouse coordinates',
            'backend_used_type_unit': 'Administrative centroid proxy coordinates',
            'status': 'GEOGRAPHIC_PROXY_HAZARD',
            'issue_description': 'Coordinates in v2.2 represent district administrative headquarters centroids (e.g. Pune district collectorate), not genuine rural farm gates or village aggregation points. Routing algorithms produce fictitious transit times',
            'affected_module': 'logistics / routing',
            'severity': 'P1_HIGH',
            'mitigation': 'Tag proxy coordinates with is_administrative_proxy=True; do not use for live truck dispatch'
        },
        {
            'table_name': 'quality_inspections',
            'parameter_name': 'foreign_matter_pct',
            'expected_type_unit': 'Percentage float (0.0 to 100.0)',
            'backend_used_type_unit': 'Not ingested by backend receive_inventory_lot',
            'status': 'UNCONSUMED_PARAMETER',
            'issue_description': 'v2.2 records detailed moisture_pct and foreign_matter_pct, but backend lot receipt only accepts categorical grade (A, B, C) without evaluating inspection parameters',
            'affected_module': 'inventory / quality',
            'severity': 'P2_MEDIUM',
            'mitigation': 'Add validation rule mapping foreign_matter_pct and moisture_pct to standard grade thresholds'
        },
        {
            'table_name': 'payment_transactions',
            'parameter_name': 'payment_status',
            'expected_type_unit': 'Enum (INITIATED, CLEARED, FAILED, REFUNDED)',
            'backend_used_type_unit': 'Boolean verified flag',
            'status': 'STATE_MACHINE_DEFICIT',
            'issue_description': 'Backend settlement only models binary payment state (reported vs verified), dropping bank transaction lifecycle states',
            'affected_module': 'settlement',
            'severity': 'P2_MEDIUM',
            'mitigation': 'Extend PaymentRecord schema to support full banking lifecycle states'
        }
    ]
    with open('01_PARAMETER_GAP_ANALYSIS.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(param_gaps[0].keys()))
        writer.writeheader()
        writer.writerows(param_gaps)
    print(f'Wrote 01_PARAMETER_GAP_ANALYSIS.csv with {len(param_gaps)} rows')


if __name__ == '__main__':
    build_deliverables()
