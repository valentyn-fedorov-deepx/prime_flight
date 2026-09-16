"""Run the real-time branch and watch it live in a browser.

    python scripts/rt_watch.py                                   # defaults below, opens http://127.0.0.1:8765/
    python scripts/rt_watch.py --max-seconds 300 --pause-testset # a short window on a machine that is busy
    python scripts/rt_watch.py --module 3-stop-brake-check --extra-modules pushback-pathway-confirmed-clear-of-obstacles

The page (`pf/rt/monitor.py`) shows the branch as a diagram — CameraBox, uplink, receiver, decoder, GM heads, causal rows,
tracker, module processes, outputs — with what each component costs per frame and how much of the 125 ms budget is left,
next to the frame the modules were given (GM detections and tracker boxes drawn on it) and the verdicts as they are emitted.

The chunks of the video are cut once (`pf.rt.chunker`) and reused. `--pause-testset` suspends the running test-set jobs for
the duration of the run and resumes them afterwards: nothing is killed, so no step is marked failed and no mp4 is fetched again.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_VIDEO = "zHxIAF2vUGxJ.mp4"
DEFAULT_MODULE = "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready"
TESTSET_JOBS = ("gm_v2_run.py", "tracker_v2_run.py", "run_module.py")
CONTROL = os.path.join(ROOT, "out", "testset", "orchestrator_control.json")


def source_video(video: str) -> str:
    """A whole event under out/testset/videos, or a decision slice under out/rt/slices (scripts/rt_slices.py)."""
    for folder in (os.path.join(ROOT, "out", "testset", "videos"), os.path.join(ROOT, "out", "rt", "slices")):
        path = os.path.join(folder, video)
        if os.path.exists(path):
            return path
    raise SystemExit(f"no video {video} under out/testset/videos or out/rt/slices "
                     f"(fetch an event with scripts/testset/fetch.py, cut a slice with scripts/rt_slices.py)")


def parent_event(video: str) -> str | None:
    """`<event>_<first>_<last>.mp4` is a slice: its camera and aircraft type come from `<event>.mp4`."""
    parts = os.path.splitext(video)[0].split("_")
    if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit():
        return "_".join(parts[:-2]) + os.path.splitext(video)[1]
    return None


def ensure_chunks(video: str, max_seconds: float | None) -> str:
    stem = os.path.splitext(video)[0]
    chunks = os.path.join(ROOT, "out", "rt", "chunks", f"{stem}_gop1")
    if os.path.exists(os.path.join(chunks, "manifest.json")):
        return chunks
    source = source_video(video)
    print(f"cutting {video} into GOP chunks (once per video)...", flush=True)
    cmd = [sys.executable, "-m", "pf.rt.chunker", "--video", source, "--out", chunks, "--gops-per-chunk", "1"]
    if max_seconds:
        cmd += ["--max-seconds", str(max_seconds)]
    subprocess.run(cmd, cwd=ROOT, check=True)
    return chunks


def testset_jobs() -> list:
    import psutil

    found = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            line = " ".join(proc.info["cmdline"] or [])
        except Exception:
            continue
        if (proc.info["name"] or "").lower().startswith("python") and any(k in line for k in TESTSET_JOBS):
            found.append(proc)
    return found


def set_control(update: dict) -> None:
    if not os.path.exists(CONTROL):
        return
    control = json.load(io.open(CONTROL, encoding="utf-8"))
    control.update(update)
    tmp = CONTROL + ".watch.tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(control, indent=1))
    os.replace(tmp, CONTROL)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default=DEFAULT_VIDEO, help="an event from out/testset/videos or a slice from out/rt/slices")
    ap.add_argument("--plan-video", default=None, help="event a slice was cut from (guessed from the slice name)")
    ap.add_argument("--module", default=DEFAULT_MODULE)
    ap.add_argument("--extra-modules", default="", help="comma list of modules run in their own processes")
    ap.add_argument("--tag", default=None, help="run folder under out/rt/runs (default: watch_<time>)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--speed", type=float, default=1.0, help="1 = real time")
    ap.add_argument("--max-seconds", type=float, default=None, help="only the first N seconds of the recording")
    ap.add_argument("--heads", default="gm,vehicle")
    ap.add_argument("--tracker-classes", default="airplane,beltloader,gse,person")
    ap.add_argument("--ingest", default="frames", choices=["chunks", "frames"])
    ap.add_argument("--bandwidth-mbps", type=float, default=10.0)
    ap.add_argument("--hold-s", type=float, default=900.0, help="keep the page up this long after the run ends")
    ap.add_argument("--pause-testset", action="store_true", help="suspend running test-set jobs for the run")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    a = ap.parse_args()

    tag = a.tag or time.strftime("watch_%H%M%S")
    ensure_chunks(a.video, a.max_seconds)
    paused = []
    if a.pause_testset and a.hold_s > 120:
        a.hold_s = 120  # the test set stays suspended while the page is held up; do not hold it for long
        print("holding the page for 120 s only: the test set is suspended until the run exits", flush=True)
    if a.pause_testset:
        set_control({"stop": True})
        for proc in testset_jobs():
            try:
                proc.suspend()
                paused.append(proc)
            except Exception as e:
                print("could not suspend", proc.pid, e, flush=True)
        print(f"suspended test-set jobs: {[p.pid for p in paused]}", flush=True)

    cmd = [sys.executable, "scripts/rt_pipeline_run.py", "--video", a.video, "--module", a.module, "--tag", tag,
           "--speed", str(a.speed), "--heads", a.heads, "--tracker-classes", a.tracker_classes,
           "--ingest", a.ingest, "--bandwidth-mbps", str(a.bandwidth_mbps),
           "--watch-port", str(a.port), "--hold-s", str(a.hold_s)]
    event = a.plan_video or parent_event(a.video)
    if event:
        cmd += ["--plan-video", event]
    if a.extra_modules:
        cmd += ["--extra-modules", a.extra_modules]
    if a.max_seconds:
        cmd += ["--max-seconds", str(a.max_seconds)]
    url = f"http://127.0.0.1:{a.port}/"
    print(f"live view: {url}  (run {tag}; the page fills in once GM and the tracker are loaded, ~40 s)", flush=True)
    if not a.no_open:
        threading.Timer(25.0, webbrowser.open, args=(url,)).start()
    try:
        return subprocess.run(cmd, cwd=ROOT).returncode
    finally:
        for proc in paused:
            try:
                proc.resume()
            except Exception as e:
                print("could not resume", proc.pid, e, flush=True)
        if a.pause_testset:
            set_control({"stop": False})
            print("test-set jobs resumed", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
