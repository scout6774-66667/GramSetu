"""Canonical unit conversion and exact integer rounding logic for GramSetu AI."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Union


class DatasetContractError(ValueError):
    """Raised when data violates unit, schema, referential, or domain contracts."""


def _to_decimal(value: Any, param_name: str = "value") -> Decimal:
    """Safely parse input into Decimal, rejecting non-finite and negative values."""
    if value is None:
        raise DatasetContractError(f"{param_name} cannot be None")
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as e:
        raise DatasetContractError(f"Invalid numeric value for {param_name}: {value!r}") from e
    if not d.is_finite() or d < 0:
        raise DatasetContractError(f"{param_name} must be a non-negative finite number, got: {value!r}")
    return d


def exact_integer(value: Decimal, name: str) -> int:
    """Ensure Decimal has no fractional component before converting to int."""
    if value != value.to_integral_value():
        raise DatasetContractError(
            f"{name} has fractional component ({value}) in canonical integer units; lossy truncation rejected"
        )
    return int(value)


def mass_to_grams(value: Union[str, int, float, Decimal], *, source_unit: str = "kg") -> int:
    unit = source_unit.strip().lower()
    multipliers = {
        "kg": Decimal("1000"),
        "g": Decimal("1"),
        "grams": Decimal("1"),
        "gram": Decimal("1"),
        "quintal": Decimal("100000"),
        "tonne": Decimal("1000000"),
        "tonnes": Decimal("1000000"),
        "mt": Decimal("1000000"),
    }
    if unit not in multipliers:
        raise DatasetContractError(f"Unsupported mass source unit: '{source_unit}'. Must be one of {list(multipliers.keys())}")
    
    d_val = _to_decimal(value, "mass")
    canonical_grams = d_val * multipliers[unit]
    return exact_integer(canonical_grams, "mass_grams")


def distance_to_meters(value: Union[str, int, float, Decimal], *, source_unit: str = "km") -> int:
    unit = source_unit.strip().lower()
    multipliers = {
        "km": Decimal("1000"),
        "m": Decimal("1"),
        "meters": Decimal("1"),
        "meter": Decimal("1"),
    }
    if unit not in multipliers:
        raise DatasetContractError(f"Unsupported distance source unit: '{source_unit}'. Must be one of {list(multipliers.keys())}")

    d_val = _to_decimal(value, "distance")
    canonical_meters = d_val * multipliers[unit]
    return exact_integer(canonical_meters, "distance_meters")


def price_to_paise_per_kg(value: Union[str, int, float, Decimal], *, source_unit: str = "INR/kg") -> int:
    unit = source_unit.strip()
    multipliers = {
        "INR/kg": Decimal("100"),
        "inr/kg": Decimal("100"),
        "Rs/kg": Decimal("100"),
        "INR/quintal": Decimal("1"),
        "inr/quintal": Decimal("1"),
        "Rs/quintal": Decimal("1"),
        "paise/kg": Decimal("1"),
        "paise/g": Decimal("1000"),
    }
    if unit not in multipliers:
        raise DatasetContractError(f"Unsupported price source unit: '{source_unit}'. Must be one of {list(multipliers.keys())}")

    d_val = _to_decimal(value, "price")
    canonical_paise_per_kg = d_val * multipliers[unit]
    return exact_integer(canonical_paise_per_kg, "price_paise_per_kg")


def gross_paise_half_up(accepted_grams: int, price_paise_per_kg: int) -> int:
    """Enforce exact half-up integer rounding: (accepted_grams * price_paise_per_kg + 500) // 1000."""
    if not isinstance(accepted_grams, int) or not isinstance(price_paise_per_kg, int):
        raise DatasetContractError(
            f"Non-integer input rejected: accepted_grams={type(accepted_grams).__name__}, "
            f"price_paise_per_kg={type(price_paise_per_kg).__name__}"
        )
    if accepted_grams < 0:
        raise DatasetContractError(f"accepted_grams cannot be negative: {accepted_grams}")
    if price_paise_per_kg < 0:
        raise DatasetContractError(f"price_paise_per_kg cannot be negative: {price_paise_per_kg}")

    return (accepted_grams * price_paise_per_kg + 500) // 1000


