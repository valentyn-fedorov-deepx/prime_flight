"""Bit-exact check of Tracker v2 against the production tracker on whole test-set videos: same machine, same GM rows, seed 0.

Why: module verdicts are a deterministic function of their inputs, so byte-identical tracker files make a module run
unnecessary for proving that the tracker port changes nothing. The production files in the bucket cannot serve as that
reference: tracker v1 subsamples keypoints with unseeded `np.random.choice`, so two production runs of one video already
differ (tasks/notes/PF-Q1-17.md). With a shared seed the port was byte-identical on 1 200-frame slices; this extends the check
to whole videos.

Per video: the production pin (`scripts/tracker_v1_profile.py --pin prod --seed 0`, start 0, every frame) on the GM v2
second-run rows that Tracker v2 consumed in the test-set run (`scripts/tracker_v2_run.py --seed 0 --exact-fast`, same
`--cone-camera` flag), then a line-by-line comparison of the two v1-compat tracker files. Line terminators are ignored
(v1 writes through a text-mode file); `raw_bytes_identical` records whether the files are also equal byte for byte.

Outputs: out/testset/trk_v1_seed0/<video>/ (tracker file, profile JSON, log); summary out/testset/tracker_exact_check.json.
Videos already in the summary are skipped unless --force.

    python scripts/testset/tracker_exact_check.py --videos zHxIAF2vUGxJ.mp4,MwCSLbQ7QvXQ.mp4
"""

from __future__ import annotations

import argparse
import io
import itertools
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.testset import orchestrate as o  # noqa: E402

TS = os.path.join(ROOT, "out", "testset")
OUT = os.path.join(TS, "trk_v1_seed0")
SUMMARY = os.path.join(TS, "tracker_exact_check.json")
PROFILE_WORKDIR = os.path.join(ROOT, "out", "tracker_profile_prod")


def compare_files(path_a: str, path_b: str) -> dict:
    lines = identical = 0
    first_diff = None
    extra_a = extra_b = 0
    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        for la, lb in itertools.zip_longest(fa, fb):
            if la is None:
                extra_b += 1
                continue
            if lb is None:
                extra_a += 1
                continue
            lines += 1
            if la.rstrip(b"\r\n") == lb.rstrip(b"\r\n"):
                identical += 1
            elif first_diff is None:
                first_diff = lines
    raw = os.path.getsize(path_a) == os.path.getsize(path_b) and identical == lines and not extra_a and not extra_b
    if raw:
        with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
            raw = fa.read() == fb.read()
    return {"lines_compared": lines, "lines_identical": identical, "first_different_line": first_diff,
            "extra_lines_v1": extra_a, "extra_lines_v2": extra_b, "raw_bytes_identical": raw}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", required=True, help="comma list of test-set videos with a finished Tracker v2 step")
    ap.add_argument("--device", default="0")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    plan = o.Plan()
    summary = json.load(io.open(SUMMARY, encoding="utf-8")) if os.path.exists(SUMMARY) else {}
    for video in [v for v in a.videos.split(",") if v]:
        if video in summary and summary[video].get("status") == "done" and not a.force:
            print(f"{video}: already checked: {json.dumps(summary[video].get('comparison'))}")
            continue
        p = o.paths(video)
        gm_rows, v2_file = p["gm_compat"], p["trk_compat"]
        missing = [f for f in (p["video"], gm_rows, v2_file) if not os.path.exists(f)]
        if missing:
            print(f"{video}: skipped, missing {missing}")
            continue
        with open(gm_rows, "rb") as fh:
            frames = sum(1 for _ in fh)
        out_dir = os.path.join(OUT, video)
        os.makedirs(out_dir, exist_ok=True)
        stale = os.path.join(PROFILE_WORKDIR, f"trackers{video}.ndjson")
        if os.path.exists(stale):
            os.remove(stale)  # a previous profile run's output must not be taken for this one
        cone = plan.cone(video)
        cmd = [sys.executable, "scripts/tracker_v1_profile.py", "--pin", "prod", "--video", p["video"], "--gm-ndjson", gm_rows,
               "--start", "0", "--frames", str(frames), "--seed", "0", "--device", a.device,
               "--out", os.path.join(out_dir, "tracker_v1_profile.json")] + (["--cone-camera"] if cone else [])
        t0 = time.time()
        with io.open(os.path.join(out_dir, "tracker_v1.log"), "w", encoding="utf-8") as log:
            rc = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
        seconds = round(time.time() - t0, 1)
        rec = {"frames": frames, "cone_camera": cone, "rc": rc, "v1_seconds": seconds,
               "v1_ms_per_frame": round(1000 * seconds / max(frames, 1), 1), "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
        if rc == 0 and os.path.exists(stale):
            v1_file = os.path.join(out_dir, f"trackers{video}.ndjson")
            shutil.move(stale, v1_file)
            rec["comparison"] = compare_files(v1_file, v2_file)
            rec["status"] = "done"
        else:
            rec["status"] = "failed"
        summary[video] = rec
        tmp = SUMMARY + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=1)
        os.replace(tmp, SUMMARY)
        print(f"{video}: {json.dumps(rec)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
