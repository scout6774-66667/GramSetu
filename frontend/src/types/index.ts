export type UserRole = 
  | 'farmer' 
  | 'buyer' 
  | 'transporter' 
  | 'storage_operator' 
  | 'fpo_admin' 
  | 'system_auditor';

export interface Farmer {
  id: string;
  name: string;
  phone: string;
  village: string;
  district: string;
  state: string;
  preferred_language: 'bn-IN' | 'hi-IN' | 'en-IN';
  landholding_hectares: number;
  latitude?: number | null;
  longitude?: number | null;
  created_at?: string;
}

export interface Buyer {
  id: string;
  name: string;
  organization: string;
  phone: string;
  email: string;
  city: string;
  district: string;
  state: string;
  verified_status: boolean;
  business_type: string;
  created_at?: string;
}

export interface Commodity {
  id: string;
  code: string;
  name_en: string;
  name_bn: string;
  name_hi: string;
  category: string;
  perishability_class: 'high' | 'medium' | 'low';
  baseline_shelf_life_days: number;
}

export interface ProduceListing {
  id: string;
  farmer_id: string;
  commodity_code: string;
  quantity_grams: number;
  asking_price_paise_per_kg: number;
  harvest_date: string;
  available_from: string;
  quality_grade: 'A' | 'B' | 'C';
  status: 'active' | 'reserved' | 'sold' | 'expired';
  notes?: string;
  created_at?: string;
}

export interface HarvestForecast {
  id: string;
  farmer_id: string;
  commodity_code: string;
  expected_quantity_grams: number;
  forecast_date: string;
  confidence_pct: number;
}

export interface BuyerRequirement {
  id: string;
  buyer_id: string;
  commodity_code: string;
  target_quantity_grams: number;
  max_price_paise_per_kg: number;
  required_by: string;
  delivery_district: string;
}

export interface ProcurementOffer {
  id: string;
  buyer_id: string;
  farmer_id: string;
  listing_id: string;
  offered_price_paise_per_kg: number;
  quantity_grams: number;
  status: 'pending' | 'accepted' | 'rejected' | 'fulfilled';
  created_at?: string;
}

export interface Vehicle {
  id: string;
  carrier_id: string;
  registration_number: string;
  vehicle_type: string;
  capacity_grams: number;
  is_refrigerated: boolean;
  status: 'available' | 'in_transit' | 'maintenance';
}

export interface TransportRequest {
  id: string;
  farmer_id: string;
  commodity_code: string;
  quantity_grams: number;
  pickup_district: string;
  drop_district: string;
  pickup_date: string;
  status: 'pending' | 'assigned' | 'completed';
}

export interface SharedTransportGroup {
  group_id: string;
  carrier_vehicle_id: string;
  pickup_district: string;
  delivery_district: string;
  assigned_requests: TransportRequest[];
  total_weight_grams: number;
  vehicle_capacity_grams: number;
  remaining_capacity_grams: number;
  utilization_pct: number;
  route_verification_status: string;
}

export interface StorageFacility {
  id: string;
  name: string;
  facility_type: 'cold_storage' | 'dry_warehouse' | 'silo';
  district: string;
  total_capacity_grams: number;
  utilized_capacity_grams: number;
  temperature_celsius?: number;
  humidity_pct?: number;
  sensor_verification_status: string;
}

export interface SpoilageRiskAlert {
  lot_id: string;
  facility_id: string;
  commodity_code: string;
  quantity_grams: number;
  storage_days: number;
  spoilage_risk_pct: number;
  urgency: 'low' | 'medium' | 'high' | 'critical';
  recommended_action: string;
}

export interface TraceabilityMilestone {
  stage: string;
  timestamp: string;
  actor: string;
  location: string;
  notes?: string;
  verification_level: 'AUTHENTIC' | 'PROVISIONAL' | 'UNVERIFIED';
}

export interface LotTraceability {
  lot_id: string;
  farmer_id: string;
  commodity_code: string;
  quantity_grams: number;
  harvest_date: string;
  quality_grade: string;
  milestones: TraceabilityMilestone[];
}

export interface SettlementLedger {
  id: string;
  transaction_id: string;
  farmer_id: string;
  buyer_id: string;
  commodity_code: string;
  quantity_grams: number;
  gross_amount_paise: number;
  fpo_commission_paise: number;
  logistics_fee_paise: number;
  net_farmer_amount_paise: number;
  settlement_status: 'pending' | 'paid' | 'disputed';
  created_at?: string;
}

export interface PaymentReceipt {
  id: string;
  settlement_id: string;
  amount_paise: number;
  payment_method: 'bank_transfer' | 'upi' | 'cash';
  reference_number: string;
  payment_date: string;
  verified_status: boolean;
}

export interface RiskIncident {
  id: string;
  risk_type: 'weather_warning' | 'road_blockage' | 'storage_failure' | 'payment_delay';
  severity: 'low' | 'medium' | 'high' | 'critical';
  district: string;
  description: string;
  status: 'active' | 'mitigated' | 'resolved';
  detected_at: string;
}

export interface RecoveryOption {
  candidate_id: string;
  buyer_name: string;
  buyer_type: 'food_processor' | 'discount_wholesaler' | 'feed_producer' | 'composter';
  offered_price_paise_per_kg: number;
  distance_km: number;
  recovery_value_pct: number;
  dispatch_deadline_hours: number;
}

export interface RecoveryPlan {
  id: string;
  lot_id: string;
  commodity_code: string;
  spoilage_risk_pct: number;
  status: 'generated' | 'fpo_approved' | 'buyer_accepted' | 'dispatched';
  best_option?: RecoveryOption;
  alternative_options?: RecoveryOption[];
  created_at?: string;
}

export interface MandiPriceBenchmark {
  mandi_name: string;
  district: string;
  commodity: string;
  modal_price_per_kg: number;
  min_price_per_kg: number;
  max_price_per_kg: number;
  arrival_tonnes: number;
  status: 'secondary_baseline' | 'authentic_live' | 'blocked';
}

export interface AcceptanceGateCheck {
  gate_id: string;
  domain: string;
  metric: string;
  target_threshold: string;
  current_observed: string;
  status: 'PASS' | 'BLOCKED' | 'PENDING';
  block_reason?: string;
}

export interface ReadinessSummary {
  overall_status: 'BLOCKED' | 'OPERATIONAL' | 'DEGRADED';
  active_gates_count: number;
  passed_gates_count: number;
  blocked_datasets: string[];
  modules: Record<string, string>;
  stats: {
    total_farmers: number;
    total_buyers: number;
    total_listings: number;
    total_facilities: number;
    active_incidents: number;
  };
}
