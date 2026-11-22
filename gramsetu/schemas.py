from __future__ import annotations

from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from gramsetu.core.config import Role


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HealthStatus(BaseSchema):
    status: str = "ok"
    version: str
    environment: str
    timestamp: datetime
    stats: Dict[str, int] = Field(default_factory=dict)


class ErrorResponse(BaseSchema):
    error: str
    message: str
    status_code: int
    details: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None


class PaginationParams(BaseSchema):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseSchema):
    items: List[Any]
    total: int
    limit: int
    offset: int


class DriverActionPayload(BaseSchema):
    assigned_driver_id: str
    action: str


# --- DemandSync Schemas (F2) ---
class HarvestForecastCreate(BaseSchema):
    crop: str
    variety: Optional[str] = None
    grade: str
    estimated_grams: int = Field(gt=0, description="Estimated harvest quantity in integer grams")
    harvest_start_date: datetime
    harvest_end_date: datetime
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)
    idempotency_key: Optional[str] = None


class HarvestForecastResponse(BaseSchema):
    forecast_id: str
    farmer_id: str
    fpo_id: str
    crop: str
    variety: Optional[str] = None
    grade: str
    estimated_grams: int
    harvest_start_date: datetime
    harvest_end_date: datetime
    confidence_score: float
    created_at: datetime
    idempotency_key: Optional[str] = None
    status: str = "ACTIVE"


class BuyerRequirementCreate(BaseSchema):
    crop: str
    variety: Optional[str] = None
    grade: str
    needed_grams: int = Field(gt=0, description="Required quantity in integer grams")
    delivery_window_start: datetime
    delivery_window_end: datetime
    max_price_paise_per_gram: int = Field(gt=0, description="Maximum price in integer paise per gram")
    idempotency_key: Optional[str] = None


class BuyerRequirementResponse(BaseSchema):
    requirement_id: str
    buyer_id: str
    crop: str
    variety: Optional[str] = None
    grade: str
    needed_grams: int
    allocated_grams: int = 0
    delivery_window_start: datetime
    delivery_window_end: datetime
    max_price_paise_per_gram: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    status: str = "OPEN"


class DemandGapAnalysis(BaseSchema):
    fpo_id: str
    crop: str
    grade: str
    total_demand_grams: int
    total_forecast_grams: int
    net_gap_grams: int  # demand - forecast (>0 deficit, <0 surplus)
    coverage_ratio: float
    as_of: datetime
    planning_disclaimer: str = "PLANNING ONLY: Unverified forecasts do NOT represent physical stock and buyer requirements are not guarantees."


# --- BatchTrace Schemas (F3) ---
class LotReceiptCreate(BaseSchema):
    farmer_id: str
    fpo_id: str
    crop: str
    variety: Optional[str] = None
    grade: str
    quantity_grams: int = Field(gt=0, description="Verified physical quantity in integer grams")
    storage_location: str


class InventoryLotResponse(BaseSchema):
    lot_id: str
    fpo_id: str
    farmer_id: str
    crop: str
    variety: Optional[str] = None
    grade: str
    quantity_grams: int
    reserved_grams: int = 0
    available_grams: int = 0
    storage_location: str
    custody: str = "FPO_WAREHOUSE"
    version: int = 1
    created_at: datetime
    updated_at: datetime
    parent_lot_ids: List[str] = Field(default_factory=list)
    status: str = "AVAILABLE"


class ChildPortion(BaseSchema):
    quantity_grams: int = Field(gt=0)
    storage_location: str


class LotSplitRequest(BaseSchema):
    child_portions: List[ChildPortion] = Field(min_length=2)


class LotSplitResponse(BaseSchema):
    parent_lot: InventoryLotResponse
    child_lots: List[InventoryLotResponse]


class LotMergeRequest(BaseSchema):
    source_lot_ids: List[str] = Field(min_length=2)
    target_storage_location: str


class LotMergeResponse(BaseSchema):
    merged_lot: InventoryLotResponse
    retired_lot_ids: List[str]


class GradeAdjustmentRequest(BaseSchema):
    new_grade: str
    reason: str


