from __future__ import annotations

import uuid
from typing import List, Optional
from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    InvariantViolationError,
    get_current_utc,
    verify_organization_access,
    verify_farmer_access,
    verify_buyer_access,
)
from gramsetu.schemas import (
    SettlementGenerateRequest,
    PaymentCreateRequest,
    PaymentReportRequest,
    PaymentVerifyRequest,
    SettlementResponse,
    PaymentRecord,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.adapters.evidence import EvidenceManager, compute_payload_digest
from gramsetu.units import calculate_gross_paise, gross_paise_half_up


def generate_settlement(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: SettlementGenerateRequest,
) -> SettlementResponse:
    """Generate payable settlement based strictly on authorized accepted produce mass."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins or system engine can generate settlements.")

    with coordinator.transaction():
        ship = coordinator.store.get_item("shipments", payload.shipment_id)
        if not ship:
            raise NotFoundError(f"Shipment '{payload.shipment_id}' not found.")

        commit = coordinator.store.get_item("commitments", ship.get("commitment_id", ""))
        if not commit:
            raise NotFoundError(f"Commitment '{ship.get('commitment_id')}' not found.")

        verify_organization_access(actor, commit["fpo_id"])

        if ship.get("status") != "DELIVERED":
            raise InvariantViolationError(
                f"Cannot generate settlement for shipment with status '{ship.get('status')}'. Delivery must be confirmed."
            )

        # Farmer identified from lot in commitment allocations
        farmer_id = "COMMUNITY_FARMERS"
        if commit.get("allocations"):
            lot = coordinator.store.get_item("lots", commit["allocations"][0]["lot_id"])
            if lot:
                farmer_id = lot.get("farmer_id", farmer_id)

        accepted_grams = ship.get("accepted_grams") or 0
        if "agreed_price_paise_per_kg" in commit:
            gross_paise = calculate_gross_paise(accepted_grams, commit["agreed_price_paise_per_kg"])
            unit_price = commit.get("agreed_price_paise_per_gram", commit["agreed_price_paise_per_kg"] // 1000)
        else:
            unit_price = commit.get("agreed_price_paise_per_gram", 0)
            gross_paise = calculate_gross_paise(accepted_grams, unit_price * 1000)

        total_deductions = sum(d.amount_paise for d in payload.deductions)
        net_payable = max(0, gross_paise - total_deductions)

        # Zero payable is immediately SETTLED rather than an overdue debt
        initial_status = "SETTLED" if net_payable == 0 else "PENDING"
        now = get_current_utc().isoformat()
        settle_id = f"set-{uuid.uuid4().hex[:10]}"

        record = {
            "settlement_id": settle_id,
            "shipment_id": ship["shipment_id"],
            "commitment_id": commit["commitment_id"],
            "fpo_id": commit["fpo_id"],
            "farmer_id": farmer_id,
            "buyer_id": commit["buyer_id"],
            "accepted_grams": accepted_grams,
            "unit_price_paise_per_gram": unit_price,
            "gross_amount_paise": gross_paise,
            "deductions": [d.model_dump() for d in payload.deductions],
            "total_deductions_paise": total_deductions,
            "net_payable_paise": net_payable,
            "paid_amount_paise": 0,
            "remaining_balance_paise": net_payable,
            "payments": [],
            "audit_events": [f"Settlement generated on {now} for accepted {accepted_grams}g produce."],
            "status": initial_status,
            "created_at": now,
            "updated_at": now,
        }
        coordinator.store.set_item("settlements", settle_id, record)

    return SettlementResponse(**record)


def record_payment(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    settlement_id: str,
    payload: PaymentCreateRequest,
) -> SettlementResponse:
    """Record a verified payment transaction against a pending settlement."""
    if actor.role not in (Role.FPO_ADMIN, Role.BUYER, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins, buyers, or system engine can record payments.")

    with coordinator.transaction():
        settle = coordinator.store.get_item("settlements", settlement_id)
        if not settle:
            raise NotFoundError(f"Settlement '{settlement_id}' not found.")

        if actor.role == Role.FPO_ADMIN:
            verify_organization_access(actor, settle["fpo_id"])
        elif actor.role == Role.BUYER:
            verify_buyer_access(actor, settle["buyer_id"])

        if settle.get("status") == "SETTLED" and settle["remaining_balance_paise"] == 0:
            raise InvariantViolationError("Settlement is already fully paid and settled.")

        # Check duplicate reference
        for p in settle.get("payments", []):
            if p["reference_number"] == payload.reference_number:
                raise ConflictError(
                    f"Payment reference '{payload.reference_number}' has already been processed for this settlement."
                )

        # Overpayment check
        if payload.amount_paise > settle["remaining_balance_paise"]:
            raise InvariantViolationError(
                f"Payment amount ({payload.amount_paise} paise) exceeds remaining payable balance "
                f"({settle['remaining_balance_paise']} paise)."
            )

        now = get_current_utc().isoformat()
        pay_id = f"pay-{uuid.uuid4().hex[:10]}"

        # Register tamper-evident provenance record
        evidence = EvidenceManager.register_payment_evidence(
            store=coordinator.store,
            coordinator=coordinator,
            actor=actor,
            reference_number=payload.reference_number,
            amount_paise=payload.amount_paise,
            raw_payload=payload.model_dump(),
            source_type="OPERATOR_MANUAL",
        )

        payment = {
            "payment_id": pay_id,
            "amount_paise": payload.amount_paise,
            "payment_method": payload.payment_method,
            "reference_number": payload.reference_number,
            "recorded_by": actor.actor_id,
            "recorded_at": now,
            "verified": True,
            "verified_by": actor.actor_id,
            "evidence_id": evidence.evidence_id,
            "verification_status": "OPERATOR_CONFIRMED",
            "payload_digest": evidence.payload_digest,
            "source_type": "OPERATOR_MANUAL",
        }

        settle["payments"].append(payment)
        settle["paid_amount_paise"] += payload.amount_paise
        settle["remaining_balance_paise"] -= payload.amount_paise

        if settle["remaining_balance_paise"] == 0:
            settle["status"] = "SETTLED"
        else:
            settle["status"] = "PARTIALLY_PAID"

        settle["updated_at"] = now
        settle["audit_events"].append(
            f"Payment of {payload.amount_paise} paise recorded via {payload.payment_method} "
            f"(Ref: {payload.reference_number}) by {actor.actor_id}."
        )
        coordinator.store.set_item("settlements", settlement_id, settle)

    return SettlementResponse(**settle)


def report_payment(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    settlement_id: str,
    payload: PaymentReportRequest,
) -> SettlementResponse:
    """Buyer reports a payment with reference and evidence. Does NOT mark as verified until authorized verification."""
    if actor.role not in (Role.BUYER, Role.SYSTEM):
        raise AuthorizationError("Only buyers or system engine can report payments.")

    with coordinator.transaction():
        settle = coordinator.store.get_item("settlements", settlement_id)
        if not settle:
            raise NotFoundError(f"Settlement '{settlement_id}' not found.")
        verify_buyer_access(actor, settle["buyer_id"])

        if settle.get("status") == "SETTLED" and settle["remaining_balance_paise"] == 0:
            raise InvariantViolationError("Settlement is already fully paid and settled.")

        # Check duplicate reference
        for p in settle.get("payments", []):
            if p["reference_number"] == payload.reference_number:
                raise ConflictError(
                    f"Payment reference '{payload.reference_number}' has already been reported for this settlement."
                )

        if payload.amount_paise > settle["remaining_balance_paise"]:
            raise InvariantViolationError(
                f"Reported payment ({payload.amount_paise} paise) exceeds remaining payable balance "
                f"({settle['remaining_balance_paise']} paise)."
            )

        now = get_current_utc().isoformat()
        pay_id = f"pay-{uuid.uuid4().hex[:10]}"

        # Register tamper-evident provenance record
        evidence = EvidenceManager.register_payment_evidence(
            store=coordinator.store,
            coordinator=coordinator,
            actor=actor,
            reference_number=payload.reference_number,
            amount_paise=payload.amount_paise,
            raw_payload=payload.model_dump(),
            source_type="BANK_API",
        )

        payment = {
            "payment_id": pay_id,
            "amount_paise": payload.amount_paise,
            "payment_method": payload.payment_method,
            "reference_number": payload.reference_number,
            "evidence_note": payload.evidence_note,
            "recorded_by": actor.actor_id,
            "recorded_at": now,
            "verified": False,
            "verified_by": None,
            "verified_at": None,
            "evidence_id": evidence.evidence_id,
            "verification_status": "REPORTED",
            "payload_digest": evidence.payload_digest,
            "source_type": "BANK_API",
        }

        settle["payments"].append(payment)
        if settle["status"] == "PENDING":
            settle["status"] = "PAID_REPORTED"
        settle["updated_at"] = now
        settle["audit_events"].append(
            f"Payment report of {payload.amount_paise} paise submitted via {payload.payment_method} "
            f"(Ref: {payload.reference_number}, Evidence: '{payload.evidence_note}') by buyer {actor.actor_id}. Pending FPO verification."
        )
        coordinator.store.set_item("settlements", settlement_id, settle)

    return SettlementResponse(**settle)


def verify_payment(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    settlement_id: str,
    payment_id: str,
    payload: Optional[PaymentVerifyRequest] = None,
) -> SettlementResponse:
    """Authorized FPO admin verifies reported payment evidence, reducing payable balance."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only authorized FPO admins or system engine can verify payment evidence.")

    with coordinator.transaction():
        settle = coordinator.store.get_item("settlements", settlement_id)
        if not settle:
            raise NotFoundError(f"Settlement '{settlement_id}' not found.")
        verify_organization_access(actor, settle["fpo_id"])

        target_payment = None
        for p in settle.get("payments", []):
            if p["payment_id"] == payment_id:
                target_payment = p
                break

        if not target_payment:
            raise NotFoundError(f"Payment record '{payment_id}' not found in settlement.")

        if target_payment.get("verified", False):
            return SettlementResponse(**settle)

        now = get_current_utc().isoformat()
        target_payment["verified"] = True
        target_payment["verified_by"] = actor.actor_id
        target_payment["verified_at"] = now

        ext_token = getattr(payload, "external_token", None) if payload else None
        if target_payment.get("evidence_id"):
            confirmed_evi = EvidenceManager.confirm_evidence(
                store=coordinator.store,
                coordinator=coordinator,
                actor=actor,
                evidence_id=target_payment["evidence_id"],
                external_confirmation_token=ext_token,
            )
            target_payment["verification_status"] = confirmed_evi.verification_status.value
        else:
            target_payment["verification_status"] = "OPERATOR_CONFIRMED"

        settle["paid_amount_paise"] += target_payment["amount_paise"]
        settle["remaining_balance_paise"] = max(0, settle["remaining_balance_paise"] - target_payment["amount_paise"])

        if settle["remaining_balance_paise"] == 0:
            settle["status"] = "SETTLED"
        else:
            settle["status"] = "PARTIALLY_PAID"

        settle["updated_at"] = now
        note = payload.verification_note if payload and payload.verification_note else "Verified with bank credit advice"
        settle["audit_events"].append(
            f"Payment '{payment_id}' ({target_payment['amount_paise']} paise) verified by {actor.actor_id}. Note: {note}"
        )
        coordinator.store.set_item("settlements", settlement_id, settle)

    return SettlementResponse(**settle)


