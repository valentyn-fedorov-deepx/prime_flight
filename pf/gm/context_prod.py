"""Production-only context logic of GM commit a0157a4 (`deployment_v_py3_10`, 2025-09-04) — the code that actually
produced the ATL-C5 files, as opposed to the reviewed master pin 13a4ddc (ported in `pf.gm.context`).

Differences vs master that affect the output (from `git diff 13a4ddc a0157a4`):
  * detector input is converted BGR→RGB (`scripts/new_model.py:308-309`) — handled in `pf.gm.onnx_detector` (bgr_to_rgb);
  * airplane candidates smaller than 10 % of the frame area are dropped before tracking (`main.py:612-621`);
  * the aircraft type is voted per frame while the main aircraft is present (not only after arrival): engine y2 vs wing y2,
    both parts must lie ≥ 50 % inside the aircraft box; the answer is taken at departure or at end of video
    (`scripts/engine_script.py` @ a0157a4); a "plane passing by" before arrival resets the counters after 10 s of absence;
  * the main aircraft tracker is `FeaturedTracker` (Norfair 0.3.1 + FAST/ORB feature check on re-association,
    `scripts/tracker.py` @ a0157a4) — not ported here; `pf.gm.context.MainAircraftTracker` approximates it;
  * the entity (airline) comes from `EntityClassifier` (CRAFT text detector + tail classifier, `scripts/entity/`) run every
    2·fps frames during the first 60 s of the main aircraft — a separate subsystem, not ported here (report field only).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pf.gm.geometry import FRAME_H, FRAME_W, bbox_area, relative_intersection
from pf.gm.rows import ClassMap


def drop_tiny_planes(
    boxes: list, frame_w: int = FRAME_W, frame_h: int = FRAME_H, min_fraction: float = 0.1
) -> list:
    """`main.py:612-621` @ a0157a4: candidates with area / frame area < 0.1 are removed (after the overlap merge)."""
    frame_area = frame_w * frame_h
    return [b for b in boxes if bbox_area(b) / frame_area >= min_fraction]


def save_plane_type_frame_data(
    rows, main_plane_xyxy, counters: dict, cm: ClassMap, departured: bool = False
) -> None:
    """Port of `scripts/engine_script.py:7-42` @ a0157a4 (class names resolved via `cm`, not reverse lookup)."""
    if main_plane_xyxy is None or departured:
        return
    best_wing, best_engine = [], []
    wing_detections, engine_detections = [], []
    if rows is not None and len(rows):
        for *xyxy, conf, cls_id in rows:
            xyxy = tuple(map(int, xyxy))
            cls_str = cm.name(int(cls_id))
            if cls_str == "airplane_wing":
                wing_detections.append((xyxy, conf))
            elif cls_str == "airplane_engine":
                engine_detections.append((xyxy, conf))
    for best_part, part_detections in [(best_wing, wing_detections), (best_engine, engine_detections)]:
        for xyxy, conf in part_detections:
            if (not best_part or conf > best_part[0][1]) and relative_intersection(
                main_plane_xyxy, xyxy
            ) >= 0.5:
                best_part.clear()
                best_part.append((xyxy, conf))
    if best_wing and best_engine:
        if best_engine[0][0][3] < best_wing[0][0][3]:
            counters["jet"] += 1
            counters["frames_evaluated"] += 1
        elif best_engine[0][0][3] > best_wing[0][0][3]:
            counters["airplane"] += 1
            counters["frames_evaluated"] += 1


def evaluate_plane_type(counters: dict, plane_was_detected: bool):
    """Port of `scripts/engine_script.py:44-53` @ a0157a4."""
    if not plane_was_detected and counters["frames_evaluated"] == 0:
        return None
    if counters["airplane"] < counters["jet"]:
        return "JET"
    return "AIRCRAFT"


def _fresh_counters() -> dict:
    return {"airplane": 0, "jet": 0, "frames_evaluated": 0, "consecutive_plane_det": 0}


@dataclass
class AircraftTypeVoterProd:
    """`main.py:741-746, 912-949, 1109-1110` @ a0157a4, driven per frame by the main-aircraft state.

    Inputs per frame: the frame's rows, whether the main aircraft is present on this frame (`plane_available`), its box,
    and its arrival / departure state (from the tracker / stage detector). `answer` becomes final at departure or when
    `finalize()` is called at the end of the event.
    """

    fps: int = 8
    counters: dict = field(default_factory=_fresh_counters)
    plane_was_detected: bool = False
    plane_passing_by: bool = False
    plane_disappearance_counter: int = 0
    answer: str | None = "not evaluated"
    decided_at: int | None = None

    def feed(
        self,
        frame_id: int,
        rows,
        cm: ClassMap,
        *,
        plane_available: bool,
        main_plane_xyxy,
        arrived: bool,
        departured: bool,
    ) -> list:
        # non-target plane passing by (before arrival): reset the counters after 10 s without the plane
        if main_plane_xyxy is not None and not arrived:
            if plane_available:
                self.plane_passing_by = True
                self.plane_disappearance_counter = 10 * self.fps
            elif self.plane_passing_by and self.plane_disappearance_counter > 0:
                self.plane_disappearance_counter -= 1
            elif self.plane_passing_by:
                self.plane_passing_by = False
                self.counters = _fresh_counters()
        if plane_available:
            self.counters["consecutive_plane_det"] += 1
            if self.counters["consecutive_plane_det"] > 120:
                self.plane_was_detected = True
            if self.answer == "not evaluated":
                save_plane_type_frame_data(rows, main_plane_xyxy, self.counters, cm, departured=departured)
                if departured:
                    return self._decide(frame_id)
        else:
            self.counters["consecutive_plane_det"] = 0
        return []

    def finalize(self, frame_id: int) -> list:
        """End of video: `main.py:1109-1110` @ a0157a4."""
        if self.answer == "not evaluated":
            return self._decide(frame_id)
        return []

    def _decide(self, frame_id: int) -> list:
        self.answer = evaluate_plane_type(self.counters, self.plane_was_detected)
        self.decided_at = frame_id
        return ["aircraft_type"]
