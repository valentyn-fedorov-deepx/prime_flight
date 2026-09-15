"""Scope check for a real-time GM: can a detector head be dropped without changing what the tracker and the modules read?

Replays the recorded first-run rows of a video (batch GM v2) through VideoContextV2 and the causal second run twice — once
with every head's rows, once without the rows of the dropped heads — and compares the second-run rows of the classes that
stay consumed, frame by frame. CPU only, no model is loaded.

Head → classes: `vehicle` → vehicle; `chocks` → chock (`pf.gm.rows.first_run_rows`). The vehicle rows also feed the
synthesised obstacle / side_obstacle rows, so those classes are compared only when --keep-classes lists them.

    python scripts/rt_gm_scope_check.py --video zHxIAF2vUGxJ.mp4 --drop vehicle --exclude-classes vehicle,obstacle,side_obstacle
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

HEAD_CLASSES = {"vehicle": ["vehicle"], "chocks": ["chock"]}


def replay(first_run_path: str, cm, drop_ids: set, variant: str, fps: int = 8, max_frames=None) -> dict:
    from pf.pipeline import GmStream
    from pf.pipeline.causal_rows import CausalSecondRun

    pending: dict = {}
    stream = GmStream(cm, event_id="replay", fps=fps, rows_provider=lambda fid, _img: pending.pop(fid), variant=variant)
    causal = CausalSecondRun(stream.context, cm, refresh_every=60)
    out = {}
    with io.open(first_run_path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if max_frames and n > max_frames:
                break
            d = json.loads(line)
            fid = int(next(iter(d)))
            pending[fid] = [r for r in next(iter(d.values())) if int(r[5]) not in drop_ids]
            stream._ingest(fid, None)
            out[fid] = causal.rows(fid, stream.raw_rows.pop(fid))
    return out


def main() -> int:
    from pf.gm.rows import ClassMap
    from scripts.gm_v2_run import load_str2id
    from scripts.testset import orchestrate as o

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--drop", required=True, help="comma list of heads: vehicle, chocks")
    ap.add_argument("--exclude-classes", default="", help="classes not compared (the dropped heads' own classes etc.)")
    ap.add_argument("--variant", default="entity_clip")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    cm = ClassMap(load_str2id(os.path.join(ROOT, "external", "cv_common", "global_config.yaml")))
    drop_ids = {cm.id(c) for h in a.drop.split(",") if h for c in HEAD_CLASSES[h]}
    exclude = {cm.id(c) for c in a.exclude_classes.split(",") if c} | drop_ids
    first_run = os.path.join(o.paths(a.video)["gm_dir"], f"general_model{a.video}.ndjson")
    full = replay(first_run, cm, set(), a.variant, max_frames=a.max_frames)
    scoped = replay(first_run, cm, drop_ids, a.variant, max_frames=a.max_frames)
    keep = lambda rows: [r for r in rows if int(r[5]) not in exclude]
    frames = [fid for fid in full if keep(full[fid]) or keep(scoped.get(fid, []))]
    same = [fid for fid in frames if keep(full[fid]) == keep(scoped.get(fid, []))]
    diff = [fid for fid in frames if fid not in set(same)]
    id2name = {v: k for k, v in cm.str2id.items()}
    first_diff = None
    if diff:
        f = diff[0]
        first_diff = {"frame": f, "full": keep(full[f]), "scoped": keep(scoped.get(f, []))}
    result = {"video": a.video, "dropped_heads": a.drop, "dropped_classes": sorted(id2name.get(i) for i in drop_ids),
              "not_compared": sorted(id2name.get(i, i) for i in exclude), "frames": len(full),
              "frames_with_compared_rows": len(frames), "identical_frames": len(same), "different_frames": len(diff),
              "first_diff": first_diff}
    print(json.dumps(result, indent=1, default=str))
    if a.out:
        with io.open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, default=str)
    return 0 if not diff else 1


if __name__ == "__main__":
    raise SystemExit(main())