def get_settlement(store: InMemoryStore, actor: DevActor, settlement_id: str) -> SettlementResponse:
    settle = store.get_item("settlements", settlement_id)
    if not settle:
        raise NotFoundError(f"Settlement '{settlement_id}' not found.")
    if actor.role == Role.FARMER:
        verify_farmer_access(actor, settle["farmer_id"])
    elif actor.role == Role.BUYER:
        verify_buyer_access(actor, settle["buyer_id"])
    elif actor.role == Role.FPO_ADMIN:
        verify_organization_access(actor, settle["fpo_id"])
    return SettlementResponse(**settle)


def list_settlements(
    store: InMemoryStore,
    actor: DevActor,
    fpo_id: Optional[str] = None,
    farmer_id: Optional[str] = None,
    buyer_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[SettlementResponse]:
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.FARMER and item.get("farmer_id") != actor.actor_id:
            return False
        if actor.role == Role.BUYER and item.get("buyer_id") != actor.actor_id:
            return False
        if actor.role == Role.FPO_ADMIN and item.get("fpo_id") != actor.organization_id:
            return False
        if fpo_id and item.get("fpo_id") != fpo_id:
            return False
        if farmer_id and item.get("farmer_id") != farmer_id:
            return False
        if buyer_id and item.get("buyer_id") != buyer_id:
            return False
        if status and item.get("status", "").upper() != status.upper():
            return False
        return True

    items = store.list_items("settlements", filter_fn)
    return [SettlementResponse(**item) for item in items]
