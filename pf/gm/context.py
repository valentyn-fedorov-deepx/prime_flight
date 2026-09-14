"""Incremental per-video context for GM v2 (ADR-001 §2, `gm_context`).

Every decision that v1 takes after end-of-file is re-expressed as an accumulator with an explicit `decided_at`
frame, so a chunk-wise pipeline can emit a "decided" event instead of waiting for the merge. The v1 rules are kept
where they are already causal (entity: 40 hits; aircraft type: > 500 votes) and reproduced as a *final* recompute
where they are not (parts layout, main aircraft, camera majority) so the v1-compat writer can regenerate the legacy
second-run artefacts bitwise at event end.

Sources: `general_model/main.py` (parts layout :199-247, :677-697; main aircraft :597-646, :669-704; entity :835-848;
camera :879-908), `scripts/engine_script.py` (aircraft type).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mode

from pf.gm.geometry import (
    FRAME_H,
    FRAME_W,
    bbox_area,
    correct_coords,
    count_bbox_frames,
    get_center,
    get_hw,
    is_overlap,
    overlay_ratio,
    relative_intersection,
)
from pf.gm.rows import ClassMap

# ---------------------------------------------------------------- parts layout (wings / nose / front wheel)


def detect_main_plane_part(parts_appeared: dict, part_name: str, main_nose=None, fps: int = 8):
    """Exact port of `main.py:210-247`."""
    main_part, wing_left, wing_right = None, None, None
    parts_list = [xyxy for xyxy in parts_appeared]
    num_appeared_list = [num for num in parts_appeared.values()]
    if len(num_appeared_list) > 10:
        limit_appeared = max(sorted(num_appeared_list, reverse=True)[9], 30 * fps)
    else:
        limit_appeared = max(sorted(num_appeared_list, reverse=True)[-1], 30 * fps)
    parts_list_sorted = sorted(parts_list, key=lambda x: bbox_area(x), reverse=True)
    for part_xyxy in parts_list_sorted:
        if parts_appeared[part_xyxy] > limit_appeared:
            if part_name == "wing" and main_nose is not None:
                if wing_left is None and get_center(part_xyxy)[0] > get_center(main_nose)[0]:
                    wing_left = correct_coords(part_xyxy)
                elif wing_right is None and get_center(part_xyxy)[0] < get_center(main_nose)[0]:
                    wing_right = correct_coords(part_xyxy)
            if part_name in ["nose", "wheel"]:
                main_part = part_xyxy
                return main_part
    if part_name == "wing":
        main_part = [wing_left, wing_right]
    return main_part


@dataclass
class PartsLayout:
    """Buckets of wing / nose / front-wheel boxes (IoU > 0.8) and the derived side-obstacle ROIs."""

    fps: int = 8
    frame_w: int = FRAME_W
    frame_h: int = FRAME_H
    wings_appeared: dict = field(default_factory=dict)
    nose_appeared: dict = field(default_factory=dict)
    wheel_appeared: dict = field(default_factory=dict)
    decided_at: int | None = None  # first frame where a main nose or wheel bucket exceeds 30·fps frames

    def update(self, frame_id: int, rows, cm: ClassMap) -> list:
        """Feed first-run rows (int-truncated, clamped boxes). Returns names of fields decided on this frame."""
        wing_id, nose_id, wheel_id = cm.id("airplane_wing"), cm.id("airplane_nose"), cm.id("front_wheel")
        for *xyxy, _conf, cls_id in rows:
            xyxy = list(map(int, xyxy))
            if cls_id == wing_id:
                self.wings_appeared = count_bbox_frames(self.wings_appeared, xyxy)
            elif cls_id == nose_id:
                self.nose_appeared = count_bbox_frames(self.nose_appeared, xyxy)
            elif cls_id == wheel_id:
                self.wheel_appeared = count_bbox_frames(self.wheel_appeared, xyxy)
        decided = []
        if self.decided_at is None:
            limit = 30 * self.fps
            if any(v > limit for v in self.nose_appeared.values()) or any(
                v > limit for v in self.wheel_appeared.values()
            ):
                self.decided_at = frame_id
                decided.append("parts_layout")
        return decided

    def snapshot(self) -> dict:
        """Recompute the v1 end-of-video layout from the current buckets (`main.py:677-697`)."""
        main_front_wheel, main_nose = None, None
        if self.wheel_appeared:
            main_front_wheel = detect_main_plane_part(self.wheel_appeared, "wheel", fps=self.fps)
        if self.nose_appeared:
            main_nose = detect_main_plane_part(self.nose_appeared, "nose", fps=self.fps)
        left_roi, right_roi = False, False
        main_left_wing = main_right_wing = None
        if main_front_wheel or main_nose:
            if main_nose is not None and self.wings_appeared:
                main_left_wing, main_right_wing = detect_main_plane_part(
                    self.wings_appeared, "wing", main_nose, fps=self.fps
                )
            elif main_front_wheel is not None and self.wings_appeared:
                main_left_wing, main_right_wing = detect_main_plane_part(
                    self.wings_appeared, "wing", main_front_wheel, fps=self.fps
                )
            if main_left_wing is not None:
                main_left_wing = correct_coords(main_left_wing)
                left_roi = [
                    main_left_wing[0] + 0.8 * get_hw(main_left_wing)[1],
                    0,
                    self.frame_w,
                    self.frame_h,
                ]
            if main_right_wing is not None:
                main_right_wing = correct_coords(main_right_wing)
                right_roi = [0, 0, main_right_wing[0] + 0.2 * get_hw(main_right_wing)[1], self.frame_h]
        return {
            "main_front_wheel": main_front_wheel,
            "main_nose": main_nose,
            "main_left_wing": main_left_wing,
            "main_right_wing": main_right_wing,
            "left_side_obstacles_roi": left_roi,
            "right_side_obstacles_roi": right_roi,
        }


# ---------------------------------------------------------------- main aircraft


def merge_overlapping_planes(boxes: list) -> list:
    """Exact port of the merge loop `main.py:598-609`: drop the LARGER of two boxes overlapping > 0.7."""
    boxes = list(boxes)
    i = 0
    while i < len(boxes) - 1:
        j = i
        while j < len(boxes) - 1:
            plane1, plane2 = boxes[j], boxes[j + 1]
            if overlay_ratio(plane1, plane2) > 0.7:
                index = j if bbox_area(plane1) > bbox_area(plane2) else j + 1
                boxes.pop(index)
            j += 1
        i += 1
    return boxes


@dataclass
class MainAircraftTracker:
    """Longest-track selection of the main aircraft with a running answer.

    v1 uses a Norfair tracker (parameters in cv_common global_config, unavailable) and re-associates a new id with
    the most overlapping known plane when overlay > 0.5 (`main.py:633-645`). Without cv_common the identity logic is
    approximated by that same overlay rule against each track's last box; `tracker` can be swapped for a Norfair
    adapter once the parameters are known (parity of class-2 rows depends on it — gm_current.md §11.1).
    """

    min_height: int = 150
    tracks: dict = field(default_factory=dict)  # track_id -> {frame_id: xyxy}
    last_box: dict = field(default_factory=dict)  # track_id -> xyxy
    _next_id: int = 1
    first_seen_at: int | None = None

    def candidates(self, rows, cm: ClassMap) -> list:
        airplane_id = cm.id("airplane")
        cands = []
        for *xyxy, _conf, cls_id in rows:
            xyxy = list(map(int, xyxy))
            if cls_id == airplane_id and get_hw(xyxy)[0] >= self.min_height:
                cands.append(xyxy)
        return merge_overlapping_planes(cands)

    def update(self, frame_id: int, rows, cm: ClassMap) -> list:
        decided = []
        for xyxy in self.candidates(rows, cm):
            xyxy = correct_coords(xyxy)
            if self.first_seen_at is None:
                self.first_seen_at = frame_id
                decided.append("first_aircraft_seen")
            tid = None
            if self.last_box:
                key = max(self.last_box, key=lambda k: relative_intersection(xyxy, self.last_box[k]))
                if overlay_ratio(xyxy, self.last_box[key]) > 0.5:
                    tid = key
            if tid is None:
                tid = self._next_id
                self._next_id += 1
                self.tracks[tid] = {}
            self.tracks[tid][frame_id] = xyxy
            self.last_box[tid] = xyxy
        return decided

    def longest(self):
        if not self.tracks:
            return None
        return max(self.tracks.keys(), key=lambda k: len(self.tracks[k].keys()))

    def snapshot(self) -> dict:
        """v1 end-of-video values (`main.py:669-704`) recomputed from the current history."""
        tid = self.longest()
        if tid is None:
            return {
                "main_plane_track": None,
                "history": {},
                "mode_plane_height": None,
                "frame_of_beginning": None,
                "frame_of_ending": None,
            }
        history = self.tracks[tid]
        heights = [round(xyxy[3] - xyxy[1], -1) for xyxy in history.values()]
        return {
            "main_plane_track": tid,
            "history": history,
            "mode_plane_height": mode(heights),
            "frame_of_beginning": min(history.keys()),
            "frame_of_ending": max(history.keys()),
        }


# ---------------------------------------------------------------- entity (airline)

ENTITY_BY_SUM = {
    0: "JetBlue",
    40: "Allegiant",
    80: "UnitedExpress",
    120: "Breze",
    160: "American",
    200: "Spirit",
}


@dataclass
class EntityVoter:
    """`main.py:835-848`: every 8th frame until 40 hits; all 40 must agree, otherwise 'Undefined'."""

    hits_needed: int = 40
    every_n_frames: int = 8
    hits: list = field(default_factory=list)
    entity: str | None = None
    decided_at: int | None = None

    def wants_frame(self, frame_id: int) -> bool:
        return len(self.hits) < self.hits_needed and frame_id % self.every_n_frames == 0

    def feed(self, frame_id: int, entity_class_ids) -> list:
        """`entity_class_ids`: class ids of the entity detector on this frame (may be empty)."""
        if self.wants_frame(frame_id):
            for cls_id in entity_class_ids or []:
                self.hits.append(int(cls_id))
        if self.entity is None and len(self.hits) == self.hits_needed:
            self.entity = ENTITY_BY_SUM.get(sum(self.hits), "Undefined")
            self.decided_at = frame_id
            return ["entity"]
        return []


# ---------------------------------------------------------------- aircraft type (JET / AIRCRAFT)


def aircraft_determining(rows, planes_dict: dict, cm: ClassMap, answer_after: int = 500) -> dict:
    """Port of `scripts/engine_script.py:7-108` on rows; class names resolved through `cm` (not reverse lookup)."""
    tail_detections, wing_detections, back_wheel_detections, engine_detections, nose_detections = (
        [],
        [],
        [],
        [],
        [],
    )
    tail_detection, wing_detection, back_wheel_detection, engine_detection, nose_detection = (
        [],
        [],
        [],
        [],
        [],
    )
    back_door_detections, front_door_detections, back_door_detection, front_door_detection = [], [], [], []
    tail_left = None
    engine_types = {"JET": 0, "AIRCRAFT": 0}

    if rows is not None and len(rows):
        for *xyxy, _conf, cls_id in rows:
            xyxy = tuple(map(int, xyxy))
            cls_str = cm.name(int(cls_id))
            if cls_str == "back_wheel":
                back_wheel_detections.append(xyxy)
            elif cls_str == "airplane_tail":
                tail_detections.append(xyxy)
            elif cls_str == "airplane_nose":
                nose_detections.append(xyxy)
            elif cls_str == "airplane_wing":
                wing_detections.append(xyxy)
            elif cls_str == "airplane_engine":
                engine_detections.append(xyxy)
            elif cls_str == "back_door":
                back_door_detections.append(xyxy)

    for plane_part, plane_part_detections in [
        (tail_detection, tail_detections),
        (wing_detection, wing_detections),
        (engine_detection, engine_detections),
        (nose_detection, nose_detections),
        (back_wheel_detection, back_wheel_detections),
        (front_door_detection, front_door_detections),
        (back_door_detection, back_door_detections),
    ]:
        if plane_part_detections:
            for coordinate in sorted(plane_part_detections, key=lambda x: bbox_area(x), reverse=True)[0]:
                plane_part.append(coordinate)

    if tail_detection and nose_detection:
        tail_left = get_center(tail_detection)[0] < get_center(nose_detection)[0]
    if tail_left is None and (back_door_detection and front_door_detection):
        tail_left = get_center(back_door_detection)[0] < get_center(front_door_detection)[0]

    if not engine_detection:
        return planes_dict

    if tail_detection and is_overlap(engine_detection, tail_detection):
        engine_types["JET"] += 1
    if back_wheel_detection and is_overlap(engine_detection, back_wheel_detection):
        engine_types["AIRCRAFT"] += 1
    if wing_detection:
        if get_center(engine_detection)[1] < get_center(wing_detection)[1]:
            engine_types["JET"] += 1
        else:
            engine_types["AIRCRAFT"] += 1
    if tail_left is not None and wing_detection:
        if (tail_left and engine_detection[0] < wing_detection[2] < engine_detection[2]) or (
            not tail_left and engine_detection[0] < wing_detection[0] < engine_detection[2]
        ):
            engine_types["AIRCRAFT"] += 1
        else:
            engine_types["JET"] += 1

    frame_plane = None
    if engine_types["JET"] > engine_types["AIRCRAFT"]:
        frame_plane = "JET"
    elif engine_types["JET"] < engine_types["AIRCRAFT"]:
        frame_plane = "AIRCRAFT"
    planes_dict[frame_plane] = planes_dict.get(frame_plane, 0) + 1

    for text_plane_type in ("JET", "AIRCRAFT"):
        if text_plane_type in planes_dict:
            if planes_dict[text_plane_type] > answer_after and "answer" not in planes_dict:
                planes_dict["answer"] = text_plane_type
    return planes_dict


@dataclass
class AircraftTypeVoter:
    """v1 votes only on frames where the main aircraft is present and `arrived`; the caller gates on T_arr."""

    answer_after: int = 500
    votes: dict = field(default_factory=dict)
    decided_at: int | None = None

    @property
    def answer(self):
        return self.votes.get("answer")

    def feed(self, frame_id: int, rows, cm: ClassMap) -> list:
        if "answer" in self.votes:
            return []
        self.votes = aircraft_determining(rows, self.votes, cm, self.answer_after)
        if "answer" in self.votes:
            self.decided_at = frame_id
            return ["aircraft_type"]
        return []


# ---------------------------------------------------------------- camera type (cone / wing)


@dataclass
class CameraVoter:
    """v1: one sigmoid ≥ 0.5 vote per frame after arrival, majority at end-of-video (`main.py:904-908, 1062-1063`).

    The streaming finalization rule (fix after N votes / N frames after T_arr) is a separate ADR; until then
    `majority()` is the running answer and `decide()` freezes it explicitly.
    """

    votes: list = field(default_factory=list)
    decided_at: int | None = None
    camera_type_cone: bool | None = None

    def feed(self, frame_id: int, is_cone: bool) -> None:
        self.votes.append(bool(is_cone))

    def majority(self):
        if not self.votes:
            return None
        return sum(self.votes) > len(self.votes) / 2

    def confidence(self) -> float:
        if not self.votes:
            return 0.0
        cone_conf = sum(self.votes) / len(self.votes)
        return cone_conf if self.majority() else 1 - cone_conf

    def decide(self, frame_id: int) -> list:
        if self.camera_type_cone is None and self.votes:
            self.camera_type_cone = self.majority()
            self.decided_at = frame_id
            return ["camera_type"]
        return []


# ---------------------------------------------------------------- aggregate


@dataclass
class VideoContextV2:
    """Implements `pf.gm.interface.VideoContext`: feed first-run rows per frame; collect decisions with frames."""

    cm: ClassMap
    fps: int = 8
    layout: PartsLayout = None
    aircraft: MainAircraftTracker = None
    entity: EntityVoter = field(default_factory=EntityVoter)
    aircraft_type: AircraftTypeVoter = field(default_factory=AircraftTypeVoter)
    camera: CameraVoter = field(default_factory=CameraVoter)
    decisions: list = field(default_factory=list)  # [(frame_id, field)]

    def __post_init__(self):
        if self.layout is None:
            self.layout = PartsLayout(fps=self.fps)
        if self.aircraft is None:
            self.aircraft = MainAircraftTracker()

    def update(
        self,
        frame_id: int,
        detections,
        image=None,
        *,
        entity_class_ids=None,
        is_cone=None,
        arrived: bool = False,
    ) -> list:
        """`detections` = first-run rows. `arrived` = T_arr already happened (from the stage detector / tracker)."""
        decided = []
        decided += self.layout.update(frame_id, detections, self.cm)
        decided += self.aircraft.update(frame_id, detections, self.cm)
        decided += self.entity.feed(frame_id, entity_class_ids)
        if arrived:
            decided += self.aircraft_type.feed(frame_id, detections, self.cm)
            if is_cone is not None:
                self.camera.feed(frame_id, is_cone)
        for name in decided:
            self.decisions.append((frame_id, name))
        return decided

    def snapshot(self) -> dict:
        s = {
            "entity": self.entity.entity,
            "aircraft_type": self.aircraft_type.answer,
            "camera_type_cone": self.camera.camera_type_cone,
            "camera_running_majority": self.camera.majority(),
            "confidence_camera": self.camera.confidence(),
            "decided_at": {name: fid for fid, name in self.decisions},
        }
        s.update(self.layout.snapshot())
        s.update(self.aircraft.snapshot())
        return s
