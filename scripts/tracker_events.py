"""Derive stage-detector events from tracker files and compare their timings (`pf.tracker.events`).

    python scripts/tracker_events.py --tracker G:/gat_stages/atlc5_inferences/trackersDjwtQRdZyt0sSk.mp4.ndjson \
        --tracker out/pipeline_Djwt_v2gm_v2trk/trackersDjwtQRdZyt0sSk.mp4.ndjson --labels production,v2 --out out/events.json

The first file is the reference. Events are matched in order per (name, door); the table shows the frame of each event in
every file and the difference to the reference.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracker", action="append", required=True, help="tracker ndjson (repeat; the first is the reference)")
    ap.add_argument("--labels", default=None, help="comma-separated labels for the files")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    from pf.tracker.events import derive_events

    labels = a.labels.split(",") if a.labels else [os.path.basename(p) for p in a.tracker]
    derived = {}
    for label, path in zip(labels, a.tracker):
        d = derive_events(path)
        derived[label] = {"events": [e.as_dict() for e in d.events], "reidentifications": d.reidentifications,
                          "open_doors_at_end": d.occupant}

    keyed = {}
    for label, res in derived.items():
        groups = defaultdict(list)
        for e in res["events"]:
            groups[(e["name"], e["attrs"].get("door"))].append(e)
        keyed[label] = groups
    ref = labels[0]
    keys = sorted({k for g in keyed.values() for k in g}, key=lambda k: (k[0], str(k[1])))
    header = "| event | door | " + " | ".join(labels) + " | " + " | ".join(f"Δ {l}" for l in labels[1:]) + " |"
    print(header)
    print("|" + "---|" * (2 + len(labels) + len(labels) - 1))
    comparison = []
    for key in keys:
        n = max(len(keyed[l].get(key, [])) for l in labels)
        for i in range(n):
            frames = []
            for l in labels:
                lst = keyed[l].get(key, [])
                frames.append(lst[i]["frame"] if i < len(lst) else None)
            deltas = [(f - frames[0]) if (f is not None and frames[0] is not None) else None for f in frames[1:]]
            comparison.append({"event": key[0], "door": key[1], "index": i, "frames": dict(zip(labels, frames)),
                               "delta_to_" + ref: dict(zip(labels[1:], deltas))})
            print(f"| {key[0]} | {key[1] or ''} | " + " | ".join(str(f) for f in frames) + " | "
                  + " | ".join("—" if d is None else f"{d:+d}" for d in deltas) + " |")
    for label, res in derived.items():
        print(f"{label}: re-identifications {res['reidentifications'][:6]} open doors at end {res['open_doors_at_end']}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with io.open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"files": dict(zip(labels, a.tracker)), "derived": derived, "comparison": comparison}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