class InventoryMovementResponse(BaseSchema):
    movement_id: str
    lot_id: str
    movement_type: str  # "RECEIPT", "SPLIT", "MERGE", "REGRADE", "PICKUP", "DELIVERY", "LOSS"
    quantity_grams: int
    source_location: Optional[str] = None
    dest_location: Optional[str] = None
    source_custody: str
    dest_custody: str
    recorded_by: str
    created_at: datetime



# --- CommitGuard Schemas (F4) ---
class CommitmentAllocationItem(BaseSchema):
    lot_id: str
    allocated_grams: int = Field(gt=0, description="Allocated quantity in integer grams")


class BuyerCommitmentCreate(BaseSchema):
    requirement_id: str
    fpo_id: str
    agreed_price_paise_per_gram: int = Field(gt=0, description="Agreed unit price in integer paise per gram")
    allocations: List[CommitmentAllocationItem] = Field(min_length=1)
    idempotency_key: Optional[str] = None


class BuyerCommitmentResponse(BaseSchema):
    commitment_id: str
    requirement_id: str
    buyer_id: str
    fpo_id: str
    crop: str
    grade: str
    agreed_price_paise_per_gram: int
    committed_grams: int
    allocations: List[CommitmentAllocationItem]
    created_at: datetime
    updated_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    status: str = "CONFIRMED"


# --- Logistics Schemas (F5) ---
class VehicleCreate(BaseSchema):
    fpo_id: str
    driver_id: str
    capacity_grams: int = Field(gt=0, description="Payload capacity in integer grams")
    vehicle_type: str = "Mini Truck"


class VehicleResponse(BaseSchema):
    vehicle_id: str
    fpo_id: str
    driver_id: str
    capacity_grams: int
    vehicle_type: str
    is_available: bool = True
    created_at: datetime


class ShipmentCreate(BaseSchema):
    commitment_id: str
    vehicle_id: str
    driver_id: str


class ShipmentResponse(BaseSchema):
    shipment_id: str
    commitment_id: str
    vehicle_id: str
    driver_id: str
    dispatched_grams: int
    version: int = 1
    status: str = "PLANNED"
    custody: str = "SCHEDULED"
    actual_pickup_time: Optional[datetime] = None
    actual_delivery_time: Optional[datetime] = None
    accepted_grams: Optional[int] = None
    rejected_grams: Optional[int] = None
    loss_grams: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class DeliveryConfirmationRequest(BaseSchema):
    accepted_grams: int = Field(ge=0)
    rejected_grams: int = Field(default=0, ge=0)
    loss_grams: int = Field(default=0, ge=0)


# --- RiskWatch Schemas (F6) ---
class RiskIncidentResponse(BaseSchema):
    incident_id: str
    fpo_id: str
    incident_type: str
    dedup_key: str
    severity: str
    title: str
    description: str
    resource_type: str
    resource_id: str
    affected_grams: int = 0
    affected_paise: int = 0
    status: str = "OPEN"
    resolution_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IncidentResolveRequest(BaseSchema):
    resolution_note: str = Field(min_length=3, description="Verifiable reason or action taken to close the incident")


# --- RecoveryOpt Schemas (F7) ---
class RecoveryCandidate(BaseSchema):
    buyer_id: str
    requirement_id: str
    offered_price_paise_per_gram: int
    allocable_grams: int
    gross_revenue_paise: int
    estimated_transport_cost_paise: int
    net_return_paise: int
    effective_price_paise_per_gram: float
    rank: int = 1


class RecoveryPlanResponse(BaseSchema):
    plan_id: str
    incident_id: str
    fpo_id: str
    lot_id: str
    crop: str
    grade: str
    available_recovery_grams: int
    candidates: List[RecoveryCandidate] = Field(default_factory=list)
    recommended_candidate: Optional[RecoveryCandidate] = None
    status: str = "RECOMMENDED"
    optimality_status: str = "OPTIMAL_PROVEN"  # OPTIMAL_PROVEN, FEASIBLE_NOT_PROVEN_OPTIMAL, NO_POSITIVE_NET_OPTION, NO_FEASIBLE_OPTION
    solver_runtime_ms: float = 0.0
    candidate_count: int = 0
    objective_value_paise: int = 0
    model_version: str = "2.0-exact"
    buyer_confirmed_at: Optional[datetime] = None
    fpo_approved_at: Optional[datetime] = None
    created_at: datetime
    disclaimer: str = (
        "RECOMMENDATION ONLY: AI recovery plans do not bind buyers or guarantee stock rescue "
        "until explicit buyer confirmation and FPO approval are executed."
    )


