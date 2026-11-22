# GramSetu AI — Real Data Source Verification & Provenance Report

**Verification Date**: 2026-11-22  
**Auditor**: Principal Data Engineer & Agricultural Data Quality Specialist  
**Standard**: Non-Fabrication Invariant — No artificial URLs, no synthetic proxy coordinates, no fabricated publishers.

---

## 1. Executive Summary & Verification Methodology
In accordance with non-negotiable data engineering principles, this report documents the investigation of authentic, authoritative Indian public sector and geospatial data sources for GramSetu AI. Every candidate source has been evaluated across 14 criteria, including accessibility, coverage, update frequency, licensing, schema compatibility, and operational integration feasibility.

Where live automated APIs require ministry registration or paid API tokens (e.g. Data.gov.in API keys or eNAM private gateways), this report explicitly notes the limitation, identifies public download endpoints, and establishes verifiable reference datasets.

---

## 2. Authoritative Source System Verification Matrix

### Component A: Agricultural Markets & Mandi Intelligence

#### 1. AGMARKNET (Agricultural Marketing Information Network)
- **Official Publisher**: Directorate of Marketing & Inspection (DMI), Ministry of Agriculture and Farmers Welfare, Government of India.
- **Exact Dataset Title**: Daily Wholesale Prices and Arrivals of Agricultural Commodities in Indian Mandis.
- **Official Landing Page**: `https://agmarknet.gov.in/`
- **Data Portal API Endpoint**: `https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070` (Open Government Data Platform India).
- **Data Format**: JSON (REST API) / CSV Bulk Exports / HTML Daily Bulletins.
- **Coverage Area**: Pan-India across 3,000+ regulated Agricultural Produce Market Committees (APMCs).
- **Coverage Period**: 2002 to Present (Daily real-time updates).
- **Last Updated Date**: Daily on market trading days (Mon–Sat).
- **Data License / Usage Restrictions**: National Data Sharing and Accessibility Policy (NDSAP) / Open Government Data (OGD) License India. Free for public, educational, and commercial application development.
- **Reliability & Known Limitations**:
  - Missing reporting on market holidays or strikes.
  - Prices reported in ₹/Quintal (100 kg); requires exact arithmetic conversion to integer paise/gram:
    $$\text{Price (paise/gram)} = \frac{\text{Price (Rs/Quintal)} \times 100\text{ paise/Rs}}{100,000\text{ grams/Quintal}} = \frac{\text{Price (Rs/Quintal)}}{1,000}$$
    Example: ₹3,500/quintal = 350 paise/gram.
  - Variety strings occasionally carry vernacular spelling variations (e.g. "JS-335" vs "JS 335" vs "Yellow").
- **Matching Backend Parameters**:
  - `market_id`, `market_name`, `state_code`, `district_name` $\rightarrow$ `mandi_master`
  - `commodity_id`, `variety`, `grade`, `price_date`, `min_price_paise_per_gram`, `max_price_paise_per_gram`, `modal_price_paise_per_gram` $\rightarrow$ `daily_mandi_prices`
  - `arrival_quantity_grams` $\rightarrow$ `daily_mandi_arrivals`
- **Missing Parameters in Source**: Integer gram representation (reported in Quintals/Tonnes); transport costs to consuming centers.
- **Join Keys**: `market_id`, `commodity_id`, `price_date`.
- **Ingestion Status**: **VERIFIED & INGESTION-READY**.

#### 2. eNAM (National Agriculture Market)
- **Official Publisher**: Small Farmers' Agribusiness Consortium (SFAC), Ministry of Agriculture & Farmers Welfare, GoI.
- **Exact Dataset Title**: Unified National Electronic Trading Portal Mandi Trade Statistics.
- **Official Landing Page**: `https://enam.gov.in/`
- **Data Format**: Web dashboard / Authenticated Mandi Trade Feeds.
- **Coverage Area**: 1,361 integrated APMC mandis across 23 States and 4 UTs.
- **Coverage Period**: 2016 to Present.
- **Data License**: Government of India Agricultural Portal.
- **Reliability & Limitations**: Real-time electronic bidding logs require authorized APMC trader credentials. Wholesale summary prices mirror AGMARKNET.
- **Ingestion Status**: **REFERENCE ONLY (Agmarknet used as primary machine-accessible feed)**.

---

### Component B: Geography, Administrative Boundaries & Road Logistics

#### 3. Local Government Directory (LGD) — Ministry of Panchayati Raj
- **Official Publisher**: Ministry of Panchayati Raj, Government of India.
- **Exact Dataset Title**: Directory of Local Government Bodies, Districts, Sub-Districts, and Census Villages.
- **Official Landing Page**: `https://lgd.gov.in/`
- **Data Format**: CSV, XML, XLS bulk downloads.
- **Coverage Area**: Pan-India (All 28 States, 8 UTs, 760+ Districts, 6,000+ Sub-districts, 600,000+ Revenue Villages).
- **Coverage Period**: Maintained continuously (Updated with every administrative boundary notification).
- **Data License**: Open Government Data (OGD) License India.
- **Reliability & Known Limitations**:
  - Authoritative source of truth for administrative hierarchy in India.
  - Primary keys are stable integer LGD codes.
  - Some newly demarcated villages may temporarily lack published boundary polygons.
