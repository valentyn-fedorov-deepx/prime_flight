"""Exact performance paths for the vendored v1 tracker classes (`pf.tracker._v1`), enabled by `TrackerOptions.exact_fast`.

Every change keeps the tracker output byte-identical to the production pin under the same `np.random` seed
(`scripts/tracker_v2_run.py --seed` vs `scripts/tracker_v1_profile.py --pin prod --seed`). They remove repeated work and
never change an algorithm, a parameter or an operation order that affects values:

1. **Grey frames once per frame.** v1 converts the previous and the current BGR frame to grey inside every object update
   (2 × `cvtColor` of a 1080p frame per object per frame). `FrameGrays` converts each tracked frame once and carries the
   current grey over as the next frame's previous grey. Optical flow needs the grey frames with `bboxes_to_remove`
   zeroed (v1 zeroes its private copies in place); objects get one masked copy per distinct box list per frame — zeroing
   is idempotent, so objects with the same list can share it. The FAST keypoint detector keeps reading the unmasked grey,
   exactly as in v1 where it runs before the masking.
2. **Vectorised in-box test** of the tracked points in `MovementAnalyzer.analyze_movement` (a Python loop over up to 250
   points per object in v1): the same comparisons under the same NumPy promotion rules.
3. **No per-frame `print`** in the airplane stage counter.

Methods are rebuilt from the vendored source with exact one-line substitutions (compiled inside a class of the same name
so private-name mangling is identical); if the pinned source changes and a substitution no longer matches, `enable()`
raises instead of silently running different code. `disable()` restores the original methods.
"""

from __future__ import annotations

import inspect
import textwrap

import numpy as np

CURRENT = None  # FrameGrays of the frame being processed; set by TrackerStream through begin_frame()
_ORIGINALS: dict = {}


class FrameGrays:
    def __init__(self, prev_img, cur_img, carry: "FrameGrays | None" = None):
        self.prev_img = prev_img
        self.cur_img = cur_img
        self._prev = None
        self._cur = None
        self._masked: dict = {}
        self.conversions = 0
        if carry is not None and prev_img is not None and carry.cur_img is prev_img and carry._cur is not None:
            self._prev = carry._cur

    @property
    def prev_gray(self):
        if self._prev is None:
            import cv2

            self._prev = cv2.cvtColor(self.prev_img, cv2.COLOR_BGR2GRAY)
            self.conversions += 1
        return self._prev

    @property
    def cur_gray(self):
        if self._cur is None:
            import cv2

            self._cur = cv2.cvtColor(self.cur_img, cv2.COLOR_BGR2GRAY)
            self.conversions += 1
        return self._cur

    def for_optical_flow(self, bboxes_to_remove):
        """(prev, cur) grey frames as `FeatureTracker.update_features` may modify them.

        No boxes → v1 does not write to the arrays → the shared unmasked frames are passed. Otherwise one private pair per
        distinct list of integer boxes (the same `map(int, xyxy)` conversion v1 uses for the zeroing)."""
        if not bboxes_to_remove:
            return self.prev_gray, self.cur_gray
        key = tuple(tuple(int(v) for v in xyxy) for xyxy in bboxes_to_remove)
        pair = self._masked.get(key)
        if pair is None:
            pair = (self.prev_gray.copy(), self.cur_gray.copy())
            self._masked[key] = pair
        return pair


def begin_frame(prev_img, cur_img) -> FrameGrays:
    global CURRENT
    CURRENT = FrameGrays(prev_img, cur_img, carry=CURRENT)
    return CURRENT


def end_stream() -> None:
    global CURRENT
    CURRENT = None


def frame_grays_for(prev_img, cur_img) -> FrameGrays:
    """The frame's shared grey cache when the object is updated with the frame images of this frame, else a private one."""
    g = CURRENT
    if g is not None and g.cur_img is cur_img and g.prev_img is prev_img:
        return g
    return FrameGrays(prev_img, cur_img)