# --- SettleTrack Schemas (F8) ---
class SettlementDeduction(BaseSchema):
    deduction_type: str = "TRANSPORT"
    amount_paise: int = Field(ge=0, description="Deduction in integer paise")
    reason: str


class VerificationStatus(str, Enum):
    REPORTED = "REPORTED"
    OPERATOR_CONFIRMED = "OPERATOR_CONFIRMED"
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"
    DISPUTED = "DISPUTED"
    REVERSED = "REVERSED"


class ProvenanceEvidenceRecord(BaseSchema):
    evidence_id: str
    source_type: str = "OPERATOR_MANUAL"  # BANK_API, WEIGHBRIDGE_IOT, OPERATOR_MANUAL, OFFLINE_SYNC
    source_identity: str
    raw_reference: str
    payload_digest: str
    quantity_or_amount: int
    unit_or_currency: str  # GRAMS or PAISE
    verification_status: VerificationStatus = VerificationStatus.REPORTED
    verifier_identity: Optional[str] = None
    calibration_metadata: Optional[str] = None
    recorded_at: datetime
    verified_at: Optional[datetime] = None


class RouteStatus(str, Enum):
    ESTIMATE_ONLY = "ESTIMATE_ONLY"
    ROUTE_VERIFIED = "ROUTE_VERIFIED"
    ROUTE_UNVERIFIED = "ROUTE_UNVERIFIED"
    NO_FEASIBLE_ROUTE = "NO_FEASIBLE_ROUTE"


class RouteVerificationRequest(BaseSchema):
    origin: str
    destination: str
    payload_weight_grams: int = Field(default=0, ge=0)


class RouteVerificationResponse(BaseSchema):
    origin: str
    destination: str
    distance_meters: int
    duration_seconds: int
    distance_km: float
    estimated_hours: float
    estimated_cost_paise: int
    route_status: RouteStatus
    path_nodes: List[str] = Field(default_factory=list)
    road_restrictions_applied: List[str] = Field(default_factory=list)
    provider_name: str
    confidence: float
    disclaimer: str


class PaymentRecord(BaseSchema):
    payment_id: str
    amount_paise: int = Field(gt=0)
    payment_method: str = "NEFT"
    reference_number: str
    evidence_note: Optional[str] = None
    evidence_id: Optional[str] = None
    verification_status: str = "REPORTED"  # REPORTED, OPERATOR_CONFIRMED, EXTERNALLY_VERIFIED, DISPUTED, REVERSED
    payload_digest: Optional[str] = None
    source_type: str = "MANUAL_ENTRY"
    recorded_by: str
    recorded_at: datetime
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None


class SettlementGenerateRequest(BaseSchema):
    shipment_id: str
    deductions: List[SettlementDeduction] = Field(default_factory=list)


class PaymentCreateRequest(BaseSchema):
    amount_paise: int = Field(gt=0, description="Payment amount in integer paise")
    payment_method: str = "NEFT"
    reference_number: str = Field(min_length=3)
    evidence_note: Optional[str] = None


class PaymentReportRequest(BaseSchema):
    amount_paise: int = Field(gt=0, description="Reported payment amount in integer paise")
    payment_method: str = "NEFT"
    reference_number: str = Field(min_length=3)
    evidence_note: Optional[str] = None


class PaymentVerifyRequest(BaseSchema):
    verification_note: Optional[str] = None
    external_token: Optional[str] = None