- **Matching Backend Parameters**:
  - `location_id`, `lgd_code`, `location_name`, `location_type`, `district_name`, `state_code` $\rightarrow$ `administrative_locations`
- **Join Keys**: `lgd_code`.
- **Ingestion Status**: **VERIFIED & INGESTION-READY**.

#### 4. OpenStreetMap (OSM) / Geofabrik India Road Extracts
- **Official Publisher**: OpenStreetMap Foundation & Geofabrik GmbH.
- **Exact Dataset Title**: India Road Network Extract (Highways, Bridges, Culverts, Surface Types, Maxweight).
- **Official Landing Page**: `https://www.openstreetmap.org/` / `https://download.geofabrik.de/asia/india.html`
- **Data Format**: `.osm.pbf`, GeoJSON, ESRI Shapefile.
- **Coverage Area**: Western India corridor (Maharashtra & Madhya Pradesh agricultural belts).
- **Coverage Period**: Continuously crowdsourced and verified by spatial surveys.
- **Data License**: Open Database License (ODbL) 1.0. Allows free commercial and non-commercial attribution usage.
- **Reliability & Known Limitations**:
  - High accuracy for National Highways (NH), State Highways (SH), and Major District Roads (MDR).
  - Minor rural unpaved tracks (`track`, `path`) require topological validation to ensure network connectivity.
  - Bridge weight limits (`maxweight=*`) are tagged on major bridges; where missing, statutory state PWD standard limits apply.
- **Matching Backend Parameters**:
  - `node_id`, `name`, `lat`, `lon` $\rightarrow$ `road_nodes`
  - `edge_id`, `source_node`, `target_node`, `distance_meters`, `speed_kmh`, `road_class`, `weight_limit_grams`, `is_open` $\rightarrow$ `road_segments`
- **Join Keys**: `node_id`, `edge_id`.
- **Ingestion Status**: **VERIFIED & INGESTION-READY**.

---

### Component C: Weather & Agrometeorology

#### 5. India Meteorological Department (IMD) — Ministry of Earth Sciences
- **Official Publisher**: India Meteorological Department (IMD), GoI.
- **Exact Dataset Title**: Daily District-Level Weather Observations & Agromet Advisory Bulletins.
- **Official Landing Page**: `https://mausam.imd.gov.in/`
- **Open Data Endpoint**: `https://data.gov.in/` (IMD daily station precipitation datasets).
- **Data Format**: CSV, GeoTIFF, NetCDF, RSS Weather Alerts.
- **Coverage Area**: Pan-India (All 700+ agrometeorological districts).
- **Coverage Period**: 1901 to Present.
- **Data License**: OGD License India / Free public weather dissemination.
- **Reliability & Known Limitations**:
  - District-level aggregation is highly accurate for rainfall, max/min temperature, and relative humidity.
  - Micro-climatic village variations require interpolation between nearest automated weather stations (AWS).
- **Matching Backend Parameters**:
  - `observation_date`, `rainfall_mm`, `temperature_max_c`, `temperature_min_c`, `humidity_pct` $\rightarrow$ `weather_observations`
  - `alert_id`, `severity`, `hazard_type`, `valid_until` $\rightarrow$ `weather_forecasts_alerts`
- **Join Keys**: `district_name`, `date`.
- **Ingestion Status**: **VERIFIED & INGESTION-READY**.

---

### Component D: Warehousing, Logistics & Corporate Buyers

#### 6. Warehousing Development and Regulatory Authority (WDRA)
- **Official Publisher**: WDRA, Department of Food & Public Distribution, Ministry of Consumer Affairs, Food & Public Distribution, GoI.
- **Exact Dataset Title**: Directory of Registered Agricultural Warehouses & Electronic Negotiable Warehouse Receipts (e-NWR) Repositories.
- **Official Landing Page**: `https://wdra.gov.in/`
- **Data Format**: Public Registry Directory (CSV / PDF / HTML).
- **Coverage Area**: 5,000+ registered commercial, CWC, SWC, and primary cooperative godowns across India.
- **Data License**: Public Regulatory Registry.
- **Matching Backend Parameters**:
  - `facility_id`, `facility_name`, `facility_type`, `total_capacity_grams`, `temperature_controlled`, `latitude`, `longitude` $\rightarrow$ `storage_facilities`
- **Ingestion Status**: **VERIFIED & INGESTION-READY**.

#### 7. Ministry of Corporate Affairs (MCA) / GSTN Portal
- **Official Publisher**: Ministry of Corporate Affairs (MCA21) & Goods and Services Tax Network (GSTN).
- **Exact Dataset Title**: Registered Corporate Entities & Active GSTIN Taxpayers.
- **Official Landing Page**: `https://www.mca.gov.in/` / `https://www.gst.gov.in/`
- **Data Format**: Public Verification Services (REST / JSON).
- **Coverage Area**: All legally incorporated corporate buyers and Farmer Producer Companies (FPCs).
- **Matching Backend Parameters**:
  - `buyer_id`, `business_name`, `gstin`, `buyer_category` $\rightarrow$ `buyer_registry`
  - `fpo_id`, `fpo_name`, `cin_registration_no` $\rightarrow$ `fpo_master`
- **Ingestion Status**: **VERIFIED & INGESTION-READY**.
