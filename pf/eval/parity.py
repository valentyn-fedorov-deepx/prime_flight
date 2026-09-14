"""Parity tooling: are two frame streams (or two per-frame ndjson files) the same, and where do they differ?

Two uses:
  * batch vs chunked feeding of the SAME frames must be byte-identical (gate level 1, synthetic data);
  * old GM/tracker vs rebuilt GM/tracker on the SAME video: per-frame comparison with a tolerance,
    reported as counts and the first differing frames, never as a bare "accuracy" number.

Production ndjson lines look like ``{"<frame_no>": [[x1, y1, x2, y2, conf, class_id], ...]}`` (GM) and
``{"<frame_no>": [ {"state_dict": {...}}, ... ]}`` (trackers). Files are hundreds of MB: always stream.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(frames) -> str:
    h = hashlib.sha256()
    for f in frames:
        h.update(canonical(f))
    return h.hexdigest()


def as_chunks(frames, size: int):
    return [frames[i : i + size] for i in range(0, len(frames), size)]


def diff_streams(a, b):
    """Indices where two frame sequences differ (structural equality)."""
    return [i for i, (x, y) in enumerate(zip(a, b)) if x != y]


# ---------------------------------------------------------------- ndjson (production format)


def iter_ndjson(path: str):
    """Yield ``(frame_no, payload)`` from a production ndjson file, streaming line by line."""
    with open(path, "rb") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            rec = json.loads(raw)
            if isinstance(rec, dict) and len(rec) == 1:
                k, v = next(iter(rec.items()))
                yield int(k), v
            else:
                yield None, rec


def _det_key(det, ndigits: int):
    # [x1, y1, x2, y2, conf, class_id] -> hashable with rounding; tolerates extra trailing fields
    x1, y1, x2, y2, conf, cls = det[:6]
    return (
        int(cls),
        round(float(x1), ndigits),
        round(float(y1), ndigits),
        round(float(x2), ndigits),
        round(float(y2), ndigits),
        round(float(conf), ndigits),
    )


@dataclass
class DetectionParity:
    frames_compared: int = 0
    frames_equal: int = 0
    frames_only_in_a: int = 0
    frames_only_in_b: int = 0
    dets_a: int = 0
    dets_b: int = 0
    dets_matched: int = 0
    first_diffs: list = field(default_factory=list)  # (frame_no, n_a, n_b)
    per_class_a: dict = field(default_factory=dict)
    per_class_b: dict = field(default_factory=dict)

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
            "dets_a": self.dets_a,
            "dets_b": self.dets_b,
            "dets_matched": self.dets_matched,
            "first_diffs": self.first_diffs[:20],
            "per_class_a": self.per_class_a,
            "per_class_b": self.per_class_b,
        }


def compare_gm_ndjson(
    path_a: str,
    path_b: str,
    *,
    ndigits: int = 1,
    max_first_diffs: int = 20,
    ignore_classes=(),
    only_common_frames: bool = False,
) -> DetectionParity:
    """Frame-by-frame comparison of two GM ndjson files as multisets of rounded detections.

    ``ndigits`` — rounding applied to coordinates and confidence before comparing (1 = 0.1 px / 0.1 conf).
    ``ignore_classes`` — class ids dropped from both sides before comparing (e.g. the synthesized 2/29/30 rows that
    depend on whole-video context when only a prefix of the video was processed).
    ``only_common_frames`` — do not count frames present in one file only (partial runs).
    Frame numbers are matched by key, never by position (X2).
    """
    ignore = {int(c) for c in ignore_classes}
    res = DetectionParity()
    ia, ib = iter_ndjson(path_a), iter_ndjson(path_b)
    na, nb = next(ia, None), next(ib, None)
    while na is not None or nb is not None:
        ka = na[0] if na is not None else None
        kb = nb[0] if nb is not None else None
        if kb is None or (ka is not None and ka < kb):
            res.frames_only_in_a += 0 if only_common_frames else 1
            na = next(ia, None)
            continue
        if ka is None or kb < ka:
            res.frames_only_in_b += 0 if only_common_frames else 1
            nb = next(ib, None)
            continue
        da, db = na[1] or [], nb[1] or []
        if ignore:
            da = [d for d in da if int(d[5]) not in ignore]
            db = [d for d in db if int(d[5]) not in ignore]
        res.frames_compared += 1
        res.dets_a += len(da)
        res.dets_b += len(db)
        for d in da:
            res.per_class_a[int(d[5])] = res.per_class_a.get(int(d[5]), 0) + 1
        for d in db:
            res.per_class_b[int(d[5])] = res.per_class_b.get(int(d[5]), 0) + 1
        ma = {}
        for d in da:
            k = _det_key(d, ndigits)
            ma[k] = ma.get(k, 0) + 1
        matched = 0
        for d in db:
            k = _det_key(d, ndigits)
            if ma.get(k):
                ma[k] -= 1
                matched += 1
        res.dets_matched += matched
        if matched == len(da) == len(db):
            res.frames_equal += 1
        elif len(res.first_diffs) < max_first_diffs:
            res.first_diffs.append((ka, len(da), len(db)))
        na, nb = next(ia, None), next(ib, None)
    return res


# ---------------------------------------------------------------- tolerant comparison (cross-hardware parity)


def _iou_xyxy(p, q) -> float:
    ix = max(0.0, min(p[2], q[2]) - max(p[0], q[0]))
    iy = max(0.0, min(p[3], q[3]) - max(p[1], q[1]))
    inter = ix * iy
    union = (p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - inter
    return inter / union if union > 0 else 0.0


def _percentile(sorted_values, p: float):
    if not sorted_values:
        return None
    return sorted_values[min(len(sorted_values) - 1, int(p * len(sorted_values)))]


@dataclass
class TolerantParity:
    """Pairs detections of the same class by IoU (greedy, best first) and reports how far the pairs are apart.

    Meant for cross-hardware / cross-runtime parity where bit-exact rows are impossible (fp16 conv algorithms, ORT
    version): the question becomes "are the same objects detected with the same class, within X px and Y conf".
    """

    match_iou: float = 0.5
    coord_tol_px: float = 2.0
    conf_tol: float = 0.02
    frames_compared: int = 0
    frames_within_tolerance: int = 0
    dets_a: int = 0
    dets_b: int = 0
    pairs: int = 0
    pairs_exact: int = 0
    pairs_within_tolerance: int = 0
    unmatched_a: int = 0
    unmatched_b: int = 0
    per_class_unmatched_a: dict = field(default_factory=dict)
    per_class_unmatched_b: dict = field(default_factory=dict)
    coord_deltas: list = field(default_factory=list)
    conf_deltas: list = field(default_factory=list)
    first_diffs: list = field(default_factory=list)

    def summary(self) -> dict:
        cd = sorted(self.coord_deltas)
        cf = sorted(self.conf_deltas)
        return {
            "match_iou": self.match_iou,
            "coord_tol_px": self.coord_tol_px,
            "conf_tol": self.conf_tol,
            "frames_compared": self.frames_compared,
            "frames_within_tolerance": self.frames_within_tolerance,
            "frame_parity_tolerant": round(self.frames_within_tolerance / self.frames_compared, 6)
            if self.frames_compared
            else 1.0,
            "dets_a": self.dets_a,
            "dets_b": self.dets_b,
            "pairs": self.pairs,
            "pairs_exact": self.pairs_exact,
            "pairs_within_tolerance": self.pairs_within_tolerance,
            "pair_recall": round(self.pairs / self.dets_a, 6) if self.dets_a else 1.0,
            "unmatched_a": self.unmatched_a,
            "unmatched_b": self.unmatched_b,
            "per_class_unmatched_a": self.per_class_unmatched_a,
            "per_class_unmatched_b": self.per_class_unmatched_b,
            "coord_delta_px": {
                "p50": _percentile(cd, 0.5),
                "p90": _percentile(cd, 0.9),
                "p99": _percentile(cd, 0.99),
                "max": cd[-1] if cd else None,
            },
            "conf_delta": {
                "p50": _percentile(cf, 0.5),
                "p90": _percentile(cf, 0.9),
                "p99": _percentile(cf, 0.99),
                "max": cf[-1] if cf else None,
            },
            "first_diffs": self.first_diffs[:20],
        }


def compare_gm_frame_tolerant(
    rows_a, rows_b, frame_no, res: TolerantParity, max_first_diffs: int = 20
) -> bool:
    used = set()
    within = True
    res.dets_a += len(rows_a)
    res.dets_b += len(rows_b)
    for d in rows_a:
        best, bi = None, -1
        for j, e in enumerate(rows_b):
            if j in used or int(e[5]) != int(d[5]):
                continue
            v = _iou_xyxy(d, e)
            if best is None or v > best:
                best, bi = v, j
        if best is not None and best >= res.match_iou:
            used.add(bi)
            e = rows_b[bi]
            dcoord = max(abs(float(d[i]) - float(e[i])) for i in range(4))
            dconf = abs(float(d[4]) - float(e[4]))
            res.pairs += 1
            res.coord_deltas.append(dcoord)
            res.conf_deltas.append(dconf)
            if dcoord == 0 and dconf == 0:
                res.pairs_exact += 1
            if dcoord <= res.coord_tol_px and dconf <= res.conf_tol:
                res.pairs_within_tolerance += 1
            else:
                within = False
                if len(res.first_diffs) < max_first_diffs:
                    res.first_diffs.append(
                        (
                            frame_no,
                            int(d[5]),
                            [round(float(x), 2) for x in d[:5]],
                            [round(float(x), 2) for x in e[:5]],
                            round(best, 3),
                        )
                    )
        else:
            within = False
            res.unmatched_a += 1
            res.per_class_unmatched_a[int(d[5])] = res.per_class_unmatched_a.get(int(d[5]), 0) + 1
    for j, e in enumerate(rows_b):
        if j not in used:
            within = False
            res.unmatched_b += 1
            res.per_class_unmatched_b[int(e[5])] = res.per_class_unmatched_b.get(int(e[5]), 0) + 1
    return within


def compare_gm_ndjson_tolerant(
    path_a: str,
    path_b: str,
    *,
    match_iou: float = 0.5,
    coord_tol_px: float = 2.0,
    conf_tol: float = 0.02,
    ignore_classes=(),
    only_common_frames: bool = False,
    max_first_diffs: int = 20,
) -> TolerantParity:
    ignore = {int(c) for c in ignore_classes}
    res = TolerantParity(match_iou=match_iou, coord_tol_px=coord_tol_px, conf_tol=conf_tol)
    ia, ib = iter_ndjson(path_a), iter_ndjson(path_b)
    na, nb = next(ia, None), next(ib, None)
    while na is not None or nb is not None:
        ka = na[0] if na is not None else None
        kb = nb[0] if nb is not None else None
        if kb is None or (ka is not None and ka < kb):
            na = next(ia, None)
            continue
        if ka is None or kb < ka:
            nb = next(ib, None)
            continue
        da = [d for d in (na[1] or []) if int(d[5]) not in ignore]
        db = [d for d in (nb[1] or []) if int(d[5]) not in ignore]
        res.frames_compared += 1
        if compare_gm_frame_tolerant(da, db, ka, res, max_first_diffs):
            res.frames_within_tolerance += 1
        na, nb = next(ia, None), next(ib, None)
    return res
