from __future__ import annotations

from typing import Tuple
from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    InvariantViolationError,
    get_current_utc,
)
from gramsetu.schemas import (
    OfflineCommandEnvelope,
    ReconciliationResponse,
    DeliveryConfirmationRequest,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.services.logistics import record_pickup, record_delivery


ALLOWED_OFFLINE_COMMANDS = {
    "DRIVER_PICKUP_OBSERVATION",
    "DRIVER_DELIVERY_OBSERVATION",
    "FARMER_FORECAST_DRAFT",
}


def reconcile_offline_command(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    envelope: OfflineCommandEnvelope,
) -> Tuple[ReconciliationResponse, int]:
    """Reconcile an offline client command envelope with optimistic concurrency version checking and idempotent replay."""
    # Scope check: actor must match envelope actor
    if actor.role != Role.SYSTEM and actor.actor_id != envelope.actor_id:
        raise AuthorizationError(
            f"Authenticated actor '{actor.actor_id}' does not match envelope actor '{envelope.actor_id}'"
        )

    # Authority check: only observation / draft commands are permitted offline
    if envelope.command_type not in ALLOWED_OFFLINE_COMMANDS:
        raise InvariantViolationError(
            f"Command type '{envelope.command_type}' is not authoritative offline. "
            f"Commercial commitments, reservations, and payments require online verification."
        )

    now = get_current_utc()

    # Idempotency check: replay detection
    existing = store.get_item("offline_commands", envelope.command_id)
    if existing:
        # Check payload match
        if (
            existing.get("resource_id") == envelope.resource_id
            and existing.get("command_type") == envelope.command_type
        ):
            return (
                ReconciliationResponse(
                    command_id=envelope.command_id,
                    status="REPLAYED",
                    applied_resource_version=existing.get("applied_resource_version"),
                    current_server_state=store.get_item(envelope.resource_type + "s", envelope.resource_id),
                    conflict_reason=None,
                    processed_at=now,
                ),
                200,
            )
        else:
            raise ConflictError(
                f"Command ID '{envelope.command_id}' was previously used with differing parameters."
            )

    collection_name = envelope.resource_type + "s"
    current_resource = store.get_item(collection_name, envelope.resource_id)
    if not current_resource:
        raise NotFoundError(f"Target resource '{envelope.resource_id}' ({envelope.resource_type}) not found.")

    server_version = current_resource.get("version", 1)

    # Optimistic concurrency version check
    if server_version != envelope.expected_version:
        # Stale offline state -> reject as conflict task
        return (
            ReconciliationResponse(
                command_id=envelope.command_id,
                status="CONFLICT_REJECTED",
                applied_resource_version=None,
                current_server_state=current_resource,
                conflict_reason=(
                    f"Resource version conflict: client expected version {envelope.expected_version}, "
                    f"but server is currently at version {server_version}."
                ),
                processed_at=now,
            ),
            409,
        )

    # Apply mutation based on command type
    if envelope.command_type == "DRIVER_PICKUP_OBSERVATION":
        res_shipment = record_pickup(store, coordinator, actor, envelope.resource_id)
        applied_version = res_shipment.version
        updated_state = res_shipment.model_dump(mode="json")
    elif envelope.command_type == "DRIVER_DELIVERY_OBSERVATION":
        del_req = DeliveryConfirmationRequest(
            accepted_grams=envelope.payload.get("accepted_grams", 0),
            rejected_grams=envelope.payload.get("rejected_grams", 0),
            loss_grams=envelope.payload.get("loss_grams", 0),
        )
        res_shipment = record_delivery(store, coordinator, actor, envelope.resource_id, del_req)
        applied_version = res_shipment.version
        updated_state = res_shipment.model_dump(mode="json")
    else:
        applied_version = server_version + 1
        updated_state = current_resource

    # Store applied offline command record
    with coordinator.transaction():
        coordinator.store.set_item(
            "offline_commands",
            envelope.command_id,
            {
                "command_id": envelope.command_id,
                "actor_id": envelope.actor_id,
                "device_id": envelope.device_id,
                "command_type": envelope.command_type,
                "resource_type": envelope.resource_type,
                "resource_id": envelope.resource_id,
                "applied_resource_version": applied_version,
                "processed_at": now.isoformat(),
            },
        )

    return (
        ReconciliationResponse(
            command_id=envelope.command_id,
            status="APPLIED",
            applied_resource_version=applied_version,
            current_server_state=updated_state,
            conflict_reason=None,
            processed_at=now,
        ),
        200,
    )
