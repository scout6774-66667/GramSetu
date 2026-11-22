-- GramSetu AI Canonical Relational & Geospatial Schema
-- Migration: 001_initial_schema.sql
-- Target Database: PostgreSQL 14+ with PostGIS 3+

BEGIN;

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 2. Organizations (FPOs, Cooperatives, Regional Hubs)
CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    org_type VARCHAR(64) NOT NULL DEFAULT 'FPO',
    district VARCHAR(128) NOT NULL,
    state VARCHAR(128) NOT NULL DEFAULT 'West Bengal',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Users & System Authentication
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(128) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    password_salt VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL,
    name VARCHAR(256) NOT NULL,
    organization_id VARCHAR(64) REFERENCES organizations(id) ON DELETE SET NULL,
    contact_phone VARCHAR(32),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- 4. Commodities Master & Grading Standards
CREATE TABLE IF NOT EXISTS commodities (
    id VARCHAR(64) PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name_en VARCHAR(128) NOT NULL,
    name_bn VARCHAR(128) NOT NULL,
    name_hi VARCHAR(128) NOT NULL,
    category VARCHAR(64) NOT NULL,
    perishability_class VARCHAR(32) NOT NULL DEFAULT 'medium',
    baseline_shelf_life_days INTEGER NOT NULL DEFAULT 30 CHECK (baseline_shelf_life_days > 0),
    hsn_code VARCHAR(32)
);
CREATE INDEX IF NOT EXISTS idx_commodities_code ON commodities(code);

