#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Streaming inspection of production General Model / Tracker NDJSON outputs.

Goal: document the OBSERVED output contract of the current production GM and
Tracker from data alone (no access to cv_trackers / cv_common source), so that
GM v2 / Tracker v2 can be validated field-by-field (or byte-by-byte) against
these files.

Files (one pair per video, in --dir):
    general_model<VIDEOID>.mp4.ndjson   one JSON object per line: {"<frame>": [[x1,y1,x2,y2,conf,class_id], ...]}
    trackers<VIDEOID>.mp4.ndjson        one JSON object per line: {"<frame>": [ {tr_id, xyxy, cls_str, conf, state_dict, data}, ... ]}

Never loads a whole file (single files are up to ~1.2 GB): every file is read
line by line in binary mode and only aggregates are kept in memory.

Usage:
    python scripts/inspect_ndjson.py --dir G:\\gat_stages\\atlc5_inferences ^
        --videos-dir G:\\gat_stages\\atlc5_videos ^
        --out docs/analysis/ndjson_observed.json [--max-frames 5000] [--workers 7] [--video ID ...]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

GM_PREFIX = "general_model"
TR_PREFIX = "trackers"
SUFFIX = ".mp4.ndjson"

# Nominal frame size used only for the "coordinates are absolute pixels" check.
NOMINAL_W, NOMINAL_H = 1920, 1080

# Airplane state fields with event semantics: sampled at every change + every SAMPLE_EVERY frames.
AIRPLANE_EVENT_FIELDS = (
    "_status", "_is_stopped", "_stops_count", "_stop_point", "_prev_stop_point",
    "have_pre_arrival_stage", "have_arrival_stage", "arrival_frame", "departure_frame",
)
# Counters that change (almost) every frame: sampled every SAMPLE_EVERY frames only, never on change.
AIRPLANE_COUNTER_FIELDS = (
    "_moving_counter", "_stopped_counter", "_static_frames", "_moving_frames",
    "_of_dots_lifetime", "_height_mode",
)
EVENT_FIELD_RE = re.compile(r"arriv|depart|stage|status|stopped|parked", re.I)
SAMPLE_EVERY = 500
MAX_SAMPLES_PER_OBJECT = 3000
SIZE_SAMPLE_EVERY = 25          # every N-th non-empty tracker frame enters the byte-size decomposition
ROUNDTRIP_SAMPLE_EVERY = 25     # every N-th line is re-serialised with json.dumps and compared byte-wise
SMALL_LIST_MAX = 8              # lists up to this length are compared element-wise for constancy
MAX_DISTINCT_VALUES = 24        # per (class, key): keep at most this many distinct scalar values
LIST_WALK_ELEMS = 3             # type inventory looks at the first N elements of every list
VEHICLE_ONLY_KEYS = ("_bl_type_bbox", "_bl_type_frames")
SCALAR_TYPES = (type(None), bool, int, float, str)


# ----------------------------------------------------------------------------- helpers

def is_fp16_representable(x: float) -> bool:
    """True if x is exactly representable as IEEE binary16 (hint that conf comes from a half-precision engine)."""
    if x == 0.0:
        return True
    if not math.isfinite(x):
        return False
    m, e = math.frexp(x)                     # x = m * 2**e, 0.5 <= |m| < 1
    if abs(x) < 2.0 ** -14:                  # subnormal range: multiples of 2**-24
        return (x * 2.0 ** 24).is_integer()
    if e - 1 > 15:
        return False
    return (m * 2048.0).is_integer()         # 10 explicit mantissa bits + implicit one


def redact(v, max_list=8, depth=0):
    """Copy of a JSON value with long lists collapsed, for human-readable examples."""
    if isinstance(v, dict):
        return {k: redact(x, max_list, depth + 1) for k, x in v.items()}
    if isinstance(v, list):
        if len(v) > max_list:
            return "<list len=%d, first=%s>" % (len(v), json.dumps(redact(v[:2], max_list, depth + 1)))
        return [redact(x, max_list, depth + 1) for x in v]
    return v


def hashable(v):
    """Representation used for change detection / distinct-value counting. None if not comparable cheaply."""
    if isinstance(v, SCALAR_TYPES):
        return v
    if isinstance(v, list):
        if len(v) <= SMALL_LIST_MAX and all(isinstance(x, SCALAR_TYPES) for x in v):
            return ("L",) + tuple(v)
        return None
    if isinstance(v, dict):
        if len(v) <= SMALL_LIST_MAX and all(isinstance(x, SCALAR_TYPES) for x in v.values()):
            return ("D",) + tuple(sorted(v.items()))
        return None
    return None


def jsonable(v):
    """Make aggregates JSON-serialisable (Counter/set/tuple keys)."""
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if isinstance(k, tuple):
                k = json.dumps(list(k), default=str)
            elif not isinstance(k, str):
                k = str(k)
            out[k] = jsonable(x)
        return out
    if isinstance(v, (set, frozenset)):
        return sorted(jsonable(x) for x in v) if all(isinstance(x, (int, float, str)) for x in v) else [jsonable(x) for x in v]
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, float) and not math.isfinite(v):
        return str(v)
    return v


def percentile_from_hist(hist: dict, q: float):
    """q in [0,1]; hist maps value -> frequency."""
    total = sum(hist.values())
    if total == 0:
        return None
    target = q * total
    acc = 0
    for val in sorted(hist):
        acc += hist[val]
        if acc >= target:
            return val
    return max(hist)


class KeySeq:
    """Frame-key numbering: min/max, duplicates, gaps, monotonicity, contiguity 1..N."""

    def __init__(self):
        self.n_lines = 0
        self.n_parse_err = 0
        self.n_bad_top_level = 0     # not a dict with exactly one key
        self.n_non_int_key = 0
        self.n_value_not_list = 0
        self.seen = set()
        self.dups = 0
        self.non_monotonic = 0
        self.gaps = 0
        self.missing = 0
        self.gap_examples = []
        self.prev = None
        self.min = None
        self.max = None
        self.key_examples = []

    def push(self, k: int, raw_key):
        if len(self.key_examples) < 3:
            self.key_examples.append(raw_key)
        if k in self.seen:
            self.dups += 1
        self.seen.add(k)
        if self.min is None or k < self.min:
            self.min = k
        if self.max is None or k > self.max:
            self.max = k
        if self.prev is not None:
            if k < self.prev:
                self.non_monotonic += 1
            elif k > self.prev + 1:
                self.gaps += 1
                self.missing += k - self.prev - 1
                if len(self.gap_examples) < 10:
                    self.gap_examples.append([self.prev, k])
        self.prev = k

    def summary(self):
        n = len(self.seen)
        contiguous = bool(n > 0 and self.min == 1 and self.max == n and self.dups == 0 and self.non_monotonic == 0)
        return {
            "lines": self.n_lines,
            "distinct_keys": n,
            "key_min": self.min,
            "key_max": self.max,
            "key_examples_raw": self.key_examples,
            "contiguous_1_to_N": contiguous,
            "duplicate_keys": self.dups,
            "non_monotonic_steps": self.non_monotonic,
            "gaps": self.gaps,
            "missing_keys_in_gaps": self.missing,
            "gap_examples": self.gap_examples,
            "parse_errors": self.n_parse_err,
            "bad_top_level_lines": self.n_bad_top_level,
            "non_int_keys": self.n_non_int_key,
            "value_not_list": self.n_value_not_list,
        }


