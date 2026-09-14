"""Id-agnostic parity of two tracker files of the same video.

Objects of the same class are matched per frame by IoU >= 0.5 (greedy, highest IoU first); then the tool measures how much
of that matching a single stable identity mapping explains (for every identity of file A, the identity of file B it is
matched to most often).

Why next to `pf.eval.tracker_parity`: that metric matches objects by identity `(cls_str, state_dict._obj_id)`, so the same
track numbered differently counts as unmatched — which happens as soon as one detection arrives a frame earlier and shifts
the numbering of every later track. Module logic keys tracks by id only within one run, so a consistent relabelling alone
does not change verdicts (the paired module comparison is the authority).

    python scripts/testset/tracker_iou_parity.py --videos KB04bkqBI7ms.mp4 --out out/testset/tracker_iou_parity.json
    python scripts/testset/tracker_iou_parity.py            # every video with a finished tracker step in the ledger
"""

from __future__ import annotations

import argparse
import collections
import glob
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TS = os.path.join(ROOT, "out", "testset")


def iou(a, b) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def objects(line: str) -> list:
    """(class, identity, box) of every record of one v1-compat tracker line."""
    records = next(iter(json.loads(line).values()))
    out = []
    for r in records:
        sd = r.get("state_dict") or {}
        box = r.get("xyxy") or sd.get("_xyxy")
        if box is None:
            continue
        cls = r.get("cls_str") or sd.get("_class_name")
        ident = sd.get("_obj_id", r.get("tr_id"))
        out.append((cls, ident, [float(v) for v in box[:4]]))
    return out


def compare(path_a: str, path_b: str, min_iou: float = 0.5) -> dict:
    c = collections.Counter()
    per_class = collections.defaultdict(collections.Counter)
    pair_frames = collections.Counter()
    with io.open(path_a, encoding="utf-8") as ha, io.open(path_b, encoding="utf-8") as hb:
        for la, lb in zip(ha, hb):
            c["frames"] += 1
            A, B = objects(la), objects(lb)
            c["objects_a"] += len(A)
            c["objects_b"] += len(B)
            for a in A:
                per_class[a[0]]["a"] += 1
            cand = sorted(((iou(a[2], b[2]), i, j) for i, a in enumerate(A) for j, b in enumerate(B) if a[0] == b[0]),
                          reverse=True)
            used_a, used_b = set(), set()
            for v, i, j in cand:
                if v < min_iou or i in used_a or j in used_b:
                    continue
                used_a.add(i)
                used_b.add(j)
                c["matched"] += 1
                c["same_identity"] += A[i][1] == B[j][1]
                per_class[A[i][0]]["matched"] += 1
                pair_frames[(A[i][0], A[i][1], B[j][1])] += 1
    best = collections.defaultdict(int)
    for (cls, ia, _ib), n in pair_frames.items():
        best[(cls, ia)] = max(best[(cls, ia)], n)
    m = max(c["matched"], 1)
    return {
        **dict(c),
        "matched_share_of_a": round(c["matched"] / max(c["objects_a"], 1), 6),
        "same_identity_share": round(c["same_identity"] / m, 6),
        "identity_mapping_consistency": round(sum(best.values()) / m, 6),
        "per_class_matched_share": {str(k): round(v["matched"] / max(v["a"], 1), 6) for k, v in per_class.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", default=None, help="comma list (default: every video with a finished tracker step)")
    ap.add_argument("--a-root", default=os.path.join(TS, "prod"), help="folder with <video>/trackers<video>.ndjson (reference)")
    ap.add_argument("--b-root", default=os.path.join(TS, "trk_v2"), help="folder with <video>/trackers<video>.ndjson")
    ap.add_argument("--min-iou", type=float, default=0.5)
    ap.add_argument("--out", default=os.path.join(TS, "tracker_iou_parity.json"))
    a = ap.parse_args()
    if a.videos:
        videos = a.videos.split(",")
    else:
        videos = []
        for f in sorted(glob.glob(os.path.join(TS, "ledger", "*.json"))):
            led = json.load(io.open(f, encoding="utf-8"))
            if led.get("steps", {}).get("tracker", {}).get("status") == "done":
                videos.append(led["video"])
    results = json.load(io.open(a.out, encoding="utf-8")) if os.path.exists(a.out) else {}
    for v in videos:
        pa = os.path.join(a.a_root, v, f"trackers{v}.ndjson")
        pb = os.path.join(a.b_root, v, f"trackers{v}.ndjson")
        if not (os.path.exists(pa) and os.path.exists(pb)):
            print(f"{v}: missing file")
            continue
        r = compare(pa, pb, a.min_iou)
        results[v] = r
        print(f"{v}: IoU-matched {r['matched_share_of_a']:.1%} of reference objects, same identity {r['same_identity_share']:.1%}, "
              f"one identity mapping explains {r['identity_mapping_consistency']:.1%} | {r['per_class_matched_share']}", flush=True)
        with io.open(a.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
