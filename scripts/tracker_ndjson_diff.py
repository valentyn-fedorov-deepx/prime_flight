"""Compare two tracker ndjson files of one video (production vs a candidate), frame by frame.

    python scripts/tracker_ndjson_diff.py --a out/tracker_cluster/fAkpu3dj2NIj_trackersbd43c3c.ndjson.gz \
        --b out/tracker_cluster/fAkpu3dj2NIj_trackersa6d6c53.ndjson.gz --out out/tracker_cluster/fAkpu3dj2NIj.json

Reads plain or gzip files (the bucket files are gzip without saying so) as streams, ignoring \r\n against \n line endings
(local runs on Windows write \r\n). Reports: identical frames, the first
differing frame, what differs on the differing frames (track ids, boxes, statuses, only the optical-flow points), the
tracker events of both files (arrival, departure, belt loader at a door / leaving it; `pf.tracker.events`) and the
number of track ids per class.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pf.tracker.events import TrackerEventDeriver  # noqa: E402

# state_dict keys that hold the optical-flow points sampled with the unseeded np.random in cv_common
FLOW_KEYS = {"_p0", "_st", "_err", "_old_points", "_good_new", "_good_old"}


def open_any(path: str):
    with io.open(path, "rb") as fh:
        magic = fh.read(2)
    return gzip.open(path, "rb") if magic == b"\x1f\x8b" else io.open(path, "rb")


def parse(line: bytes):
    ((k, v),) = json.loads(line).items()
    return int(k), v


def records_by_key(records):
    out = {}
    for r in records or []:
        out[(r.get("cls_str"), r.get("tr_id"))] = r
    return out


def compare(a_path: str, b_path: str, max_frames: int | None = None) -> dict:
    ha, hb = hashlib.sha256(), hashlib.sha256()
    ev = {"a": TrackerEventDeriver(), "b": TrackerEventDeriver()}
    ids = {"a": defaultdict(set), "b": defaultdict(set)}
    frames = identical = 0
    first_diff = None
    kinds = Counter()  # what differs on a differing frame
    diff_keys = Counter()  # state_dict keys that differ on shared tracks
    box_shift = []  # max |Δ| of xyxy on shared tracks whose box differs
    extra_lines = {"a": 0, "b": 0}
    with open_any(a_path) as fa, open_any(b_path) as fb:
        while max_frames is None or frames < max_frames:
            la, lb = fa.readline(), fb.readline()
            if not la and not lb:
                break
            if not la or not lb:
                extra_lines["b" if not la else "a"] += 1
                continue
            # files written on Windows end their lines with \r\n; the hash is that of the file with \n endings
            la, lb = la.rstrip(b"\r\n"), lb.rstrip(b"\r\n")
            ha.update(la + b"\n")
            hb.update(lb + b"\n")
            frames += 1
            fa_id, ra = parse(la)
            fb_id, rb = parse(lb)
            ev["a"].feed(fa_id, ra)
            ev["b"].feed(fb_id, rb)
            for side, recs in (("a", ra), ("b", rb)):
                for r in recs or []:
                    ids[side][r.get("cls_str")].add(r.get("tr_id"))
            if la == lb:
                identical += 1
                continue
            if first_diff is None:
                first_diff = fa_id
            if fa_id != fb_id:
                kinds["frame number"] += 1
                continue
            ka, kb = records_by_key(ra), records_by_key(rb)
            if set(ka) != set(kb):
                kinds["different tracks"] += 1
            shared = set(ka) & set(kb)
            box = status = flow_only = other = False
            for key in shared:
                x, y = ka[key], kb[key]
                if x == y:
                    continue
                if x.get("xyxy") != y.get("xyxy"):
                    box = True
                    try:
                        box_shift.append(max(abs(p - q) for p, q in zip(x["xyxy"], y["xyxy"])))
                    except (TypeError, KeyError):
                        pass
                sa, sb = x.get("state_dict") or {}, y.get("state_dict") or {}
                keys = {k for k in set(sa) | set(sb) if sa.get(k) != sb.get(k)}
                diff_keys.update(keys)
                if sa.get("_status") != sb.get("_status"):
                    status = True
                if keys and keys <= FLOW_KEYS and x.get("xyxy") == y.get("xyxy") and x.get("data") == y.get("data"):
                    flow_only = True
                elif keys - FLOW_KEYS or x.get("data") != y.get("data") or x.get("conf") != y.get("conf"):
                    other = True
            if box:
                kinds["box moved"] += 1
            if status:
                kinds["status changed"] += 1
            if flow_only and not (box or status or other) and set(ka) == set(kb):
                kinds["only optical-flow points"] += 1
    box_shift.sort()

    def pct(q):
        return box_shift[min(len(box_shift) - 1, int(q * len(box_shift)))] if box_shift else None

    return {
        "a": a_path, "b": b_path,
        "sha256_unpacked": {"a": ha.hexdigest(), "b": hb.hexdigest()},
        "frames": frames, "extra_lines": extra_lines,
        "identical_frames": identical, "first_differing_frame": first_diff,
        "differing_frames_by_kind": dict(kinds),
        "differing_state_keys": dict(diff_keys.most_common(20)),
        "box_shift_px": {"n": len(box_shift), "median": pct(0.5), "p90": pct(0.9), "p99": pct(0.99),
                         "max": box_shift[-1] if box_shift else None},
        "track_ids_per_class": {s: {c: len(v) for c, v in sorted(ids[s].items(), key=lambda kv: str(kv[0]))}
                                for s in ids},
        "events": {s: [e.as_dict() for e in ev[s].events] for s in ev},
        "reidentifications": {s: len(ev[s].reidentifications) for s in ev},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, help="reference file (production)")
    ap.add_argument("--b", required=True, help="candidate file")
    ap.add_argument("--frames", type=int, default=None, help="compare only the first N frames (a slice against a full file)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = compare(a.a, a.b, a.frames)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with io.open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    short = {k: v for k, v in res.items() if k not in ("events",)}
    print(json.dumps(short, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
