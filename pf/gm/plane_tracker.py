"""Production main-aircraft tracking (GM commit a0157a4): norfair 0.2.0 engine + v1 identity/history bookkeeping.

Faithful to `general_model/main.py:597-646` (@ a0157a4 lines 599-660) and `scripts/tracker.py` (FeaturedTracker):
  * candidates = `airplane` rows with height ≥ `airplane_min_height` (150 px), overlap-merged (drop the LARGER box of a
    pair overlapping > 0.7), then (production only) boxes < 10 % of the frame area dropped;
  * Norfair `Tracker(distance_function=iou_distance, distance_threshold=0.8, initialization_delay=8, hit_inertia_max=40)`
    from `cv_common/global_config.yaml: tracking.airplane.norfair`; `iou_distance = 1 - bboxes_iou(...)` with the
    cv_common +1 convention; a track is reported only after the initialization delay (≈ 9 frames after first sight);
  * `FeaturedTracker` computes FAST/ORB features per object but its `update()` never passes `image` to
    `update_objects_in_place`, so the feature-similarity gate is dead code — the engine is exactly norfair 0.2.0;
  * per reported object: `xyxy = correct_coords(obj.last_detection.data)` (the raw detection box, not the Kalman estimate);
    the `BboxStabilizer` is applied only when the noise preprocessor is in HEAVY mode (`stabilize_when_heavy`, used by the
    master-lineage variant `entity_clip`; `pf.gm.stabilizer`);
  * history bookkeeping (`planes_tracking_meta_data`): the first object initialises the dict; a known norfair id
    updates its history; a NEW norfair id is re-associated with the most overlapping known plane
    (`max(..., key=get_relative_intersection(xyxy, plane.xyxy))`, then `get_overlay_ratio > 0.5`) and SHARES that
    plane's history object (v1 aliases the list), otherwise starts a new history;
  * the main aircraft = the history with the most frames; `mode_plane_height` = statistics.mode of heights rounded to
    tens; class-2 rows of the second run exist for exactly the frames in that history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mode

import numpy as np

from pf.gm._norfair020 import Detection, Tracker
from pf.gm.context_prod import drop_tiny_planes
from pf.gm.stabilizer import BboxStabilizer, PlanesView
from pf.gm.geometry import bboxes_iou, correct_coords, get_hw, overlay_ratio, relative_intersection
from pf.gm.rows import ClassMap

NORFAIR_AIRPLANE = {"distance_threshold": 0.8, "initialization_delay": 8, "hit_inertia_max": 40}


def xyxy_to_det_arr(xyxy) -> np.ndarray:
    """`cv_common/common.py:194-201`."""
    x1, y1, x2, y2 = xyxy
    return np.array([[x1, y1], [x2, y2]])


def det_arr_to_xyxy(det: np.ndarray) -> tuple:
    """`cv_common/common.py:182-191`."""
    return tuple(det.flatten())


def iou_distance(detection, tracked_object) -> float:
    """`cv_common/common.py:253-255`: Norfair distance = 1 - IoU (+1 convention)."""
    return 1 - bboxes_iou(det_arr_to_xyxy(detection.points), det_arr_to_xyxy(tracked_object.estimate))


def merge_overlapping_planes(boxes: list) -> list:
    """Exact port of the merge loop `main.py:598-609`: drop the LARGER of two boxes overlapping > 0.7."""
    boxes = list(boxes)
    i = 0
    while i < len(boxes) - 1:
        j = i
        while j < len(boxes) - 1:
            plane1, plane2 = boxes[j], boxes[j + 1]
            if overlay_ratio(plane1, plane2) > 0.7:
                a1 = (plane1[2] - plane1[0]) * (plane1[3] - plane1[1])
                a2 = (plane2[2] - plane2[0]) * (plane2[3] - plane2[1])
                index = j if a1 > a2 else j + 1
                boxes.pop(index)
            j += 1
        i += 1
    return boxes


@dataclass
class PlaneHistory:
    """One entry of v1's `planes_tracking_meta_data[id] = [Plane, {frame_id: xyxy}]` (the Plane object is not needed
    for the second-run rows; only the history dict and the last box)."""

    frames: dict = field(default_factory=dict)  # frame_id -> xyxy
    last_xyxy: list | None = None


@dataclass
class NorfairPlaneTracker:
    """Main-aircraft tracker with production semantics. One instance per event."""

    min_height: int = 150
    drop_tiny: bool = True
    stabilize_when_heavy: bool = False  # master lineage (13a4ddc … 8576299): BboxStabilizer on HEAVY-noise frames
    stabilizer: BboxStabilizer = None
    norfair_params: dict = field(default_factory=lambda: dict(NORFAIR_AIRPLANE))
    tracker: Tracker = None
    planes: dict = field(
        default_factory=dict
    )  # norfair id -> PlaneHistory (aliased on re-association, as in v1)
    first_seen_at: int | None = None
    first_track_at: int | None = None

    def __post_init__(self):
        if self.tracker is None:
            self.tracker = Tracker(distance_function=iou_distance, **self.norfair_params)
        if self.stabilizer is None and self.stabilize_when_heavy:
            self.stabilizer = BboxStabilizer()

    # ---------------------------------------------------------------- per frame
    def candidates(self, rows, cm: ClassMap) -> list:
        airplane_id = cm.id("airplane")
        cands = []
        for *xyxy, _conf, cls_id in rows:
            xyxy = list(map(int, xyxy))
            xyxy = correct_coords(xyxy)
            if int(cls_id) == airplane_id and get_hw(xyxy)[0] >= self.min_height:
                cands.append(xyxy)
        cands = merge_overlapping_planes(cands)
        return drop_tiny_planes(cands) if self.drop_tiny else cands

    def update(self, frame_id: int, rows, cm: ClassMap, heavy: bool = False) -> list:
        decided = []
        cands = self.candidates(rows, cm)
        if not cands:
            return decided  # v1 only calls tracker.update when there are candidates
        if self.first_seen_at is None:
            self.first_seen_at = frame_id
            decided.append("first_aircraft_seen")
        detections = [Detection(xyxy_to_det_arr(b), data=b) for b in cands]
        for obj in self.tracker.update(detections):
            xyxy = correct_coords(obj.last_detection.data)
            if heavy and self.stabilizer is not None:
                xyxy = self.stabilizer.update_bbox(obj.id, frame_id, xyxy, PlanesView(self.planes))
            if self.first_track_at is None:
                self.first_track_at = frame_id
                decided.append("first_aircraft_track")
            if not self.planes:
                self.planes[obj.id] = PlaneHistory({frame_id: xyxy}, xyxy)
            elif obj.id in self.planes:
                hist = self.planes[obj.id]
                hist.frames[frame_id] = xyxy
                hist.last_xyxy = xyxy
            else:
                key_to_copy = max(
                    self.planes, key=lambda k: relative_intersection(xyxy, self.planes[k].last_xyxy)
                )
                if overlay_ratio(xyxy, self.planes[key_to_copy].last_xyxy) > 0.5:
                    self.planes[obj.id] = self.planes[key_to_copy]  # alias, as v1 does
                    hist = self.planes[obj.id]
                    hist.frames[frame_id] = xyxy
                    hist.last_xyxy = xyxy
                else:
                    self.planes[obj.id] = PlaneHistory({frame_id: xyxy}, xyxy)
        return decided

    # ---------------------------------------------------------------- results
    def longest(self):
        if not self.planes:
            return None
        return max(self.planes.keys(), key=lambda k: len(self.planes[k].frames.keys()))

    @property
    def tracks(self) -> dict:
        """Compatibility with `MainAircraftTracker`: id -> {frame: xyxy}."""
        return {k: v.frames for k, v in self.planes.items()}

    @property
    def last_box(self) -> dict:
        return {k: v.last_xyxy for k, v in self.planes.items()}

    def snapshot(self) -> dict:
        tid = self.longest()
        if tid is None:
            return {
                "main_plane_track": None,
                "history": {},
                "mode_plane_height": None,
                "frame_of_beginning": None,
                "frame_of_ending": None,
                "first_aircraft_track": self.first_track_at,
            }
        history = self.planes[tid].frames
        heights = [round(xyxy[3] - xyxy[1], -1) for xyxy in history.values()]
        return {
            "main_plane_track": tid,
            "history": history,
            "mode_plane_height": mode(heights),
            "frame_of_beginning": min(history.keys()),
            "frame_of_ending": max(history.keys()),
            "first_aircraft_track": self.first_track_at,
        }