-- 5. Farmers Registry with PostGIS Spatial Coordinates
CREATE TABLE IF NOT EXISTS farmers (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    village VARCHAR(128) NOT NULL,
    district VARCHAR(128) NOT NULL,
    state VARCHAR(128) NOT NULL DEFAULT 'West Bengal',
    preferred_language VARCHAR(16) NOT NULL DEFAULT 'bn-IN',
    landholding_hectares DOUBLE PRECISION NOT NULL CHECK (landholding_hectares >= 0.0),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom geometry(Point, 4326),
    organization_id VARCHAR(64) REFERENCES organizations(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_farmers_district ON farmers(district);
CREATE INDEX IF NOT EXISTS idx_farmers_phone ON farmers(phone);
CREATE INDEX IF NOT EXISTS idx_farmers_geom ON farmers USING GIST (geom);

-- 6. Buyers Registry
CREATE TABLE IF NOT EXISTS buyers (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    organization VARCHAR(256) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    email VARCHAR(128),
    city VARCHAR(128) NOT NULL,
    district VARCHAR(128) NOT NULL,
    state VARCHAR(128) NOT NULL DEFAULT 'West Bengal',
    business_type VARCHAR(64) NOT NULL DEFAULT 'Wholesaler',
    verified_status BOOLEAN NOT NULL DEFAULT FALSE,
    gstin VARCHAR(64),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom geometry(Point, 4326),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_buyers_district ON buyers(district);
CREATE INDEX IF NOT EXISTS idx_buyers_verified ON buyers(verified_status);

-- 7. Produce Listings (Marketplace)
CREATE TABLE IF NOT EXISTS produce_listings (
    id VARCHAR(64) PRIMARY KEY,
    farmer_id VARCHAR(64) NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
    commodity_code VARCHAR(64) NOT NULL REFERENCES commodities(code) ON DELETE RESTRICT,
    quantity_grams BIGINT NOT NULL CHECK (quantity_grams > 0),
    asking_price_paise_per_kg BIGINT NOT NULL CHECK (asking_price_paise_per_kg >= 0),
    harvest_date VARCHAR(32) NOT NULL,
    available_from VARCHAR(32) NOT NULL,
    quality_grade VARCHAR(8) NOT NULL DEFAULT 'A',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_listings_farmer ON produce_listings(farmer_id);
CREATE INDEX IF NOT EXISTS idx_listings_status ON produce_listings(status);

-- 8. Harvest Forecasts (Supply Aggregation)
CREATE TABLE IF NOT EXISTS harvest_forecasts (
    id VARCHAR(64) PRIMARY KEY,
    farmer_id VARCHAR(64) NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
    commodity_code VARCHAR(64) NOT NULL,
    expected_quantity_grams BIGINT NOT NULL CHECK (expected_quantity_grams > 0),
    forecast_date VARCHAR(32) NOT NULL,
    confidence_pct INTEGER NOT NULL DEFAULT 85 CHECK (confidence_pct >= 0 AND confidence_pct <= 100),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 9. Buyer Requirements (Demand Sync)
CREATE TABLE IF NOT EXISTS buyer_requirements (
    id VARCHAR(64) PRIMARY KEY,
    buyer_id VARCHAR(64) NOT NULL REFERENCES buyers(id) ON DELETE CASCADE,
    commodity_code VARCHAR(64) NOT NULL,
    target_quantity_grams BIGINT NOT NULL CHECK (target_quantity_grams > 0),
    max_price_paise_per_kg BIGINT NOT NULL CHECK (max_price_paise_per_kg >= 0),
    delivery_district VARCHAR(128) NOT NULL,
    required_by VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_req_district ON buyer_requirements(delivery_district);

-- 10. Procurement Offers (CommitGuard)
CREATE TABLE IF NOT EXISTS procurement_offers (
    id VARCHAR(64) PRIMARY KEY,
    buyer_id VARCHAR(64) NOT NULL REFERENCES buyers(id) ON DELETE CASCADE,
    farmer_id VARCHAR(64) NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
    listing_id VARCHAR(64) NOT NULL REFERENCES produce_listings(id) ON DELETE CASCADE,
    offered_price_paise_per_kg BIGINT NOT NULL CHECK (offered_price_paise_per_kg >= 0),
    quantity_grams BIGINT NOT NULL CHECK (quantity_grams > 0),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. Logistics Carriers & Vehicles
CREATE TABLE IF NOT EXISTS transporters (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    district VARCHAR(128) NOT NULL,
    coverage_districts TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicles (
    id VARCHAR(64) PRIMARY KEY,
    carrier_id VARCHAR(64) NOT NULL REFERENCES transporters(id) ON DELETE CASCADE,
    registration_number VARCHAR(64) NOT NULL UNIQUE,
    vehicle_type VARCHAR(64) NOT NULL,
    capacity_grams BIGINT NOT NULL CHECK (capacity_grams > 0),
    is_refrigerated BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'available'
);

-- 12. Transport Requests
CREATE TABLE IF NOT EXISTS transport_requests (
    id VARCHAR(64) PRIMARY KEY,
    farmer_id VARCHAR(64) NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
    commodity_code VARCHAR(64) NOT NULL,
    quantity_grams BIGINT NOT NULL CHECK (quantity_grams > 0),
    pickup_district VARCHAR(128) NOT NULL,
    drop_district VARCHAR(128) NOT NULL,
    pickup_date VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 13. Storage Facilities with PostGIS Spatial Coordinates
CREATE TABLE IF NOT EXISTS storage_facilities (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    facility_type VARCHAR(64) NOT NULL DEFAULT 'cold_storage',
    district VARCHAR(128) NOT NULL,
    total_capacity_grams BIGINT NOT NULL CHECK (total_capacity_grams > 0),
    utilized_capacity_grams BIGINT NOT NULL DEFAULT 0 CHECK (utilized_capacity_grams >= 0),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom geometry(Point, 4326),
    sensor_verification_status VARCHAR(64) NOT NULL DEFAULT 'PENDING_CALIBRATION',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_facility_capacity_limit CHECK (utilized_capacity_grams <= total_capacity_grams)
);
CREATE INDEX IF NOT EXISTS idx_facilities_geom ON storage_facilities USING GIST (geom);

-- 14. Inventory Lots with Mass Conservation Invariant
CREATE TABLE IF NOT EXISTS inventory_lots (
    id VARCHAR(64) PRIMARY KEY,
    farmer_id VARCHAR(64) NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
    commodity_code VARCHAR(64) NOT NULL,
    total_grams BIGINT NOT NULL CHECK (total_grams > 0),
    available_grams BIGINT NOT NULL CHECK (available_grams >= 0),
    reserved_grams BIGINT NOT NULL DEFAULT 0 CHECK (reserved_grams >= 0),
    facility_id VARCHAR(64) REFERENCES storage_facilities(id) ON DELETE RESTRICT,
    quality_grade VARCHAR(8) NOT NULL DEFAULT 'A',
    status VARCHAR(32) NOT NULL DEFAULT 'stored',
    harvest_date VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_mass_conservation CHECK (total_grams = available_grams + reserved_grams)
);

-- 15. Inventory Movements (Immutable Traceability Event Log)
CREATE TABLE IF NOT EXISTS inventory_movements (
    id VARCHAR(64) PRIMARY KEY,
    lot_id VARCHAR(64) NOT NULL REFERENCES inventory_lots(id) ON DELETE CASCADE,
    from_location VARCHAR(128) NOT NULL,
    to_location VARCHAR(128) NOT NULL,
    quantity_grams BIGINT NOT NULL CHECK (quantity_grams > 0),
    actor VARCHAR(128) NOT NULL,
    verification_level VARCHAR(32) NOT NULL DEFAULT 'AUTHENTIC',
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_movements_lot ON inventory_movements(lot_id);

-- 16. Financial Settlement Records (SettleTrack)
CREATE TABLE IF NOT EXISTS settlement_records (
    id VARCHAR(64) PRIMARY KEY,
    transaction_id VARCHAR(64) NOT NULL UNIQUE,
    farmer_id VARCHAR(64) NOT NULL REFERENCES farmers(id) ON DELETE RESTRICT,
    buyer_id VARCHAR(64) NOT NULL REFERENCES buyers(id) ON DELETE RESTRICT,
    commodity_code VARCHAR(64) NOT NULL,
    quantity_grams BIGINT NOT NULL CHECK (quantity_grams > 0),
    gross_amount_paise BIGINT NOT NULL CHECK (gross_amount_paise >= 0),
    fpo_commission_paise BIGINT NOT NULL DEFAULT 0 CHECK (fpo_commission_paise >= 0),
    logistics_fee_paise BIGINT NOT NULL DEFAULT 0 CHECK (logistics_fee_paise >= 0),
    net_farmer_amount_paise BIGINT NOT NULL CHECK (net_farmer_amount_paise >= 0),
    settlement_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_financial_reconciliation CHECK (gross_amount_paise - (fpo_commission_paise + logistics_fee_paise) = net_farmer_amount_paise)
);
CREATE INDEX IF NOT EXISTS idx_settle_status ON settlement_records(settlement_status);

-- 17. Risk Incidents (RiskWatch)
CREATE TABLE IF NOT EXISTS risk_incidents (
    id VARCHAR(64) PRIMARY KEY,
    risk_type VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'medium',
    district VARCHAR(128) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    dedup_key VARCHAR(128) UNIQUE,
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 18. Recovery Plans (RecoveryOpt)
CREATE TABLE IF NOT EXISTS recovery_plans (
    id VARCHAR(64) PRIMARY KEY,
    lot_id VARCHAR(64) NOT NULL REFERENCES inventory_lots(id) ON DELETE CASCADE,
    commodity_code VARCHAR(64) NOT NULL,
    spoilage_risk_pct INTEGER NOT NULL CHECK (spoilage_risk_pct >= 0 AND spoilage_risk_pct <= 100),
    status VARCHAR(32) NOT NULL DEFAULT 'generated',
    best_buyer_name VARCHAR(256),
    offered_price_paise_per_kg BIGINT,
    recovery_value_pct INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 19. Immutable Audit Event Log
CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(64) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    metadata_json TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id);

COMMIT;
