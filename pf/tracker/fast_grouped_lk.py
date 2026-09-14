"""Exact grouped optical flow for the vendored tracker's Vehicle objects (beltloaders, GSE) — part of `exact_fast`.

v1 calls `cv2.calcOpticalFlowPyrLK` once per object per frame, and every call rebuilds both image pyramids. Objects of one
class use the same masked grey frames (their `bboxes_to_remove` is the class's list for the frame), and Lucas–Kanade tracks
every point independently of the others. One call over the concatenated points therefore returns, for each object's slice,
bit-identical positions, statuses and errors — verified on real ATL-C5 frames in both directions — at about a third of the
cost for three objects (15.2 ms → 5.7 ms).

The object update is split exactly at that call:

  begin_vehicle_update()  everything `Vehicle.update_params` → `TrackedObject.update_params` → `_update_moving_status` →
                          `FeatureTracker.update_features` does BEFORE the optical flow, in the original order: box repair,
                          previous box, box queue, stop-flag reset, area-shift early return, keypoint re-detection (with its
                          random subsampling and the YOLO-seg cache), zeroing of the class grey pair;
  run_grouped()           one `calcOpticalFlowPyrLK` per (grey pair, direction) group;
  finish()                the rest of `update_features` and the movement analysis for one object.

`Batch` drives a class loop of the stream: the loop calls `update()` (begin) and `then()` (the per-object logic that needs
the updated state — beltloader typing, records) in the original order; `flush()` runs the grouped flow, finishes every
pending object and then runs the queued steps in order. This is exact because nothing a later object's begin reads is written
by an earlier object's finish or queued step (objects keep separate states; typing writes only the frame's label dicts, which
begin never reads). If an object is updated a second time while its first update is pending, the batch flushes first.

`check_pinned_source()` verifies, at stream start, that the replicated lines are still present in the vendored methods.
"""

from __future__ import annotations

import ast
import inspect

import numpy as np

REQUIRED_LINES = {
    ("tracked_object", "TrackedObject", "update_params"): [
        "if self.__state.status != Status.UNOBSERVED:",
        "if xyxy and not check_bounding_box(xyxy, prev_im0s.shape[:2]):",
        "xyxy = fix_incorrect_bbox(xyxy, prev_im0s.shape[:2])",
        "raise ValueError(f'Trying to set incorrect bounding box: {xyxy}')",
        "self.__previous_xyxy = self.xyxy",
        "self.xyxy = xyxy",
        "self.__bboxes_queue.update_recent_bboxes(self.xyxy)",
        "self.__state._is_stopped = None",
        "self._update_moving_status(prev_im0s, im0s, predictor, bboxes_to_remove, is_noised=is_noised, frame_number=frame_number, invoker=invoker, yolo_idx=yolo_idx)",
    ],
    ("tracked_object", "TrackedObject", "_update_moving_status"): [
        "if not self.__state._is_stopped:",
        "prev_gray = cv2.cvtColor(prev_im0s, cv2.COLOR_BGR2GRAY)",
        "cur_gray = cv2.cvtColor(im0s, cv2.COLOR_BGR2GRAY)",
        "area_shift = bbox_area(self.xyxy) / bbox_area(self.__previous_xyxy)",
        "if area_shift > 1.5 or area_shift < 0.66:",
        "if self.__feature_tracker.p0 is None or self.__feature_tracker._of_dots_lifetime == 0 or len(self.__feature_tracker.p0) == 0:",
        "self.__feature_tracker._p0 = self._find_new_features_OF(im0s, cur_gray, predictor, bboxes_to_remove=bboxes_to_remove, is_noised=is_noised, frame_number=frame_number, invoker=invoker, yolo_idx=yolo_idx)",
        "good_old, good_new = self.__feature_tracker.update_features(prev_gray, cur_gray, bboxes_to_remove)",
        "if good_old is None or good_new is None:",
        "self.__state = self.__movement_analyzer.analyze_movement(prev_gray, cur_gray, good_old, good_new, self.__state, self.xyxy, self.__feature_tracker)",
    ],
    ("tracked_object", "FeatureTracker", "update_features"): [
        "if bboxes_to_remove is not None:",
        "for xyxy in bboxes_to_remove:",
        "x1, y1, x2, y2 = map(int, xyxy)",
        "prev_gray[y1:y2, x1:x2] = 0",
        "cur_gray[y1:y2, x1:x2] = 0",
        "if self._p0 is None or len(self._p0) == 0:",
        "if self._new_features:",
        "p1, st, err = cv2.calcOpticalFlowPyrLK(cur_gray, prev_gray, self._p0, None, **self._lk_params)",
        "p1, st, err = cv2.calcOpticalFlowPyrLK(prev_gray, cur_gray, self._p0, None, **self._lk_params)",
        "good_old = self._p0[st == 1]",
        "good_new = p1[st == 1]",
        "except (TypeError, IndexError) as e:",
        "self._p0 = good_new.reshape(-1, 1, 2)",
        "if not self._new_features:",
        "self._st = st.reshape(-1)",
        "self._of_dots_lifetime -= 1",
        "self._new_features = False",
        "return good_old, good_new",
    ],
    ("transport", "Vehicle", "update_params"): [
        "super().update_params(xyxy, prev_im0s, im0s, predictor, bboxes_to_remove, is_noised=is_noised, frame_number=frame_id, invoker=self, yolo_idx=yolo_idx)",
    ],
}
# statement counts of the replicated methods in the pinned source (any added/removed statement fails the check)
EXPECTED_STATEMENTS = {
    ("tracked_object", "TrackedObject", "update_params"): 11,
    ("tracked_object", "TrackedObject", "_update_moving_status"): 13,
    ("tracked_object", "FeatureTracker", "update_features"): 22,
    ("transport", "Vehicle", "update_params"): 1,
}


