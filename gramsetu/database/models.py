"""SQLAlchemy 2.0 Declarative Relational Models for GramSetu AI.

Provides full PostgreSQL & PostGIS relational schema with:
- Strict foreign keys and cascading rules.
- Data integrity check constraints (mass conservation, non-negative monetary amounts).
- Unique constraints and performance indexes.
- WGS84 spatial attributes for farm gates, storage hubs, and transport waypoints.
"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from gramsetu.database.session import Base


def _utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    username = Column(String(128), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    password_salt = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    organization_id = Column(String(64), nullable=True, index=True)
    contact_phone = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    org_type = Column(String(64), default="FPO", nullable=False)
    district = Column(String(128), nullable=False)
    state = Column(String(128), default="West Bengal", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class Commodity(Base):
    __tablename__ = "commodities"

    id = Column(String(64), primary_key=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name_en = Column(String(128), nullable=False)
    name_bn = Column(String(128), nullable=False)
    name_hi = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)
    perishability_class = Column(String(32), default="medium", nullable=False)
    baseline_shelf_life_days = Column(Integer, default=30, nullable=False)
    hsn_code = Column(String(32), nullable=True)

    __table_args__ = (
        CheckConstraint("baseline_shelf_life_days > 0", name="chk_shelf_life_positive"),
    )


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False, index=True)
    phone = Column(String(32), nullable=False, index=True)
    village = Column(String(128), nullable=False)
    district = Column(String(128), nullable=False, index=True)
    state = Column(String(128), default="West Bengal", nullable=False)
    preferred_language = Column(String(16), default="bn-IN", nullable=False)
    landholding_hectares = Column(Float, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("landholding_hectares >= 0.0", name="chk_farmer_landholding_non_negative"),
        Index("idx_farmer_district_village", "district", "village"),
    )


class Buyer(Base):
    __tablename__ = "buyers"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False, index=True)
    organization = Column(String(256), nullable=False)
    phone = Column(String(32), nullable=False, index=True)
    email = Column(String(128), nullable=True)
    city = Column(String(128), nullable=False)
    district = Column(String(128), nullable=False, index=True)
    state = Column(String(128), default="West Bengal", nullable=False)
    business_type = Column(String(64), default="Wholesaler", nullable=False)
    verified_status = Column(Boolean, default=False, nullable=False, index=True)
    gstin = Column(String(64), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class ProduceListing(Base):
    __tablename__ = "produce_listings"

    id = Column(String(64), primary_key=True)
    farmer_id = Column(String(64), ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    commodity_code = Column(String(64), ForeignKey("commodities.code", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_grams = Column(BigInteger, nullable=False)
    asking_price_paise_per_kg = Column(BigInteger, nullable=False)
    harvest_date = Column(String(32), nullable=False)
    available_from = Column(String(32), nullable=False)
    quality_grade = Column(String(8), default="A", nullable=False)
    status = Column(String(32), default="active", nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity_grams > 0", name="chk_listing_qty_positive"),
        CheckConstraint("asking_price_paise_per_kg >= 0", name="chk_listing_price_non_negative"),
    )


class HarvestForecast(Base):
    __tablename__ = "harvest_forecasts"

    id = Column(String(64), primary_key=True)
    farmer_id = Column(String(64), ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    commodity_code = Column(String(64), nullable=False, index=True)
    expected_quantity_grams = Column(BigInteger, nullable=False)
    forecast_date = Column(String(32), nullable=False)
    confidence_pct = Column(Integer, default=85, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("expected_quantity_grams > 0", name="chk_forecast_qty_positive"),
        CheckConstraint("confidence_pct >= 0 AND confidence_pct <= 100", name="chk_forecast_confidence_pct"),
    )


class BuyerRequirement(Base):
    __tablename__ = "buyer_requirements"

    id = Column(String(64), primary_key=True)
    buyer_id = Column(String(64), ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False, index=True)
    commodity_code = Column(String(64), nullable=False, index=True)
    target_quantity_grams = Column(BigInteger, nullable=False)
    max_price_paise_per_kg = Column(BigInteger, nullable=False)
    delivery_district = Column(String(128), nullable=False, index=True)
    required_by = Column(String(32), nullable=False)
    status = Column(String(32), default="open", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("target_quantity_grams > 0", name="chk_req_qty_positive"),
        CheckConstraint("max_price_paise_per_kg >= 0", name="chk_req_price_non_negative"),
    )


class ProcurementOffer(Base):
    __tablename__ = "procurement_offers"

    id = Column(String(64), primary_key=True)
    buyer_id = Column(String(64), ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False, index=True)
    farmer_id = Column(String(64), ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    listing_id = Column(String(64), ForeignKey("produce_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    offered_price_paise_per_kg = Column(BigInteger, nullable=False)
    quantity_grams = Column(BigInteger, nullable=False)
    status = Column(String(32), default="pending", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity_grams > 0", name="chk_offer_qty_positive"),
        CheckConstraint("offered_price_paise_per_kg >= 0", name="chk_offer_price_non_negative"),
    )


class Transporter(Base):
    __tablename__ = "transporters"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    phone = Column(String(32), nullable=False, index=True)
    district = Column(String(128), nullable=False, index=True)
    coverage_districts = Column(Text, nullable=True)  # JSON-encoded array or CSV
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(String(64), primary_key=True)
    carrier_id = Column(String(64), ForeignKey("transporters.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_number = Column(String(64), unique=True, nullable=False, index=True)
    vehicle_type = Column(String(64), nullable=False)
    capacity_grams = Column(BigInteger, nullable=False)
    is_refrigerated = Column(Boolean, default=False, nullable=False)
    status = Column(String(32), default="available", nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("capacity_grams > 0", name="chk_vehicle_capacity_positive"),
    )


class TransportRequest(Base):
    __tablename__ = "transport_requests"

    id = Column(String(64), primary_key=True)
    farmer_id = Column(String(64), ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    commodity_code = Column(String(64), nullable=False, index=True)
    quantity_grams = Column(BigInteger, nullable=False)
    pickup_district = Column(String(128), nullable=False, index=True)
    drop_district = Column(String(128), nullable=False, index=True)
    pickup_date = Column(String(32), nullable=False)
    status = Column(String(32), default="pending", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity_grams > 0", name="chk_trans_req_qty_positive"),
    )


class StorageFacility(Base):
    __tablename__ = "storage_facilities"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    facility_type = Column(String(64), default="cold_storage", nullable=False)
    district = Column(String(128), nullable=False, index=True)
    total_capacity_grams = Column(BigInteger, nullable=False)
    utilized_capacity_grams = Column(BigInteger, default=0, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    sensor_verification_status = Column(String(64), default="PENDING_CALIBRATION", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("total_capacity_grams > 0", name="chk_facility_total_cap_positive"),
        CheckConstraint("utilized_capacity_grams >= 0", name="chk_facility_util_cap_non_negative"),
        CheckConstraint("utilized_capacity_grams <= total_capacity_grams", name="chk_facility_no_overfill"),
    )


class InventoryLot(Base):
    __tablename__ = "inventory_lots"

    id = Column(String(64), primary_key=True)
    farmer_id = Column(String(64), ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    commodity_code = Column(String(64), nullable=False, index=True)
    total_grams = Column(BigInteger, nullable=False)
    available_grams = Column(BigInteger, nullable=False)
    reserved_grams = Column(BigInteger, default=0, nullable=False)
    facility_id = Column(String(64), ForeignKey("storage_facilities.id", ondelete="RESTRICT"), nullable=True, index=True)
    quality_grade = Column(String(8), default="A", nullable=False)
    status = Column(String(32), default="stored", nullable=False, index=True)
    harvest_date = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("total_grams = available_grams + reserved_grams", name="chk_lot_mass_conservation"),
        CheckConstraint("total_grams > 0", name="chk_lot_total_positive"),
        CheckConstraint("available_grams >= 0", name="chk_lot_avail_non_negative"),
        CheckConstraint("reserved_grams >= 0", name="chk_lot_reserved_non_negative"),
    )


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id = Column(String(64), primary_key=True)
    lot_id = Column(String(64), ForeignKey("inventory_lots.id", ondelete="CASCADE"), nullable=False, index=True)
    from_location = Column(String(128), nullable=False)
    to_location = Column(String(128), nullable=False)
    quantity_grams = Column(BigInteger, nullable=False)
    actor = Column(String(128), nullable=False)
    verification_level = Column(String(32), default="AUTHENTIC", nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_utc_now, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("quantity_grams > 0", name="chk_movement_qty_positive"),
    )


class SettlementRecord(Base):
    __tablename__ = "settlement_records"

    id = Column(String(64), primary_key=True)
    transaction_id = Column(String(64), unique=True, nullable=False, index=True)
    farmer_id = Column(String(64), ForeignKey("farmers.id", ondelete="RESTRICT"), nullable=False, index=True)
    buyer_id = Column(String(64), ForeignKey("buyers.id", ondelete="RESTRICT"), nullable=False, index=True)
    commodity_code = Column(String(64), nullable=False)
    quantity_grams = Column(BigInteger, nullable=False)
    gross_amount_paise = Column(BigInteger, nullable=False)
    fpo_commission_paise = Column(BigInteger, default=0, nullable=False)
    logistics_fee_paise = Column(BigInteger, default=0, nullable=False)
    net_farmer_amount_paise = Column(BigInteger, nullable=False)
    settlement_status = Column(String(32), default="pending", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("gross_amount_paise >= 0", name="chk_settle_gross_non_negative"),
        CheckConstraint("net_farmer_amount_paise >= 0", name="chk_settle_net_non_negative"),
        CheckConstraint("gross_amount_paise - (fpo_commission_paise + logistics_fee_paise) = net_farmer_amount_paise", name="chk_settle_reconciliation"),
    )


class RiskIncident(Base):
    __tablename__ = "risk_incidents"

    id = Column(String(64), primary_key=True)
    risk_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), default="medium", nullable=False, index=True)
    district = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=False)
    status = Column(String(32), default="active", nullable=False, index=True)
    dedup_key = Column(String(128), unique=True, nullable=True, index=True)
    detected_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class RecoveryPlan(Base):
    __tablename__ = "recovery_plans"

    id = Column(String(64), primary_key=True)
    lot_id = Column(String(64), ForeignKey("inventory_lots.id", ondelete="CASCADE"), nullable=False, index=True)
    commodity_code = Column(String(64), nullable=False)
    spoilage_risk_pct = Column(Integer, nullable=False)
    status = Column(String(32), default="generated", nullable=False, index=True)
    best_buyer_name = Column(String(256), nullable=True)
    offered_price_paise_per_kg = Column(BigInteger, nullable=True)
    recovery_value_pct = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(128), nullable=False, index=True)
    payload_hash = Column(String(64), nullable=False)
    metadata_json = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utc_now, nullable=False, index=True)
