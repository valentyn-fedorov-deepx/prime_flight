"""Pose models over the whole validation set: the modules' own pose models against one shared model, video by video.

The monthly plan has 90 videos with pose modules (`Plan.modules(video)`); the v2 GM / tracker inferences of all of them are
on disk (`out/testset/v2_inf/<video>`), the mp4 of only some, with little free space. Per video: fetch the mp4 (a few
ahead while there is room), run each of its pose modules once per label, then delete the mp4 if this script fetched it.

  pose_ctl  the module's own pose model, timed (`run_module.py --pose-timing`) - the baseline
  pose_rtm  RTMPose-l for every pose interface (`--pose-override rtmpose-l`)
  pose_dw   DWPose-l, body keypoints (`--pose-override dwpose-l`)

The three runs of a module on a video are started next to each other, so they share the machine's load. Resumable: a
result JSON that exists is not recomputed; videos that were on disk at the first start are never deleted
(`out/pose/full_run_state.json`). handrails-on-gse-being-used is left out: it runs DWPose-l itself and reads the hands,
so no label changes its model. `out/pose/full_run.stop` drains the running jobs and exits.

    python scripts/testset/pose_full_run.py --jobs 4
    python scripts/testset/pose_full_run.py --compare-only
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.testset import fetch  # noqa: E402
from scripts.testset import orchestrate as orch  # noqa: E402
from scripts.testset import profiles  # noqa: E402
from scripts.testset.variant_run import module_command  # noqa: E402

TS, PY = orch.TS, sys.executable
OUT = os.path.join(ROOT, "out", "pose")
STATE = os.path.join(OUT, "full_run_state.json")
STOP = os.path.join(OUT, "full_run.stop")
LABELS = {"pose_ctl": "--pose-timing", "pose_rtm": "--pose-override rtmpose-l", "pose_dw": "--pose-override dwpose-l"}
MODULES = [
    "hand-signals",
    "steering-by-pass-pin-installed-or-steering-otherwise-bypassed",
    "pin-verification",
    "lead-marshaller-and-wing-walkers-in-position",
    "wing-walkers-in-proper-position-and-using-approved-wands",
    "fod-walk-completed",
    "gse-chocks",
]


def log(text: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
    print(line, flush=True)
    with io.open(os.path.join(OUT, "full_run.log"), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def free_gb() -> float:
    return shutil.disk_usage(TS).free / 1e9


def load_state(videos: list) -> dict:
    if os.path.exists(STATE):
        with io.open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    keep = [v for v in videos if os.path.exists(os.path.join(TS, "videos", v))]
    return {"keep": keep, "fetched": [], "failed_fetch": {}}


def save_state(state: dict) -> None:
    with io.open(STATE + ".part", "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)
    os.replace(STATE + ".part", STATE)


def compare(labels: list) -> None:
    for label in labels:
        base = "v2" if label == "pose_ctl" else "pose_ctl"
        out = os.path.join(TS, f"compare_{label}_vs_{base}_full.json")
        cmd = [PY, "scripts/testset/compare.py", "--runs-root", os.path.join(TS, "modules", label), "--label", label,
               "--baseline-root", os.path.join(TS, "modules", base), "--baseline-label", base, "--out", out]
        with io.open(os.path.join(OUT, f"compare_{label}_full.log"), "w", encoding="utf-8") as fh:
            rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
        tot = json.load(io.open(out, encoding="utf-8"))["totals"] if os.path.exists(out) else {}
        log(f"compare {label} vs {base} rc={rc}: " + json.dumps({k: tot.get(k, 0) for k in (
            "paired", "paired_equal", "paired_with_truth", "paired_ours_correct", "paired_baseline_correct")}))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default=",".join(LABELS))
    ap.add_argument("--jobs", type=int, default=4, help="module runs at a time")
    ap.add_argument("--prefetch", type=int, default=3, help="fetched videos waiting or in work at most")
    ap.add_argument("--fetch-workers", type=int, default=2)
    ap.add_argument("--min-free-gb", type=float, default=15.0, help="never fetch below this free space after the download")
    ap.add_argument("--compare-only", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    labels = [x for x in a.labels.split(",") if x]
    if a.compare_only:
        compare(labels)
        return 0

    plan = orch.Plan()
    videos = [v for v in plan.order if any(m in MODULES for m in plan.modules(v))]
    state = load_state(videos)
    save_state(state)
    todo = {}
    for v in videos:
        runs = [(label, m) for m in plan.modules(v) if m in MODULES for label in labels
                if not os.path.exists(orch.module_out(label, v, m))]
        if runs:
            todo[v] = runs
    log(f"start: {len(videos)} videos with pose modules, {len(todo)} with runs to do, "
        f"{sum(len(r) for r in todo.values())} runs; labels {labels}; jobs {a.jobs}; free {free_gb():.0f} GB")

    lock = threading.Lock()
    fetching: set = set()
    ready = {v for v in todo if os.path.exists(os.path.join(TS, "videos", v))}
    env = dict(os.environ, **profiles.ENV)

    def do_fetch(video: str) -> None:
        try:
            r = fetch.fetch_video(video, os.path.join(TS, "videos"))
            with lock:
                ready.add(video)
                if video not in state["keep"] and video not in state["fetched"]:
                    state["fetched"].append(video)
                save_state(state)
            log(f"fetched {video}: {r.get('gb')} GB in {r.get('seconds', 0)} s ({r.get('mb_per_s', '-')} MB/s)")
        except Exception as e:  # noqa: BLE001 - recorded, the video is retried up to 3 times
            with lock:
                state["failed_fetch"][video] = state["failed_fetch"].get(video, 0) + 1
                save_state(state)
            log(f"fetch FAILED {video}: {type(e).__name__}: {str(e)[:200]}")
        finally:
            with lock:
                fetching.discard(video)

    running: list = []  # (video, label, module, proc, fh)
    order = [v for v in videos if v in todo]
    while True:
        stop = os.path.exists(STOP)
        # finished runs
        for item in list(running):
            video, label, module, proc, fh = item
            if proc.poll() is None:
                continue
            fh.close()
            running.remove(item)
            if proc.returncode:
                log(f"{video}: {label} {module} rc={proc.returncode}")
        # videos done: drop the mp4 this script fetched
        for video in list(ready):
            if todo.get(video) or any(r[0] == video for r in running):
                continue
            ready.discard(video)
            todo.pop(video, None)
            path = os.path.join(TS, "videos", video)
            if video in state["fetched"] and os.path.exists(path):
                os.remove(path)
                log(f"{video}: done, mp4 removed (free {free_gb():.0f} GB)")
            else:
                log(f"{video}: done")
        if stop and not running:
            log("stop file: exiting")
            return 0
        if not todo and not running:
            break
        # fetch ahead, in plan order, while there is room
        with lock:
            # fetched by this script and not finished yet (the videos that were on disk do not count)
            in_work = {v for v in order if v in todo and v not in state["keep"] and (v in ready or v in fetching)}
            for video in order:
                if stop or len(in_work) >= a.prefetch or len(fetching) >= a.fetch_workers:
                    break
                if video not in todo or video in ready or video in fetching:
                    continue
                if state["failed_fetch"].get(video, 0) >= 3:
                    continue
                size = plan.inventory[video]["size"] / 1e9
                in_flight = sum(plan.inventory[v]["size"] for v in fetching) / 1e9  # not on disk yet
                if free_gb() - in_flight - size < a.min_free_gb:
                    break
                fetching.add(video)
                in_work.add(video)
                threading.Thread(target=do_fetch, args=(video,), daemon=True).start()
        # start runs of ready videos, in plan order
        while not stop and len(running) < a.jobs:
            pick = next((v for v in order if v in ready and todo.get(v)), None)
            if pick is None:
                break
            label, module = todo[pick].pop(0)
            if os.path.exists(orch.module_out(label, pick, module)):
                continue
            cmd = module_command(plan, label, pick, module, orch.paths(pick)["v2_inf"], LABELS[label])
            lp = os.path.join(orch.paths(pick)["logs"], f"mod_{label}_{module}.log")
            os.makedirs(os.path.dirname(lp), exist_ok=True)
            fh = io.open(lp, "w", encoding="utf-8")
            fh.write(" ".join(cmd) + "\n")
            fh.flush()
            running.append((pick, label, module, subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=env), fh))
        # give up on videos that cannot be fetched
        for video in [v for v in todo if state["failed_fetch"].get(v, 0) >= 3 and v not in ready]:
            log(f"{video}: skipped after 3 failed fetches ({len(todo[video])} runs)")
            todo.pop(video)
        time.sleep(3)

    log("all runs done")
    compare(labels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