def in_bbox_vec(points: np.ndarray, bbox) -> np.ndarray:
    """`np.array([in_bbox(p, bbox) for p in points], dtype=bool)` for an (N, 2) array — identical booleans."""
    x1, y1, x2, y2 = bbox
    c1 = points[:, 0]
    c2 = points[:, 1]
    return (x1 <= c1) & (c1 <= x2) & (y1 <= c2) & (c2 <= y2)


def _silent_print(*args, **kwargs):
    return None


def rebuild_method(module, class_name: str, method_name: str, substitutions: list):
    cls = getattr(module, class_name)
    src = textwrap.dedent(inspect.getsource(cls.__dict__[method_name]))
    for old, new in substitutions:
        found = src.count(old)
        if found != 1:
            raise RuntimeError(
                f"pf.tracker.fast_paths: expected exactly one occurrence of {old!r} in {class_name}.{method_name}, found {found}"
            )
        src = src.replace(old, new)
    code = f"class {class_name}:\n" + textwrap.indent(src, "    ")
    local_ns: dict = {}
    exec(compile(code, f"<pf.tracker.fast_paths {class_name}.{method_name}>", "exec"), vars(module), local_ns)
    return local_ns[class_name].__dict__[method_name]


MOVING_STATUS_SUBSTITUTIONS = [
    (
        "prev_gray = cv2.cvtColor(prev_im0s, cv2.COLOR_BGR2GRAY)",
        "_pf_g = _pf_frame_grays_for(prev_im0s, im0s); prev_gray = _pf_g.prev_gray",
    ),
    ("cur_gray = cv2.cvtColor(im0s, cv2.COLOR_BGR2GRAY)", "cur_gray = _pf_g.cur_gray"),
    (
        "good_old, good_new = self.__feature_tracker.update_features(prev_gray, cur_gray, bboxes_to_remove)",
        "prev_gray, cur_gray = _pf_g.for_optical_flow(bboxes_to_remove); "
        "good_old, good_new = self.__feature_tracker.update_features(prev_gray, cur_gray, bboxes_to_remove)",
    ),
]
ANALYZE_SUBSTITUTIONS = [
    (
        "in_bbox_mask = np.array([in_bbox(point, xyxy) for point in good_new], dtype=bool)",
        "in_bbox_mask = _pf_in_bbox_vec(good_new, xyxy)",
    ),
]


def enable() -> None:
    if _ORIGINALS:
        return
    from pf.tracker._v1 import tracked_object as to_mod
    from pf.tracker._v1 import transport as tr_mod

    to_mod._pf_frame_grays_for = frame_grays_for
    to_mod._pf_in_bbox_vec = in_bbox_vec
    fast_moving = rebuild_method(to_mod, "TrackedObject", "_update_moving_status", MOVING_STATUS_SUBSTITUTIONS)
    fast_analyze = rebuild_method(to_mod, "MovementAnalyzer", "analyze_movement", ANALYZE_SUBSTITUTIONS)
    _ORIGINALS["moving"] = to_mod.TrackedObject.__dict__["_update_moving_status"]
    _ORIGINALS["analyze"] = to_mod.MovementAnalyzer.__dict__["analyze_movement"]
    _ORIGINALS["print"] = tr_mod.__dict__.get("print")
    to_mod.TrackedObject._update_moving_status = fast_moving
    to_mod.MovementAnalyzer.analyze_movement = fast_analyze
    tr_mod.print = _silent_print


def disable() -> None:
    if not _ORIGINALS:
        return
    from pf.tracker._v1 import tracked_object as to_mod
    from pf.tracker._v1 import transport as tr_mod

    to_mod.TrackedObject._update_moving_status = _ORIGINALS.pop("moving")
    to_mod.MovementAnalyzer.analyze_movement = _ORIGINALS.pop("analyze")
    original_print = _ORIGINALS.pop("print")
    if original_print is None:
        tr_mod.__dict__.pop("print", None)
    else:
        tr_mod.print = original_print
    end_stream()


def enabled() -> bool:
    return bool(_ORIGINALS)
