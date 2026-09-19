"""The modules that run in real time as they are, TOGETHER on the whole event: one GM with every head, one tracker with every
class, every module a component in its own process. Checks the sharing model of `scripts/rt_module_report.py` with a
measurement and records the machine it takes (GPU, GPU memory, CPU cores, RAM) and every verdict against the batch run.

    python scripts/rt_joint_run.py [--video zHxIAF2vUGxJ.mp4] [--speed 1] [--name all_ready] [--modules a,b,c]

Without `--modules`: every module that `docs/analysis/rt_module_cost.json` marks as running in real time as it is.
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


def ready_modules(video: str) -> list:
    """Modules marked as running as they are that the plan runs on this video (a batch verdict exists to compare with)."""
    table = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"), encoding="utf-8"))
    ready = [r["module"] for r in table["modules"] if r["runs_in_real_time_as_is"].startswith("yes")]
    batch = os.path.join(ROOT, "out", "testset", "modules", "v2", video)
    return [m for m in ready if os.path.exists(os.path.join(batch, f"{m}.json"))
            and "error" not in json.load(io.open(os.path.join(batch, f"{m}.json"), encoding="utf-8"))]


def ensure_chunks(video: str) -> None:
    chunks = os.path.join(ROOT, "out", "rt", "chunks", f"{os.path.splitext(video)[0]}_gop1")
    if not os.path.exists(os.path.join(chunks, "manifest.json")):
        subprocess.run([sys.executable, "-m", "pf.rt.chunker", "--video", os.path.join("out", "testset", "videos", video),
                        "--out", chunks, "--gops-per-chunk", "1"], cwd=ROOT, check=True)


def primary_of(modules: list) -> str:
    """The primary module runs inside the pipeline process, on the frame path: take the cheapest pixel-free one."""
    table = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"), encoding="utf-8"))
    rows = [r for r in table["modules"] if r["module"] in modules and not r.get("pixels")]
    rows.sort(key=lambda r: (r["whole_event_ms"].get("module") or 1e9))
    return rows[0]["module"] if rows else modules[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="zHxIAF2vUGxJ.mp4")
    ap.add_argument("--modules", default="", help="comma list; default: every module marked as running as it is")
    ap.add_argument("--speed", type=float, default=1.0, help="1: real time; 8: the GPU kept busy (work per frame)")
    ap.add_argument("--name", default="all_ready")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--no-subscriptions", action="store_true", help="hand every module the full rows instead of its declared ones")
    a = ap.parse_args()

    modules = [m for m in a.modules.split(",") if m] or ready_modules(a.video)
    ensure_chunks(a.video)
    primary = primary_of(modules)
    extras = [m for m in modules if m != primary]
    stem = os.path.splitext(a.video)[0]
    tag = f"joint_{stem}_{a.name}_x{a.speed:g}"
    cmd = [sys.executable, "scripts/rt_pipeline_run.py", "--video", a.video, "--module", primary,
           "--extra-modules", ",".join(extras), "--tag", tag, "--speed", str(a.speed), "--no-write-rows",
           "--ingest", "frames" if a.speed == 1 else "chunks", "--bandwidth-mbps", "10" if a.speed == 1 else "1000"]
    if not a.no_subscriptions:
        cmd.append("--subscriptions")
    if a.max_seconds:
        cmd += ["--max-seconds", str(a.max_seconds)]
    print(time.strftime("%H:%M:%S"), f"{len(modules)} modules together at {a.speed:g}x, primary {primary}", flush=True)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sampler = MachineSampler(proc.pid).start()
    rc = proc.wait()
    sampler.stop()
    record = {"video": a.video, "modules": modules, "primary": primary, "speed": a.speed, "exit_code": rc,
              "subscriptions": not a.no_subscriptions, "wall_s": round(time.time() - t0, 1),
              "measured": time.strftime("%Y-%m-%d %H:%M")}
    path = os.path.join(ROOT, "out", "rt", "runs", tag, "summary.json")
    if os.path.exists(path):
        s = json.load(io.open(path, encoding="utf-8"))
        comp = s.get("components_ms_per_frame") or {}
        verdicts = [{"module": primary, **{k: s.get(k) for k in ("live_status", "decided_after_frame", "batch_v2", "batch_ctl")}}]
        verdicts += [{k: v.get(k) for k in ("module", "live_status", "decided_after_frame", "batch_v2", "batch_ctl")}
                     for v in s.get("extra_module_verdicts") or []]
        record.update({
            "frames": s.get("frames"), "keeps_up": s.get("keeps_up"), "frame_latency_s": s.get("frame_latency_s"),
            "latency_drift_s_per_recording_minute": s.get("latency_drift_s_per_recording_minute"),
            "ms_per_frame": {k: {"mean": (v or {}).get("mean"), "p95": (v or {}).get("p95")} for k, v in comp.items()},
            "tracker_detail_ms": s.get("tracker_ms_per_frame"), "gm_heads_detail": s.get("gm_heads"),
            "host_send_ms_per_frame": s.get("host_send_ms_per_frame"), "module_hosts": s.get("module_hosts"),
            "module_error": s.get("module_error"), "runtime_error": s.get("runtime_error"), "verdicts": verdicts,
            "verdicts_identical_to_batch_v2": sum(1 for v in verdicts if (v.get("batch_v2") or {}).get("status_identical")),
            "reports_identical_to_batch_v2": sum(1 for v in verdicts if (v.get("batch_v2") or {}).get("report_identical")),
            "machine": sampler.summary(steady_s=max(60.0, (s.get("frames") or 0) / 8.0 / a.speed)),
        })
    else:
        record["error"] = f"run failed (see out/rt/runs/{tag}.log)"
    out_path = os.path.join(ROOT, "out", "rt", "cost", stem, f"joint_{a.name}_x{a.speed:g}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(record, io.open(out_path, "w", encoding="utf-8"), indent=1, default=str)
    print(time.strftime("%H:%M:%S"), json.dumps({k: record.get(k) for k in (
        "exit_code", "error", "keeps_up", "frame_latency_s", "verdicts_identical_to_batch_v2",
        "reports_identical_to_batch_v2", "machine", "module_error")}, indent=1, default=str), flush=True)
    print({k: v.get("mean") for k, v in (record.get("ms_per_frame") or {}).items()})
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
