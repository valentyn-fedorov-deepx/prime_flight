"""PUSHBACK_ATTACHED for the stage detector — causal port of aircraft-chocks' rule, plus an offline replication of the
production two-pass computation to measure what the causal version changes.

aircraft-chocks (`main.py:1240-1300` first pass, `:1519-1548` second pass) decides "pushback attached" itself:

  first pass   (looks ahead) the biggest pushback box of every frame goes into a 120 s window; at departure — or at the last
               frame, if the aircraft is tracked there — the median of the OLDER half of the window (about 120 s to 60 s
               before departure) becomes `median_pushback`, if that half holds more than `fps` boxes;
  second pass  from the frame whose number equals the tracker's `arrival_frame` until `departure_frame`:
               * with `median_pushback`: +1 when the frame's FIRST pushback row overlaps it with IoU > 0.8, otherwise −1
                 (not below 0);
               * without it: +1 when the highest-confidence nose and the first pushback satisfy
                 `nose.x2 + pushback.w // 2 > pushback.x1` and `pushback.y2 − aircraft.y2 < 0.3 · aircraft.h` (no decrement);
               the event fires on the frame the counter exceeds 5 · fps.

The nose rule uses only past frames, so `PushbackAttachedCausal` implements it exactly (same row order, integer nose boxes,
float pushback box, floor division). The median rule needs the future and cannot run causally;
`production_pushback_attached_frame` replicates both branches offline, so the causal frame can be compared with what production
computes from the same GM and tracker files.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from pf.tracker._v1.common import bbox_area, bboxes_iou, get_hw


def airplane_state(records):
    """What aircraft-chocks restores from the airplane record: box, arrival_frame, departure_frame."""
    for r in records or []:
        if r.get("cls_str") == "airplane":
            sd = r.get("state_dict") or {}
            box = sd.get("_xyxy") or r.get("xyxy")
            return {"xyxy": tuple(box), "arrival_frame": sd.get("arrival_frame"), "departure_frame": sd.get("departure_frame")}
    return None


def first_pushback(rows, pushback_id):
    """aircraft-chocks `pushback_attached(img, det)`: the first pushback row in row order, raw coordinates."""
    for *xyxy, conf, cls_id in rows or []:
        if cls_id == pushback_id:
            return xyxy
    return None


def best_nose(rows, nose_id):
    """The highest-confidence nose (integer box), as `noses.sort(reverse=True)[0]` in aircraft-chocks."""
    noses = []
    for *xyxy, conf, cls_id in rows or []:
        if int(cls_id) == nose_id:
            noses.append((conf, tuple(map(int, xyxy))))
    noses.sort(reverse=True)
    return noses[0][1] if noses else None


def nose_rule_hit(nose, p_box, aircraft_xyxy) -> bool:
    return bool(
        p_box is not None
        and nose[2] + get_hw(p_box)[1] // 2 > p_box[0]
        and p_box[3] - aircraft_xyxy[3] < get_hw(aircraft_xyxy)[0] * 0.3
    )


class PushbackAttachedCausal:
    """Causal PUSHBACK_ATTACHED: the nose rule of aircraft-chocks, fed frame by frame with GM rows and tracker records."""

    def __init__(self, str2id: dict, fps: int = 8):
        self.pushback_id = str2id["pushback"]
        self.nose_id = str2id["airplane_nose"]
        self.fps = fps
        self.aircraft = None
        self.stop_frame = 0
        self.departed = False
        self.counter = 0
        self.frame = None

    def feed(self, frame_id: int, gm_rows, tracker_records):
        """Returns the attach frame on the frame the event fires, else None."""
        st = airplane_state(tracker_records)
        if st is not None:
            self.aircraft = st
            if frame_id == st["arrival_frame"]:
                if not self.stop_frame:
                    self.stop_frame = frame_id
            elif frame_id == st["departure_frame"]:
                self.departed = True
        if self.departed or not self.stop_frame or self.frame is not None:
            return None
        nose = best_nose(gm_rows, self.nose_id)
        if nose:
            p_box = first_pushback(gm_rows, self.pushback_id)
            if nose_rule_hit(nose, p_box, self.aircraft["xyxy"]):
                self.counter += 1
        if self.counter > 5 * self.fps:
            self.frame = frame_id
            return frame_id
        return None


def production_pushback_attached_frame(gm_iter_fn, tracker_iter_fn, n_frames: int, str2id: dict, fps: int = 8) -> dict:
    """Offline replication of aircraft-chocks' two passes. `gm_iter_fn()` / `tracker_iter_fn()` yield (frame, rows|records)
    positionally aligned (the module zips the two files)."""
    pushback_id = str2id["pushback"]
    nose_id = str2id["airplane_nose"]

    window = deque(maxlen=120 * fps)
    median = None
    for (f, rows), (_f2, recs) in zip(gm_iter_fn(), tracker_iter_fn()):
        st = airplane_state(recs)
        if st is not None and (st["departure_frame"] is not None or f == n_frames):
            needed = [p for p in list(window)[: window.maxlen // 2] if p is not None]
            if len(needed) > fps:
                median = np.median(needed, axis=0)
            break
        if rows:
            pushbacks = [xyxy for *xyxy, conf, cls_id in rows if cls_id == pushback_id]
            if pushbacks:
                pushbacks.sort(key=bbox_area, reverse=True)
                window.append(pushbacks[0])
            else:
                window.append(None)

    stop_frame = 0
    counter = 0
    attached = None
    aircraft = None
    for (f, rows), (_f2, recs) in zip(gm_iter_fn(), tracker_iter_fn()):
        st = airplane_state(recs)
        if st is not None:
            aircraft = st
            if f == st["arrival_frame"]:
                if not stop_frame:
                    stop_frame = f
            elif f == st["departure_frame"]:
                break
        if not stop_frame or attached:
            continue
        p_box = first_pushback(rows, pushback_id)
        if median is not None:
            if p_box is not None and bboxes_iou(p_box, median) > 0.8:
                counter += 1
            elif counter > 0:
                counter -= 1
        else:
            nose = best_nose(rows, nose_id)
            if nose and nose_rule_hit(nose, p_box, aircraft["xyxy"]):
                counter += 1
        if counter > 5 * fps:
            attached = f
    return {
        "frame": attached,
        "rule": "median" if median is not None else "nose",
        "median_pushback": None if median is None else [float(x) for x in median],
        "stop_frame": stop_frame or None,
    }