def calculate_adjustment_paise_half_up(adjustment_grams: int, price_paise_per_kg: int) -> int:
    if not isinstance(adjustment_grams, int) or not isinstance(price_paise_per_kg, int):
        raise DatasetContractError("Integer quantities and prices required for adjustments")
    if price_paise_per_kg < 0:
        raise DatasetContractError(f"price_paise_per_kg cannot be negative: {price_paise_per_kg}")

    if adjustment_grams >= 0:
        return (adjustment_grams * price_paise_per_kg + 500) // 1000
    else:
        abs_grams = -adjustment_grams
        return -((abs_grams * price_paise_per_kg + 500) // 1000)


def calculate_gross_paise(accepted_grams: int, price_paise_per_kg: int) -> int:
    return gross_paise_half_up(accepted_grams, price_paise_per_kg)


def reconcile_delivery_inspection(
    delivered_grams: int,
    accepted_grams: int,
    rejected_grams: int,
    pending_grams: int = 0,
    final: bool = True,
) -> bool:
    quantities = {
        "delivered_grams": delivered_grams,
        "accepted_grams": accepted_grams,
        "rejected_grams": rejected_grams,
        "pending_grams": pending_grams,
    }
    for name, val in quantities.items():
        if not isinstance(val, int) or val < 0:
            raise DatasetContractError(f"{name} must be a non-negative integer, got {val!r}")

    accounted = accepted_grams + rejected_grams + pending_grams
    if delivered_grams != accounted:
        raise DatasetContractError(
            f"Delivery mass conservation failure: delivered ({delivered_grams}) != "
            f"accepted ({accepted_grams}) + rejected ({rejected_grams}) + pending ({pending_grams}) [total={accounted}]"
        )

    if final and pending_grams != 0:
        raise DatasetContractError(
            f"Final settlement requires FULLY_INSPECTED delivery with pending_grams == 0, got pending_grams={pending_grams}"
        )

    return True


def calculate_net_paise(gross_payable_paise: int, authorized_deductions_paise: int) -> int:
    if gross_payable_paise < 0:
        raise DatasetContractError(f"gross_payable_paise cannot be negative: {gross_payable_paise}")
    if authorized_deductions_paise < 0:
        raise DatasetContractError(f"authorized_deductions_paise cannot be negative: {authorized_deductions_paise}")
    if authorized_deductions_paise > gross_payable_paise:
        raise DatasetContractError(
            f"authorized_deductions_paise ({authorized_deductions_paise}) exceeds gross_payable_paise ({gross_payable_paise})"
        )
    return gross_payable_paise - authorized_deductions_paise


def parse_iso_utc(timestamp_str: str, param_name: str = "timestamp") -> datetime:
    if not timestamp_str or not timestamp_str.strip():
        raise DatasetContractError(f"{param_name} cannot be empty")
    s = timestamp_str.strip()
    try:
        normalized = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except Exception as e:
        raise DatasetContractError(f"Invalid ISO 8601 format for {param_name}: '{s}'") from e

    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise DatasetContractError(f"Ambiguous naive timestamp rejected for {param_name}: '{s}'. Explicit timezone required.")
    
    return dt.astimezone(timezone.utc)


def validate_requirement_demand_semantics(needed_grams: int, uncommitted_grams: int, remaining_grams: int) -> None:
    if needed_grams < 0 or uncommitted_grams < 0 or remaining_grams < 0:
        raise DatasetContractError("Demand quantities cannot be negative")
    if uncommitted_grams > remaining_grams:
        raise DatasetContractError(
            f"uncommitted_grams ({uncommitted_grams}) cannot exceed remaining_grams ({remaining_grams})"
        )
    if remaining_grams > needed_grams:
        raise DatasetContractError(
            f"remaining_grams ({remaining_grams}) cannot exceed needed_grams ({needed_grams})"
        )


def validate_commitment_delivery_reconciliation(delivered_grams: int, accepted_grams: int, rejected_grams: int) -> None:
    if delivered_grams < 0 or accepted_grams < 0 or rejected_grams < 0:
        raise DatasetContractError("Delivery quantities cannot be negative")
    if delivered_grams != (accepted_grams + rejected_grams):
        raise DatasetContractError(
            f"Delivery reconciliation failure: delivered_grams ({delivered_grams}) != accepted ({accepted_grams}) + rejected ({rejected_grams})"
        )
