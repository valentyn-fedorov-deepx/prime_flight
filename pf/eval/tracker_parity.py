"""Tracker parity: compare two tracker ndjson files on the fields the modules actually consume.

Production tracker records look like (docs/analysis/contract_observed.md):
    {"<frame_no>": [ {"tr_id": 12, "xyxy": [x1,y1,x2,y2], "cls_str": "airplane", "conf": 0.0,
                      "state_dict": {"_class_name": "airplane", "_obj_id": 1, "_status": "stopped",
                                     "arrival_frame": [11151], ... 39 keys ...}, "data": null}, ... ]}

Rules (measurement_plan.md §3.2, module_consumption.md §2.2):
  * objects are matched by identity `(cls_str, state_dict._obj_id)` — `tr_id` collides across classes and re-spawns;
  * only CONSUMED fields are compared by default (what the 27 modules read); the optical-flow payload `_p0` / `_st`
    (80–87 % of the bytes) is compared by length only;
  * frames are matched by key (`frame_id`), never by position (X2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pf.eval.parity import iter_ndjson

# state_dict fields read by modules (module_consumption.md §2.2–2.3) + the envelope fields.
CONSUMED_STATE_FIELDS = (
    "_class_name",
    "_obj_id",
    "_xyxy",
    "_status",
    "_is_stopped",
    "_stops_count",
    "arrival_frame",
    "departure_frame",
    "have_arrival_stage",
    "have_pre_arrival_stage",
    "_static_frames",
    "_moving_frames",
    "_stopping_time_thres",
    "_display_proceeding_time_thres",
    "_of_dots_lifetime",
    "_init_dots_lifetime",
)
LENGTH_ONLY_FIELDS = ("_p0", "_st")
ENVELOPE_FIELDS = ("xyxy", "cls_str", "tr_id")


def identity(obj: dict):
    sd = obj.get("state_dict") or {}
    return obj.get("cls_str"), sd.get("_obj_id")


def _norm(v, ndigits):
    if isinstance(v, float):
        return round(v, ndigits)
    if isinstance(v, list):
        return [_norm(x, ndigits) for x in v]
    if isinstance(v, dict):
        return {k: _norm(x, ndigits) for k, x in v.items()}
    return v


@dataclass
class TrackerParity:
    frames_compared: int = 0
    frames_equal: int = 0
    frames_only_in_a: int = 0
    frames_only_in_b: int = 0
    objects_a: int = 0
    objects_b: int = 0
    objects_matched: int = 0
    objects_only_in_a: int = 0
    objects_only_in_b: int = 0
    field_mismatches: dict = field(default_factory=dict)  # field -> count
    first_diffs: list = field(default_factory=list)  # (frame_no, identity, field, a, b)
    identities_a: set = field(default_factory=set)
    identities_b: set = field(default_factory=set)

    @property
    def frame_parity(self) -> float:
        return self.frames_equal / self.frames_compared if self.frames_compared else 1.0

    def summary(self) -> dict:
        return {
            "frames_compared": self.frames_compared,
            "frames_equal": self.frames_equal,
            "frame_parity": round(self.frame_parity, 6),
            "frames_only_in_a": self.frames_only_in_a,
            "frames_only_in_b": self.frames_only_in_b,
            "objects_a": self.objects_a,
            "objects_b": self.objects_b,
            "objects_matched": self.objects_matched,
            "objects_only_in_a": self.objects_only_in_a,
            "objects_only_in_b": self.objects_only_in_b,
            "unique_identities_a": len(self.identities_a),
            "unique_identities_b": len(self.identities_b),
            "field_mismatches": dict(sorted(self.field_mismatches.items(), key=lambda kv: -kv[1])),
            "first_diffs": [list(map(str, d)) for d in self.first_diffs[:20]],
        }


def compare_tracker_frames(
    objs_a,
    objs_b,
    frame_no,
    res: TrackerParity,
    *,
    fields=CONSUMED_STATE_FIELDS,
    envelope=ENVELOPE_FIELDS,
    length_only=LENGTH_ONLY_FIELDS,
    ndigits=1,
    max_first_diffs=20,
) -> bool:
    """Compare the object lists of one frame; returns True when everything consumed is equal."""
    a_by = {identity(o): o for o in objs_a or [] if isinstance(o, dict)}
    b_by = {identity(o): o for o in objs_b or [] if isinstance(o, dict)}
    res.objects_a += len(a_by)
    res.objects_b += len(b_by)
    res.identities_a.update(a_by)
    res.identities_b.update(b_by)
    equal = True

    def diff(ident, name, va, vb):
        nonlocal equal
        equal = False
        res.field_mismatches[name] = res.field_mismatches.get(name, 0) + 1
        if len(res.first_diffs) < max_first_diffs:
            res.first_diffs.append((frame_no, ident, name, va, vb))

    for ident, oa in a_by.items():
        ob = b_by.get(ident)
        if ob is None:
            res.objects_only_in_a += 1
            diff(ident, "<object>", "present", "missing")
            continue
        res.objects_matched += 1
        for name in envelope:
            if _norm(oa.get(name), ndigits) != _norm(ob.get(name), ndigits):
                diff(ident, name, oa.get(name), ob.get(name))
        da, db = (oa.get("data") or {}), (ob.get("data") or {})
        if da.get("bl_type") != db.get("bl_type"):
            diff(ident, "data.bl_type", da.get("bl_type"), db.get("bl_type"))
        sa, sb = oa.get("state_dict") or {}, ob.get("state_dict") or {}
        for name in fields:
            if _norm(sa.get(name), ndigits) != _norm(sb.get(name), ndigits):
                diff(ident, name, sa.get(name), sb.get(name))
        for name in length_only:
            la = len(sa[name]) if isinstance(sa.get(name), list) else None
            lb = len(sb[name]) if isinstance(sb.get(name), list) else None
            if la != lb:
                diff(ident, f"len({name})", la, lb)
        if set(sa.keys()) != set(sb.keys()):
            diff(ident, "state_dict.keys", sorted(set(sa) - set(sb)), sorted(set(sb) - set(sa)))
    for ident in b_by.keys() - a_by.keys():
        res.objects_only_in_b += 1
        diff(ident, "<object>", "missing", "present")
    return equal


def compare_tracker_ndjson(path_a: str, path_b: str, **kw) -> TrackerParity:
    """Frame-by-frame comparison of two tracker ndjson files (streaming; frames matched by key)."""
    res = TrackerParity()
    ia, ib = iter_ndjson(path_a), iter_ndjson(path_b)
    na, nb = next(ia, None), next(ib, None)
    while na is not None or nb is not None:
        ka = na[0] if na is not None else None
        kb = nb[0] if nb is not None else None
        if kb is None or (ka is not None and ka < kb):
            res.frames_only_in_a += 1
            na = next(ia, None)
            continue
        if ka is None or kb < ka:
            res.frames_only_in_b += 1
            nb = next(ib, None)
            continue
        res.frames_compared += 1
        if compare_tracker_frames(na[1], nb[1], ka, res, **kw):
            res.frames_equal += 1
        na, nb = next(ia, None), next(ib, None)
    return res
