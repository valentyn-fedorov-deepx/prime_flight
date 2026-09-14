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
from .tracker_parity import (
    CONSUMED_STATE_FIELDS,
    TrackerParity,
    compare_tracker_frames,
    compare_tracker_ndjson,
)

__all__ = [
    "CONSUMED_STATE_FIELDS",
    "DetectionParity",
    "TrackerParity",
    "as_chunks",
    "canonical",
    "compare_gm_ndjson",
    "compare_tracker_frames",
    "compare_tracker_ndjson",
    "diff_streams",
    "digest",
    "iter_ndjson",
]
