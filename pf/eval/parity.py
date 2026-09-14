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
    path_a: str, path_b: str, *, ndigits: int = 1, max_first_diffs: int = 20
) -> DetectionParity:
    """Frame-by-frame comparison of two GM ndjson files as multisets of rounded detections.

    ``ndigits`` — rounding applied to coordinates and confidence before comparing (1 = 0.1 px / 0.1 conf).
    Frame numbers are matched by key, never by position (X2).
    """
    res = DetectionParity()
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
        da, db = na[1] or [], nb[1] or []
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
