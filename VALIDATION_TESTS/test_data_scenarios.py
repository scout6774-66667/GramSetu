"""GramSetu AI End-to-End Operational Scenario Tests.

Executes real-world domain workflows against the backend using canonical dataset records:
 - Scenario A: Normal fulfillment (Forecast -> Lot -> Req -> Commitment -> Shipment -> Settlement)
 - Scenario B: Supply shortage (Demand gap analysis & harvest deficit)
 - Scenario C: Logistics disruption (Quality rejection & short delivery risk scan)
 - Scenario D: Quality failure (Grade downgrade / moisture excess handling)
 - Scenario E: Financial settlement & statutory deduction calculation
"""

import os
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.core import DEV_ACTOR_HEADER


@pytest.fixture
def test_setup():
    app = create_app()
    client = TestClient(app)
    return client


def test_scenario_a_normal_fulfillment(test_setup):
    """Scenario A: Standard end-to-end procurement and settlement workflow."""
    client = test_setup
    now = datetime.now(timezone.utc)

    # 1. Farmer records harvest forecast (Soybean Grade A)
    fc_res = client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Soybean",
            "variety": "JS-335",
            "grade": "A",
            "estimated_grams": 1_000_000,
            "harvest_start_date": now.isoformat(),
            "harvest_end_date": (now + timedelta(days=5)).isoformat(),
            "confidence_score": 0.95,
            "idempotency_key": "fc-scen-a-1"
        }
    )
    assert fc_res.status_code in (200, 201)

    # 2. FPO receives physical lot into storage facility
    lot_res = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Soybean",
            "grade": "A",
            "quantity_grams": 1_000_000,
            "storage_location": "FAC-WH-01"
        }
    )
    assert lot_res.status_code in (200, 201)
    lot_id = lot_res.json()["lot_id"]

    # 3. Buyer posts purchase requirement
    req_res = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Soybean",
            "variety": "JS-335",
            "grade": "A",
            "needed_grams": 1_000_000,
            "delivery_window_start": now.isoformat(),
            "delivery_window_end": (now + timedelta(days=7)).isoformat(),
            "max_price_paise_per_gram": 50,
            "idempotency_key": "req-scen-a-1"
        }
    )
    assert req_res.status_code in (200, 201)
    req_id = req_res.json()["requirement_id"]

    # 4. Buyer creates commitment allocating physical lot
    commit_res = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "requirement_id": req_id,
            "fpo_id": "fpo-alpha",
            "agreed_price_paise_per_gram": 48,
            "allocations": [{"lot_id": lot_id, "allocated_grams": 1_000_000}]
        }
    )
    assert commit_res.status_code in (200, 201)
    commit_id = commit_res.json()["commitment_id"]

    # 5. Register vehicle and dispatch shipment
    veh_res = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "fpo_id": "fpo-alpha",
            "driver_id": "driver-1",
            "capacity_grams": 4_000_000,
            "vehicle_type": "TRUCK_4T"
        }
    )
    assert veh_res.status_code in (200, 201)
    veh_id = veh_res.json()["vehicle_id"]

    ship_res = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "commitment_id": commit_id,
            "vehicle_id": veh_id,
            "driver_id": "driver-1"
        }
    )
    assert ship_res.status_code in (200, 201)
    shipment_id = ship_res.json()["shipment_id"]

    # 6. Driver pickup & delivery
    client.post(f"/api/v1/shipments/{shipment_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    deliv_res = client.post(
        f"/api/v1/shipments/{shipment_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={
            "accepted_grams": 1_000_000,
            "rejected_grams": 0,
            "loss_grams": 0
        }
    )
    assert deliv_res.status_code == 200

    # 7. Settlement generation
    settle_res = client.post(
        "/api/v1/settlements/generate",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "shipment_id": shipment_id,
            "deductions": [
                {
                    "deduction_type": "TRANSPORT",
                    "amount_paise": 504_000,
                    "reason": "Freight haulage charge"
                }
            ]
        }
    )
    assert settle_res.status_code in (200, 201)
    settle_data = settle_res.json()
    assert settle_data["gross_amount_paise"] == 1_000_000 * 48
    assert settle_data["net_payable_paise"] == 48_000_000 - 504_000


def test_scenario_b_supply_shortage(test_setup):
    """Scenario B: Supply shortfall detection against verified requirements."""
    client = test_setup
    now = datetime.now(timezone.utc)

    # Buyer posts demand for 5,000,000 grams of Grade A Wheat
    client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Wheat",
            "variety": "Lokwan",
            "grade": "A",
            "needed_grams": 5_000_000,
            "delivery_window_start": now.isoformat(),
            "delivery_window_end": (now + timedelta(days=10)).isoformat(),
            "max_price_paise_per_gram": 35,
            "idempotency_key": "req-scen-b-1"
        }
    )

    # Farmer forecasts only 1,500,000 grams
    client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1"},
        json={
            "crop": "Wheat",
            "variety": "Lokwan",
            "grade": "A",
            "estimated_grams": 1_500_000,
            "harvest_start_date": now.isoformat(),
            "harvest_end_date": (now + timedelta(days=5)).isoformat(),
            "confidence_score": 0.90,
            "idempotency_key": "fc-scen-b-1"
        }
    )

    # Check demand gap analysis
    gap_res = client.get(
        "/api/v1/demand-gap?fpo_id=fpo-alpha&crop=Wheat&grade=A",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}
    )
    assert gap_res.status_code == 200
    gap_list = gap_res.json()
    assert len(gap_list) > 0
    gap_data = gap_list[0]
    assert gap_data["net_gap_grams"] == 3_500_000


