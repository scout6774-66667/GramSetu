"""Comprehensive verification tests for GramSetu audit completion.

Validates:
- Module 1: Farmer management & profiles
- Module 2: Buyer management & verification
- Module 3: Produce listings & pilot commodities
- Module 4: Market intelligence, blocked dataset disclosure & net earnings estimator
- Module 6: Shared transport requests & vehicle pooling
- Module 7: Storage facilities, capacity & spoilage risk calculation
- Module 8: BatchTrace chronological timeline
- Module 9: Buyer procurement offers lifecycle
- Module 10: SettleTrack farmer & buyer statements
- Module 13: Multilingual AI voice assistant (Bengali, Hindi, English)
- Module 14: Secure user registration & JWT authentication
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import Settings, Environment, DEV_ACTOR_HEADER
from gramsetu.store import InMemoryStore, TransactionCoordinator


@pytest.fixture
def api_client():
    settings = Settings(ENVIRONMENT=Environment.TESTING)
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    app = create_app(settings=settings, coordinator=coord)
    client = TestClient(app)
    return client


# ==============================================================================
# Module 1: Farmer Management Tests
# ==============================================================================
def test_farmer_registration_and_profile_lifecycle(api_client):
    """Test farmer registration, profile fetch, update and scoping."""
    # Register farmer
    res = api_client.post(
        "/api/v1/farmers",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_name": "Subhashish Ghosh",
            "contact_phone": "9876543210",
            "fpo_id": "fpo-alpha",
            "village": "Galsi",
            "district": "Purba Bardhaman",
            "state": "West Bengal",
            "pincode": "713406",
            "landholding_acres": 3.5,
            "primary_crops": ["Potato", "Rice (Paddy)"],
        },
    )
    assert res.status_code == 201
    data = res.json()
    farmer_id = data["farmer_id"]
    assert data["farmer_name"] == "Subhashish Ghosh"
    assert data["location_provenance"] == "MANUAL_DECLARED_NOT_GNSS"
    assert data["kyc_verified"] is False

    # Get profile
    res_get = api_client.get(
        f"/api/v1/farmers/{farmer_id}",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_get.status_code == 200
    assert res_get.json()["district"] == "Purba Bardhaman"

    # Update profile
    res_up = api_client.put(
        f"/api/v1/farmers/{farmer_id}",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"landholding_acres": 4.0, "village": "Galsi North"},
    )
    assert res_up.status_code == 200
    assert res_up.json()["landholding_acres"] == 4.0
    assert res_up.json()["village"] == "Galsi North"

    # List farmers
    res_list = api_client.get(
        "/api/v1/farmers?fpo_id=fpo-alpha",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1


# ==============================================================================
# Module 2: Buyer Management Tests
# ==============================================================================
def test_buyer_registration_and_verification_status(api_client):
    """Test buyer registration, unverified default status, and profile lookup."""
    res = api_client.post(
        "/api/v1/buyers",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "business_name": "Bengal Fresh Wholesalers Pvt Ltd",
            "gstin": "19AABCB1234D1Z1",
            "contact_person": "Amitava Roy",
            "contact_phone": "9831122334",
            "contact_email": "procurement@bengalfresh.in",
            "buyer_category": "Wholesaler",
            "terminal_location": "Burdwan APMC Hub",
            "preferred_commodities": ["Potato", "Mustard"],
        },
    )
    assert res.status_code == 201
    buyer = res.json()
    b_id = buyer["buyer_id"]
    assert buyer["is_verified"] is False
    assert buyer["verification_status"] == "REGISTERED"

    # Get buyer profile
    res_get = api_client.get(
        f"/api/v1/buyers/{b_id}",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_get.status_code == 200
    assert res_get.json()["business_name"] == "Bengal Fresh Wholesalers Pvt Ltd"


# ==============================================================================
# Module 3: Produce Listings & Commodities Tests
# ==============================================================================
def test_produce_listings_and_commodities(api_client):
    """Test produce listing creation, unit conversions, and commodities list."""
    # List pilot commodities
    res_comms = api_client.get("/api/v1/commodities")
    assert res_comms.status_code == 200
    commodities = res_comms.json()
    assert len(commodities) >= 5
    crop_names = [c["commodity_name"] for c in commodities]
    assert "Potato" in crop_names
    assert "Rice (Paddy)" in crop_names

    # Create produce listing
    now = datetime.now(timezone.utc)
    res_list = api_client.post(
        "/api/v1/listings",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Potato",
            "variety": "Jyoti",
            "grade": "A",
            "quantity_grams": 2_500_000,  # 2,500 kg = 25 quintals
            "asking_price_paise_per_gram": 16,  # 16 paise/g = ₹16/kg
            "harvest_date": (now - timedelta(days=2)).isoformat(),
            "description": "Fresh Jyoti potatoes harvested in Galsi.",
        },
    )
    assert res_list.status_code == 201
    listing = res_list.json()
    listing_id = listing["listing_id"]
    assert listing["quantity_kg"] == 2500.0
    assert listing["quantity_quintals"] == 25.0
    assert listing["asking_price_inr_per_kg"] == 1.6
    assert listing["status"] == "ACTIVE"

    # Update listing
    res_up = api_client.put(
        f"/api/v1/listings/{listing_id}",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={"asking_price_paise_per_gram": 15},
    )
    assert res_up.status_code == 200
    assert res_up.json()["asking_price_paise_per_gram"] == 15


# ==============================================================================
# Module 4: Market Intelligence & Earnings Estimator Tests
# ==============================================================================
def test_market_intelligence_and_honest_disclosures(api_client):
    """Test market price queries disclosing dataset limitations, and net earnings estimator."""
    # Query prices
    res_prices = api_client.get("/api/v1/market/prices?commodity=Potato")
    assert res_prices.status_code == 200
    data = res_prices.json()
    assert data["data_status"] in ("BLOCKED_UNVERIFIED_BASELINE", "PARTIAL_SECONDARY_ONLY")
    assert "RESTRICTED DATASET NOTICE" in data["blocked_datasets_notice"]
    assert len(data["supported_mandis"]) >= 4

    # Pilot mandis
    res_mandis = api_client.get("/api/v1/market/mandis")
    assert res_mandis.status_code == 200
    assert len(res_mandis.json()) >= 4

    # Estimate net earnings
    res_est = api_client.post(
        "/api/v1/market/estimate-earnings",
        json={
            "crop": "Potato",
            "quantity_grams": 5_000_000,  # 5 tonnes
            "distance_km": 30.0,
        },
    )
    assert res_est.status_code == 200
    est = res_est.json()
    assert est["quantity_quintals"] == 50.0
    assert est["estimated_gross_paise"] is not None
    assert est["estimated_transport_cost_paise"] > 0
    assert est["estimated_net_farmer_earnings_paise"] > 0
    assert "CALCULATED ESTIMATE" in est["disclaimer"]


# ==============================================================================
# Module 6: Shared Transportation & Vehicle Pooling Tests
# ==============================================================================
def test_shared_transport_requests_and_pooling(api_client):
    """Test transporter registration, transport requests, and shared group pooling."""
    now = datetime.now(timezone.utc)

    # Register transporter
    res_trans = api_client.post(
        "/api/v1/transporters",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "company_name": "Burdwan Rural Agri-Logistics",
            "contact_person": "Bikash Mondal",
            "contact_phone": "9830099887",
            "fpo_id": "fpo-alpha",
            "operating_districts": ["Purba Bardhaman"],
            "fleet_size": 3,
        },
    )
    assert res_trans.status_code == 201

    # Farmer creates transport request 1
    res_req1 = api_client.post(
        "/api/v1/transport/requests",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "farmer_id": "farmer-1",
            "crop": "Potato",
            "quantity_grams": 1_000_000,  # 1 tonne
            "pickup_village": "Galsi",
            "pickup_district": "Purba Bardhaman",
            "destination_facility_id": "FAC-WH-01",
            "requested_pickup_date": (now + timedelta(days=1)).isoformat(),
            "contact_phone": "9876543210",
        },
    )
    assert res_req1.status_code == 201
    assert res_req1.json()["status"] == "PENDING"

    # Farmer creates transport request 2
    res_req2 = api_client.post(
        "/api/v1/transport/requests",
        headers={DEV_ACTOR_HEADER: "farmer-2"},
        json={
            "farmer_id": "farmer-2",
            "crop": "Paddy",
            "quantity_grams": 1_500_000,  # 1.5 tonne
            "pickup_village": "Mankar",
            "pickup_district": "Purba Bardhaman",
            "destination_facility_id": "FAC-WH-01",
            "requested_pickup_date": (now + timedelta(days=1)).isoformat(),
            "contact_phone": "9876543211",
        },
    )
    assert res_req2.status_code == 201

    # Optimize shared transport pooling
    res_pool = api_client.post(
        "/api/v1/transport/optimize-shared?district=Purba Bardhaman",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_pool.status_code == 200
    groups = res_pool.json()
    assert len(groups) >= 1
    grp = groups[0]
    assert grp["request_count"] == 2
    assert grp["allocated_grams"] == 2_500_000
    assert grp["route_classification"] == "ROUTE_UNVERIFIED_ESTIMATE"


# ==============================================================================
# Module 7: Storage Facilities & Spoilage Risk Tests
# ==============================================================================
def test_storage_facilities_and_spoilage_risks(api_client):
    """Test storage facility registration, capacity tracking, and spoilage risk calculation."""
    # Register facility
    res_fac = api_client.post(
        "/api/v1/storage/facilities",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "facility_name": "Katwa Rural Cold Chamber",
            "fpo_id": "fpo-alpha",
            "location_name": "Katwa APMC Yard",
            "district": "Purba Bardhaman",
            "total_capacity_grams": 40_000_000,
            "temperature_controlled": True,
            "target_temp_celsius": 8.0,
        },
    )
    assert res_fac.status_code == 201
    fac = res_fac.json()
    assert fac["sensor_telemetry_status"] == "UNAVAILABLE_NO_CALIBRATED_SENSORS"

    # Add a lot to storage to check spoilage risk
    res_lot = api_client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Tomato",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": fac["facility_id"],
        },
    )
    assert res_lot.status_code == 201

    # Compute spoilage risks
    res_risks = api_client.get("/api/v1/storage/spoilage-risks?fpo_id=fpo-alpha")
    assert res_risks.status_code == 200
    risks = res_risks.json()
    assert len(risks) >= 1
    assert risks[0]["sensor_evidence"] == "THEORETICAL_DECAY_CURVE_NO_IOT"


# ==============================================================================
# Module 8: BatchTrace Timeline Tests
# ==============================================================================
def test_batchtrace_chronological_timeline(api_client):
    """Test lot traceability timeline reconstructing full lifecycle milestones."""
    # Create lot receipt
    res_lot = api_client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Soybean",
            "grade": "A",
            "quantity_grams": 1_000_000,
            "storage_location": "FAC-WH-01",
        },
    )
    lot_id = res_lot.json()["lot_id"]

    # Get timeline
    res_trace = api_client.get(
        f"/api/v1/traceability/{lot_id}",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res_trace.status_code == 200
    trace = res_trace.json()
    assert trace["lot_id"] == lot_id
    assert len(trace["milestones"]) >= 1
    assert trace["milestones"][0]["stage"] in ("FORECAST", "RECEIPT")
    assert trace["chain_of_custody_verified"] is False
    assert "Events reflect internal transaction ledger" in trace["verification_notice"]


# ==============================================================================
# Module 9: Buyer Procurement Offers Lifecycle Tests
# ==============================================================================
def test_buyer_procurement_offers_lifecycle(api_client):
    """Test buyer posting procurement offers on listings, and acceptance workflow."""
    now = datetime.now(timezone.utc)
    # Create listing
    res_list = api_client.post(
        "/api/v1/listings",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Potato",
            "grade": "A",
            "quantity_grams": 2_000_000,
            "asking_price_paise_per_gram": 18,
            "harvest_date": now.isoformat(),
        },
    )
    listing_id = res_list.json()["listing_id"]

    # Buyer posts offer
    res_offer = api_client.post(
        "/api/v1/procurement/offers",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "listing_id": listing_id,
            "offered_price_paise_per_gram": 17,
            "offered_grams": 2_000_000,
            "delivery_terms": "EX_WAREHOUSE",
            "notes": "Offer from Reliance Wholesale for Grade A Potato",
        },
    )
    assert res_offer.status_code == 201
    offer = res_offer.json()
    offer_id = offer["offer_id"]
    assert offer["status"] == "OFFERED"
    assert offer["offered_price_inr_per_kg"] == 1.7

    # Farmer accepts offer
    res_accept = api_client.post(
        f"/api/v1/procurement/offers/{offer_id}/accept",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
    )
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "ACCEPTED"


# ==============================================================================
# Module 10: SettleTrack Statements Tests
# ==============================================================================
def test_settletrack_farmer_and_buyer_statements(api_client):
    """Test farmer and buyer specific settlement statement endpoints."""
    res_f = api_client.get(
        "/api/v1/settlements/farmer/farmer-1",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
    )
    assert res_f.status_code == 200
    assert isinstance(res_f.json(), list)

    res_b = api_client.get(
        "/api/v1/settlements/buyer/buyer-reliance",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
    )
    assert res_b.status_code == 200
    assert isinstance(res_b.json(), list)


# ==============================================================================
# Module 13: Multilingual AI Voice Assistant Tests
# ==============================================================================
def test_ai_voice_assistant_multilingual_intents(api_client):
    """Test Bengali, Hindi, and English query recognition and intent routing."""
    # 1. Bengali query for potato price
    res_bn = api_client.post(
        "/api/v1/voice/query",
        json={"query_text": "বর্ধমান বাজারে আলুর দাম কত?"},
    )
    assert res_bn.status_code == 200
    data_bn = res_bn.json()
    assert data_bn["detected_intent"] == "MARKET_PRICE_CHECK"
    assert data_bn["detected_language"] == "bn-IN"
    assert "আলু" in data_bn["reply_text"]

    # 2. Hindi query for harvest logging
    res_hi = api_client.post(
        "/api/v1/voice/query",
        json={"query_text": "मैंने 500kg टमाटर की कटाई की है"},
    )
    assert res_hi.status_code == 200
    data_hi = res_hi.json()
    assert data_hi["detected_intent"] == "HARVEST_REGISTER"
    assert data_hi["detected_language"] == "hi-IN"

    # 3. English query for transport booking
    res_en = api_client.post(
        "/api/v1/voice/query",
        json={"query_text": "I need a pickup truck to transport 10 quintals of potato"},
    )
    assert res_en.status_code == 200
    data_en = res_en.json()
    assert data_en["detected_intent"] == "TRANSPORT_REQUEST"
    assert data_en["detected_language"] == "en-IN"


# ==============================================================================
# Module 14: User Authentication & JWT Tests
# ==============================================================================
def test_user_registration_and_jwt_authentication(api_client):
    """Test user registration, password verification, and JWT login."""
    # Register new user
    res_reg = api_client.post(
        "/api/v1/auth/register",
        json={
            "username": "farmer_bengal_101",
            "password": "SecurePassword123!",
            "role": "FARMER",
            "name": "Pranab Mukherjee",
            "organization_id": "fpo-alpha",
            "contact_phone": "9832109876",
        },
    )
    assert res_reg.status_code == 201
    token_data = res_reg.json()
    assert "access_token" in token_data
    assert token_data["role"] == "FARMER"

    # Login with valid credentials
    res_login = api_client.post(
        "/api/v1/auth/login",
        json={
            "username": "farmer_bengal_101",
            "password": "SecurePassword123!",
        },
    )
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()

    # Login with invalid password
    res_fail = api_client.post(
        "/api/v1/auth/login",
        json={
            "username": "farmer_bengal_101",
            "password": "WrongPassword!",
        },
    )
    assert res_fail.status_code == 401
