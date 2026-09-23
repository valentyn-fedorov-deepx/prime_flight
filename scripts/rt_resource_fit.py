"""How small an allocation keeps a module (or a set) at 8 fps in real time, and what the same allocation makes of post-processing.

Post-processing uses whatever it gets and finishes sooner or later; real time has to keep up with the camera, so the question
is the smallest allocation that does. This runs the real-time branch on the decisive minutes of a module under a constrained
allocation and reports whether it keeps up:

  * CPU: the whole run (pipeline, decoder, module processes) pinned to N logical cores (`--cpu-cores`);
  * GPU: the detector heads run as if the card were k times slower (`--gpu-slowdown`: the run waits (k - 1) x the time the
    frame spent on the card; rows unchanged). This card is an RTX 5070 Ti; a production Tesla T4 is an estimated 3-4x slower
    on these heads (NOT measured: the break-even k below is what a T4 benchmark has to be compared with);
  * RAM: not limited, the peak of the process tree is reported against the 8 GiB a production job gets.

With `--speed 8` the same allocation is fed as fast as it goes: that is what post-processing would make of it (frames per
second), so both branches are compared on the same emulated machine.

    python scripts/rt_resource_fit.py --module steering-by-pass-pin-installed-or-steering-otherwise-bypassed \
        --grid 1:1,1:4,1:6,1:8,2:8 [--seconds 180] [--with-post]
    python scripts/rt_resource_fit.py --set pixel_free --grid 1:4,2:4,3:4,3:3 --seconds 180

Results: `out/rt/cost/<event>/resource_fit_<name>.json`.
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

BUDGET_MS = 125.0


def run(slice_video: str, event: str, modules: list, heads: list, classes: list, cores: int, k: float, speed: float,
        seconds: float, tag: str, gpu_base_ms: float, tracker_base_ms: float | None = None, provider: str = "cuda") -> dict:
    stem = os.path.splitext(slice_video)[0]
    cmd = [sys.executable, "scripts/rt_pipeline_run.py", "--video", slice_video, "--plan-video", event, "--module", modules[0],
           "--tag", tag, "--speed", str(speed), "--no-write-rows", "--heads", ",".join(heads), "--tracker-classes", ",".join(classes),
           "--ingest", "frames" if speed == 1 else "chunks", "--bandwidth-mbps", "10" if speed == 1 else "1000",
           "--max-seconds", str(seconds), "--chunks", os.path.join("out", "rt", "chunks", f"{stem}_gop1"),
           "--gpu-slowdown", str(k), "--gpu-base-ms", str(gpu_base_ms), "--cpu-cores", str(cores), "--subscriptions",
           "--provider", provider]
    if len(modules) > 1:
        cmd += ["--extra-modules", ",".join(modules[1:])]
    if tracker_base_ms:
        cmd += ["--tracker-base-ms", str(tracker_base_ms)]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sampler = MachineSampler(proc.pid).start()
    rc = proc.wait()
    sampler.stop()
    rec = {"cpu_cores": cores, "gpu_slowdown": k, "tracker_slowed_too": bool(tracker_base_ms), "provider": provider,
           "speed": speed, "exit_code": rc,
           "wall_s": round(time.time() - t0, 1)}
    path = os.path.join(ROOT, "out", "rt", "runs", tag, "summary.json")
    if rc != 0 or not os.path.exists(path):
        return {**rec, "error": f"run failed (out/rt/runs/{tag}.log)"}
    s = json.load(io.open(path, encoding="utf-8"))
    comp = s.get("components_ms_per_frame") or {}
    frames = s.get("frames") or 0
    total = (comp.get("total") or {}).get("mean")
    rec.update({
        "frames": frames, "keeps_up": s.get("keeps_up"), "frame_latency_s": s.get("frame_latency_s"),
        "latency_drift_s_per_recording_minute": s.get("latency_drift_s_per_recording_minute"),
        "ms_per_frame": {name: {"mean": (v or {}).get("mean"), "p95": (v or {}).get("p95")} for name, v in comp.items()},
        "of_budget": round(total / BUDGET_MS, 2) if total else None,
        "gm_heads": s.get("gm_heads"), "module_error": s.get("module_error"), "runtime_error": s.get("runtime_error"),
        "machine": sampler.summary(steady_s=max(30.0, frames / 8.0 / speed)),
    })
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="zHxIAF2vUGxJ.mp4")
    ap.add_argument("--module", default="steering-by-pass-pin-installed-or-steering-otherwise-bypassed")
    ap.add_argument("--modules", default="", help="instead of one module or a named set: this comma list, on the common busy stretch")
    ap.add_argument("--name", default="", help="name of the result file when --modules is given")
    ap.add_argument("--set", default="", choices=["", "pixel_free", "all_ready"],
                    help="instead of one module: the ready modules (all, or the pixel-free ones) behind the full GM and tracker, "
                         "on the common busy stretch")
    ap.add_argument("--grid", default="1:4,1:6,1:8,2:8,1:1", help="comma list of cores:slowdown")
    ap.add_argument("--seconds", type=float, default=180.0)
    ap.add_argument("--with-post", action="store_true", help="also feed every allocation as fast as it goes (post-processing)")
    ap.add_argument("--slow-tracker", action="store_true",
                    help="pessimistic bound: the tracker slowed down by the same factor as the detector heads")
    ap.add_argument("--provider", default="cuda", choices=["cuda", "tensorrt"],
                    help="tensorrt: the same heads through TensorRT (8 ms instead of 19 on this card; tolerant parity)")
    ap.add_argument("--gpu-base-ms", type=float, default=None,
                    help="override the busy-card time of the heads the slowdown is built on (TensorRT: about 8 ms for three)")
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()

    stem = os.path.splitext(a.video)[0]
    cost_dir = os.path.join(ROOT, "out", "rt", "cost", stem)
    measured = json.load(io.open(os.path.join(cost_dir, "modules.json"), encoding="utf-8"))
    if a.set or a.modules:
        table = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"), encoding="utf-8"))
        ready = [r for r in table["modules"] if r["runs_in_real_time_as_is"].startswith("yes")]
        if a.set == "pixel_free":
            ready = [r for r in ready if not r.get("pixels")]
        if a.modules:
            chosen = [m for m in a.modules.split(",") if m]
            ready = sorted((r for r in ready if r["module"] in chosen), key=lambda r: chosen.index(r["module"]))
        ready.sort(key=lambda r: r["whole_event_ms"].get("module") or 1e9)
        modules = [r["module"] for r in ready]
        heads, classes = ["gm", "chocks", "vehicle"], ["airplane", "beltloader", "gse", "person"]
        slice_video, name = f"{stem}_6961_12007.mp4", a.set or a.name or "set"  # the common busy stretch of rt_shared_cost.py
        gpu_base_ms = table["gm_by_head_set_ms"]["gm+chocks+vehicle"]
        tracker_base_ms = table["tracker_by_tracked_classes_ms"]["airplane+beltloader+gse+person"]
    else:
        rec = measured[a.module]
        modules, heads, classes = [a.module], rec["heads"], rec["tracker_classes"]
        slice_video, name = f"{stem}_{rec['slice']['start']}_{rec['slice']['end']}.mp4", a.module[:40]
        gpu_base_ms = rec["whole_event"]["ms_per_frame_at_this_speed"]["gm"]  # the heads of this module with the card kept busy
        tracker_base_ms = rec["whole_event"]["ms_per_frame_at_this_speed"]["tracker"]
    gpu_base_ms = a.gpu_base_ms or gpu_base_ms
    out_path = os.path.join(cost_dir, f"resource_fit_{name}.json")
    result = json.load(io.open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {"runs": {}}
    result.update(modules=modules, heads=heads, tracker_classes=classes, slice=slice_video, seconds=a.seconds,
                  gpu_base_ms=gpu_base_ms)
    for item in [g for g in a.grid.split(",") if g]:
        cores, k = int(item.split(":")[0]), float(item.split(":")[1])
        for speed in ([1.0, 8.0] if a.with_post else [1.0]):
            key = f"cores{cores}_k{k:g}{'_trk' if a.slow_tracker else ''}{'_trt' if a.provider == 'tensorrt' else ''}_x{speed:g}"
            if not a.redo and key in result["runs"] and not result["runs"][key].get("error"):
                continue
            rec = run(slice_video, a.video, modules, heads, classes, cores, k, speed, a.seconds, f"fit_{name}_{key}", gpu_base_ms,
                      tracker_base_ms if a.slow_tracker else None, a.provider)
            result["runs"][key] = rec
            json.dump(result, io.open(out_path, "w", encoding="utf-8", newline="\n"), indent=1, default=str)
            ms = rec.get("ms_per_frame") or {}
            print(f"{key}: keeps_up={rec.get('keeps_up')} total {(ms.get('total') or {}).get('mean')} ms (p95 "
                  f"{(ms.get('total') or {}).get('p95')}), gm {(ms.get('gm') or {}).get('mean')}, tracker "
                  f"{(ms.get('tracker') or {}).get('mean')}, module {(ms.get('module') or {}).get('mean')} | latency p95 "
                  f"{(rec.get('frame_latency_s') or {}).get('p95')} s | cpu {(rec.get('machine') or {}).get('cpu_cores_used')} cores, "
                  f"ram {(rec.get('machine') or {}).get('rss_peak_gb')} GB, gpu {(rec.get('machine') or {}).get('gpu_util_mean')} % "
                  f"| err {rec.get('error') or rec.get('runtime_error')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
