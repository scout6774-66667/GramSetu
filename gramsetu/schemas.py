from __future__ import annotations

from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


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











