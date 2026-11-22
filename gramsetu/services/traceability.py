"""GramSetu AI BatchTrace Chronological Traceability Service (Module 8).

Reconstructs the full end-to-end chain-of-custody and transformation timeline
for any inventory lot from harvest forecasting to final financial settlement:
1. Forecast -> 2. Physical Receipt -> 3. Regrade/Split/Merge ->
4. Storage Movement -> 5. Commitment Allocation -> 6. Shipment Dispatch ->
7. Transport Pickup -> 8. Delivery Acceptance / Inspection -> 9. Final Payment Settlement.

Strictly distinguishes recorded internal ledger events from unverified physical weighbridge
or external bank confirmations without fabricating evidence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    NotFoundError,
    get_current_utc,
)
from gramsetu.store import InMemoryStore
from gramsetu.schemas import (
    TraceabilityMilestone,
    BatchTraceTimelineResponse,
)


def get_lot_traceability_timeline(
    store: InMemoryStore,
    actor: DevActor,
    lot_id: str,
) -> BatchTraceTimelineResponse:
    """Reconstruct complete chronological lifecycle for produce lot."""
    lot = store.get_item("lots", lot_id)
    if not lot:
        raise NotFoundError(f"Produce lot '{lot_id}' not found in inventory registry.")

    milestones: List[TraceabilityMilestone] = []
    farmer_id = lot.get("farmer_id", "farmer-1")
    fpo_id = lot.get("fpo_id", "fpo-alpha")
    crop = lot.get("crop", "Unknown Crop")
    grade = lot.get("grade", "A")

    # 1. Harvest Forecast Milestone
    forecasts = store.list_items("forecasts", lambda it: it.get("farmer_id") == farmer_id and it.get("crop") == crop)
    if forecasts:
        fc = forecasts[0]
        milestones.append(
            TraceabilityMilestone(
                milestone_id=f"ms-fc-{fc['forecast_id']}",
                timestamp=datetime.fromisoformat(fc["created_at"]),
                stage="FORECAST",
                actor_id=farmer_id,
                actor_role="FARMER",
                title="Harvest Anticipation Recorded",
                description=f"Farmer {farmer_id} recorded expected harvest of {round(fc['estimated_grams']/1000.0, 1)} kg {crop}.",
                quantity_grams=fc["estimated_grams"],
                evidence_type="FARMER_SELF_DECLARATION",
                verification_level="UNVERIFIED_SELF_REPORTED",
                details={"confidence_score": fc.get("confidence_score", 0.8)},
            )
        )

    # 2. Physical Receipt Milestone
    receipt_dt = datetime.fromisoformat(lot["created_at"]) if isinstance(lot["created_at"], str) else lot["created_at"]
    milestones.append(
        TraceabilityMilestone(
            milestone_id=f"ms-rcpt-{lot_id}",
            timestamp=receipt_dt,
            stage="RECEIPT",
            actor_id=lot.get("fpo_id", "fpo-alpha"),
            actor_role="FPO_ADMIN",
            title="Physical Stock Received at Silo",
            description=f"FPO intake confirmed {round(lot['quantity_grams']/1000.0, 1)} kg {crop} Grade {grade} into {lot.get('storage_location', 'Bay-1')}.",
            quantity_grams=lot["quantity_grams"],
            evidence_type="FPO_INTAKE_SLIP",
            verification_level="OPERATOR_CONFIRMED_MANUAL",
            details={"storage_location": lot.get("storage_location")},
        )
    )

    # 3. Lot Movements (Splits, Merges, Regrades)
    movements = store.list_items("movements", lambda it: it.get("lot_id") == lot_id)
    for m in sorted(movements, key=lambda x: x["created_at"]):
        m_dt = datetime.fromisoformat(m["created_at"]) if isinstance(m["created_at"], str) else m["created_at"]
        milestones.append(
            TraceabilityMilestone(
                milestone_id=f"ms-mov-{m['movement_id']}",
                timestamp=m_dt,
                stage=m.get("movement_type", "MOVEMENT"),
                actor_id=m.get("recorded_by", "fpo-admin-alpha"),
                actor_role="FPO_ADMIN",
                title=f"Stock Operation: {m.get('movement_type')}",
                description=f"Custody transferred from {m.get('source_custody')} to {m.get('dest_custody')}.",
                quantity_grams=m.get("quantity_grams"),
                evidence_type="INTERNAL_JOURNAL_MUTATION",
                verification_level="OPERATOR_CONFIRMED_MANUAL",
                details=m,
            )
        )

    # 4. Commitments Allocation
    commitments = store.list_items(
        "commitments",
        lambda c: any(alloc.get("lot_id") == lot_id for alloc in c.get("allocations", [])),
    )
    for c in commitments:
        c_dt = datetime.fromisoformat(c["created_at"]) if isinstance(c["created_at"], str) else c["created_at"]
        alloc_qty = sum(a.get("allocated_grams", 0) for a in c.get("allocations", []) if a.get("lot_id") == lot_id)
        milestones.append(
            TraceabilityMilestone(
                milestone_id=f"ms-com-{c['commitment_id']}",
                timestamp=c_dt,
                stage="ALLOCATION",
                actor_id=c.get("buyer_id", "buyer-reliance"),
                actor_role="BUYER",
                title="Buyer Commitment Allocation",
                description=f"Allocated {round(alloc_qty/1000.0, 1)} kg to Buyer {c.get('buyer_id')} at agreed price {c.get('agreed_price_paise_per_gram')} paise/g.",
                quantity_grams=alloc_qty,
                evidence_type="SIGNED_PURCHASE_COMMITMENT",
                verification_level="BUYER_COUNTERPARTY_CONFIRMED",
                details={"agreed_price_paise_per_gram": c.get("agreed_price_paise_per_gram")},
            )
        )

        # 5. Shipments linked to commitment
        shipments = store.list_items("shipments", lambda s: s.get("commitment_id") == c["commitment_id"])
        for s in shipments:
            s_dt = datetime.fromisoformat(s["created_at"]) if isinstance(s["created_at"], str) else s["created_at"]
            milestones.append(
                TraceabilityMilestone(
                    milestone_id=f"ms-ship-{s['shipment_id']}",
                    timestamp=s_dt,
                    stage="SHIPMENT",
                    actor_id=s.get("driver_id", "driver-1"),
                    actor_role="DRIVER",
                    title="Shipment Created & Fleet Assigned",
                    description=f"Vehicle {s.get('vehicle_id')} assigned under driver {s.get('driver_id')}.",
                    quantity_grams=s.get("dispatched_grams"),
                    evidence_type="CONSIGNMENT_WAYBILL",
                    verification_level="CARRIER_DISPATCH_RECORD",
                    details=s,
                )
            )

            # Pickup
            if s.get("actual_pickup_time"):
                p_dt = datetime.fromisoformat(s["actual_pickup_time"]) if isinstance(s["actual_pickup_time"], str) else s["actual_pickup_time"]
                milestones.append(
                    TraceabilityMilestone(
                        milestone_id=f"ms-pick-{s['shipment_id']}",
                        timestamp=p_dt,
                        stage="PICKUP",
                        actor_id=s.get("driver_id", "driver-1"),
                        actor_role="DRIVER",
                        title="Carrier Custody Handover (Pickup)",
                        description=f"Driver confirmed custody pickup from warehouse silo.",
                        quantity_grams=s.get("dispatched_grams"),
                        evidence_type="CARRIER_RECEIPT",
                        verification_level="DRIVER_CONFIRMED_MOBILE",
                        details={"status": s.get("status")},
                    )
                )

            # Delivery
            if s.get("actual_delivery_time"):
                d_dt = datetime.fromisoformat(s["actual_delivery_time"]) if isinstance(s["actual_delivery_time"], str) else s["actual_delivery_time"]
                milestones.append(
                    TraceabilityMilestone(
                        milestone_id=f"ms-del-{s['shipment_id']}",
                        timestamp=d_dt,
                        stage="DELIVERY",
                        actor_id=c.get("buyer_id", "buyer-reliance"),
                        actor_role="BUYER",
                        title="Destination Terminal Delivery & Quality Inspection",
                        description=f"Accepted: {round(s.get('accepted_grams', 0)/1000.0, 1)} kg | Rejected: {round(s.get('rejected_grams', 0)/1000.0, 1)} kg | Loss: {round(s.get('loss_grams', 0)/1000.0, 1)} kg.",
                        quantity_grams=s.get("accepted_grams"),
                        evidence_type="INSPECTION_ACCEPTANCE_CERTIFICATE",
                        verification_level="DESTINATION_INSPECTION_RECORD",
                        details={"accepted_grams": s.get("accepted_grams"), "loss_grams": s.get("loss_grams")},
                    )
                )

            # 6. Settlement linked to shipment
            settlements = store.list_items("settlements", lambda st: st.get("shipment_id") == s["shipment_id"])
            for st in settlements:
                st_dt = datetime.fromisoformat(st["created_at"]) if isinstance(st["created_at"], str) else st["created_at"]
                milestones.append(
                    TraceabilityMilestone(
                        milestone_id=f"ms-set-{st['settlement_id']}",
                        timestamp=st_dt,
                        stage="SETTLEMENT",
                        actor_id=st.get("fpo_id", "fpo-alpha"),
                        actor_role="FPO_ADMIN",
                        title="Final Financial Settlement Generated",
                        description=f"Gross ₹{round(st.get('gross_amount_paise', 0)/100.0, 2)} - Deductions ₹{round(st.get('total_deductions_paise', 0)/100.0, 2)} = Net ₹{round(st.get('net_payable_paise', 0)/100.0, 2)}.",
                        quantity_grams=st.get("accepted_grams"),
                        evidence_type="TAX_INVOICE_SETTLEMENT_VOUCHER",
                        verification_level="OPERATOR_APPROVED_LEDGER",
                        details={"net_payable_paise": st.get("net_payable_paise"), "status": st.get("status")},
                    )
                )

    # Sort milestones chronologically
    sorted_milestones = sorted(milestones, key=lambda m: m.timestamp)

    return BatchTraceTimelineResponse(
        lot_id=lot_id,
        fpo_id=fpo_id,
        farmer_id=farmer_id,
        crop=crop,
        variety=lot.get("variety"),
        grade=grade,
        initial_quantity_grams=lot.get("quantity_grams", 0),
        current_quantity_grams=lot.get("quantity_grams", 0),
        current_custody=lot.get("custody", "FPO_WAREHOUSE"),
        status=lot.get("status", "AVAILABLE"),
        created_at=receipt_dt,
        milestones=sorted_milestones,
        chain_of_custody_verified=False,
        verification_notice=(
            "Events reflect internal transaction ledger. Physical weighbridge telemetry and "
            "bank credit confirmations are unverified self-reported entries."
        ),
    )