class SettlementResponse(BaseSchema):
    settlement_id: str
    shipment_id: str
    commitment_id: str
    fpo_id: str
    farmer_id: str
    buyer_id: str
    accepted_grams: int
    unit_price_paise_per_gram: int
    gross_amount_paise: int
    deductions: List[SettlementDeduction] = Field(default_factory=list)
    total_deductions_paise: int
    net_payable_paise: int
    paid_amount_paise: int = 0
    remaining_balance_paise: int
    payments: List[PaymentRecord] = Field(default_factory=list)
    audit_events: List[str] = Field(default_factory=list)
    status: str = "PENDING"
    created_at: datetime
    updated_at: datetime


# --- Overview Schemas (F9) ---
class FarmerOverviewResponse(BaseSchema):
    farmer_id: str
    active_forecasts_count: int
    active_forecasts_grams: int
    delivered_lots_count: int
    delivered_grams: int
    total_earned_paise: int
    pending_payout_paise: int
    as_of: datetime


class BuyerOverviewResponse(BaseSchema):
    buyer_id: str
    open_requirements_count: int
    open_needed_grams: int
    active_commitments_count: int
    active_committed_grams: int
    in_transit_shipments_count: int
    total_payable_paise: int
    total_paid_paise: int
    outstanding_balance_paise: int
    as_of: datetime


class DriverOverviewResponse(BaseSchema):
    driver_id: str
    assigned_vehicle_id: Optional[str] = None
    pending_pickups_count: int
    active_deliveries_count: int
    completed_trips_count: int
    as_of: datetime


class FpoOverviewResponse(BaseSchema):
    fpo_id: str
    total_physical_stock_grams: int
    total_available_stock_grams: int
    total_reserved_stock_grams: int
    at_risk_lots_count: int
    unfulfilled_commitments_count: int
    pending_collections_count: int
    pending_settlements_count: int
    total_settlement_payable_paise: int
    total_settlement_paid_paise: int
    as_of: datetime


# --- Offline Sync Schemas (F10) ---
class OfflineCommandEnvelope(BaseSchema):
    command_id: str
    actor_id: str
    device_id: str
    command_type: str
    resource_type: str
    resource_id: str
    expected_version: int = 1
    client_timestamp: datetime
    payload: Dict[str, Any] = Field(default_factory=dict)


class ReconciliationResponse(BaseSchema):
    command_id: str
    status: str  # "APPLIED", "REPLAYED", "CONFLICT_REJECTED"
    applied_resource_version: Optional[int] = None
    current_server_state: Optional[Dict[str, Any]] = None
    conflict_reason: Optional[str] = None
    processed_at: datetime


# --- Market Intelligence & Price Forecasting Schemas (Phase 4) ---
class MarketForecastRequest(BaseSchema):
    market_id: str
    commodity_id: str
    variety: str = "NOT_REPORTED"
    grade: str = "NOT_REPORTED"
    target_date: Optional[str] = None


class MarketForecastResponse(BaseSchema):
    status: str  # "PREDICTED_RESEARCH_ONLY", "UNAVAILABLE_FEATURE_DISABLED", "UNAVAILABLE_NO_TRAINED_MODEL", "REFUSED_UNVERIFIED_PROVENANCE", etc.
    market_id: str
    commodity_id: str
    variety: str = "NOT_REPORTED"
    grade: str = "NOT_REPORTED"
    forecast_target_date: Optional[str] = None
    forecast_issue_timestamp_utc: str
    price_unit: str = "INR/quintal"
    predicted_modal_price_inr_quintal: Optional[float] = None
    model_version: Optional[str] = None
    training_dataset_sha256: Optional[str] = None
    source_review_tier: Optional[str] = None
    feature_availability: Dict[str, str] = Field(default_factory=dict)
    planning_disclaimer: str = (
        "PLANNING DISCLOSURE: Wholesale mandi forecasts are indicative estimates only and "
        "must NEVER be treated as binding buyer procurement offers or settlement rates."
    )
    operational_notice: Optional[str] = None


