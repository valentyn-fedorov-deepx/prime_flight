"""Parity / regression tooling."""

from .parity import (
    DetectionParity,
    as_chunks,
    canonical,
    compare_gm_ndjson,
    diff_streams,
    digest,
    iter_ndjson,
)

__all__ = [
    "DetectionParity",
    "as_chunks",
    "canonical",
    "compare_gm_ndjson",
    "diff_streams",
    "digest",
    "iter_ndjson",
]