def test_scenario_c_logistics_disruption(test_setup):
    """Scenario C: Logistics transit risk scan and incident response."""
    client = test_setup
    now = datetime.now(timezone.utc)

    # Setup active shipment with partial rejection
    veh_res = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 4_000_000, "vehicle_type": "TRUCK_4T"}
    )
    veh_id = veh_res.json()["vehicle_id"]

    lot_res = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"farmer_id": "farmer-1", "fpo_id": "fpo-alpha", "crop": "Tomato", "grade": "A", "quantity_grams": 1_000_000, "storage_location": "FAC-WH-01"}
    )
    lot_id = lot_res.json()["lot_id"]

    req_res = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Tomato", "grade": "A", "needed_grams": 1_000_000,
            "delivery_window_start": now.isoformat(), "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 30
        }
    )
    req_id = req_res.json()["requirement_id"]

    commit_res = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={"requirement_id": req_id, "fpo_id": "fpo-alpha", "agreed_price_paise_per_gram": 25, "allocations": [{"lot_id": lot_id, "allocated_grams": 1_000_000}]}
    )
    commit_id = commit_res.json()["commitment_id"]

    ship_res = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"}
    )
    ship_id = ship_res.json()["shipment_id"]

    client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 900_000, "rejected_grams": 100_000, "loss_grams": 0}
    )

    # Trigger risk scan
    scan_res = client.post("/api/v1/risk/scan?fpo_id=fpo-alpha", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert scan_res.status_code == 200
    incidents = scan_res.json()
    assert len(incidents) > 0
    types = [i["incident_type"] for i in incidents]
    assert "QUALITY_REJECTION" in types


def test_scenario_d_quality_failure(test_setup):
    """Scenario D: Lot grade adjustment due to quality downgrade."""
    client = test_setup

    # FPO receives lot as Grade A
    lot_res = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Soybean",
            "grade": "A",
            "quantity_grams": 2_000_000,
            "storage_location": "FAC-WH-01"
        }
    )
    lot_id = lot_res.json()["lot_id"]

    # Quality inspection reveals moisture > 12%, downgrade to Grade B
    adj_res = client.post(
        f"/api/v1/lots/{lot_id}/grade",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "new_grade": "B",
            "reason": "Moisture content tested at 14.2%, exceeding Grade A threshold of 10.0%"
        }
    )
    assert adj_res.status_code == 200
    assert adj_res.json()["grade"] == "B"


def test_scenario_e_financial_discrepancy(test_setup):
    """Scenario E: Audit of settlement deductions against statutory rules."""
    client = test_setup
    now = datetime.now(timezone.utc)

    # Setup delivered shipment
    veh_res = client.post(
        "/api/v1/vehicles",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"fpo_id": "fpo-alpha", "driver_id": "driver-1", "capacity_grams": 1_000_000}
    )
    veh_id = veh_res.json()["vehicle_id"]

    lot_res = client.post(
        "/api/v1/lots/receipt",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"farmer_id": "farmer-1", "fpo_id": "fpo-alpha", "crop": "Soybean", "grade": "A", "quantity_grams": 500_000, "storage_location": "FAC-WH-01"}
    )
    lot_id = lot_res.json()["lot_id"]

    req_res = client.post(
        "/api/v1/requirements",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={
            "crop": "Soybean", "grade": "A", "needed_grams": 500_000,
            "delivery_window_start": now.isoformat(), "delivery_window_end": (now + timedelta(days=5)).isoformat(),
            "max_price_paise_per_gram": 50
        }
    )
    req_id = req_res.json()["requirement_id"]

    commit_res = client.post(
        "/api/v1/commitments",
        headers={DEV_ACTOR_HEADER: "buyer-reliance"},
        json={"requirement_id": req_id, "fpo_id": "fpo-alpha", "agreed_price_paise_per_gram": 45, "allocations": [{"lot_id": lot_id, "allocated_grams": 500_000}]}
    )
    commit_id = commit_res.json()["commitment_id"]

    ship_res = client.post(
        "/api/v1/shipments",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={"commitment_id": commit_id, "vehicle_id": veh_id, "driver_id": "driver-1"}
    )
    ship_id = ship_res.json()["shipment_id"]

    client.post(f"/api/v1/shipments/{ship_id}/pickup", headers={DEV_ACTOR_HEADER: "driver-1"})
    client.post(
        f"/api/v1/shipments/{ship_id}/delivery",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"accepted_grams": 500_000, "rejected_grams": 0, "loss_grams": 0}
    )

    # Generate settlement with multiple statutory deductions
    deductions = [
        {"deduction_type": "MANDI_CESS", "amount_paise": 236_250, "reason": "APMC Mandi Cess (1.05%)"},
        {"deduction_type": "TRANSPORT", "amount_paise": 150_000, "reason": "Freight haulage charge"}
    ]

    res = client.post(
        "/api/v1/settlements/generate",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
        json={
            "shipment_id": ship_id,
            "deductions": deductions
        }
    )
    assert res.status_code in (200, 201)
    settlement = res.json()
    gross = 500_000 * 45  # 22,500,000 paise
    assert settlement["gross_amount_paise"] == gross
    assert settlement["total_deductions_paise"] == 236_250 + 150_000
    assert settlement["net_payable_paise"] == gross - (236_250 + 150_000)