# --- Farmer Management Schemas (Module 1) ---
class FarmerCreate(BaseSchema):
    farmer_name: str = Field(min_length=2)
    contact_phone: str = Field(min_length=10)
    fpo_id: str = "fpo-alpha"
    village: str
    district: str
    state: str = "West Bengal"
    pincode: Optional[str] = None
    landholding_acres: float = Field(default=1.0, ge=0.0)
    primary_crops: List[str] = Field(default_factory=lambda: ["Potato", "Rice", "Tomato"])


class FarmerUpdate(BaseSchema):
    contact_phone: Optional[str] = None
    village: Optional[str] = None
    district: Optional[str] = None
    landholding_acres: Optional[float] = None
    primary_crops: Optional[List[str]] = None


class FarmerResponse(BaseSchema):
    farmer_id: str
    farmer_name: str
    contact_phone: str
    fpo_id: str
    village: str
    district: str
    state: str
    pincode: Optional[str] = None
    landholding_acres: float
    primary_crops: List[str]
    kyc_verified: bool = False
    location_provenance: str = "MANUAL_DECLARED_NOT_GNSS"
    created_at: datetime
    updated_at: datetime


# --- Produce Listings & Commodity Schemas (Module 3) ---
class ProduceListingCreate(BaseSchema):
    crop: str
    variety: Optional[str] = "Standard"
    grade: str = "A"
    quantity_grams: int = Field(gt=0, description="Available quantity in integer grams")
    asking_price_paise_per_gram: int = Field(gt=0, description="Asking price in paise per gram")
    harvest_date: datetime
    description: Optional[str] = None
    storage_location_hint: Optional[str] = None
    idempotency_key: Optional[str] = None


class ProduceListingUpdate(BaseSchema):
    asking_price_paise_per_gram: Optional[int] = Field(default=None, gt=0)
    quantity_grams: Optional[int] = Field(default=None, gt=0)
    status: Optional[str] = None
    description: Optional[str] = None


class ProduceListingResponse(BaseSchema):
    listing_id: str
    farmer_id: str
    fpo_id: str
    crop: str
    variety: Optional[str]
    grade: str
    quantity_grams: int
    quantity_kg: float
    quantity_quintals: float
    asking_price_paise_per_gram: int
    asking_price_inr_per_kg: float
    harvest_date: datetime
    status: str = "ACTIVE"
    description: Optional[str] = None
    storage_location_hint: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CommodityItem(BaseSchema):
    commodity_id: str
    commodity_name: str
    category: str
    default_shelf_life_days: int
    is_perishable: bool
    standard_moisture_max_pct: float
    supported_grades: List[str]


# --- Buyer Management & Procurement Offers (Module 2 & 9) ---
class BuyerCreate(BaseSchema):
    business_name: str = Field(min_length=2)
    gstin: Optional[str] = None
    contact_person: str = Field(min_length=2)
    contact_phone: str = Field(min_length=10)
    contact_email: Optional[str] = None
    buyer_category: str = "Wholesaler"  # Retailer, Wholesaler, Processor, Institutional, Exporter
    terminal_location: str
    preferred_commodities: List[str] = Field(default_factory=lambda: ["Potato", "Rice", "Tomato"])


class BuyerUpdate(BaseSchema):
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    buyer_category: Optional[str] = None
    terminal_location: Optional[str] = None
    preferred_commodities: Optional[List[str]] = None


class BuyerResponse(BaseSchema):
    buyer_id: str
    business_name: str
    gstin: Optional[str]
    contact_person: str
    contact_phone: str
    contact_email: Optional[str]
    buyer_category: str
    terminal_location: str
    preferred_commodities: List[str]
    is_verified: bool = False
    verification_status: str = "REGISTERED"  # REGISTERED, PENDING_VERIFICATION, VERIFIED, REJECTED
    verification_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProcurementOfferCreate(BaseSchema):
    requirement_id: Optional[str] = None
    listing_id: Optional[str] = None
    offered_price_paise_per_gram: int = Field(gt=0)
    offered_grams: int = Field(gt=0)
    delivery_terms: str = "EX_WAREHOUSE"
    notes: Optional[str] = None


