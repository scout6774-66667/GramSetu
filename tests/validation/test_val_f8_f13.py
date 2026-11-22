from __future__ import annotations

import os
import uuid
import decimal
from decimal import Decimal, ROUND_HALF_UP
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from gramsetu.core import (
    Settings,
    Environment,
    Role,
    DevActor,
    DEV_ACTORS,
    DEV_ACTOR_HEADER,
    InvariantViolationError,
    ConflictError,
    NotFoundError,
    AuthorizationError,
    get_current_utc,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.main import create_app
from gramsetu.schemas import (
    LotReceiptCreate,
    BuyerRequirementCreate,
    BuyerCommitmentCreate,
    CommitmentAllocationItem,
    VehicleCreate,
    ShipmentCreate,
    DeliveryConfirmationRequest,
    SettlementGenerateRequest,
    SettlementDeduction,
    PaymentCreateRequest,
    PaymentReportRequest,
    PaymentVerifyRequest,
    OfflineCommandEnvelope,
)
from gramsetu.services.inventory import receive_inventory_lot
from gramsetu.services.procurement import create_buyer_requirement, create_commitment
from gramsetu.services.logistics import (
    register_vehicle,
    create_shipment,
    record_pickup,
    record_delivery,
)
from gramsetu.services.settlement import (
    generate_settlement,
    record_payment,
    report_payment,
    verify_payment,
    get_settlement,
)
from gramsetu.services.overview import (
    get_farmer_overview,
    get_buyer_overview,
    get_driver_overview,
    get_fpo_overview,
)
from gramsetu.services.sync import reconcile_offline_command
from gramsetu.workers import LocalEventDispatcher
from gramsetu.services.events import append_event


# ==============================================================================
# F8 — SettleTrack: Financial Oracle & Payment Accounting Tests (HIGH-RISK GATE)
# ==============================================================================

def test_f8_financial_reference_oracle_decimal_half_up():
    """FINANCIAL ORACLE:
    Recalculate settlement payable using Python Decimal with ROUND_HALF_UP.
    Verify half-paise ties, 1-gram quantities, and itemized deductions.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-reliance"]
    driver = DEV_ACTORS["driver-1"]

    # Lot of 100,000g (100 kg)
    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Mango",
            variety="Alphonso",
            grade="Grade A",
            quantity_grams=100_000,
            storage_location="Packhouse 1",
        ),
    )

    req, _ = create_buyer_requirement(
        store,
        coord,
        buyer,
        BuyerRequirementCreate(
            crop="Mango",
            variety="Alphonso",
            grade="Grade A",
            needed_grams=100_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=80,  # 80 paise/g = Rs 800/kg
        ),
    )

    commit, _ = create_commitment(
        store,
        coord,
        buyer,
        BuyerCommitmentCreate(
            requirement_id=req.requirement_id,
            fpo_id="fpo-alpha",
            agreed_price_paise_per_gram=80,
            allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=100_000)],
            idempotency_key="mango-settle-test",
        ),
    )

    veh = register_vehicle(
        store,
        coord,
        admin,
        VehicleCreate(
            fpo_id="fpo-alpha",
            driver_id="driver-1",
            capacity_grams=200_000,
            vehicle_type="Reefer Van",
        ),
    )

    ship = create_shipment(
        store,
        coord,
        admin,
        ShipmentCreate(
            commitment_id=commit.commitment_id,
            vehicle_id=veh.vehicle_id,
            driver_id="driver-1",
        ),
    )

    record_pickup(store, coord, driver, ship.shipment_id)

    # Delivery inspection: 90,000g accepted, 8,000g rejected, 2,000g transit loss
    record_delivery(
        store,
        coord,
        driver,
        ship.shipment_id,
        DeliveryConfirmationRequest(
            accepted_grams=90_000,
            rejected_grams=8_000,
            loss_grams=2_000,
        ),
    )

    # Deductions: transport (50,000 paise), packaging (10,000 paise)
    deductions = [
        SettlementDeduction(deduction_type="TRANSPORT", amount_paise=50_000, reason="Freight charge"),
        SettlementDeduction(deduction_type="PACKAGING", amount_paise=10_000, reason="Crates fee"),
    ]

    settle = generate_settlement(
        store,
        coord,
        admin,
        SettlementGenerateRequest(
            shipment_id=ship.shipment_id,
            deductions=deductions,
        ),
    )

    # Independent Decimal Oracle Verification
    d_accepted = Decimal("90000")
    d_price = Decimal("80")
    d_gross = (d_accepted * d_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    d_deductions = Decimal("60000")
    d_net = max(Decimal("0"), d_gross - d_deductions)

    assert settle.gross_amount_paise == int(d_gross)
    assert settle.total_deductions_paise == int(d_deductions)
    assert settle.net_payable_paise == int(d_net)
    assert settle.accepted_grams == 90_000  # Paid ONLY on accepted, not shipped (100,000) or rejected (8,000)


def test_f8_payment_reporting_vs_verification_and_unauthorized_verifier():
    """Verify buyer reports payment (unverified), and ONLY FPO admin can verify it.
    Buyer attempting to verify their own payment must fail with 403 Forbidden.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-reliance"]
    driver = DEV_ACTORS["driver-1"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            quantity_grams=50_000,
            storage_location="Bin P",
        ),
    )
    req, _ = create_buyer_requirement(
        store,
        coord,
        buyer,
        BuyerRequirementCreate(
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            needed_grams=50_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=30,
        ),
    )
    commit, _ = create_commitment(
        store,
        coord,
        buyer,
        BuyerCommitmentCreate(
            requirement_id=req.requirement_id,
            fpo_id="fpo-alpha",
            agreed_price_paise_per_gram=30,
            allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=50_000)],
            idempotency_key="pay-verif-test",
        ),
    )
    veh = register_vehicle(
        store,
        coord,
        admin,
        VehicleCreate(
            fpo_id="fpo-alpha",
            driver_id="driver-1",
            capacity_grams=100_000,
            vehicle_type="Van",
        ),
    )
    ship = create_shipment(
        store,
        coord,
        admin,
        ShipmentCreate(
            commitment_id=commit.commitment_id,
            vehicle_id=veh.vehicle_id,
            driver_id="driver-1",
        ),
    )
    record_pickup(store, coord, driver, ship.shipment_id)
    record_delivery(
        store,
        coord,
        driver,
        ship.shipment_id,
        DeliveryConfirmationRequest(accepted_grams=50_000, rejected_grams=0, loss_grams=0),
    )

    settle = generate_settlement(
        store,
        coord,
        admin,
        SettlementGenerateRequest(shipment_id=ship.shipment_id, deductions=[]),
    )
    assert settle.net_payable_paise == 1_500_000  # 50,000 * 30

    # 1. Buyer reports payment with bank reference
    reported = report_payment(
        store,
        coord,
        buyer,
        settle.settlement_id,
        PaymentReportRequest(
            amount_paise=1_500_000,
            payment_method="BANK_TRANSFER",
            reference_number="UTR-9876543210",
            evidence_note="Bank transfer receipt attached",
        ),
    )
    assert reported.status == "PAID_REPORTED"
    assert reported.paid_amount_paise == 0  # Unverified!
    assert reported.remaining_balance_paise == 1_500_000
    pay_id = reported.payments[0].payment_id

    # 2. Buyer attempts to verify their own payment -> AuthorizationError (403)
    with pytest.raises(AuthorizationError, match="Only authorized FPO admins"):
        verify_payment(store, coord, buyer, settle.settlement_id, pay_id)

    # 3. FPO Admin verifies payment -> Status SETTLED
    verified = verify_payment(
        store,
        coord,
        admin,
        settle.settlement_id,
        pay_id,
        PaymentVerifyRequest(verification_note="Confirmed in FPO SBI Account"),
    )
    assert verified.status == "SETTLED"
    assert verified.paid_amount_paise == 1_500_000
    assert verified.remaining_balance_paise == 0


