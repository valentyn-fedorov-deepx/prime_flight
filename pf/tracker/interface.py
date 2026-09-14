"""Tracker v2 — interface only (implementation after the tracker analysis; cv_trackers/cv_common source pending).

Invariants (CLAUDE.md, docs/02_target_architecture.md):
  * X1 — one tracker instance per event, never reset between chunks;
  * every ``update`` is causal: it may only use frames <= frame_id;
  * the per-object ``state_dict`` is what modules restore via cv_common classes, so its keys per class are a
    contract (see docs/analysis/contract_observed.md and module_consumption.md for the consumed set);
  * event primitives the stage detector needs (aircraft stopped/moving, BL near aircraft, pushback geometry) are
    exposed as fields, not recomputed by modules from private ``_p0/_prev_p0/_st`` optical-flow state.
"""

from __future__ import annotations

from typing import Any, Protocol

from pf.gm.interface import Detection


class TrackedObject(Protocol):
    """One tracked object as serialised on the bus: ``{"state_dict": {...}}`` (+ optional extras)."""

    def to_record(self) -> dict: ...


class Tracker(Protocol):
    """Stateful, causal, one instance per event."""

    schema_version: str

    def update(self, frame_id: int, detections: list[Detection], image: Any | None = None) -> list[dict]:
        """Consume one frame's detections, return the tracker records for this frame (``frame["trackers"]``)."""
        ...

    def snapshot(self) -> dict:
        """Serialisable full state (for checkpoint / restart of a session without losing X1)."""
        ...