class ProcurementOfferResponse(BaseSchema):
    offer_id: str
    buyer_id: str
    buyer_name: str
    requirement_id: Optional[str] = None
    listing_id: Optional[str] = None
    crop: str
    grade: str
    offered_price_paise_per_gram: int
    offered_price_inr_per_kg: float
    offered_grams: int
    delivery_terms: str
    status: str = "OFFERED"  # OFFERED, ACCEPTED, REJECTED, EXPIRED, CONVERTED_TO_COMMITMENT
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# --- Transporter & Shared Transport Schemas (Module 6) ---
class TransporterCreate(BaseSchema):
    company_name: str = Field(min_length=2)
    contact_person: str = Field(min_length=2)
    contact_phone: str = Field(min_length=10)
    fpo_id: str = "fpo-alpha"
    operating_districts: List[str] = Field(default_factory=lambda: ["Purba Bardhaman", "Paschim Bardhaman", "Hooghly"])
    fleet_size: int = Field(default=1, ge=1)


class TransporterResponse(BaseSchema):
    transporter_id: str
    company_name: str
    contact_person: str
    contact_phone: str
    fpo_id: str
    operating_districts: List[str]
    fleet_size: int
    is_verified: bool = False
    created_at: datetime


class TransportRequestCreate(BaseSchema):
    farmer_id: str
    listing_id: Optional[str] = None
    crop: str
    quantity_grams: int = Field(gt=0)
    pickup_village: str
    pickup_district: str
    destination_facility_id: str
    requested_pickup_date: datetime
    contact_phone: str


class TransportRequestResponse(BaseSchema):
    request_id: str
    farmer_id: str
    fpo_id: str
    listing_id: Optional[str] = None
    crop: str
    quantity_grams: int
    quantity_kg: float
    pickup_village: str
    pickup_district: str
    destination_facility_id: str
    requested_pickup_date: datetime
    contact_phone: str
    status: str = "PENDING"  # PENDING, ASSIGNED_SHARED, IN_TRANSIT, DELIVERED, CANCELLED
    assigned_vehicle_id: Optional[str] = None
    assigned_shipment_id: Optional[str] = None
    shared_group_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SharedTransportGroupResponse(BaseSchema):
    group_id: str
    vehicle_id: str
    driver_id: str
    capacity_grams: int
    allocated_grams: int
    remaining_capacity_grams: int = 0
    utilization_pct: float
    request_count: int
    requests: List[TransportRequestResponse]
    route_classification: str = "ROUTE_UNVERIFIED_ESTIMATE"
    disclaimer: str = "Shared transport plan based on topological clustering. Does not claim certified GNSS road routing."


# --- Storage Facility & Spoilage Schemas (Module 7) ---
class StorageFacilityCreate(BaseSchema):
    facility_name: str = Field(min_length=2)
    fpo_id: str = "fpo-alpha"
    location_name: str
    district: str
    total_capacity_grams: int = Field(gt=0)
    temperature_controlled: bool = False
    target_temp_celsius: Optional[float] = None


class StorageFacilityResponse(BaseSchema):
    facility_id: str
    facility_name: str
    fpo_id: str
    location_name: str
    district: str
    total_capacity_grams: int
    utilized_grams: int
    available_grams: int
    utilization_pct: float
    temperature_controlled: bool
    target_temp_celsius: Optional[float]
    sensor_telemetry_status: str = "UNAVAILABLE_NO_CALIBRATED_SENSORS"
    status_notice: str = "Facility records are operator-reported. Real-time calibrated IoT environmental feed is unavailable."
    created_at: datetime


class SpoilageRiskItem(BaseSchema):
    lot_id: str
    crop: str
    grade: str
    storage_location: str
    days_in_storage: int
    max_shelf_life_days: int
    spoilage_risk_pct: float
    risk_level: str  # LOW, MODERATE, HIGH, CRITICAL
    recommendation: str
    sensor_evidence: str = "THEORETICAL_DECAY_CURVE_NO_IOT"


