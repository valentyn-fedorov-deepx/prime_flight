"""Cut an event down to the stretches where the real-time modules actually decide, and rehearse real time on those.

A turnaround is 30–40 minutes of which a module needs a few: the batch run of every module already says which frames it
decided on (`smart_timeline`), so the decision windows are data, not a guess. This tool reads them for the modules of
interest, adds a pre-roll (the tracker and the GM context need history before the decision), merges what overlaps and
cuts contiguous GOP-aligned slices with stream copy — no re-encoding, every frame bit-identical to the source.

    python scripts/rt_slices.py --video zHxIAF2vUGxJ.mp4                       # plan only
    python scripts/rt_slices.py --video zHxIAF2vUGxJ.mp4 --cut                 # plan + slice mp4s + chunk folders
    python scripts/rt_slices.py --video zHxIAF2vUGxJ.mp4 --cut --run --watch   # and run them through the branch

What a slice is and is not: a slice is a **pseudo-event** — its frames are renumbered from 1 and the modules see a session
of that length, so a module whose decision needs more history than the pre-roll can answer differently than on the whole
video. `--run` compares each verdict with the whole-video batch verdict and prints which modules survive the cut; use the
survivors for real-time rehearsals and the whole event for parity.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RT_MODULES = [  # the modules that run in the real-time branch today (tasks/notes/PF-Q2-02.md)
    "pushback-pathway-confirmed-clear-of-obstacles",
    "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready",
    "3-stop-brake-check",
]
GOP = 30  # frames per keyframe interval on the DXGAT cameras (3.75 s at 8 fps)


def frames_of(entry) -> list:
    """`smart_timeline` entries carry Start/End as int, str or list, one entry or several."""
    out = []
    for key in ("Start", "End"):
        value = entry.get(key)
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
    return out


def module_windows(video: str, modules: list, label: str = "v2") -> list:
    """[{module, status, first, last}] from the batch outputs; modules without a timeline are reported as unusable."""
    windows = []
    for module in modules:
        path = os.path.join(ROOT, "out", "testset", "modules", label, video, f"{module}.json")
        if not os.path.exists(path):
            windows.append({"module": module, "error": f"no batch output at {os.path.relpath(path, ROOT)}"})
            continue
        data = json.load(io.open(path, encoding="utf-8"))
        frames = []
        for entry in data.get("smart_timeline") or []:
            for item in (entry if isinstance(entry, list) else [entry]):
                if isinstance(item, dict):
                    frames.extend(frames_of(item))
        record = {"module": module, "status": data.get("status"), "report": data.get("report")}
        if frames:
            record.update(first=min(frames), last=max(frames))
        else:
            record["error"] = "no smart timeline in the batch output (nothing was observed): no window to cut"
        windows.append(record)
    return windows


def merge(windows: list, fps: float, pre_s: float, post_s: float, join_s: float, n_frames: int) -> list:
    spans = []
    for w in windows:
        if "first" not in w:
            continue
        spans.append((max(1, int(w["first"] - pre_s * fps)), min(n_frames, int(w["last"] + post_s * fps)), w["module"]))
    spans.sort()
    slices = []
    for start, end, module in spans:
        if slices and start - slices[-1]["end"] <= join_s * fps:
            slices[-1]["end"] = max(slices[-1]["end"], end)
            slices[-1]["modules"].append(module)
        else:
            slices.append({"start": start, "end": end, "modules": [module]})
    for s in slices:  # snap the start to a keyframe: a stream copy can only cut there
        s["start"] = max(1, (s["start"] - 1) // GOP * GOP + 1)
        s["seconds"] = round((s["end"] - s["start"] + 1) / fps, 1)
    return slices


def cut(video_path: str, s: dict, fps: float, out_dir: str) -> dict:
    """Stream-copy the slice and cut it into chunks, the way the CameraBox writes them."""
    stem = os.path.splitext(os.path.basename(video_path))[0]
    name = f"{stem}_{s['start']}_{s['end']}"
    mp4 = os.path.join(out_dir, name + ".mp4")
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.exists(mp4):
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{(s['start'] - 1) / fps:.3f}",
               "-i", video_path, "-t", f"{(s['end'] - s['start'] + 1) / fps:.3f}", "-c", "copy",
               "-avoid_negative_ts", "make_zero", "-reset_timestamps", "1", "-y", mp4]
        subprocess.run(cmd, check=True)
    chunks = os.path.join(ROOT, "out", "rt", "chunks", f"{name}_gop1")
    if not os.path.exists(os.path.join(chunks, "manifest.json")):
        subprocess.run([sys.executable, "-m", "pf.rt.chunker", "--video", mp4, "--out", chunks, "--gops-per-chunk", "1"],
                       cwd=ROOT, check=True)
    manifest = json.load(io.open(os.path.join(chunks, "manifest.json"), encoding="utf-8"))
    return {"video": mp4, "chunks": chunks, "frames": manifest["n_frames"], "first_frame_in_event": s["start"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--modules", default=",".join(RT_MODULES))
    ap.add_argument("--pre-seconds", type=float, default=120.0, help="history before the first decided frame")
    ap.add_argument("--post-seconds", type=float, default=20.0)
    ap.add_argument("--join-seconds", type=float, default=90.0, help="windows closer than this become one slice")
    ap.add_argument("--target-minutes", type=float, default=10.0, help="warn when the slices add up to more than this")
    ap.add_argument("--cut", action="store_true", help="write the slice mp4s and their chunk folders")
    ap.add_argument("--run", action="store_true", help="run each slice through the branch and compare the verdicts")
    ap.add_argument("--watch", action="store_true", help="serve the live page while running (port 8765)")
    ap.add_argument("--pause-testset", action="store_true")
    ap.add_argument("--ingest", default="frames", choices=["chunks", "frames"])
    ap.add_argument("--speed", type=float, default=1.0, help="1 = real time; higher only to check verdicts quickly")
    ap.add_argument("--heads", default="gm,chocks,vehicle")
    a = ap.parse_args()

    from scripts.testset import orchestrate as o

    modules = [m for m in a.modules.split(",") if m]
    paths = o.paths(a.video)
    if not os.path.exists(paths["video"]):
        raise SystemExit(f"no video at {paths['video']}")
    manifest_path = os.path.join(ROOT, "out", "rt", "chunks", f"{os.path.splitext(a.video)[0]}_gop1", "manifest.json")
    if os.path.exists(manifest_path):
        manifest = json.load(io.open(manifest_path, encoding="utf-8"))
        fps, n_frames = float(manifest["fps"]), int(manifest["n_frames"])
    else:
        import cv2

        cap = cv2.VideoCapture(paths["video"])
        fps, n_frames = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

    windows = module_windows(a.video, modules)
    slices = merge(windows, fps, a.pre_seconds, a.post_seconds, a.join_seconds, n_frames)
    total_s = sum(s["seconds"] for s in slices)
    plan = {"video": a.video, "fps": fps, "event_minutes": round(n_frames / fps / 60, 1),
            "pre_seconds": a.pre_seconds, "post_seconds": a.post_seconds,
            "windows": windows, "slices": slices, "total_minutes": round(total_s / 60, 1),
            "share_of_event": round(total_s * fps / n_frames, 3)}
    for w in windows:
        when = f"{w['first']}–{w['last']} ({w['first'] / fps / 60:.1f}–{w['last'] / fps / 60:.1f} min)" if "first" in w \
            else w.get("error")
        print(f"{w['module'][:60]:62s} {str(w.get('status'))[:13]:14s} {when}")
    print(f"\n{len(slices)} slice(s), {plan['total_minutes']} min of the {plan['event_minutes']} min event "
          f"({plan['share_of_event'] * 100:.0f} %)")
    for s in slices:
        print(f"  frames {s['start']}–{s['end']}  {s['seconds'] / 60:.1f} min  "
              f"{s['start'] / fps / 60:.1f}–{s['end'] / fps / 60:.1f} min of the recording  "
              f"covers: {', '.join(m.split('-')[0] for m in s['modules'])}")
    if plan["total_minutes"] > a.target_minutes:
        print(f"  note: longer than the {a.target_minutes} min target — lower --pre-seconds or run fewer modules")

    if a.cut or a.run:
        out_dir = os.path.join(ROOT, "out", "rt", "slices")
        for s in slices:
            s.update(cut(paths["video"], s, fps, out_dir))
            print(f"  cut {os.path.relpath(s['video'], ROOT)} ({s['frames']} frames) -> {os.path.relpath(s['chunks'], ROOT)}")
    plan_path = os.path.join(ROOT, "out", "rt", "slices", f"{os.path.splitext(a.video)[0]}_plan.json")
    os.makedirs(os.path.dirname(plan_path), exist_ok=True)
    json.dump(plan, io.open(plan_path, "w", encoding="utf-8"), indent=1, default=str)
    print(f"plan: {os.path.relpath(plan_path, ROOT)}")

    if not a.run:
        return 0
    for i, s in enumerate(slices, 1):
        tag = f"slice_{os.path.splitext(a.video)[0]}_{s['start']}"
        cmd = [sys.executable, "scripts/rt_pipeline_run.py", "--video", os.path.basename(s["video"]),
               "--plan-video", a.video, "--module", s["modules"][0], "--tag", tag, "--speed", str(a.speed),
               "--heads", a.heads, "--ingest", a.ingest, "--bandwidth-mbps", "10",
               "--chunks", os.path.relpath(s["chunks"], ROOT)]
        if len(s["modules"]) > 1:
            cmd += ["--extra-modules", ",".join(s["modules"][1:])]
        if a.watch:
            cmd += ["--watch-port", "8765", "--hold-s", "60"]
        print(f"\nslice {i}/{len(slices)}: {s['seconds'] / 60:.1f} min, modules {', '.join(s['modules'])}", flush=True)
        t0 = time.time()
        rc = subprocess.run(cmd, cwd=ROOT).returncode
        print(f"slice {i} exit {rc} in {time.time() - t0:.0f} s", flush=True)
        compare_verdicts(a.video, tag, s)
    return 0


def compare_verdicts(video: str, tag: str, s: dict) -> None:
    """Slice verdict against the whole-video batch verdict: which modules survive the cut."""
    summary_path = os.path.join(ROOT, "out", "rt", "runs", tag, "summary.json")
    if not os.path.exists(summary_path):
        print("  no summary written")
        return
    summary = json.load(io.open(summary_path, encoding="utf-8"))
    live = [{"module": s["modules"][0], "status": summary.get("live_status")}]
    live += [{"module": v.get("module"), "status": v.get("live_status")} for v in summary.get("extra_module_verdicts") or []]
    for item in live:
        batch_path = os.path.join(ROOT, "out", "testset", "modules", "v2", video, f"{item['module']}.json")
        batch = json.load(io.open(batch_path, encoding="utf-8")) if os.path.exists(batch_path) else {}
        same = item["status"] == batch.get("status")
        print(f"  {item['module'][:58]:60s} slice {str(item['status'])[:13]:14s} whole video {str(batch.get('status'))[:13]:14s}"
              f" {'same' if same else 'DIFFERENT — this module needs more history than the pre-roll'}")


if __name__ == "__main__":
    raise SystemExit(main())
