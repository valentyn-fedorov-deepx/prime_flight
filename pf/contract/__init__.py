"""Frame contract (schema 1.0) and input hygiene."""

from .frame import (
    EVENTS,
    OPTIONAL_FRAME_KEYS,
    REQUIRED_FRAME_KEYS,
    SCHEMA_VERSION,
    STAGES,
    ContractError,
    empty_frame,
    make_frame,
    validate_frame,
)
from .hygiene import VEHICLE_CLASSES, VEHICLE_ONLY_KEYS, check_class_leakage, strip_class_leakage

__all__ = [
    "EVENTS",
    "OPTIONAL_FRAME_KEYS",
    "REQUIRED_FRAME_KEYS",
    "SCHEMA_VERSION",
    "STAGES",
    "VEHICLE_CLASSES",
    "VEHICLE_ONLY_KEYS",
    "ContractError",
    "check_class_leakage",
    "empty_frame",
    "make_frame",
    "strip_class_leakage",
    "validate_frame",
]
