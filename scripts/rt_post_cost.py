"""What each module costs as a post-processing job, measured cleanly: one job at a time on a quiet machine.

The batch timings kept by the test-set campaign were taken with three module jobs, a GM run and two tracker runs sharing the
machine, so they overstate the job. This runs the same command the orchestrator runs (`scripts/testset/orchestrate.py`,
label v2: the module on the GM v2 + Tracker v2 files, reading the video as the production worker does) for one event, one
module after another, and samples the process tree: wall time, CPU seconds, peak memory, GPU. With `--also-no-video` the
modules that do not read pixels are timed a second time without decoding the video (what an optimised post job would do).

    python scripts/rt_post_cost.py [--video zHxIAF2vUGxJ.mp4] [--modules a,b] [--also-no-video] [--redo]

Results: `out/rt/cost/<event>/post_jobs.json` (the verdict of every run is checked against the test-set run).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.rt_module_cost import MachineSampler  # noqa: E402
from scripts.testset import orchestrate as o  # noqa: E402
from scripts.testset import profiles  # noqa: E402


def run(video: str, module: str, plan, out_dir: str, no_video: bool) -> dict:
    cmd, env = o.build_cmd(f"mod:v2:{module}", video, plan)
    out = os.path.join(out_dir, f"{module}{'.no_video' if no_video else ''}.json")
    cmd[cmd.index("--out") + 1] = out
    if no_video and "--videos-dir" in cmd:
        i = cmd.index("--videos-dir")
        del cmd[i:i + 2]
        cmd.append("--no-video")
    if os.path.exists(out):
        os.remove(out)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    sampler = MachineSampler(proc.pid).start()
    rc = proc.wait()
    sampler.stop()
    wall = time.time() - t0
    rec = {"module": module, "with_video": not no_video, "exit_code": rc, "wall_s": round(wall, 1),
           "machine": sampler.summary(steady_s=wall, tail_s=0.0)}
    if os.path.exists(out):
        result = json.load(io.open(out, encoding="utf-8"))
        rec.update(detect_s=result.get("seconds"), status=result.get("status"), error=result.get("error"))
        reference = o.module_out("v2", video, module)
        if os.path.exists(reference):
            rec["status_as_in_the_test_set"] = json.load(io.open(reference, encoding="utf-8")).get("status") == result.get("status")
    samples = sampler.samples
    if len(samples) > 1:
        rec["cpu_seconds"] = round(samples[-1]["cpu_s"] - samples[0]["cpu_s"], 1)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="zHxIAF2vUGxJ.mp4")
    ap.add_argument("--modules", default="", help="comma list; default: every module measured in real time on this event")
    ap.add_argument("--also-no-video", action="store_true")
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    stem = os.path.splitext(a.video)[0]
    cost_dir = os.path.join(ROOT, "out", "rt", "cost", stem)
    out_dir = os.path.join(cost_dir, "post_jobs")
    os.makedirs(out_dir, exist_ok=True)
    measured = json.load(io.open(os.path.join(cost_dir, "modules.json"), encoding="utf-8"))
    modules = [m for m in a.modules.split(",") if m] or [m for m, r in measured.items() if (r.get("whole_event") or {}).get("frames")]
    plan = o.Plan([a.video])
    path = os.path.join(cost_dir, "post_jobs.json")
    result = json.load(io.open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for i, module in enumerate(modules, 1):
        pixel_free = bool(profiles.profile(module).get("pixel_free"))
        for no_video in ([False, True] if a.also_no_video and pixel_free else [False]):
            key = "no_video" if no_video else "as_production"
            if not a.redo and key in result.get(module, {}) and not result[module][key].get("error"):
                continue
            rec = run(a.video, module, plan, out_dir, no_video)
            result.setdefault(module, {"pixel_free": pixel_free})[key] = rec
            print(f"[{i}/{len(modules)}] {module} {key}: wall {rec['wall_s']} s, detect {rec.get('detect_s')} s, cpu "
                  f"{rec.get('cpu_seconds')} s, status {rec.get('status')} same={rec.get('status_as_in_the_test_set')} "
                  f"err={rec.get('error')}", flush=True)
            json.dump(result, io.open(path, "w", encoding="utf-8", newline="\n"), indent=1, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
