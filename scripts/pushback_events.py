"""PUSHBACK_ATTACHED on recorded inferences: the causal nose rule (`pf.stage.pushback.PushbackAttachedCausal`) vs the offline
replication of what aircraft-chocks computes in production from the same GM second-run and tracker files.

    python scripts/pushback_events.py --inferences-dir G:/gat_stages/atlc5_inferences --out out/pushback_events_atlc5.json
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def iter_gm(path):
    with io.open(path, "rb") as fh:
        for line in fh:
            ((k, v),) = json.loads(line).items()
            yield int(k), v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inferences-dir", required=True)
    ap.add_argument("--gm-dir", default=None, help="take GM files from here instead (e.g. GM v2 second-run files)")
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    from pf.stage.pushback import PushbackAttachedCausal, production_pushback_attached_frame
    from pf.tracker._v1.config import config
    from pf.tracker.events import iter_tracker_lines

    s2i = config["str2id"]
    rows_out = []
    for trk in sorted(glob.glob(os.path.join(a.inferences_dir, "trackers*.ndjson"))):
        video = os.path.basename(trk)[len("trackers"):-len(".ndjson")]
        gm = os.path.join(a.gm_dir or a.inferences_dir, f"general_model{video}.ndjson")
        if not os.path.exists(gm):
            continue
        n_frames = sum(1 for _ in io.open(gm, "rb"))
        prod = production_pushback_attached_frame(lambda: iter_gm(gm), lambda: iter_tracker_lines(trk), n_frames, s2i, fps=a.fps)
        causal = PushbackAttachedCausal(s2i, fps=a.fps)
        for (f, rows), (_f2, recs) in zip(iter_gm(gm), iter_tracker_lines(trk)):
            causal.feed(f, rows, recs)
            if causal.frame is not None or causal.departed:
                break
        delta = (causal.frame - prod["frame"]) if (causal.frame is not None and prod["frame"] is not None) else None
        row = {"video": video, "frames": n_frames, "stop_frame": prod["stop_frame"], "production_rule": prod["rule"],
               "production_frame": prod["frame"], "causal_frame": causal.frame, "delta_frames": delta,
               "median_pushback": prod["median_pushback"]}
        rows_out.append(row)
    print("| video | frames | stop frame | production rule | production frame | causal frame | Δ frames |")
    print("|---|---|---|---|---|---|---|")
    for r in rows_out:
        print(f"| {r['video']} | {r['frames']} | {r['stop_frame']} | {r['production_rule']} | {r['production_frame']} | "
              f"{r['causal_frame']} | {'—' if r['delta_frames'] is None else r['delta_frames']} |")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with io.open(a.out, "w", encoding="utf-8") as fh:
            json.dump(rows_out, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
