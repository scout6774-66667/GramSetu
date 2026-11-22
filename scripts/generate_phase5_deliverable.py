"""Generate Phase 5 Missing Data Dependency Report CSV for GramSetu AI."""

import csv

def generate_phase5():
    issues = [
        {
            'issue_id': 'MDD-01',
            'component': 'A: Market Intelligence',
            'required_dataset': 'market_arrivals',
            'missing_field': 'arrival_quantity_quintals',
            'downstream_feature': 'DemandSync Market Glut & Arrival Pressure Warning',
            'root_cause': 'Declared in v2.2 data dictionary (10 columns) but 0 records populated in export',
            'current_source': 'NONE (Empty Table)',
            'recommended_source': 'AGMARKNET Daily Mandi Arrival Portal (https://agmarknet.gov.in/)',
            'severity': 'P1_HIGH',
            'production_impact': 'System cannot assess physical mandi supply pressure, risking misleading price assumptions during harvest gluts',
            'proposed_fix': 'Implement nightly AGMARKNET arrival scraper in INGESTION_PIPELINE/loaders.py and hydrate store.arrivals collection',
            'evidence': 'data_dictionary.csv defines market_arrivals; gramsetu_all_records.csv contains 0 records for table'
        },
        {
            'issue_id': 'MDD-02',
            'component': 'A: Market Intelligence',
            'required_dataset': 'price_forecasts',
            'missing_field': 'forecast_modal_price_paise_per_gram',
            'downstream_feature': 'Market Intelligence Predictive Pricing & Timing Advisory',
            'root_cause': 'No ML model developed, trained, or serialized; table declared in schema but omitted in runtime',
            'current_source': 'NONE (Empty Table)',
            'recommended_source': 'Prophet / LightGBM time-series model trained on historical Agmarknet 5-year modal price series',
            'severity': 'P1_HIGH',
            'production_impact': 'FPO managers have no forward-looking price visibility; system cannot optimize harvest dispatch timing',
            'proposed_fix': 'Develop time-series model pipeline in scripts/train_price_forecast.py; serialize artifact to models/price_v1.onnx',
            'evidence': 'data_dictionary.csv defines price_forecasts; gramsetu_all_records.csv has 0 records; no model files exist'
        },
        {
            'issue_id': 'MDD-03',
            'component': 'D: Logistics',
            'required_dataset': 'road_edges',
            'missing_field': 'weight_limit_kg, height_limit_meters, pavement_type',
            'downstream_feature': 'Logistics Route Feasibility Verification',
            'root_cause': 'v2.2 synthetic road network uses unverified segment connections without real-world structural road constraints',
            'current_source': 'Synthetic generated road edges',
            'recommended_source': 'OpenStreetMap (OSM) Overpass API / National Highways Authority of India (NHAI) Truck Restrictions',
            'severity': 'P1_HIGH',
            'production_impact': 'Heavy trucks (e.g. 16-ton multi-axle) may be routed over rural culverts or low bridges incapable of carrying vehicle gross weight',
            'proposed_fix': 'Enrich road_segments.csv with real OSM maxweight and maxheight tags, checked in LogisticsService.verify_route',
            'evidence': 'gramsetu/algorithms.py RoadEdge model has optional weight_limit_grams; 98% of edges in v2.2 leave it blank'
        },
        {
            'issue_id': 'MDD-04',
            'component': 'D: Logistics',
            'required_dataset': 'locations',
            'missing_field': 'verified_farm_gps_lat, verified_farm_gps_lon',
            'downstream_feature': 'Farm-Gate First-Mile Pickup Optimization',
            'root_cause': 'All rural farm locations in v2.2 use administrative block/district collectorate centroid coordinates as proxies',
            'current_source': 'LGD District / Block Headquarters Centroids',
            'recommended_source': 'Farmer Mobile App Geolocation Check-In / Survey of India Village Maps',
            'severity': 'P1_HIGH',
            'production_impact': 'First-mile transit duration and freight costs cannot be accurately calculated; drivers dispatched to collectorate instead of farm gate',
            'proposed_fix': 'Add farm_latitude and farm_longitude to farmer_registry.csv verified via mobile GPS onboarding',
            'evidence': 'geography_reference_points.csv in v2.2 lists headquarters centroids with 84 static points'
        },
        {
            'issue_id': 'MDD-05',
            'component': 'E: Storage and Quality',
            'required_dataset': 'storage_conditions',
            'missing_field': 'live_temp_c, live_humidity_rh_pct',
            'downstream_feature': 'RiskWatch Storage Spoilage Prevention',
            'root_cause': 'Storage conditions in v2.2 are simulated static records; no IoT telemetry streaming endpoint exists in backend',
            'current_source': 'Simulated static telemetry records',
            'recommended_source': 'MQTT / HTTP Webhook IoT Sensor Ingestion from Warehouse Data Loggers',
            'severity': 'P2_MEDIUM',
            'production_impact': 'System cannot detect cold storage refrigeration failures in real time, resulting in avoidable spoilage before shipment dispatch',
            'proposed_fix': 'Add POST /api/v1/telemetry/storage endpoint to ingest live temperature logs and trigger PERISHABLE_TEMP_STRESS incidents',
            'evidence': 'storage_conditions table has 220 static rows; no telemetry router exists in gramsetu/main.py'
        },
        {
            'issue_id': 'MDD-06',
            'component': 'F: Cost and Payment',
            'required_dataset': 'payment_transactions',
            'missing_field': 'bank_cleared_amount_paise, bank_utr_verified_timestamp',
            'downstream_feature': 'SettleTrack Automated Bank Reconciliation',
            'root_cause': 'System relies on buyer-reported text UTR numbers without automated two-way bank settlement verification',
            'current_source': 'Buyer self-reported string UTRs',
            'recommended_source': 'NPCI e-NACH / Corporate Banking Webhook API (ICICI / SBI / HDFC Open Banking Gateway)',
            'severity': 'P1_HIGH',
            'production_impact': 'Vulnerable to fraudulent payment claims: buyer marks invoices as settled with fictitious UTR without funds clearance',
            'proposed_fix': 'Integrate bank webhook adapter in gramsetu/adapters/evidence.py requiring signed cryptographic webhook from payment gateway',
            'evidence': 'settlement.py record_payment accepts arbitrary text UTR without cryptographic verification'
        },
        {
            'issue_id': 'MDD-07',
            'component': 'G: Risk and Recovery',
            'required_dataset': 'crop_weather_perishability_risk',
            'missing_field': 'forecast_rainfall_mm, high_heat_hours_count',
            'downstream_feature': 'Proactive Weather Risk Incident Scanning',
            'root_cause': 'Weather data is completely missing from v2.2; RiskWatch relies purely on calendar shelf-life subtraction',
            'current_source': 'NONE (Not defined in v2.2)',
            'recommended_source': 'India Meteorological Department (IMD) Agromet Advisory Bulletins & Open Weather API',
            'severity': 'P2_MEDIUM',
            'production_impact': 'System cannot anticipate rain-induced transit delays or unseasonal harvest moisture damage prior to physical inspection',
            'proposed_fix': 'Create data/verified/weather_alerts.csv and ingest into RiskWatch scanner',
            'evidence': 'No weather tables exist in data_dictionary.csv; gramsetu/services/risk.py has zero weather attributes'
        },
        {
            'issue_id': 'MDD-08',
            'component': 'B: Supply and Inventory',
            'required_dataset': 'quality_inspections',
            'missing_field': 'tested_moisture_pct, tested_foreign_matter_pct, test_equipment_id',
            'downstream_feature': 'Automated Lot Grade Assignment & Dispute Resolution',
            'root_cause': 'Backend receive_inventory_lot accepts user-provided grade string (A, B, C) directly without evaluating scientific metrics',
            'current_source': 'User-selected grade dropdown',
            'recommended_source': 'AGMARKNET Standard Quality Grading Norms / Electronic Weighbridge Moisture Meter export',
            'severity': 'P2_MEDIUM',
            'production_impact': 'Grade assignments are subjective and prone to operator error or dispute between farmer and FPO grader',
            'proposed_fix': 'Enforce automated grade resolution in inventory.py: if moisture > 12.0% -> automatically cap grade at B',
            'evidence': 'gramsetu/schemas.py LotReceiptCreate only has grade: str; quality_inspections metrics in v2.2 are ignored by API'
        },
        {
            'issue_id': 'MDD-09',
            'component': 'C: Buyer Demand',
            'required_dataset': 'buyers',
            'missing_field': 'gstn_active_status, e_invoice_eligible_flag',
            'downstream_feature': 'Statutory Tax Invoice Generation & GST Compliance',
            'root_cause': 'GSTIN is stored as an unvalidated string; system does not query GST Common Portal API',
            'current_source': 'Static string in buyer_registry.csv',
            'recommended_source': 'GSTN Public Search API via Karza / Masters India API Gateway',
            'severity': 'P2_MEDIUM',
            'production_impact': 'Risk of generating commercial tax invoices for cancelled or non-compliant GSTINs, triggering tax penalties',
            'proposed_fix': 'Implement GSTIN regex + checksum validator in BuyerRegistryLoader and add live verification worker',
            'evidence': 'buyer_registry.csv has gstin: 27AAACR1234F1Z5 without live validation'
        },
        {
            'issue_id': 'MDD-10',
            'component': 'H: Provenance and Audit',
            'required_dataset': 'actors',
            'missing_field': 'aadhaar_ekyc_token, mobile_otp_verified',
            'downstream_feature': 'Farmer Identity Non-Repudiation',
            'root_cause': 'Development environment relies on X-Dev-Actor mock headers without cryptographic user signing',
            'current_source': 'Static mock DEV_ACTORS dictionary in core.py',
            'recommended_source': 'UIDAI Aadhaar e-KYC / Digilocker API',
            'severity': 'P1_HIGH',
            'production_impact': 'In production, actors can repudiate lot commitments or harvest submissions; lacks legal non-repudiation',
            'proposed_fix': 'Mandate JWT Bearer tokens with verifiable e-KYC claims in production environment mode',
            'evidence': 'core.py defines DEV_ACTORS; DevIdentityAdapter accepts any string matching 12 static keys'
        }
    ]

    with open('05_MISSING_DATA_DEPENDENCY_REPORT.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(issues[0].keys()))
        writer.writeheader()
        writer.writerows(issues)
    print(f'Wrote 05_MISSING_DATA_DEPENDENCY_REPORT.csv with {len(issues)} rows')


if __name__ == '__main__':
    generate_phase5()
