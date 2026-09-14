"""v1-compat sink: regenerate the legacy *second-run* GM ndjson from first-run rows + final context (ADR-001 §1).

Exact port of the row logic of `general_model/main.py:767-871` (SECOND RUN), including its quirks, because the 27
modules and the tracker consume this file as is:
  * every first-run row is int-truncated and clamped again; raw `airplane` rows are dropped;
  * transport boxes (beltloader, gse, pushback, tow_bar, fuel_truck, trailer, ladder) and de-duplicated `vehicle` boxes
    (IoU > 0.7 with any transport → dropped) that are "in our gate" (left of / below the main front wheel and area >
    7000 px²) are appended again as `side_obstacle` (> 70 % inside a side ROI) or `obstacle`;
  * the `conf` written into those obstacle rows is the STALE loop variable of v1 (`main.py:823, 829`): the confidence
    of the last row iterated — the last vehicle row if any vehicle rows exist, else the last first-run row;
  * the main aircraft row `[x1, y1, x2, y2, int(mode_plane_height), airplane_id]` is appended LAST, only on frames that
    belong to the longest track.
Line format is db_worker's `ndjson.writer.writerow({str(frame_id): rows})` → `json.dumps` with default separators.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from pf.gm.geometry import bbox_area, bboxes_iou, correct_coords, relative_intersection
from pf.gm.rows import TRANSPORT_CLASSES, ClassMap


@dataclass
class CompatContext:
    """Final per-video values the second run depends on (from `VideoContextV2.snapshot()`)."""

    main_front_wheel: list | None = None
    left_side_obstacles_roi: list | bool = False
    right_side_obstacles_roi: list | bool = False
    plane_history: dict = field(default_factory=dict)  # frame_id -> xyxy of the longest track
    mode_plane_height: int | None = None

    @classmethod
    def from_snapshot(cls, snap: dict) -> CompatContext:
        return cls(
            main_front_wheel=snap.get("main_front_wheel"),
            left_side_obstacles_roi=snap.get("left_side_obstacles_roi", False),
            right_side_obstacles_roi=snap.get("right_side_obstacles_roi", False),
            plane_history=snap.get("history") or {},
            mode_plane_height=snap.get("mode_plane_height"),
        )


def second_run_rows(first_run_rows, frame_id: int, ctx: CompatContext, cm: ClassMap) -> list:
    """First-run rows of one frame → the rows v1 writes in its second pass (same order, same quirks)."""
    airplane_id = cm.id("airplane")
    vehicle_id = cm.id("vehicle")
    transport_ids = {cm.str2id[c]: c for c in TRANSPORT_CLASSES if c in cm.str2id}
    detc = []
    vehicle_detections = []
    detected_transport = {}
    conf = None  # the stale variable, see module docstring

    if first_run_rows is not None and len(first_run_rows):
        for *xyxy, conf, cls_id in first_run_rows:
            xyxy = list(map(int, xyxy))
            xyxy = correct_coords(xyxy)
            cls_id = int(cls_id)
            if cls_id != airplane_id:
                detc.append([*list(map(float, xyxy)), float(conf), cls_id])
            if cls_id == vehicle_id:
                vehicle_detections.append([*xyxy, conf, cls_id])
            if cls_id in transport_ids:
                detected_transport[tuple(xyxy)] = transport_ids[cls_id]

    if len(vehicle_detections):
        for *xyxy, conf, _cls_id in vehicle_detections:
            if detected_transport.keys():
                ious = np.array([bboxes_iou(xyxy, transport) for transport in detected_transport])
                if np.max(ious) > 0.7:
                    continue
            detected_transport[tuple(xyxy)] = "vehicle"

    gate_transport = {}
    if ctx.main_front_wheel is not None and detected_transport.keys():
        mfw = ctx.main_front_wheel
        for transport in detected_transport:
            if (transport[0] < mfw[0] or transport[3] > mfw[3]) and bbox_area(transport) > 7000:
                gate_transport[transport] = detected_transport[transport]

    if gate_transport.keys():
        left_roi, right_roi = ctx.left_side_obstacles_roi, ctx.right_side_obstacles_roi
        for transport in gate_transport:
            if (left_roi and relative_intersection(left_roi, transport) > 0.7) or (
                right_roi and relative_intersection(right_roi, transport) > 0.7
            ):
                detc.append([*list(map(float, transport)), float(conf), int(cm.id("side_obstacle"))])
            else:
                detc.append([*list(map(float, transport)), float(conf), int(cm.id("obstacle"))])

    if frame_id in ctx.plane_history:
        largest_plane = ctx.plane_history[frame_id]
        detc.append([*list(map(float, largest_plane)), int(ctx.mode_plane_height), airplane_id])
    return detc


def ndjson_line(frame_id: int, rows) -> str:
    """Byte-identical to db_worker: `ndjson.writer.writerow({str(frame_id): rows})`."""
    return json.dumps({str(frame_id): rows}) + "\n"


def write_second_run_file(path: str, frames, ctx: CompatContext, cm: ClassMap) -> int:
    """`frames`: iterable of (frame_id, first_run_rows) in order. Returns the number of lines written."""
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for frame_id, rows in frames:
            fh.write(ndjson_line(frame_id, second_run_rows(rows, frame_id, ctx, cm)))
            n += 1
    return n