def iter_frames(path, ks: KeySeq, max_frames):
    """Yield (frame_int, value, line_bytes, line_index) for every parsable line; updates KeySeq counters."""
    with open(path, "rb") as f:
        for line in f:
            ks.n_lines += 1
            if max_frames and ks.n_lines > max_frames:
                ks.n_lines -= 1
                break
            if not line.strip():
                ks.n_parse_err += 1
                continue
            try:
                d = json.loads(line)
            except Exception:
                ks.n_parse_err += 1
                continue
            if not isinstance(d, dict) or len(d) != 1:
                ks.n_bad_top_level += 1
                if not isinstance(d, dict) or not d:
                    continue
            raw_key, value = next(iter(d.items()))
            try:
                k = int(raw_key)
            except (TypeError, ValueError):
                ks.n_non_int_key += 1
                continue
            ks.push(k, raw_key)
            if not isinstance(value, list):
                ks.n_value_not_list += 1
                continue
            yield k, value, line, ks.n_lines


# ----------------------------------------------------------------------------- GM

def inspect_gm(path, max_frames=None):
    t0 = time.time()
    ks = KeySeq()
    per_class = {}
    hist = Counter()                 # detections per frame -> frames
    det_shapes = Counter()           # tuple of type names per detection
    det_len = Counter()              # len(det) for malformed detections
    n_det = 0
    n_det_conf_valid = 0
    weird = {}                       # class_id -> records whose conf is not a float in [0,1]
    runs_hist = Counter()            # number of non-increasing conf runs per frame -> frames
    class_run_index = defaultdict(Counter)   # class_id -> run index -> detections
    empty_frames = 0
    max_per_frame = (0, None)
    coord = {"x1_min": None, "y1_min": None, "x2_max": None, "y2_max": None, "x1_max": None, "y1_max": None}
    n_nonint_coord = 0
    n_x2_le_x1 = 0
    n_y2_le_y1 = 0
    n_out_of_nominal = 0
    n_conf_fp16 = 0
    n_conf_out01 = 0
    n_nonfinite = 0
    conf_global = [1.0, 0.0]
    frames_sorted_desc = 0
    frames_ge2 = 0
    bytes_total = 0
    max_line = (0, None)
    example_line = None
    roundtrip = {"sampled": 0, "identical": 0, "mismatch_examples": []}

    for k, dets, line, idx in iter_frames(path, ks, max_frames):
        nb = len(line)
        bytes_total += nb
        if nb > max_line[0]:
            max_line = (nb, k)
        if example_line is None:
            example_line = {"frame": k, "n_detections": len(dets), "first_3": dets[:3]}
        if idx % ROUNDTRIP_SAMPLE_EVERY == 1:
            roundtrip["sampled"] += 1
            re_ser = (json.dumps({str(k): dets}) + "\n").encode("utf-8")
            if re_ser == line or re_ser.rstrip(b"\r\n") == line.rstrip(b"\r\n"):
                roundtrip["identical"] += 1
            elif len(roundtrip["mismatch_examples"]) < 2:
                roundtrip["mismatch_examples"].append({"frame": k, "file": line[:160].decode("utf-8", "replace"),
                                                       "dumps": re_ser[:160].decode("utf-8", "replace")})
        n = len(dets)
        hist[n] += 1
        if n == 0:
            empty_frames += 1
        if n > max_per_frame[0]:
            max_per_frame = (n, k)
        per_frame_cls = Counter()
        prev_conf = None
        sorted_desc = True
        run_idx = 0
        for pos, det in enumerate(dets):
            if not isinstance(det, list) or len(det) != 6:
                det_len[len(det) if isinstance(det, list) else -1] += 1
                continue
            n_det += 1
            det_shapes[tuple(type(v).__name__ for v in det)] += 1
            x1, y1, x2, y2, c, cid = det
            try:
                if not all(math.isfinite(v) for v in (x1, y1, x2, y2, c)):
                    n_nonfinite += 1
                    continue
            except TypeError:
                n_nonfinite += 1
                continue
            conf_valid = isinstance(c, float) and 0.0 <= c <= 1.0
            if not conf_valid:
                w = weird.get(cid)
                if w is None:
                    w = weird[cid] = {"count": 0, "values": Counter(), "types": Counter(), "first_frame": k,
                                      "last_frame": k, "position_first": 0, "position_last": 0}
                w["count"] += 1
                w["last_frame"] = k
                w["types"][type(c).__name__] += 1
                if len(w["values"]) < 10 or str(c) in w["values"]:
                    w["values"][str(c)] += 1
                if pos == 0:
                    w["position_first"] += 1
                if pos == n - 1:
                    w["position_last"] += 1
            for v in (x1, y1, x2, y2):
                if isinstance(v, float) and not v.is_integer():
                    n_nonint_coord += 1
                    break
            if x2 <= x1:
                n_x2_le_x1 += 1
            if y2 <= y1:
                n_y2_le_y1 += 1
            if x1 < 0 or y1 < 0 or x2 > NOMINAL_W or y2 > NOMINAL_H:
                n_out_of_nominal += 1
            if coord["x1_min"] is None:
                coord.update(x1_min=x1, y1_min=y1, x2_max=x2, y2_max=y2, x1_max=x1, y1_max=y1)
            else:
                if x1 < coord["x1_min"]: coord["x1_min"] = x1
                if y1 < coord["y1_min"]: coord["y1_min"] = y1
                if x2 > coord["x2_max"]: coord["x2_max"] = x2
                if y2 > coord["y2_max"]: coord["y2_max"] = y2
                if x1 > coord["x1_max"]: coord["x1_max"] = x1
                if y1 > coord["y1_max"]: coord["y1_max"] = y1
            if conf_valid:
                n_det_conf_valid += 1
                if is_fp16_representable(c):
                    n_conf_fp16 += 1
                if c < conf_global[0]: conf_global[0] = c
                if c > conf_global[1]: conf_global[1] = c
                if prev_conf is not None and c > prev_conf:
                    sorted_desc = False
                    run_idx += 1
                prev_conf = c
                class_run_index[cid][run_idx] += 1
            else:
                n_conf_out01 += 1
            cs = per_class.get(cid)
            w = x2 - x1
            h = y2 - y1
            if cs is None:
                cs = per_class[cid] = {"count": 0, "count_conf_valid": 0, "conf_min": None, "conf_max": None, "conf_sum": 0.0,
                                       "w_min": w, "w_max": w, "w_sum": 0.0, "h_min": h, "h_max": h, "h_sum": 0.0,
                                       "max_per_frame": 0, "frames_present": 0, "first_frame": k, "last_frame": k,
                                       "id_type": type(cid).__name__}
            cs["count"] += 1
            if conf_valid:
                cs["count_conf_valid"] += 1
                cs["conf_sum"] += c
                if cs["conf_min"] is None or c < cs["conf_min"]: cs["conf_min"] = c
                if cs["conf_max"] is None or c > cs["conf_max"]: cs["conf_max"] = c
            cs["w_sum"] += w; cs["h_sum"] += h
            if w < cs["w_min"]: cs["w_min"] = w
            if w > cs["w_max"]: cs["w_max"] = w
            if h < cs["h_min"]: cs["h_min"] = h
            if h > cs["h_max"]: cs["h_max"] = h
            cs["last_frame"] = k
            per_frame_cls[cid] += 1
        if n >= 2:
            frames_ge2 += 1
            if sorted_desc:
                frames_sorted_desc += 1
        if n >= 1:
            runs_hist[run_idx + 1] += 1
        for cid, m in per_frame_cls.items():
            cs = per_class[cid]
            cs["frames_present"] += 1
            if m > cs["max_per_frame"]:
                cs["max_per_frame"] = m

    n_frames = len(ks.seen)
    classes = {}
    for cid in sorted(per_class, key=lambda x: (str(type(x)), x)):
        cs = per_class[cid]
        classes[str(cid)] = {
            "class_id": cid, "id_type": cs["id_type"], "count": cs["count"],
            "count_conf_valid": cs["count_conf_valid"],
            "share_of_detections": round(cs["count"] / n_det, 5) if n_det else None,
            "conf_min": cs["conf_min"], "conf_max": cs["conf_max"],
            "conf_mean": round(cs["conf_sum"] / cs["count_conf_valid"], 5) if cs["count_conf_valid"] else None,
            "sorted_run_index": {str(r): c for r, c in sorted(class_run_index[cid].items())},
            "w_min": cs["w_min"], "w_max": cs["w_max"], "w_mean": round(cs["w_sum"] / cs["count"], 1),
            "h_min": cs["h_min"], "h_max": cs["h_max"], "h_mean": round(cs["h_sum"] / cs["count"], 1),
            "max_per_frame": cs["max_per_frame"], "frames_present": cs["frames_present"],
            "frames_present_share": round(cs["frames_present"] / n_frames, 4) if n_frames else None,
            "first_frame": cs["first_frame"], "last_frame": cs["last_frame"],
        }
    return {
        "file": os.path.basename(path),
        "file_bytes": os.path.getsize(path),
        "elapsed_s": round(time.time() - t0, 1),
        "keys": ks.summary(),
        "frames": n_frames,
        "empty_frames": empty_frames,
        "detections_total": n_det,
        "detections_per_frame": {
            "mean": round(n_det / n_frames, 3) if n_frames else None,
            "min": min(hist) if hist else None,
            "p50": percentile_from_hist(hist, 0.50),
            "p90": percentile_from_hist(hist, 0.90),
            "p99": percentile_from_hist(hist, 0.99),
            "max": max_per_frame[0], "max_at_frame": max_per_frame[1],
            "histogram": {str(n): hist[n] for n in sorted(hist)},
        },
        "detection_record": {
            "shapes_by_type": {json.dumps(list(s)): c for s, c in det_shapes.most_common()},
            "malformed_len": {str(l): c for l, c in det_len.items()},
            "coords_integer_valued": n_nonint_coord == 0,
            "non_integer_coord_records": n_nonint_coord,
            "coord_range": coord,
            "within_nominal_1920x1080": n_out_of_nominal == 0,
            "out_of_nominal_records": n_out_of_nominal,
            "x2_le_x1": n_x2_le_x1, "y2_le_y1": n_y2_le_y1,
            "non_finite": n_nonfinite,
            "conf_min": conf_global[0], "conf_max": conf_global[1],
            "conf_not_float_in_0_1": n_conf_out01,
            "weird_conf_by_class": {str(cid): {"count": w["count"], "values": dict(w["values"]), "types": dict(w["types"]),
                                               "first_frame": w["first_frame"], "last_frame": w["last_frame"],
                                               "at_position_first": w["position_first"], "at_position_last": w["position_last"]}
                                    for cid, w in weird.items()},
            "conf_fp16_representable": n_conf_fp16,
            "conf_fp16_share": round(n_conf_fp16 / n_det_conf_valid, 5) if n_det_conf_valid else None,
            "frames_sorted_by_conf_desc": frames_sorted_desc,
            "frames_with_ge2_detections": frames_ge2,
            "sorted_runs_per_frame_hist": {str(r): c for r, c in sorted(runs_hist.items())},
        },
        "classes": classes,
        "class_ids": sorted((cid for cid in per_class), key=lambda x: (str(type(x)), x)),
        "bytes": {"total": bytes_total, "avg_per_line": round(bytes_total / ks.n_lines, 1) if ks.n_lines else None,
                  "max_line": max_line[0], "max_line_frame": max_line[1]},
        "json_dumps_roundtrip": roundtrip,
        "example_first_line": example_line,
    }