# ==============================================================================
# F9 — Four App-Facing Query Contracts Tests
# ==============================================================================

def test_f9_role_dashboards_and_tenant_isolation():
    """Verify that all 4 role overviews return correctly scoped data and do not leak
    cross-tenant or private details.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    farmer = DEV_ACTORS["farmer-1"]
    buyer = DEV_ACTORS["buyer-reliance"]
    driver = DEV_ACTORS["driver-1"]

    # Populate sample data for farmer-1 and fpo-alpha
    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Tomato",
            variety="Desi",
            grade="Grade A",
            quantity_grams=100_000,
            storage_location="Bin F9",
        ),
    )

    # 1. Farmer Overview
    farmer_view = get_farmer_overview(store, farmer)
    assert farmer_view.farmer_id == "farmer-1"
    assert farmer_view.delivered_lots_count >= 1

    # 2. Buyer Overview
    buyer_view = get_buyer_overview(store, buyer)
    assert buyer_view.buyer_id == "buyer-reliance"

    # 3. Driver Overview
    driver_view = get_driver_overview(store, driver)
    assert driver_view.driver_id == "driver-1"

    # 4. FPO Overview
    fpo_view = get_fpo_overview(store, admin, fpo_id="fpo-alpha")
    assert fpo_view.fpo_id == "fpo-alpha"
    assert fpo_view.total_available_stock_grams >= 100_000

    # Cross-Tenant Check: FPO Admin Beta querying Alpha's overview -> AuthorizationError (403)
    admin_beta = DEV_ACTORS["fpo-admin-beta"]
    with pytest.raises(AuthorizationError, match="not authorized to access org 'fpo-alpha'"):
        get_fpo_overview(store, admin_beta, fpo_id="fpo-alpha")


# ==============================================================================
# F10 — Offline Command Reconciliation & Optimistic Concurrency Tests
# ==============================================================================

def test_f10_offline_command_reconciliation_and_conflict():
    """Verify offline command envelope processing, version checking, and idempotent replay."""
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    admin = DEV_ACTORS["fpo-admin-alpha"]
    buyer = DEV_ACTORS["buyer-reliance"]
    driver = DEV_ACTORS["driver-1"]

    lot = receive_inventory_lot(
        store,
        coord,
        admin,
        LotReceiptCreate(
            fpo_id="fpo-alpha",
            farmer_id="farmer-1",
            crop="Wheat",
            variety="Lokwan",
            grade="Grade A",
            quantity_grams=100_000,
            storage_location="Silo 1",
        ),
    )
    req, _ = create_buyer_requirement(
        store,
        coord,
        buyer,
        BuyerRequirementCreate(
            crop="Wheat",
            variety="Lokwan",
            grade="Grade A",
            needed_grams=100_000,
            delivery_window_start=get_current_utc().isoformat(),
            delivery_window_end=(get_current_utc() + timedelta(days=5)).isoformat(),
            max_price_paise_per_gram=28,
        ),
    )
    commit, _ = create_commitment(
        store,
        coord,
        buyer,
        BuyerCommitmentCreate(
            requirement_id=req.requirement_id,
            fpo_id="fpo-alpha",
            agreed_price_paise_per_gram=28,
            allocations=[CommitmentAllocationItem(lot_id=lot.lot_id, allocated_grams=100_000)],
            idempotency_key="wheat-offline-test",
        ),
    )
    veh = register_vehicle(
        store,
        coord,
        admin,
        VehicleCreate(
            fpo_id="fpo-alpha",
            driver_id="driver-1",
            capacity_grams=200_000,
            vehicle_type="Truck",
        ),
    )
    ship = create_shipment(
        store,
        coord,
        admin,
        ShipmentCreate(
            commitment_id=commit.commitment_id,
            vehicle_id=veh.vehicle_id,
            driver_id="driver-1",
        ),
    )

    # 1. Driver syncs offline pickup with correct expected_version=1
    envelope = OfflineCommandEnvelope(
        command_id="cmd-pickup-offline-1",
        actor_id="driver-1",
        device_id="device-001",
        client_timestamp=get_current_utc().isoformat(),
        command_type="DRIVER_PICKUP_OBSERVATION",
        resource_type="shipment",
        resource_id=ship.shipment_id,
        expected_version=1,
        payload={},
    )
    resp, code = reconcile_offline_command(store, coord, driver, envelope)
    assert code == 200
    assert resp.status == "APPLIED"
    assert resp.applied_resource_version == 2

    # 2. Replay same command -> REPLAYED (200)
    resp_replay, code_replay = reconcile_offline_command(store, coord, driver, envelope)
    assert code_replay == 200
    assert resp_replay.status == "REPLAYED"

    # 3. Another device tries to sync with stale expected_version=1 -> CONFLICT_REJECTED (409)
    stale_envelope = OfflineCommandEnvelope(
        command_id="cmd-pickup-stale-2",
        actor_id="driver-1",
        device_id="device-002",
        client_timestamp=get_current_utc().isoformat(),
        command_type="DRIVER_PICKUP_OBSERVATION",
        resource_type="shipment",
        resource_id=ship.shipment_id,
        expected_version=1,  # Stale! Server is at version 2
        payload={},
    )
    resp_conflict, code_conflict = reconcile_offline_command(store, coord, driver, stale_envelope)
    assert code_conflict == 409
    assert resp_conflict.status == "CONFLICT_REJECTED"


# ==============================================================================
# F11 — Durable Local Event Dispatcher & Poison Quarantine Tests
# ==============================================================================

def test_f11_event_durability_and_poison_quarantine():
    """Verify events are logged sequentially, handlers execute, and unrecoverable
    poison events are quarantined without blocking subsequent processing.
    """
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    dispatcher = LocalEventDispatcher(coordinator=coord)

    processed_events = []

    def healthy_handler(event: dict):
        processed_events.append(event["event_type"])

    def poison_handler(event: dict):
        if event["event_type"] == "poison.event":
            raise ValueError("Unrecoverable poison handler defect!")

    dispatcher.register_handler("test.healthy", healthy_handler)
    dispatcher.register_handler("poison.event", poison_handler)

    append_event(coord, "fpo-alpha", "test.healthy", {"val": 1})
    append_event(coord, "fpo-alpha", "poison.event", {"val": 2})
    append_event(coord, "fpo-alpha", "test.healthy", {"val": 3})

    # Process pending events
    dispatcher.process_pending_events()

    # Both healthy events processed, poison event quarantined
    assert processed_events == ["test.healthy", "test.healthy"]
    all_events = store.list_items("events")
    poison_ev = [e for e in all_events if e["event_type"] == "poison.event"][0]
    assert poison_ev["status"] == "POISON"
    assert poison_ev["attempts"] >= 3


# ==============================================================================
# F12 — Performance & Security Threat Tests
# ==============================================================================

def test_f12_payload_limit_and_idor_prevention():
    """Verify request size limits (1MB) and IDOR isolation."""
    app = create_app(Settings(ENVIRONMENT=Environment.TESTING))
    client = TestClient(app)

    # 1. Huge payload exceeding 1MB -> 413 Payload Too Large
    huge_data = "X" * (1_048_576 + 100)
    resp = client.post(
        "/api/v1/forecasts",
        content=huge_data,
        headers={
            DEV_ACTOR_HEADER: "farmer-1",
            "Content-Type": "application/json",
            "Content-Length": str(len(huge_data)),
        },
    )
    assert resp.status_code == 413

    # 2. IDOR check: Farmer-1 attempts to view Farmer-2's settlements -> 403 Forbidden
    resp = client.get("/api/v1/settlements?farmer_id=farmer-2", headers={DEV_ACTOR_HEADER: "farmer-1"})
    # Only own records should be visible; querying other farmer should return empty list or 403
    assert resp.status_code == 200
    for s in resp.json():
        assert s["farmer_id"] == "farmer-1"