# --- BatchTrace Timeline Schemas (Module 8) ---
class TraceabilityMilestone(BaseSchema):
    milestone_id: str
    timestamp: datetime
    stage: str  # FORECAST, RECEIPT, INSPECTION, STORAGE, ALLOCATION, SHIPMENT, PICKUP, DELIVERY, SETTLEMENT
    actor_id: str
    actor_role: str
    title: str
    description: str
    quantity_grams: Optional[int] = None
    evidence_type: str = "OPERATOR_JOURNAL_RECORD"
    verification_level: str = "UNVERIFIED_MANUAL_RECORD"
    details: Dict[str, Any] = Field(default_factory=dict)


class BatchTraceTimelineResponse(BaseSchema):
    lot_id: str
    fpo_id: str
    farmer_id: str
    crop: str
    variety: Optional[str]
    grade: str
    initial_quantity_grams: int
    current_quantity_grams: int
    current_custody: str
    status: str
    created_at: datetime
    milestones: List[TraceabilityMilestone]
    chain_of_custody_verified: bool = False
    verification_notice: str = "Events reflect internal transaction ledger. Physical weighbridge and bank credit confirmations are unverified self-reported entries."


# --- Market Intelligence & Comparison Schemas (Module 4) ---
class MarketPriceRecord(BaseSchema):
    observation_id: str
    market_id: str
    market_name: str
    commodity_id: str
    commodity_name: str
    variety: str
    grade: str
    price_date: str
    min_price_paise_per_gram: int
    modal_price_paise_per_gram: int
    max_price_paise_per_gram: int
    min_price_rs_quintal: float
    modal_price_rs_quintal: float
    max_price_rs_quintal: float
    source_tier: str
    data_authenticity: str


class MarketPricesQueryResponse(BaseSchema):
    query_commodity: Optional[str] = None
    query_market: Optional[str] = None
    data_status: str  # "BLOCKED_UNVERIFIED_BASELINE", "EMPTY", "PARTIAL_SECONDARY_ONLY"
    total_records: int
    records: List[MarketPriceRecord] = Field(default_factory=list)
    blocked_datasets_notice: str = (
        "RESTRICTED DATASET NOTICE: Verified official APMC historical market prices panel "
        "(market_prices.csv, market_arrivals.csv, official_crosswalk_approvals.csv) is awaiting authoritative "
        "government portal integration. Currently baseline contains only unverified secondary observations without verified arrivals."
    )
    supported_mandis: List[Dict[str, str]] = Field(default_factory=list)


class NetEarningsEstimateRequest(BaseSchema):
    crop: str
    quantity_grams: int = Field(gt=0)
    market_id: Optional[str] = None
    distance_km: float = Field(default=25.0, ge=0.0)


class NetEarningsEstimateResponse(BaseSchema):
    crop: str
    quantity_grams: int
    quantity_quintals: float
    benchmark_modal_price_paise_per_gram: Optional[int]
    estimated_gross_paise: Optional[int]
    estimated_transport_cost_paise: int
    estimated_mandi_cess_paise: int
    estimated_net_farmer_earnings_paise: Optional[int]
    estimated_net_farmer_earnings_inr: Optional[float]
    price_source_status: str
    disclaimers: List[str] = Field(default_factory=list)
    disclaimer: Optional[str] = None


# --- AI Voice Assistant Schemas (Module 13) ---
class VoiceQueryRequest(BaseSchema):
    query_text: str = Field(min_length=1)
    language_code: str = "auto"  # "auto", "bn-IN", "hi-IN", "en-IN"
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None


class VoiceQueryResponse(BaseSchema):
    detected_intent: str
    detected_language: str
    language_confidence: float
    reply_text: str
    audio_synthesis_hint: str
    structured_action: Optional[Dict[str, Any]] = None
    suggested_followups: List[str] = Field(default_factory=list)
    factual_notice: str = "AI Assistant provides operational guidance without fabricating financial or market data."


# --- User Authentication & Session Schemas (Module 14) ---
class UserRegisterRequest(BaseSchema):
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)
    role: Role
    name: str = Field(min_length=2)
    organization_id: Optional[str] = "fpo-alpha"
    contact_phone: Optional[str] = None


class UserLoginRequest(BaseSchema):
    username: str
    password: str


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int = 86400
    actor_id: str
    role: str
    organization_id: Optional[str]
    name: str











