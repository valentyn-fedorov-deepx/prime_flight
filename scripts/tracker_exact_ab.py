"""Production tracker against its exact-speed-ups branch on the same slice: the tracks and the debug video must be
byte-identical; the per-frame cost is compared component by component.

Each round runs `scripts/tracker_v1_profile.py --pin prod` (seeded, fixed optical-flow palette) once on the production
checkout and once on the branch checkout, alternating, so both see the same machine load on average.

    python scripts/tracker_exact_ab.py --label busy --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 \
        --gm-ndjson G:/gat_stages/atlc5_inferences/general_modelDjwtQRdZyt0sSk.mp4.ndjson --start 9000 --frames 1200
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKOUTS = {
    "prod": os.path.join(ROOT, "external", "cv_trackers_prod"),
    "exact": os.path.join(ROOT, "external", "_work", "cv_trackers_exact"),
}
WORKDIR = os.path.join(ROOT, "out", "tracker_profile_prod")  # tracker_v1_profile.py --pin prod writes here
OUT = os.path.join(ROOT, "out", "tracker_ab")


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def same_frames(a: str, b: str) -> tuple[int, int]:
    import cv2

    ca, cb = cv2.VideoCapture(a), cv2.VideoCapture(b)
    n = same = 0
    while True:
        ra, fa = ca.read()
        rb, fb = cb.read()
        if not ra or not rb:
            break
        n += 1
        same += fa.tobytes() == fb.tobytes()
    return n, same


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--gm-ndjson", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--no-video", action="store_true", help="without the debug video")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    name = os.path.basename(a.video)
    runs: dict = {k: [] for k in CHECKOUTS}
    for r in range(a.rounds):
        for variant, checkout in CHECKOUTS.items():
            tag = f"{a.label}_{variant}_{r}"
            cmd = [sys.executable, "scripts/tracker_v1_profile.py", "--pin", "prod", "--tracker-dir", checkout,
                   "--video", a.video, "--gm-ndjson", a.gm_ndjson, "--start", str(a.start), "--frames", str(a.frames),
                   "--seed", str(a.seed), "--variant", variant, "--out", os.path.join(OUT, tag + ".json")]
            if not a.no_video:
                cmd.append("--save-video")
            with io.open(os.path.join(OUT, tag + ".log"), "w", encoding="utf-8") as fh:
                rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
            if rc:
                print(f"{tag}: rc={rc}, see {os.path.join(OUT, tag + '.log')}")
                return rc
            shutil.copyfile(os.path.join(WORKDIR, f"trackers{name}.ndjson"), os.path.join(OUT, tag + ".ndjson"))
            if not a.no_video:
                shutil.copyfile(os.path.join(WORKDIR, f"debug_{variant}.mp4"), os.path.join(OUT, tag + ".mp4"))
            report = json.load(io.open(os.path.join(OUT, tag + ".json"), encoding="utf-8"))
            runs[variant].append(report)
            print(f"{tag}: {report['ms_per_frame_total']} ms per frame")

    result = {"label": a.label, "video": name, "start": a.start, "frames": a.frames, "seed": a.seed, "rounds": a.rounds}
    tracks = {f"{v}_{r}": sha(os.path.join(OUT, f"{a.label}_{v}_{r}.ndjson")) for v in CHECKOUTS for r in range(a.rounds)}
    result["tracks_sha256"] = tracks
    result["tracks_identical"] = len(set(tracks.values())) == 1
    if not a.no_video:
        videos = {f"{v}_{r}": sha(os.path.join(OUT, f"{a.label}_{v}_{r}.mp4")) for v in CHECKOUTS for r in range(a.rounds)}
        result["video_sha256"] = videos
        result["video_identical"] = len(set(videos.values())) == 1
        n, same = same_frames(os.path.join(OUT, f"{a.label}_prod_0.mp4"), os.path.join(OUT, f"{a.label}_exact_0.mp4"))
        result["decoded_frames"], result["decoded_frames_identical"] = n, same
    for v, reps in runs.items():
        comp: dict = {}
        for rep in reps:
            for k, ms in rep["components_ms_per_frame"].items():
                comp[k] = comp.get(k, 0.0) + ms / len(reps)
        result[v] = {"ms_per_frame": round(sum(r["ms_per_frame_total"] for r in reps) / len(reps), 1),
                     "per_round": [r["ms_per_frame_total"] for r in reps],
                     "components_ms_per_frame": {k: round(x, 2) for k, x in sorted(comp.items(), key=lambda kv: -kv[1])}}
    result["change"] = f"{100 * (result['exact']['ms_per_frame'] / result['prod']['ms_per_frame'] - 1):+.1f} %"
    with io.open(os.path.join(OUT, f"{a.label}.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print(json.dumps(result, indent=1))
    return 0 if result["tracks_identical"] and result.get("video_identical", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