def _method_segment(module, class_name: str, method_name: str):
    src = inspect.getsource(module)
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item, ast.get_source_segment(src, item)
    raise RuntimeError(f"pf.tracker.fast_grouped_lk: {class_name}.{method_name} not found in {module.__name__}")


def method_statement_count(module, class_name: str, method_name: str) -> int:
    node, _ = _method_segment(module, class_name, method_name)
    return sum(1 for n in ast.walk(node) if isinstance(n, ast.stmt)) - 1  # without the def itself


def check_pinned_source() -> None:
    from pf.tracker._v1 import tracked_object, transport

    modules = {"tracked_object": tracked_object, "transport": transport}
    for key, lines in REQUIRED_LINES.items():
        mod_name, cls, meth = key
        _, seg = _method_segment(modules[mod_name], cls, meth)
        norm = " ".join(seg.split())
        for line in lines:
            if " ".join(line.split()) not in norm:
                raise RuntimeError(f"pf.tracker.fast_grouped_lk: pinned {cls}.{meth} changed — missing: {line}")
        count = method_statement_count(modules[mod_name], cls, meth)
        if count != EXPECTED_STATEMENTS[key]:
            raise RuntimeError(
                f"pf.tracker.fast_grouped_lk: pinned {cls}.{meth} has {count} statements, expected {EXPECTED_STATEMENTS[key]}"
            )


class Pending:
    __slots__ = ("obj", "ft", "prev_gray", "cur_gray", "reverse", "p0")

    def __init__(self, obj, ft, prev_gray, cur_gray, reverse, p0):
        self.obj, self.ft, self.prev_gray, self.cur_gray, self.reverse, self.p0 = obj, ft, prev_gray, cur_gray, reverse, p0


def begin_vehicle_update(obj, xyxy, prev_im0s, im0s, frame_id, predictor, bboxes_to_remove=None, is_noised=False, yolo_idx=None):
    """`Vehicle.update_params` up to (excluding) the optical-flow call. Returns a Pending, or None when v1 would not run
    optical flow for this object on this frame."""
    from pf.tracker import fast_paths
    from pf.tracker._v1.common import bbox_area, check_bounding_box, fix_incorrect_bbox
    from pf.tracker._v1.tracked_object import Status

    frame_number, invoker = frame_id, obj
    state = obj._TrackedObject__state
    if state.status != Status.UNOBSERVED:
        if xyxy and not check_bounding_box(xyxy, prev_im0s.shape[:2]):
            xyxy = fix_incorrect_bbox(xyxy, prev_im0s.shape[:2])
            if not check_bounding_box(xyxy, prev_im0s.shape[:2]):
                raise ValueError(f"Trying to set incorrect bounding box: {xyxy}")
        obj._TrackedObject__previous_xyxy = obj.xyxy
        obj.xyxy = xyxy
        obj._TrackedObject__bboxes_queue.update_recent_bboxes(obj.xyxy)
        obj._TrackedObject__state._is_stopped = None
        # --- _update_moving_status -----------------------------------------------------------------
        if not obj._TrackedObject__state._is_stopped:
            g = fast_paths.frame_grays_for(prev_im0s, im0s)
            prev_gray = g.prev_gray
            cur_gray = g.cur_gray
            area_shift = bbox_area(obj.xyxy) / bbox_area(obj._TrackedObject__previous_xyxy)
            if area_shift > 1.5 or area_shift < 0.66:
                return None
            ft = obj._TrackedObject__feature_tracker
            if ft.p0 is None or ft._of_dots_lifetime == 0 or len(ft.p0) == 0:
                ft._p0 = obj._find_new_features_OF(
                    im0s, cur_gray, predictor, bboxes_to_remove=bboxes_to_remove, is_noised=is_noised,
                    frame_number=frame_number, invoker=invoker, yolo_idx=yolo_idx,
                )
            prev_gray, cur_gray = g.for_optical_flow(bboxes_to_remove)
            # --- FeatureTracker.update_features before the optical flow ---------------------------------
            if bboxes_to_remove is not None:
                for box in bboxes_to_remove:
                    x1, y1, x2, y2 = map(int, box)
                    prev_gray[y1:y2, x1:x2] = 0
                    cur_gray[y1:y2, x1:x2] = 0
            if ft._p0 is None or len(ft._p0) == 0:
                return None
            return Pending(obj, ft, prev_gray, cur_gray, bool(ft._new_features), ft._p0)
    return None


