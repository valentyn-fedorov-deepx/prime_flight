"""Tracker v1-compat output contract: the exact `state_dict` key sets and the record envelope the 27 modules restore.

Source: `docs/analysis/tracker_current.md` §3 (cv_common @ ac5098d `tracked_object.py:538-601`, `transport.py:115-127,
192-198`), confirmed on the 7 ATL-C5 production files (`contract_observed.md`: airplane 39 keys, beltloader/gse 34,
person `{}`). `from_state_dict` on the 2025+ cv_common family raises `ValueError` on ANY unknown key and tolerates only
`_recent_bboxes`, `_recent_bboxes_time`, `arrival_frame` as extras — so for the v1-compat file the key set per class is
frozen in both directions (ADR-001 §3). New fields go to the envelope's `data{}` or to the frame's `anchors`/`events`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 32 base keys in the order `TrackedObject.to_state_dict` writes them (`tracked_object.py:538-601`).
BASE_KEYS = (
    "to_numpy",
    "to_status",
    "_obj_id",
    "_class_name",
    "_xyxy",
    "_previous_xyxy",
    "_init_xyxy",
    "_status",
    "_color",
    "_prev_status",
    "_prev_color",
    "_static_frames",
    "_moving_frames",
    "_is_stopped",
    "_prev_stop_point",
    "_stop_point",
    "_stops_count",
    "_p0",
    "_st",
    "_of_dots_lifetime",
    "_init_dots_lifetime",
    "_mask",
    "_segm_points",
    "_static_points_thres",
    "_stopping_time_thres",
    "_moving_time_thres",
    "_proceeding_time_thres",
    "_display_proceeding_time_thres",
    "_from_x",
    "_to_x",
    "_from_y",
    "_to_y",
)
# `Airplane.to_state_dict` appends 7 (`transport.py:115-127`).
AIRPLANE_KEYS = (
    "_moving_counter",
    "_stopped_counter",
    "have_pre_arrival_stage",
    "have_arrival_stage",
    "arrival_frame",
    "departure_frame",
    "_height_mode",
)
# `Vehicle.to_state_dict` appends 2 (`transport.py:192-198`); beltloader and gse are Vehicles.
VEHICLE_KEYS = ("_bl_type_bbox", "_bl_type_frames")
# Keys `from_state_dict` tolerates without raising (`tracked_object.py:666-668`).
TOLERATED_EXTRAS = ("_recent_bboxes", "_recent_bboxes_time", "arrival_frame")
# `Status.value` strings (`tracked_object.py:11-17`).
STATUS_VALUES = ("stopped", "moving", "stopping", "unobserved", "proceeding")
ENVELOPE_KEYS = ("tr_id", "xyxy", "cls_str", "conf", "state_dict", "data")
VEHICLE_CLASSES = ("beltloader", "gse")
# Only beltloader records carry `data.bl_type`; gse/airplane/person records have `data: null` (observed on ATL-C5).
BL_TYPE_CLASSES = ("beltloader",)


def expected_keys(class_name: str) -> tuple:
    """Exact key set (ordered) per class as written by v1; person → empty (default `Track`)."""
    if class_name == "airplane":
        return BASE_KEYS + AIRPLANE_KEYS
    if class_name in VEHICLE_CLASSES:
        return BASE_KEYS + VEHICLE_KEYS
    if class_name == "person":
        return ()
    raise KeyError(f"no v1 state contract for class {class_name!r}")


@dataclass
class Violation:
    kind: str  # missing | unknown | status | envelope
    detail: str


@dataclass
class ContractCheck:
    violations: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def add(self, kind: str, detail: str) -> None:
        self.violations.append(Violation(kind, detail))


def check_state_dict(class_name: str, state: dict, *, allow_tolerated_extras: bool = True) -> ContractCheck:
    """Would v1's `from_state_dict` for `class_name` accept this state, and does it carry every key v1 writes?"""
    res = ContractCheck()
    exp = set(expected_keys(class_name))
    got = set(state.keys())
    for k in sorted(exp - got):
        res.add("missing", k)
    unknown = got - exp
    if allow_tolerated_extras:
        unknown -= set(TOLERATED_EXTRAS)
    for k in sorted(unknown):
        res.add("unknown", k)  # v1 raises ValueError("Unexpected keys in state_dict: ...") on these
    if "_status" in state and state["_status"] not in STATUS_VALUES:
        res.add("status", f"_status={state['_status']!r} not in {STATUS_VALUES}")
    if state.get("_class_name") not in (None, class_name):
        res.add("status", f"_class_name={state.get('_class_name')!r} != {class_name!r}")
    return res


def check_record(rec: dict) -> ContractCheck:
    """Envelope + state check of one serialised track record (`Track.__dict__`)."""
    res = ContractCheck()
    missing = [k for k in ENVELOPE_KEYS if k not in rec]
    if missing:
        res.add("envelope", f"missing envelope keys {missing}")
        return res
    if rec.get("conf") != 0.0:
        res.add("envelope", f"conf is {rec.get('conf')!r}, v1 always writes 0.0")
    xyxy = rec.get("xyxy")
    if not (isinstance(xyxy, list) and len(xyxy) == 4):
        res.add("envelope", f"xyxy must be a 4-list, got {xyxy!r}")
    cls = rec.get("cls_str")
    data = rec.get("data")
    if cls in BL_TYPE_CLASSES:
        if not (isinstance(data, dict) and data.get("bl_type") in ("front", "back", "undefined")):
            res.add("envelope", f"beltloader data.bl_type must be front|back|undefined, got {data!r}")
    elif data not in (None, {}):
        res.add("envelope", f"data must be null for {cls}, got {data!r}")
    state = rec.get("state_dict")
    if not isinstance(state, dict):
        res.add("envelope", "state_dict must be a dict")
        return res
    try:
        inner = check_state_dict(cls, state)
    except KeyError as e:
        res.add("envelope", str(e))
        return res
    res.violations.extend(inner.violations)
    return res


def make_record(tr_id: int, xyxy, cls_str: str, state_dict: dict, bl_type: str | None = None) -> dict:
    """Build a v1-compat record; `conf` is always 0.0, `data` only for beltloaders (`tracker.py` → `Track.__dict__`)."""
    data = {"bl_type": bl_type or "undefined"} if cls_str in BL_TYPE_CLASSES else None
    return {
        "tr_id": int(tr_id),
        "xyxy": [int(v) for v in xyxy],
        "cls_str": cls_str,
        "conf": 0.0,
        "state_dict": state_dict,
        "data": data,
    }
