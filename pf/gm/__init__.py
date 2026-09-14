"""General Model v2 (ADR-001): pure inference core + incremental context + v1-compat / v2 sinks.

Modules:
    interface       FrameDetector / VideoContext protocols
    geometry        letterbox arithmetic and box helpers (ports + flagged assumptions for cv_common helpers)
    onnx_detector   YoloV8Onnx — numerically faithful port of v1's ONNX wrapper (lazy torch/onnxruntime)
    rows            detector outputs → 6-element rows, ClassMap (str2id)
    context         VideoContextV2: parts layout, main aircraft, entity, aircraft type, camera — with decided_at
    compat_writer   second-run (legacy) ndjson regeneration for the 27 modules
"""

from .compat_writer import CompatContext, ndjson_line, second_run_rows, write_second_run_file
from .context import VideoContextV2
from .geometry import Letterbox, letterbox_geometry
from .interface import Detection, FrameDetector, VideoContext
from .rows import ClassMap, first_run_rows

__all__ = [
    "ClassMap",
    "CompatContext",
    "Detection",
    "FrameDetector",
    "Letterbox",
    "VideoContext",
    "VideoContextV2",
    "first_run_rows",
    "letterbox_geometry",
    "ndjson_line",
    "second_run_rows",
    "write_second_run_file",
]