def run_grouped(pendings: list, lk_params: dict, stats: dict | None = None) -> dict:
    """One optical-flow call per (grey pair, direction); returns {id(pending): (p1_slice, st_slice)}."""
    import cv2

    groups: dict = {}
    order = []
    for p in pendings:
        key = (id(p.prev_gray), id(p.cur_gray), p.reverse)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(p)
    out = {}
    for key in order:
        ps = groups[key]
        same_layout = all(p.p0.ndim == 3 and p.p0.shape[1:] == (1, 2) and p.p0.dtype == np.float32 for p in ps)
        chunks = [ps] if same_layout else [[p] for p in ps]
        for chunk in chunks:
            first = chunk[0]
            pts = first.p0 if len(chunk) == 1 else np.concatenate([p.p0 for p in chunk], axis=0)
            if first.reverse:
                p1, st, _err = cv2.calcOpticalFlowPyrLK(first.cur_gray, first.prev_gray, pts, None, **lk_params)
            else:
                p1, st, _err = cv2.calcOpticalFlowPyrLK(first.prev_gray, first.cur_gray, pts, None, **lk_params)
            if stats is not None:
                stats["lk_calls"] = stats.get("lk_calls", 0) + 1
                stats["lk_objects"] = stats.get("lk_objects", 0) + len(chunk)
            off = 0
            for p in chunk:
                n = len(p.p0)
                if len(chunk) == 1:
                    out[id(p)] = (p1, st)
                else:
                    out[id(p)] = (None if p1 is None else p1[off : off + n].copy(), None if st is None else st[off : off + n].copy())
                off += n
    return out


def finish(p: Pending, p1, st) -> None:
    """The rest of `FeatureTracker.update_features` and `_update_moving_status` for one object."""
    ft = p.ft
    try:
        good_old = ft._p0[st == 1]
        good_new = p1[st == 1]
    except (TypeError, IndexError) as e:
        print("Exc:", e)
        print(ft._p0.shape)
        return
    ft._p0 = good_new.reshape(-1, 1, 2)
    if not ft._new_features:
        ft._st = st.reshape(-1)
    ft._of_dots_lifetime -= 1
    ft._new_features = False
    obj = p.obj
    obj._TrackedObject__state = obj._TrackedObject__movement_analyzer.analyze_movement(
        p.prev_gray, p.cur_gray, good_old, good_new, obj._TrackedObject__state, obj.xyxy, ft
    )


class Batch:
    def __init__(self, lk_params: dict, stats: dict):
        self.lk_params = lk_params
        self.stats = stats
        self.steps: list = []
        self.pending: list = []
        self.pending_objs: set = set()

    def update(self, obj, xyxy, prev_im0s, im0s, frame_id, predictor, bboxes_to_remove, yolo_idx, is_noised=False) -> None:
        if id(obj) in self.pending_objs:
            self.stats["early_flushes"] = self.stats.get("early_flushes", 0) + 1
            self.flush()
        p = begin_vehicle_update(obj, xyxy, prev_im0s, im0s, frame_id, predictor, bboxes_to_remove=bboxes_to_remove,
                                 is_noised=is_noised, yolo_idx=yolo_idx)
        if p is not None:
            self.pending.append(p)
            self.pending_objs.add(id(obj))

    def then(self, fn) -> None:
        self.steps.append(fn)

    def flush(self) -> None:
        if self.pending:
            results = run_grouped(self.pending, self.lk_params, self.stats)
            for p in self.pending:
                finish(p, *results[id(p)])
        steps = self.steps
        self.steps, self.pending, self.pending_objs = [], [], set()
        for fn in steps:
            fn()
