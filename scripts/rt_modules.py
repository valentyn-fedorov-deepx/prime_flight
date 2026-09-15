"""Run production modules through the real-time branch prototype in parallel (one process each) and compare their live
verdicts with the batch results of the test set.

Each module runs `python -m pf.rt.simulate --adapter prod` with the launch facts of scripts/testset/profiles.py (checkout,
overlays, shims, device, environment) and the production GM / tracker rows of the video as metadata, i.e. GM and tracker are
not computed in the loop. Afterwards, per module: the live verdict and report against
out/testset/modules/ctl/<video>/<module>.json (with the checkout each came from), whether the module decided before the
session closed, module cost, frame latency and the real-time audit.

    python scripts/rt_modules.py --video zHxIAF2vUGxJ.mp4 --modules beltloader-chocks,pushback-pathway-confirmed-clear-of-obstacles
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

from scripts.testset import profiles  # noqa: E402
from scripts.testset.orchestrate import Plan  # noqa: E402


def adapter_args(module: str, video: str, plan: Plan, work_dir: str, inferences_dir: str | None = None) -> dict:
    prof = profiles.profile(module)
    if prof.get("launcher"):
        raise SystemExit(f"{module} runs in another interpreter ({prof['launcher'][0]}); not supported by this script")
    return {"module": module, "module_dir": prof["module_dir"] or None,
            "inferences_dir": inferences_dir or f"out/testset/prod/{video}",
            "device": prof["device"], "cone_camera": plan.cone(video), "airplane_type": plan.airplane_type(video),
            "numpy1_scalars": prof["numpy1"], "drop_state_keys": prof["drop_state_keys"],
            "prepend_path": prof["prepend_path"], "env": profiles.ENV, "work_dir": work_dir}


def video_time(frame_id) -> str:
    if not frame_id:
        return "--"
    s = (frame_id - 1) / 8.0
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def summarise(module: str, out: str, video: str) -> dict:
    rec = {"module": module}
    report_path = os.path.join(out, "report.json")
    if not os.path.exists(report_path):
        rec["error"] = "no report (see the run log)"
        return rec
    r = json.load(io.open(report_path, encoding="utf-8"))
    outs = [json.loads(line) for line in io.open(os.path.join(out, "outputs.ndjson"), encoding="utf-8")]
    verdict = next((o for o in outs if o["kind"] == "verdict"), None)
    error = next((o for o in outs if o["name"] == "module_error"), None)
    audit = next((o for o in outs if o["name"] == "real_time_audit"), {}).get("payload", {})
    batch_path = os.path.join(ROOT, "out", "testset", "modules", "ctl", video, f"{module}.json")
    batch = json.load(io.open(batch_path, encoding="utf-8")) if os.path.exists(batch_path) else {}
    v2_path = os.path.join(ROOT, "out", "testset", "modules", "v2", video, f"{module}.json")
    batch_v2 = json.load(io.open(v2_path, encoding="utf-8")) if os.path.exists(v2_path) else {}
    live = (verdict or {}).get("payload", {})
    rec.update({
        "batch_v2_status": batch_v2.get("status"),
        "status_identical_v2": live.get("status") == batch_v2.get("status") if verdict and batch_v2 else None,
        "report_identical_v2": live.get("report") == batch_v2.get("report") if verdict and batch_v2 else None,
    })
    rec.update({
        "live_status": live.get("status"), "batch_status": batch.get("status"),
        "status_identical": live.get("status") == batch.get("status") if verdict and batch else None,
        "report_identical": live.get("report") == batch.get("report") if verdict and batch else None,
        "live_report": live.get("report"), "batch_report": batch.get("report"),
        "batch_checkout": batch.get("module_source"), "module_error": (error or {}).get("payload", {}).get("error"),
        "decided_after_frame": live.get("decided_after_frame"), "decided_at_video_time": video_time(live.get("decided_after_frame")),
        "decided_before_session_closed": live.get("session_closed") is False if verdict else None,
        "verdict_emitted_after_capture_s": (verdict or {}).get("latency_s"),
        "frames": r["frames"], "keeps_up": r["keeps_up"], "module_ms_per_frame": r["module_ms_per_frame"],
        "latency_drift_s_per_recording_minute": r["latency_drift_s_per_recording_minute"],
        "frame_latency_s": r["frame_latency_s"], "non_causal_reads": audit.get("non_causal_reads"),
        "lookback_misses": audit.get("lookback_misses"), "runtime_error": r.get("error"),
    })
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--modules", required=True, help="comma list")
    ap.add_argument("--chunks", default=None, help="default out/rt/chunks/<video stem>_gop1")
    ap.add_argument("--tag", default=None, help="run folder under out/rt/runs (default: modules_<video stem>_<time>)")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--inferences-dir", default=None,
                    help="GM / tracker ndjson to feed (default out/testset/prod/<video>; e.g. the rows a pipeline run wrote)")
    a = ap.parse_args()

    stem = os.path.splitext(a.video)[0]
    chunks = a.chunks or os.path.join("out", "rt", "chunks", f"{stem}_gop1")
    tag = a.tag or f"modules_{stem}_{time.strftime('%Y%m%d_%H%M')}"
    root = os.path.join("out", "rt", "runs", tag)
    os.makedirs(os.path.join(ROOT, root), exist_ok=True)
    plan = Plan([a.video])
    procs = []
    for module in [m for m in a.modules.split(",") if m]:
        out = os.path.join(root, module)
        args = adapter_args(module, a.video, plan, os.path.join("out", "rt", "work", tag, module), a.inferences_dir)
        cmd = [sys.executable, "-m", "pf.rt.simulate", "--chunks", chunks, "--adapter", "prod", "--adapter-args",
               json.dumps(args), "--out", out, "--speed", str(a.speed)]
        if a.max_seconds:
            cmd += ["--max-seconds", str(a.max_seconds)]
        log = io.open(os.path.join(ROOT, out + ".log"), "w", encoding="utf-8")
        procs.append((module, out, subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT), log))
        print(f"started {module}", flush=True)
    for module, out, proc, log in procs:
        rc = proc.wait()
        log.close()
        print(f"finished {module}: exit {rc}", flush=True)
    summary = [summarise(m, os.path.join(ROOT, out), a.video) for m, out, _, _ in procs]
    with io.open(os.path.join(ROOT, root, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=str)
    for s in summary:
        print(json.dumps(s, default=str)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
