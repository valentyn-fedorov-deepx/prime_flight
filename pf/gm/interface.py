"""General Model v2 — interface only (implementation lands after docs/analysis/gm_current.md).

Design intent (docs/02_target_architecture.md, CLAUDE.md):
  * a pure inference core ``frame -> detections`` with no knowledge of videos, chunks, MongoDB or buckets;
  * per-video "context" decisions (camera cone/wing, aircraft/jet, entity, main aircraft) made INCREMENTALLY with an
    explicit "decided at frame X" event instead of at end-of-video;
  * I/O adapters (ndjson writer, bucket/Mongo) kept outside the core so the core can be replayed and benchmarked.

Detection format is frozen to what modules consume today (observed production ndjson):
    [x1, y1, x2, y2, conf, class_id]   absolute pixels in the source resolution, class_id per GM ``str2id``.
Any change to this tuple or to the class-id mapping is a schema bump (ADR), never a silent edit.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

Detection = Sequence[float]  # [x1, y1, x2, y2, conf, class_id]


class FrameDetector(Protocol):
    """Pure inference core: one frame in, detections out. Stateless across frames."""

    #: class_id -> class name, identical to the production ``str2id`` mapping (inverted)
    class_names: dict[int, str]

    def detect(self, image: Any, frame_id: int) -> list[Detection]:
        """``image`` is a decoded BGR frame (HxWx3, uint8) in the source resolution."""
        ...


class VideoContext(Protocol):
    """Incremental per-video decisions (camera type, aircraft type, entity, main aircraft ...).

    ``update`` consumes each frame's detections and returns the list of context fields that became final on this
    frame (e.g. ``["camera"]``), so downstream can emit an event instead of waiting for end-of-video.
    """

    def update(self, frame_id: int, detections: list[Detection], image: Any | None = None) -> list[str]: ...

    def snapshot(self) -> dict:
        """Current (possibly undecided) context values, e.g. ``{"camera": "cone", "aircraft_type": None}``."""
        ...
