import axios from 'axios';
import type {
  Farmer,
  Buyer,
  ProduceListing,
  ProcurementOffer,
  Vehicle,
  TransportRequest,
  SharedTransportGroup,
  StorageFacility,
  SpoilageRiskAlert,
  LotTraceability,
  SettlementLedger,
  PaymentReceipt,
  RiskIncident,
  RecoveryPlan,
  ReadinessSummary,
} from '../types';

const API_BASE_URL = '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor for active actor role & token
apiClient.interceptors.request.use((config) => {
  const currentActor = localStorage.getItem('gramsetu_active_actor') || 'fpo_admin';
  config.headers['X-Dev-Actor'] = currentActor;
  
  const token = localStorage.getItem('gramsetu_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  // Authentication
  login: async (credentials: { username: string; password: string }) => {
    const res = await apiClient.post('/auth/login', credentials);
    return res.data;
  },
  register: async (data: {
    username: string;
    password: string;
    role: string;
    name: string;
    contact_phone?: string;
    organization_id?: string;
  }) => {
    const res = await apiClient.post('/auth/register', data);
    return res.data;
  },
  getMe: async () => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },
  getDbStatus: async () => {
    const res = await apiClient.get('/system/db-status');
    return res.data;
  },

  // System Readiness & Health
  getReadiness: async (): Promise<ReadinessSummary> => {
    const res = await apiClient.get('/system/readiness');
    return res.data;
  },

  // Farmers
  getFarmers: async (): Promise<Farmer[]> => {
    const res = await apiClient.get('/farmers');
    return res.data;
  },
  getFarmer: async (id: string): Promise<Farmer> => {
    const res = await apiClient.get(`/farmers/${id}`);
    return res.data;
  },
  createFarmer: async (data: Partial<Farmer>): Promise<Farmer> => {
    const res = await apiClient.post('/farmers', data);
    return res.data;
  },
  getFarmerDashboard: async (id: string) => {
    const res = await apiClient.get(`/farmers/${id}/dashboard`);
    return res.data;
  },

  // Buyers
  getBuyers: async (): Promise<Buyer[]> => {
    const res = await apiClient.get('/buyers');
    return res.data;
  },
  createBuyer: async (data: Partial<Buyer>): Promise<Buyer> => {
    const res = await apiClient.post('/buyers', data);
    return res.data;
  },

  // Commodities & Listings
  getCommodities: async () => {
    const res = await apiClient.get('/commodities');
    return res.data;
  },
  getListings: async (): Promise<ProduceListing[]> => {
    const res = await apiClient.get('/listings');
    return res.data;
  },
  createListing: async (data: Partial<ProduceListing>): Promise<ProduceListing> => {
    const res = await apiClient.post('/listings', data);
    return res.data;
  },

  // DemandSync
  getDemandGap: async (commodityCode?: string, district?: string) => {
    const res = await apiClient.get('/demand-gap', {
      params: { commodity_code: commodityCode, district },
    });
    return res.data;
  },
  createRequirement: async (data: {
    buyer_id: string;
    commodity_code: string;
    target_quantity_grams: number;
    max_price_paise_per_kg: number;
    required_by: string;
    delivery_district: string;
  }) => {
    const res = await apiClient.post('/requirements', data);
    return res.data;
  },
  createForecast: async (data: {
    farmer_id: string;
    commodity_code: string;
    expected_quantity_grams: number;
    forecast_date: string;
    confidence_pct?: number;
  }) => {
    const res = await apiClient.post('/forecasts', data);
    return res.data;
  },

  // Procurement Offers
  getProcurementOffers: async (): Promise<ProcurementOffer[]> => {
    const res = await apiClient.get('/procurement/offers');
    return res.data;
  },
  createProcurementOffer: async (data: {
    buyer_id: string;
    farmer_id: string;
    listing_id: string;
    offered_price_paise_per_kg: number;
    quantity_grams: number;
  }): Promise<ProcurementOffer> => {
    const res = await apiClient.post('/procurement/offers', data);
    return res.data;
  },
  acceptProcurementOffer: async (offerId: string): Promise<ProcurementOffer> => {
    const res = await apiClient.post(`/procurement/offers/${offerId}/accept`);
    return res.data;
  },
  rejectProcurementOffer: async (offerId: string): Promise<ProcurementOffer> => {
    const res = await apiClient.post(`/procurement/offers/${offerId}/reject`);
    return res.data;
  },

  // Logistics & Vehicles
  getTransporters: async () => {
    const res = await apiClient.get('/transporters');
    return res.data;
  },
  createTransporter: async (data: { name: string; phone: string; district: string; coverage_districts?: string[] }) => {
    const res = await apiClient.post('/transporters', data);
    return res.data;
  },
  getTransportRequests: async (): Promise<TransportRequest[]> => {
    const res = await apiClient.get('/transport/requests');
    return res.data;
  },
  createTransportRequest: async (data: Partial<TransportRequest>): Promise<TransportRequest> => {
    const res = await apiClient.post('/transport/requests', data);
    return res.data;
  },
  createVehicle: async (data: Partial<Vehicle>): Promise<Vehicle> => {
    const res = await apiClient.post('/vehicles', data);
    return res.data;
  },
  optimizeSharedTransport: async (data: {
    pickup_district: string;
    delivery_district: string;
    max_vehicle_capacity_grams: number;
  }): Promise<SharedTransportGroup[]> => {
    const res = await apiClient.post('/transport/optimize-shared', data);
    return res.data;
  },

  // Storage & Spoilage
  getStorageFacilities: async (): Promise<StorageFacility[]> => {
    const res = await apiClient.get('/storage/facilities');
    return res.data;
  },
  createStorageFacility: async (data: Partial<StorageFacility>): Promise<StorageFacility> => {
    const res = await apiClient.post('/storage/facilities', data);
    return res.data;
  },
  getSpoilageRisks: async (): Promise<SpoilageRiskAlert[]> => {
    const res = await apiClient.get('/storage/spoilage-risks');
    return res.data;
  },

  // BatchTrace
  getTraceability: async (lotId: string): Promise<LotTraceability> => {
    const res = await apiClient.get(`/traceability/${lotId}`);
    return res.data;
  },

  // Settlements & Payments
  getSettlements: async (): Promise<SettlementLedger[]> => {
    const res = await apiClient.get('/settlements');
    return res.data;
  },
  generateSettlement: async (data: {
    transaction_id: string;
    farmer_id: string;
    buyer_id: string;
    commodity_code: string;
    quantity_grams: number;
    gross_amount_paise: number;
    fpo_commission_paise?: number;
    logistics_fee_paise?: number;
  }): Promise<SettlementLedger> => {
    const res = await apiClient.post('/settlements/generate', data);
    return res.data;
  },
  recordPayment: async (
    settlementId: string,
    data: { amount_paise: number; payment_method: string; reference_number: string }
  ): Promise<PaymentReceipt> => {
    const res = await apiClient.post(`/settlements/${settlementId}/payments`, data);
    return res.data;
  },
  verifyPayment: async (settlementId: string, paymentId: string) => {
    const res = await apiClient.post(`/settlements/${settlementId}/payments/${paymentId}/verify`);
    return res.data;
  },

  // RiskWatch
  getRiskIncidents: async (): Promise<RiskIncident[]> => {
    const res = await apiClient.get('/risk/incidents');
    return res.data;
  },
  scanRisks: async () => {
    const res = await apiClient.post('/risk/scan');
    return res.data;
  },
  resolveRiskIncident: async (incidentId: string) => {
    const res = await apiClient.post(`/risk/incidents/${incidentId}/resolve`);
    return res.data;
  },

  // RecoveryOpt
  generateRecoveryPlan: async (data: { lot_id: string; commodity_code: string; spoilage_risk_pct: number }): Promise<RecoveryPlan> => {
    const res = await apiClient.post('/recovery/plans/generate', data);
    return res.data;
  },
  approveRecoveryPlan: async (planId: string): Promise<RecoveryPlan> => {
    const res = await apiClient.post(`/recovery/plans/${planId}/approve`);
    return res.data;
  },

  // Market Intelligence
  getMarketPrices: async (commodityCode?: string, district?: string) => {
    const res = await apiClient.get('/market/prices', {
      params: { commodity_code: commodityCode, district },
    });
    return res.data;
  },
  getMarketMandis: async () => {
    const res = await apiClient.get('/market/mandis');
    return res.data;
  },
  estimateEarnings: async (data: {
    commodity_code: string;
    quantity_kg: number;
    district: string;
    channel: 'direct_buyer' | 'fpo_pool' | 'local_mandi';
  }) => {
    const res = await apiClient.post('/market/estimate-earnings', data);
    return res.data;
  },

  // Voice Assistant
  voiceQuery: async (data: {
    audio_base64?: string;
    transcription_text?: string;
    language?: 'bn-IN' | 'hi-IN' | 'en-IN';
    caller_phone?: string;
  }) => {
    const res = await apiClient.post('/voice/query', data);
    return res.data;
  },
};