# ----------------------------------------------------------------------------- Trackers

def box_iou(a, b):
    """a = [x1,y1,x2,y2] (tracker), b = (x1,y1,x2,y2,...) (GM)."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = ix2 - ix1, iy2 - iy1
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def iou_bin(v, exact):
    if exact:
        return "exact"
    if v >= 0.99: return "[0.99,1)"
    if v >= 0.9: return "[0.9,0.99)"
    if v >= 0.7: return "[0.7,0.9)"
    if v >= 0.5: return "[0.5,0.7)"
    if v > 0: return "(0,0.5)"
    return "0"


class LockstepGM:
    """Streams the GM file of the same video in lockstep with the tracker file (both keyed 1..N, monotonic)."""

    def __init__(self, path):
        self.f = open(path, "rb") if path else None
        self.k = None
        self.dets = None
        self.exhausted = self.f is None
        self.missing = 0

    def get(self, k):
        if self.exhausted:
            return None
        while self.k is None or self.k < k:
            line = self.f.readline()
            if not line:
                self.exhausted = True
                return None
            try:
                d = json.loads(line)
                rk, v = next(iter(d.items()))
                self.k = int(rk)
                self.dets = v if isinstance(v, list) else []
            except Exception:  # noqa: BLE001
                continue
        if self.k == k:
            return self.dets
        self.missing += 1
        return None

    def close(self):
        if self.f:
            self.f.close()


def new_class_stats():
    return {
        "object_frames": 0, "empty_state": 0, "obj_ids": set(), "tr_ids": set(),
        "envelope_orders": Counter(),
        "join": {"objects": 0, "exact_bbox": 0, "iou_bins": Counter(), "no_match_ge05": 0,
                 "class_id_by_iou": Counter(), "matched_conf": {}},
        "first_frame": None, "last_frame": None, "max_per_frame": 0,
        "signatures": {},            # tuple(state keys) -> {"count", "first_frame", "last_frame"}
        "class_name_in_state": Counter(),
        "status": Counter(), "is_stopped": Counter(), "to_numpy": Counter(), "to_status": Counter(),
        "data": Counter(),
        "conf_nonzero": 0, "conf_min": None, "conf_max": None,
        "tr_id_ne_obj_id": 0, "xyxy_ne_state_xyxy": 0,
        "fields": {},                # key -> constancy / distinct-value stats
    }


def new_field_stats():
    return {"present": 0, "compared": 0, "changes": 0, "objects_changed": set(), "large": 0,
            "distinct": Counter(), "many": False, "num_min": None, "num_max": None, "types": Counter()}


def walk_types(v, p, paths):
    e = paths.get(p)
    if e is None:
        e = paths[p] = {"count": 0, "types": Counter(), "len_min": None, "len_max": None, "len_sum": 0, "len_n": 0}
    e["count"] += 1
    tn = type(v).__name__
    e["types"][tn] += 1
    if tn == "dict":
        for kk, vv in v.items():
            walk_types(vv, p + "." + kk, paths)
    elif tn == "list":
        L = len(v)
        e["len_sum"] += L
        e["len_n"] += 1
        if e["len_min"] is None or L < e["len_min"]: e["len_min"] = L
        if e["len_max"] is None or L > e["len_max"]: e["len_max"] = L
        for vv in v[:LIST_WALK_ELEMS]:
            walk_types(vv, p + "[]", paths)


def inspect_tracker(path, max_frames=None, gm_path=None):
    t0 = time.time()
    ks = KeySeq()
    paths = {}
    cls_stats = {}
    gm = LockstepGM(gm_path)
    rev = {}                         # GM class_id -> [detections, detections with a tracker object at IoU>=0.5]
    last_vals = {}                   # (cls, obj_id) -> {key: hashable value}
    airplanes = {}                   # obj_id -> event timeline
    objs_hist = Counter()
    empty_frames = 0
    first_nonempty = None
    nonempty_frames = 0
    max_objs = (0, None)
    dup_id_in_frame = 0
    envelope_keys = Counter()
    envelope_key_orders = Counter()
    id_classes = defaultdict(set)    # tr_id -> classes
    bytes_total = 0
    max_line = (0, None)
    size_sample = {"frames_sampled": 0, "bytes_total": 0, "per_class": {}}
    roundtrip = {"sampled": 0, "identical": 0, "mismatch_examples": []}
    examples = {}                    # cls_str -> redacted first object
    example_frame = None

    for k, objs, line, idx in iter_frames(path, ks, max_frames):
        nb = len(line)
        bytes_total += nb
        if nb > max_line[0]:
            max_line = (nb, k)
        n = len(objs)
        objs_hist[n] += 1
        dets = gm.get(k) if gm_path else None
        gm_boxes = None
        if dets is not None:
            gm_boxes = [(d[0], d[1], d[2], d[3], d[5], d[4]) for d in dets if isinstance(d, list) and len(d) == 6]
            for b in gm_boxes:
                r = rev.get(b[4])
                if r is None:
                    r = rev[b[4]] = [0, 0]
                r[0] += 1
        matched_det_idx = set()
        if n == 0:
            empty_frames += 1
            continue
        nonempty_frames += 1
        if first_nonempty is None:
            first_nonempty = k
            example_frame = {"frame": k, "top_level_type": type(objs).__name__, "n_objects": n,
                             "element_type": type(objs[0]).__name__,
                             "first_object_redacted": redact(objs[0])}
        if n > max_objs[0]:
            max_objs = (n, k)
        if idx % ROUNDTRIP_SAMPLE_EVERY == 1:
            roundtrip["sampled"] += 1
            re_ser = (json.dumps({str(k): objs}) + "\n").encode("utf-8")
            if re_ser.rstrip(b"\r\n") == line.rstrip(b"\r\n"):
                roundtrip["identical"] += 1
            elif len(roundtrip["mismatch_examples"]) < 2:
                # find first differing byte
                a, b = re_ser.rstrip(b"\r\n"), line.rstrip(b"\r\n")
                i = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
                roundtrip["mismatch_examples"].append({"frame": k, "first_diff_at": i,
                                                       "file": b[max(0, i - 60):i + 60].decode("utf-8", "replace"),
                                                       "dumps": a[max(0, i - 60):i + 60].decode("utf-8", "replace")})
        do_size = (nonempty_frames % SIZE_SAMPLE_EVERY == 1)
        if do_size:
            size_sample["frames_sampled"] += 1
            size_sample["bytes_total"] += nb
        per_frame_cls = Counter()
        ids_in_frame = set()
        for obj in objs:
            if not isinstance(obj, dict):
                walk_types(obj, "<non-dict object>", paths)
                continue
            envelope_keys.update(obj.keys())
            envelope_key_orders[tuple(obj.keys())] += 1
            for kk, vv in obj.items():
                walk_types(vv, kk, paths)
            cls = obj.get("cls_str")
            state = obj.get("state_dict")
            tr_id = obj.get("tr_id")
            cs = cls_stats.get(cls)
            if cs is None:
                cs = cls_stats[cls] = new_class_stats()
                cs["first_frame"] = k
            cs["object_frames"] += 1
            cs["last_frame"] = k
            cs["envelope_orders"][tuple(obj.keys())] += 1
            per_frame_cls[cls] += 1
            cs["tr_ids"].add(tr_id)
            xy = obj.get("xyxy")
            if gm_boxes is not None and isinstance(xy, list) and len(xy) == 4:
                js = cs["join"]
                js["objects"] += 1
                best, best_i = 0.0, -1
                for i, b in enumerate(gm_boxes):
                    v = box_iou(xy, b)
                    if v > best:
                        best, best_i = v, i
                exact = best_i >= 0 and all(gm_boxes[best_i][j] == xy[j] for j in range(4))
                if exact:
                    js["exact_bbox"] += 1
                js["iou_bins"][iou_bin(best, exact)] += 1
                if best >= 0.5:
                    b = gm_boxes[best_i]
                    js["class_id_by_iou"][b[4]] += 1
                    matched_det_idx.add(best_i)
                    mc = js["matched_conf"].get(b[4])
                    if mc is None:
                        mc = js["matched_conf"][b[4]] = [b[5], b[5]]
                    else:
                        if b[5] < mc[0]: mc[0] = b[5]
                        if b[5] > mc[1]: mc[1] = b[5]
                else:
                    js["no_match_ge05"] += 1
            id_classes[tr_id].add(cls)
            if tr_id in ids_in_frame:
                dup_id_in_frame += 1
            ids_in_frame.add(tr_id)
            conf = obj.get("conf")
            if isinstance(conf, (int, float)):
                if conf != 0:
                    cs["conf_nonzero"] += 1
                if cs["conf_min"] is None or conf < cs["conf_min"]: cs["conf_min"] = conf
                if cs["conf_max"] is None or conf > cs["conf_max"]: cs["conf_max"] = conf
            data = obj.get("data")
            dkey = json.dumps(data, sort_keys=True, default=str)
            if len(cs["data"]) < 50 or dkey in cs["data"]:
                cs["data"][dkey] += 1
            else:
                cs["data"]["<other>"] += 1
            if cls not in examples:
                examples[cls] = {"frame": k, "object_redacted": redact(obj)}
            if do_size:
                pc = size_sample["per_class"].get(cls)
                if pc is None:
                    pc = size_sample["per_class"][cls] = {"objects": 0, "bytes": 0, "envelope_bytes": 0, "keys": Counter()}
                pc["objects"] += 1
                pc["bytes"] += len(json.dumps(obj))
                pc["envelope_bytes"] += len(json.dumps({kk: vv for kk, vv in obj.items() if kk != "state_dict"}))
                if isinstance(state, dict):
                    for kk, vv in state.items():
                        pc["keys"][kk] += len(json.dumps(vv)) + len(kk) + 6   # + quotes, colon, comma, spaces
            if not isinstance(state, dict) or not state:
                cs["empty_state"] += 1
                sig = ()
                se = cs["signatures"].get(sig)
                if se is None:
                    se = cs["signatures"][sig] = {"count": 0, "first_frame": k, "last_frame": k}
                se["count"] += 1
                se["last_frame"] = k
                continue
            sig = tuple(state.keys())
            se = cs["signatures"].get(sig)
            if se is None:
                se = cs["signatures"][sig] = {"count": 0, "first_frame": k, "last_frame": k}
            se["count"] += 1
            se["last_frame"] = k
            cname = state.get("_class_name")
            cs["class_name_in_state"][str(cname)] += 1
            obj_id = state.get("_obj_id")
            cs["obj_ids"].add(obj_id)
            if obj_id != tr_id:
                cs["tr_id_ne_obj_id"] += 1
            if state.get("_xyxy") != obj.get("xyxy"):
                cs["xyxy_ne_state_xyxy"] += 1
            cs["status"][str(state.get("_status"))] += 1
            cs["is_stopped"][str(state.get("_is_stopped"))] += 1
            cs["to_numpy"][json.dumps(state.get("to_numpy"))] += 1
            cs["to_status"][json.dumps(state.get("to_status"))] += 1
            # constancy per field for the same object across frames
            lv_key = (cls, obj_id)
            lv = last_vals.get(lv_key)
            if lv is None:
                lv = last_vals[lv_key] = {}
            fields = cs["fields"]
            for kk, vv in state.items():
                fe = fields.get(kk)
                if fe is None:
                    fe = fields[kk] = new_field_stats()
                fe["present"] += 1
                fe["types"][type(vv).__name__] += 1
                h = hashable(vv)
                if h is None:
                    fe["large"] += 1
                    continue
                if isinstance(vv, (int, float)) and not isinstance(vv, bool):
                    if fe["num_min"] is None or vv < fe["num_min"]: fe["num_min"] = vv
                    if fe["num_max"] is None or vv > fe["num_max"]: fe["num_max"] = vv
                if not fe["many"]:
                    dk = json.dumps(h, default=str) if not isinstance(h, str) else h
                    if dk in fe["distinct"] or len(fe["distinct"]) < MAX_DISTINCT_VALUES:
                        fe["distinct"][dk] += 1
                    else:
                        fe["many"] = True
                if kk in lv:
                    fe["compared"] += 1
                    if lv[kk] != h:
                        fe["changes"] += 1
                        fe["objects_changed"].add(obj_id)
                lv[kk] = h
            # airplane event timeline
            if cls == "airplane" or cname == "airplane":
                ap = airplanes.get(obj_id)
                if ap is None:
                    ap = airplanes[obj_id] = {
                        "obj_id": obj_id, "cls_str": cls, "first_frame": k, "last_frame": k, "n_frames": 0,
                        "samples": [], "truncated": False, "_last_ev": None,
                        "status_counter": Counter(), "status_transitions": 0, "_last_status": None,
                        "arrival_frame": {"first_set_at_frame": None, "value_when_set": None, "distinct_values": Counter()},
                        "departure_frame": {"first_set_at_frame": None, "value_when_set": None, "distinct_values": Counter()},
                        "have_arrival_stage_first_true": None, "have_pre_arrival_stage_first_true": None,
                        "leaked_vehicle_keys": Counter(), "n_keys": Counter(),
                        "_prev_frame": None, "_run_start": k, "runs": [], "n_runs": 1,
                    }
                ap["n_frames"] += 1
                if ap["_prev_frame"] is not None and k != ap["_prev_frame"] + 1:
                    ap["n_runs"] += 1
                    if len(ap["runs"]) < 60:
                        ap["runs"].append([ap["_run_start"], ap["_prev_frame"]])
                    ap["_run_start"] = k
                ap["_prev_frame"] = k
                ap["last_frame"] = k
                ap["n_keys"][len(state)] += 1
                for vk in VEHICLE_ONLY_KEYS:
                    if vk in state:
                        ap["leaked_vehicle_keys"][vk] += 1
                st = state.get("_status")
                ap["status_counter"][str(st)] += 1
                if ap["_last_status"] is not None and st != ap["_last_status"]:
                    ap["status_transitions"] += 1
                ap["_last_status"] = st
                for fld in ("arrival_frame", "departure_frame"):
                    val = state.get(fld)
                    if val is not None:
                        if ap[fld]["first_set_at_frame"] is None:
                            ap[fld]["first_set_at_frame"] = k
                            ap[fld]["value_when_set"] = val
                        if len(ap[fld]["distinct_values"]) < 20 or str(val) in ap[fld]["distinct_values"]:
                            ap[fld]["distinct_values"][str(val)] += 1
                if state.get("have_arrival_stage") is True and ap["have_arrival_stage_first_true"] is None:
                    ap["have_arrival_stage_first_true"] = k
                if state.get("have_pre_arrival_stage") is True and ap["have_pre_arrival_stage_first_true"] is None:
                    ap["have_pre_arrival_stage_first_true"] = k
                ev_keys = list(AIRPLANE_EVENT_FIELDS) + [x for x in state if EVENT_FIELD_RE.search(x)
                                                         and x not in AIRPLANE_EVENT_FIELDS
                                                         and x not in AIRPLANE_COUNTER_FIELDS]
                ev = {x: state.get(x, "<absent>") for x in ev_keys}
                ev_h = json.dumps(ev, sort_keys=True, default=str)
                if ap["_last_ev"] is None or ev_h != ap["_last_ev"] or k % SAMPLE_EVERY == 0:
                    if len(ap["samples"]) < MAX_SAMPLES_PER_OBJECT:
                        rec = {"frame": k, "xyxy": obj.get("xyxy")}
                        rec.update(ev)
                        rec.update({x: state.get(x, "<absent>") for x in AIRPLANE_COUNTER_FIELDS})
                        rec["n_keys"] = len(state)
                        ap["samples"].append(rec)
                    else:
                        ap["truncated"] = True
                ap["_last_ev"] = ev_h
        for cls, m in per_frame_cls.items():
            if m > cls_stats[cls]["max_per_frame"]:
                cls_stats[cls]["max_per_frame"] = m
        if gm_boxes is not None:
            for i in matched_det_idx:
                rev[gm_boxes[i][4]][1] += 1
    gm.close()

    n_frames = len(ks.seen)
    # ---- finalise per-class
    classes_out = {}
    for cls in sorted(cls_stats, key=str):
        cs = cls_stats[cls]
        sigs = []
        for sig, se in sorted(cs["signatures"].items(), key=lambda x: -x[1]["count"]):
            sigs.append({"n_keys": len(sig), "count": se["count"], "first_frame": se["first_frame"],
                         "last_frame": se["last_frame"], "keys": list(sig)})
        fields_out = {}
        for kk, fe in cs["fields"].items():
            fields_out[kk] = {
                "present": fe["present"], "types": dict(fe["types"]),
                "compared": fe["compared"], "changes": fe["changes"],
                "objects_changed": len(fe["objects_changed"]),
                "constant_per_object": (fe["changes"] == 0 and fe["large"] == 0 and fe["compared"] > 0),
                "not_compared_large_values": fe["large"],
                "distinct_values": ({"<more_than_%d>" % MAX_DISTINCT_VALUES: True} if fe["many"]
                                    else {d: c for d, c in fe["distinct"].most_common()}),
                "num_min": fe["num_min"], "num_max": fe["num_max"],
            }
        classes_out[str(cls)] = {
            "cls_str": cls,
            "object_frames": cs["object_frames"],
            "empty_state_dict_object_frames": cs["empty_state"],
            "distinct_tr_ids": len(cs["tr_ids"]),
            "distinct_obj_ids_in_state": len(cs["obj_ids"]),
            "tr_id_min": min((x for x in cs["tr_ids"] if isinstance(x, int)), default=None),
            "tr_id_max": max((x for x in cs["tr_ids"] if isinstance(x, int)), default=None),
            "first_frame": cs["first_frame"], "last_frame": cs["last_frame"],
            "max_per_frame": cs["max_per_frame"],
            "class_name_in_state": dict(cs["class_name_in_state"]),
            "state_signatures": sigs,
            "status_values": dict(cs["status"]),
            "is_stopped_values": dict(cs["is_stopped"]),
            "to_numpy_values": dict(cs["to_numpy"]),
            "to_status_values": dict(cs["to_status"]),
            "data_values": dict(cs["data"].most_common(50)),
            "envelope_conf": {"nonzero": cs["conf_nonzero"], "min": cs["conf_min"], "max": cs["conf_max"]},
            "tr_id_ne_state_obj_id": cs["tr_id_ne_obj_id"],
            "xyxy_ne_state_xyxy": cs["xyxy_ne_state_xyxy"],
            "envelope_key_orders": {json.dumps(list(o)): c for o, c in cs["envelope_orders"].most_common()},
            "join_with_gm": {
                "objects": cs["join"]["objects"],
                "exact_bbox_match": cs["join"]["exact_bbox"],
                "best_iou_bins": dict(cs["join"]["iou_bins"]),
                "no_gm_box_iou_ge05": cs["join"]["no_match_ge05"],
                "gm_class_id_of_best_match": {str(c): n for c, n in cs["join"]["class_id_by_iou"].most_common()},
                "gm_conf_range_of_matches": {str(c): v for c, v in cs["join"]["matched_conf"].items()},
            },
            "fields": fields_out,
        }
    # ---- airplanes
    ap_out = []
    for obj_id, ap in sorted(airplanes.items(), key=lambda x: x[1]["first_frame"]):
        if len(ap["runs"]) < 60:
            ap["runs"].append([ap["_run_start"], ap["last_frame"]])
        ap.pop("_prev_frame", None); ap.pop("_run_start", None)
        ap.pop("_last_ev", None); ap.pop("_last_status", None)
        span = ap["last_frame"] - ap["first_frame"] + 1
        ap["span_frames"] = span
        ap["absent_frames_within_span"] = span - ap["n_frames"]
        ap["status_counter"] = dict(ap["status_counter"])
        ap["leaked_vehicle_keys"] = dict(ap["leaked_vehicle_keys"])
        ap["n_keys"] = dict(ap["n_keys"])
        for fld in ("arrival_frame", "departure_frame"):
            ap[fld]["distinct_values"] = dict(ap[fld]["distinct_values"])
        ap_out.append(ap)
    # ---- paths
    paths_out = {}
    for p in sorted(paths):
        e = paths[p]
        rec = {"count": e["count"], "types": dict(e["types"].most_common())}
        if e["len_n"]:
            rec["list_len"] = {"min": e["len_min"], "max": e["len_max"], "mean": round(e["len_sum"] / e["len_n"], 1)}
        paths_out[p] = rec
    # ---- sizes
    ss = {"frames_sampled": size_sample["frames_sampled"], "bytes_total_sampled_lines": size_sample["bytes_total"],
          "per_class": {}}
    for cls, pc in sorted(size_sample["per_class"].items(), key=lambda x: -x[1]["bytes"]):
        keys_sorted = pc["keys"].most_common()
        ss["per_class"][str(cls)] = {
            "objects": pc["objects"], "bytes": pc["bytes"],
            "share_of_sampled_bytes": round(pc["bytes"] / size_sample["bytes_total"], 4) if size_sample["bytes_total"] else None,
            "avg_bytes_per_object": round(pc["bytes"] / pc["objects"], 1) if pc["objects"] else None,
            "envelope_bytes": pc["envelope_bytes"],
            "top_keys_bytes": {kk: b for kk, b in keys_sorted[:12]},
            "top_keys_share_of_class": {kk: round(b / pc["bytes"], 4) for kk, b in keys_sorted[:12]} if pc["bytes"] else {},
        }
    multi_class_ids = sum(1 for s in id_classes.values() if len(s) > 1)
    return {
        "file": os.path.basename(path),
        "file_bytes": os.path.getsize(path),
        "elapsed_s": round(time.time() - t0, 1),
        "keys": ks.summary(),
        "frames": n_frames,
        "empty_frames": empty_frames,
        "first_nonempty_frame": first_nonempty,
        "objects_per_frame": {
            "mean": round(sum(n * c for n, c in objs_hist.items()) / n_frames, 3) if n_frames else None,
            "p50": percentile_from_hist(objs_hist, 0.5), "p90": percentile_from_hist(objs_hist, 0.9),
            "p99": percentile_from_hist(objs_hist, 0.99),
            "max": max_objs[0], "max_at_frame": max_objs[1],
            "histogram": {str(n): objs_hist[n] for n in sorted(objs_hist)},
        },
        "envelope": {"keys": dict(envelope_keys), "key_orders": {json.dumps(list(o)): c for o, c in envelope_key_orders.items()}},
        "duplicate_tr_id_within_frame": dup_id_in_frame,
        "distinct_tr_ids_total": len(id_classes),
        "tr_ids_with_multiple_classes": multi_class_ids,
        "key_paths": paths_out,
        "classes": classes_out,
        "airplanes": ap_out,
        "gm_join": {
            "gm_file": os.path.basename(gm_path) if gm_path else None,
            "tracker_frames_without_gm_line": gm.missing,
            "gm_class_track_coverage": {str(cid): {"detections": r[0], "with_track_iou_ge05": r[1],
                                                   "share": round(r[1] / r[0], 4) if r[0] else None}
                                        for cid, r in sorted(rev.items(), key=lambda x: (str(type(x[0])), x[0]))},
        },
        "bytes": {"total": bytes_total, "avg_per_line": round(bytes_total / ks.n_lines, 1) if ks.n_lines else None,
                  "avg_per_nonempty_line": round((bytes_total - 10 * empty_frames) / nonempty_frames, 1) if nonempty_frames else None,
                  "max_line": max_line[0], "max_line_frame": max_line[1]},
        "size_decomposition_sampled": ss,
        "json_dumps_roundtrip": roundtrip,
        "example_first_nonempty_frame": example_frame,
        "example_object_per_class": {str(c): e for c, e in examples.items()},
    }


# ----------------------------------------------------------------------------- videos

def ffprobe_info(path):
    exe = shutil.which("ffprobe")
    if not exe:
        return {"error": "ffprobe not found"}
    cmd = [exe, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration",
           "-of", "json", path]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        st = json.loads(out.stdout)["streams"][0]
        return {"codec": st.get("codec_name"), "width": st.get("width"), "height": st.get("height"),
                "r_frame_rate": st.get("r_frame_rate"), "avg_frame_rate": st.get("avg_frame_rate"),
                "nb_frames": int(st["nb_frames"]) if st.get("nb_frames", "N/A").isdigit() else st.get("nb_frames"),
                "duration_s": float(st["duration"]) if st.get("duration") else None}
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}


# ----------------------------------------------------------------------------- cross-video

def cross_video_summary(videos: dict):
    gm_ids = {vid: v["gm"]["class_ids"] for vid, v in videos.items() if v.get("gm")}
    all_ids = sorted({cid for ids in gm_ids.values() for cid in ids})
    gm_classes_total = Counter()
    for vid, v in videos.items():
        if v.get("gm"):
            for cid, cs in v["gm"]["classes"].items():
                gm_classes_total[cid] += cs["count"]
    tr_classes = defaultdict(dict)           # cls -> vid -> [n_keys of signatures]
    key_union = defaultdict(set)
    key_by_video = defaultdict(dict)
    leak = {}
    counts = defaultdict(dict)
    for vid, v in videos.items():
        tr = v.get("trackers")
        if not tr:
            continue
        for cls, cs in tr["classes"].items():
            tr_classes[cls][vid] = [s["n_keys"] for s in cs["state_signatures"]]
            counts[cls][vid] = {"object_frames": cs["object_frames"], "distinct_tr_ids": cs["distinct_tr_ids"],
                                "empty_state": cs["empty_state_dict_object_frames"]}
            keys = set()
            for s in cs["state_signatures"]:
                keys.update(s["keys"])
            key_union[cls].update(keys)
            key_by_video[cls][vid] = sorted(keys)
        leak[vid] = {str(ap["obj_id"]): ap["leaked_vehicle_keys"] for ap in tr["airplanes"]}
    schema_diff = {}
    for cls, per_vid in key_by_video.items():
        union = key_union[cls]
        diff = {vid: sorted(union - set(keys)) for vid, keys in per_vid.items() if set(keys) != union}
        if diff:
            schema_diff[cls] = {"union_n_keys": len(union), "missing_per_video": diff}
    frame_counts = {}
    for vid, v in videos.items():
        frame_counts[vid] = {
            "gm_lines": v["gm"]["keys"]["lines"] if v.get("gm") else None,
            "tracker_lines": v["trackers"]["keys"]["lines"] if v.get("trackers") else None,
            "ffprobe_nb_frames": (v.get("video") or {}).get("nb_frames"),
        }
    id_by_cls = defaultdict(Counter)          # tracker cls_str -> GM class_id -> matched object-frames (all videos)
    coverage = defaultdict(lambda: [0, 0])    # GM class_id -> [detections, with track]
    weird_conf = {}
    for vid, v in videos.items():
        tr = v.get("trackers")
        if v.get("gm"):
            wc = v["gm"]["detection_record"].get("weird_conf_by_class") or {}
            if wc:
                weird_conf[vid] = {cid: {"count": w["count"], "values": w["values"]} for cid, w in wc.items()}
        if not tr:
            continue
        for cls, cs in tr["classes"].items():
            for cid, n in cs["join_with_gm"]["gm_class_id_of_best_match"].items():
                id_by_cls[cls][cid] += n
        for cid, r in tr["gm_join"]["gm_class_track_coverage"].items():
            coverage[cid][0] += r["detections"]
            coverage[cid][1] += r["with_track_iou_ge05"]
    airplane_events = {}
    for vid, v in videos.items():
        tr = v.get("trackers")
        if not tr:
            continue
        airplane_events[vid] = [{
            "obj_id": ap["obj_id"], "first_frame": ap["first_frame"], "last_frame": ap["last_frame"],
            "n_frames": ap["n_frames"], "absent_within_span": ap["absent_frames_within_span"],
            "arrival_frame": ap["arrival_frame"]["value_when_set"],
            "arrival_set_at": ap["arrival_frame"]["first_set_at_frame"],
            "arrival_distinct": list(ap["arrival_frame"]["distinct_values"].keys()),
            "departure_frame": ap["departure_frame"]["value_when_set"],
            "departure_set_at": ap["departure_frame"]["first_set_at_frame"],
            "departure_distinct": list(ap["departure_frame"]["distinct_values"].keys()),
            "have_arrival_stage_first_true": ap["have_arrival_stage_first_true"],
            "have_pre_arrival_stage_first_true": ap["have_pre_arrival_stage_first_true"],
            "status_counter": ap["status_counter"], "status_transitions": ap["status_transitions"],
            "n_keys": ap["n_keys"], "leaked_vehicle_keys": ap["leaked_vehicle_keys"],
        } for ap in tr["airplanes"]]
    return {
        "gm_class_ids_union": all_ids,
        "gm_class_ids_per_video": gm_ids,
        "gm_class_counts_total": dict(sorted(gm_classes_total.items(), key=lambda x: -x[1])),
        "tracker_classes_signature_nkeys_per_video": tr_classes,
        "tracker_class_counts_per_video": counts,
        "tracker_state_keys_union": {c: sorted(k) for c, k in key_union.items()},
        "tracker_state_keys_per_video": key_by_video,
        "tracker_schema_differences": schema_diff,
        "airplane_vehicle_key_leak_per_video": leak,
        "frame_counts": frame_counts,
        "airplane_events": airplane_events,
        "gm_class_id_by_tracker_cls_str": {cls: dict(c.most_common()) for cls, c in id_by_cls.items()},
        "gm_class_track_coverage_all_videos": {cid: {"detections": r[0], "with_track_iou_ge05": r[1],
                                                     "share": round(r[1] / r[0], 4) if r[0] else None}
                                               for cid, r in sorted(coverage.items(), key=lambda x: int(x[0]) if x[0].lstrip("-").isdigit() else 10**9)},
        "gm_weird_conf_per_video": weird_conf,
    }


# ----------------------------------------------------------------------------- driver

def _job(kind, path, max_frames, gm_path=None):
    if kind == "gm":
        return kind, path, inspect_gm(path, max_frames)
    return kind, path, inspect_tracker(path, max_frames, gm_path)


def discover(dir_path, only=None):
    videos = {}
    for fn in sorted(os.listdir(dir_path)):
        if not fn.endswith(SUFFIX):
            continue
        if fn.startswith(GM_PREFIX):
            vid, kind = fn[len(GM_PREFIX):-len(SUFFIX)], "gm"
        elif fn.startswith(TR_PREFIX):
            vid, kind = fn[len(TR_PREFIX):-len(SUFFIX)], "trackers"
        else:
            continue
        if only and vid not in only:
            continue
        videos.setdefault(vid, {})[kind] = os.path.join(dir_path, fn)
    return videos


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="directory with general_model*/trackers* .mp4.ndjson files")
    ap.add_argument("--videos-dir", default=None, help="directory with <VIDEOID>.mp4 (ffprobe header only; never decoded)")
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--max-frames", type=int, default=None, help="stop after N lines per file (quick test)")
    ap.add_argument("--workers", type=int, default=None, help="parallel processes (default: min(files, cpu))")
    ap.add_argument("--video", nargs="*", default=None, help="restrict to these video ids")
    args = ap.parse_args(argv)

    t0 = time.time()
    files = discover(args.dir, set(args.video) if args.video else None)
    if not files:
        sys.exit("no *.mp4.ndjson files found in %s" % args.dir)
    jobs = [(kind, path, d.get("gm") if kind == "trackers" else None)
            for vid, d in files.items() for kind, path in d.items()]
    # biggest files first so the pool tail is short
    jobs.sort(key=lambda j: -os.path.getsize(j[1]))
    workers = args.workers or max(1, min(len(jobs), os.cpu_count() or 1, 8))
    print("[inspect] %d videos, %d files, %d workers, max_frames=%s" % (len(files), len(jobs), workers, args.max_frames),
          file=sys.stderr, flush=True)

    results = {vid: {} for vid in files}
    if workers == 1:
        for kind, path, gm_path in jobs:
            _, _, res = _job(kind, path, args.max_frames, gm_path)
            vid = os.path.basename(path)[len(GM_PREFIX if kind == "gm" else TR_PREFIX):-len(SUFFIX)]
            results[vid][kind] = res
            print("[inspect] done %-9s %s  %.1fs  lines=%d" % (kind, os.path.basename(path), res["elapsed_s"], res["keys"]["lines"]),
                  file=sys.stderr, flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_job, kind, path, args.max_frames, gm_path) for kind, path, gm_path in jobs]
            for fut in as_completed(futs):
                kind, path, res = fut.result()
                vid = os.path.basename(path)[len(GM_PREFIX if kind == "gm" else TR_PREFIX):-len(SUFFIX)]
                results[vid][kind] = res
                print("[inspect] done %-9s %s  %.1fs  lines=%d" % (kind, os.path.basename(path), res["elapsed_s"], res["keys"]["lines"]),
                      file=sys.stderr, flush=True)

    videos_dir_listing = None
    if args.videos_dir and os.path.isdir(args.videos_dir):
        videos_dir_listing = {}
        for fn in sorted(os.listdir(args.videos_dir)):
            if fn.lower().endswith(".mp4"):
                vid = fn[:-4]
                info = {"file": fn, "bytes": os.path.getsize(os.path.join(args.videos_dir, fn)),
                        "has_inferences": vid in files}
                if vid in files:
                    info.update(ffprobe_info(os.path.join(args.videos_dir, fn)))
                videos_dir_listing[vid] = info
        for vid in results:
            results[vid]["video"] = videos_dir_listing.get(vid, {"file": None, "note": "no matching video file"})

    out = {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dir": os.path.abspath(args.dir),
            "videos_dir": os.path.abspath(args.videos_dir) if args.videos_dir else None,
            "max_frames": args.max_frames,
            "elapsed_s": round(time.time() - t0, 1),
            "python": sys.version.split()[0],
            "constants": {"SAMPLE_EVERY": SAMPLE_EVERY, "SIZE_SAMPLE_EVERY": SIZE_SAMPLE_EVERY,
                          "ROUNDTRIP_SAMPLE_EVERY": ROUNDTRIP_SAMPLE_EVERY, "SMALL_LIST_MAX": SMALL_LIST_MAX,
                          "MAX_DISTINCT_VALUES": MAX_DISTINCT_VALUES, "LIST_WALK_ELEMS": LIST_WALK_ELEMS},
        },
        "videos": results,
        "videos_dir_listing": videos_dir_listing,
        "cross_video": cross_video_summary(results),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(jsonable(out), f, ensure_ascii=False, indent=1)
    print("[inspect] wrote %s (%.1f MB) in %.1fs" % (args.out, os.path.getsize(args.out) / 1e6, time.time() - t0),
          file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
