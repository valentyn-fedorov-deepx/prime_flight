"""What one module costs in real time: the module alone, behind the GM heads and tracked classes only it needs.

For every module this runs the real-time branch on the stretch of an event where that module decides (from its batch
smart timeline), with a GM and a tracker scoped to that module alone (`scripts/rt_scope_for.py`), and samples the machine
while it runs:

    per frame   GM, causal rows, tracker, the module itself (mean / p95), end-to-end latency, keeps-up
    machine     GPU utilisation and memory (device totals: WDDM does not report per-process memory), CPU cores used and
                resident memory over the process tree of the run
    against     the batch cost of the same module on the same event (module seconds per frame; full GM + full tracker)

The point of running modules ONE AT A TIME is attribution: heads and tracked classes are shared, so the cost of a set of
modules is `GM[union of heads] + tracker[union of classes] + sum of the modules' own cost`, not the sum of the single
runs. `--report` builds that table from the single runs and says what any set of modules is predicted to cost.

    python scripts/rt_module_cost.py --video zHxIAF2vUGxJ.mp4                     # every module that can run live
    python scripts/rt_module_cost.py --video zHxIAF2vUGxJ.mp4 --modules 3-stop-brake-check,bl_rear_cone
    python scripts/rt_module_cost.py --video zHxIAF2vUGxJ.mp4 --report            # table from what has been measured

Run it on a quiet machine: a second GPU job doubles every number here (tasks/notes/PF-Q2-02.md).
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.rt_scope_for import scope  # noqa: E402
from scripts.rt_slices import cut, module_windows  # noqa: E402
from scripts.testset import orchestrate as o  # noqa: E402
from scripts.testset import profiles  # noqa: E402

FPS = 8.0
GOP = 30
BUDGET_MS = 1000.0 / FPS
FALLBACK_SLICE = (6961, 12007)  # the decision slice of zHxIAF2vUGxJ: busy apron, arrival handled, pushback inside


class MachineSampler:
    """Once a second: device GPU utilisation and memory, CPU seconds and resident memory of a process tree."""

    def __init__(self, pid: int, period_s: float = 1.0):
        self.pid, self.period_s = pid, period_s
        self.samples: list = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="machine-sampler")
        self._cpu_seen: dict = {}

    @staticmethod
    def gpu() -> tuple:
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout
            util, mem = out.strip().splitlines()[0].split(",")
            return float(util), float(mem) / 1024.0
        except Exception:
            return None, None

    def _tree(self) -> list:
        import psutil

        try:
            root = psutil.Process(self.pid)
            return [root, *root.children(recursive=True)]
        except psutil.Error:
            return []

    def _run(self) -> None:
        import psutil

        while not self._stop.wait(self.period_s):
            cpu_s = rss = 0.0
            for proc in self._tree():
                try:
                    t = proc.cpu_times()
                    self._cpu_seen[proc.pid] = t.user + t.system  # keeps the last value of a process that has exited
                    rss += proc.memory_info().rss
                except psutil.Error:
                    continue
            cpu_s = sum(self._cpu_seen.values())
            util, mem = self.gpu()
            self.samples.append({"t": time.perf_counter(), "cpu_s": cpu_s, "rss_gb": rss / 2**30,
                                 "gpu_util": util, "gpu_mem_gb": mem})

    def start(self) -> "MachineSampler":
        self.baseline_gpu_mem_gb = self.gpu()[1]
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def summary(self, steady_s: float, tail_s: float = 3.0) -> dict:
        """The steady window: the last `steady_s` seconds of the run, without the teardown tail."""
        if len(self.samples) < 5:
            return {}
        end = self.samples[-1]["t"] - tail_s
        window = [s for s in self.samples if end - steady_s <= s["t"] <= end]
        if len(window) < 3:
            window = self.samples
        wall = window[-1]["t"] - window[0]["t"]
        utils = sorted(s["gpu_util"] for s in window if s["gpu_util"] is not None)
        mems = [s["gpu_mem_gb"] for s in window if s["gpu_mem_gb"] is not None]
        pick = lambda values, q: values[min(len(values) - 1, int(q * len(values)))] if values else None
        return {
            "window_s": round(wall, 1),
            "cpu_cores_used": round((window[-1]["cpu_s"] - window[0]["cpu_s"]) / wall, 2) if wall > 0 else None,
            "rss_peak_gb": round(max(s["rss_gb"] for s in window), 2),
            "gpu_util_mean": round(sum(utils) / len(utils), 1) if utils else None,
            "gpu_util_p95": pick(utils, 0.95),
            "gpu_mem_peak_gb": round(max(mems), 2) if mems else None,
            "gpu_mem_over_baseline_gb": round(max(mems) - (self.baseline_gpu_mem_gb or 0.0), 2) if mems else None,
        }


def decision_slice(video: str, module: str, fps: float, n_frames: int, pre_s: float, post_s: float, cap_s: float):
    """Frames [start, end] around the module's decision on this event, capped to `cap_s` seconds ending at its decision."""
    window = module_windows(video, [module])[0]
    if "first" not in window:
        start, end = FALLBACK_SLICE
        return {"start": start, "end": min(end, start + int(cap_s * fps)), "source": "common busy slice (no decision "
                "window in the batch output of this event)", "batch_status": window.get("status")}
    end = min(n_frames, int(window["last"] + post_s * fps))
    start = max(1, int(window["first"] - pre_s * fps))
    if (end - start) / fps > cap_s:
        start = end - int(cap_s * fps)
    start = max(1, (start - 1) // GOP * GOP + 1)
    return {"start": start, "end": end, "source": f"batch decision frames {window['first']}-{window['last']}",
            "batch_status": window.get("status")}


def batch_cost(video: str, module: str) -> dict:
    """What the same module cost in post-processing on this event (seconds of the module alone, full GM and tracker)."""
    path = os.path.join(ROOT, "out", "testset", "modules", "v2", video, f"{module}.json")
    led = o.load_ledger(video)["steps"]
    rec = {"gm_ms_per_frame": (led.get("gm") or {}).get("ms_per_frame"),
           "tracker_ms_per_frame": (led.get("tracker") or {}).get("ms_per_frame"),
           "frames": (led.get("gm") or {}).get("frames")}
    if os.path.exists(path):
        data = json.load(io.open(path, encoding="utf-8"))
        rec["module_seconds"] = data.get("seconds")
        if rec["frames"] and data.get("seconds"):
            rec["module_ms_per_frame"] = round(1000.0 * data["seconds"] / rec["frames"], 2)
        rec["status"] = data.get("status")
    return rec


def measure(video: str, module: str, a, fps: float, n_frames: int) -> dict:
    record = {"module": module, "video": video, "measured": time.strftime("%Y-%m-%d %H:%M")}
    prof = profiles.profile(module)
    if prof.get("launcher"):
        return {**record, "skipped": f"runs in another interpreter ({prof['launcher'][0]}): not hosted by the branch yet"}
    try:
        sc = scope([module])
    except SystemExit as e:
        return {**record, "skipped": f"no declaration: {e}"}
    record.update(heads=sc["heads"], tracker_classes=sc["tracker_classes"], pixels=not prof.get("pixel_free"))
    sl = decision_slice(video, module, fps, n_frames, a.pre_seconds, a.post_seconds, a.cap_minutes * 60)
    cut_info = cut(o.paths(video)["video"], sl, fps, os.path.join(ROOT, "out", "rt", "slices"))
    record["slice"] = {**{k: sl[k] for k in ("start", "end", "source", "batch_status")}, "frames": cut_info["frames"],
                       "seconds": round(cut_info["frames"] / fps, 1)}
    tag = f"cost_{module[:40]}"
    cmd = [sys.executable, "scripts/rt_pipeline_run.py", "--video", os.path.basename(cut_info["video"]),
           "--plan-video", video, "--module", module, "--tag", tag, "--speed", "1", "--no-write-rows",
           "--heads", ",".join(sc["heads"]), "--tracker-classes", ",".join(sc["tracker_classes"]),
           "--ingest", "frames", "--bandwidth-mbps", "10", "--chunks", os.path.relpath(cut_info["chunks"], ROOT)]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sampler = MachineSampler(proc.pid).start()
    rc = proc.wait()
    sampler.stop()
    record.update(exit_code=rc, wall_s=round(time.time() - t0, 1))
    summary_path = os.path.join(ROOT, "out", "rt", "runs", tag, "summary.json")
    if rc != 0 or not os.path.exists(summary_path):
        return {**record, "error": f"run failed (see out/rt/runs/{tag}.log)"}
    s = json.load(io.open(summary_path, encoding="utf-8"))
    comp = s.get("components_ms_per_frame") or {}
    record.update({
        "keeps_up": s.get("keeps_up"), "frame_latency_s": s.get("frame_latency_s"),
        "verdict_on_slice": s.get("live_status"), "module_error": s.get("module_error"),
        "ms_per_frame": {k: {"mean": (v or {}).get("mean"), "p95": (v or {}).get("p95")} for k, v in comp.items()},
        "tracker_detail_ms": s.get("tracker_ms_per_frame"), "gm_heads_detail": s.get("gm_heads"),
        "machine": sampler.summary(steady_s=cut_info["frames"] / fps),
        "batch": batch_cost(video, module),
    })
    total = (comp.get("total") or {}).get("mean")
    if total:
        record["share_of_budget"] = round(total / BUDGET_MS, 3)
        record["streams_per_gpu_by_time"] = int(0.8 * BUDGET_MS / total)  # 20 % headroom for the busy minutes
    return record


def load_records(video: str) -> dict:
    path = os.path.join(ROOT, "out", "rt", "cost", os.path.splitext(video)[0], "modules.json")
    return json.load(io.open(path, encoding="utf-8")) if os.path.exists(path) else {}


def save_records(video: str, records: dict) -> str:
    path = os.path.join(ROOT, "out", "rt", "cost", os.path.splitext(video)[0], "modules.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(records, io.open(tmp, "w", encoding="utf-8"), indent=1, default=str)
    os.replace(tmp, path)
    return path


def shared_costs(records: dict) -> dict:
    """GM cost per head set and tracker cost per class set: the median over the single runs that used that set."""
    gm, trk = {}, {}
    for r in records.values():
        ms = r.get("ms_per_frame") or {}
        if not ms:
            continue
        gm.setdefault("+".join(r["heads"]), []).append((ms.get("gm") or {}).get("mean"))
        trk.setdefault("+".join(r["tracker_classes"]), []).append((ms.get("tracker") or {}).get("mean"))
    med = lambda values: round(sorted(v for v in values if v is not None)[len(values) // 2], 2)
    return {"gm": {k: med(v) for k, v in gm.items() if any(v)}, "tracker": {k: med(v) for k, v in trk.items() if any(v)}}


def predict(records: dict, modules: list) -> dict:
    """Cost of running these modules together: shared heads and tracked classes once, the modules' own cost added up."""
    shared = shared_costs(records)
    heads = [h for h in ("gm", "chocks", "vehicle") if any(h in records[m]["heads"] for m in modules)]
    classes = [c for c in ("airplane", "beltloader", "gse", "person")
               if any(c in records[m]["tracker_classes"] for m in modules)]

    def nearest(table: dict, wanted: list):
        key = "+".join(wanted)
        if key in table:
            return table[key], key
        bigger = [(k, v) for k, v in table.items() if set(wanted) <= set(k.split("+"))]  # a superset bounds it from above
        return (min(bigger, key=lambda kv: kv[1])[1], min(bigger, key=lambda kv: kv[1])[0] + " (superset)") if bigger \
            else (max(table.values()), "largest measured")

    gm_ms, gm_src = nearest(shared["gm"], heads)
    trk_ms, trk_src = nearest(shared["tracker"], classes)
    own = sum(((records[m]["ms_per_frame"].get("module") or {}).get("mean") or 0.0) for m in modules)
    alone = sum(((records[m]["ms_per_frame"].get("total") or {}).get("mean") or 0.0) for m in modules)
    decode_rows = 5.0  # decode + causal rows + hand-off, measured 4-6 ms
    total = gm_ms + trk_ms + own + decode_rows
    return {"modules": modules, "heads": heads, "gm_ms": gm_ms, "gm_from": gm_src, "tracker_classes": classes,
            "tracker_ms": trk_ms, "tracker_from": trk_src, "modules_own_ms": round(own, 2),
            "predicted_total_ms": round(total, 1), "sum_of_single_runs_ms": round(alone, 1),
            "saved_by_sharing_ms": round(alone - total, 1), "share_of_budget": round(total / BUDGET_MS, 2)}


def report(video: str, records: dict) -> str:
    rows = [r for r in records.values() if r.get("ms_per_frame")]
    rows.sort(key=lambda r: (r["ms_per_frame"].get("total") or {}).get("mean") or 0.0)
    lines = [f"# What each module costs in real time, alone — {video}", "",
             "One module per run, behind the GM heads and tracked classes only it needs, on the stretch of the event where it "
             "decides, at real-time speed. Budget: 125 ms per frame at 8 fps.", "",
             "| module | heads | tracked | GM | tracker | module (mean / p95) | total | of budget | GPU util | GPU mem over idle "
             "| CPU cores | RAM | batch module ms |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ms, mach, batch = r["ms_per_frame"], r.get("machine") or {}, r.get("batch") or {}
        val = lambda k, f="mean": (ms.get(k) or {}).get(f)
        lines.append(
            f"| {r['module']} | {'+'.join(r['heads'])} | {'+'.join(r['tracker_classes'])} | {val('gm')} | {val('tracker')} | "
            f"{val('module')} / {val('module', 'p95')} | **{val('total')}** | {round(100 * r.get('share_of_budget', 0))} % | "
            f"{mach.get('gpu_util_mean')} % | {mach.get('gpu_mem_over_baseline_gb')} GB | {mach.get('cpu_cores_used')} | "
            f"{mach.get('rss_peak_gb')} GB | {batch.get('module_ms_per_frame')} |")
    skipped = [r for r in records.values() if r.get("skipped") or r.get("error")]
    if skipped:
        lines += ["", "Not measured:", ""] + [f"- {r['module']}: {r.get('skipped') or r.get('error')}" for r in skipped]
    shared = shared_costs(records)
    lines += ["", "## What is shared", "", "GM by head set (ms per frame): " + ", ".join(f"{k} {v}" for k, v in shared["gm"].items()),
              "", "Tracker by tracked classes (ms per frame): " + ", ".join(f"{k} {v}" for k, v in shared["tracker"].items())]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, help="an event with batch module outputs and its mp4 on disk")
    ap.add_argument("--modules", default="", help="comma list; default: every module of the event's plan")
    ap.add_argument("--pre-seconds", type=float, default=120.0)
    ap.add_argument("--post-seconds", type=float, default=20.0)
    ap.add_argument("--cap-minutes", type=float, default=6.0, help="longest stretch measured per module")
    ap.add_argument("--redo", action="store_true", help="measure again what is already measured")
    ap.add_argument("--report", action="store_true", help="only build the table from what has been measured")
    ap.add_argument("--predict", default="", help="comma list of modules: what they cost together, from the single runs")
    a = ap.parse_args()

    records = load_records(a.video)
    if not a.report and not a.predict:
        plan = o.Plan([a.video])
        modules = [m for m in a.modules.split(",") if m] or plan.modules(a.video)
        manifest = json.load(io.open(os.path.join(ROOT, "out", "rt", "chunks", f"{os.path.splitext(a.video)[0]}_gop1",
                                                  "manifest.json"), encoding="utf-8"))
        fps, n_frames = float(manifest["fps"]), int(manifest["n_frames"])
        for i, module in enumerate(modules, 1):
            if module in records and not a.redo and not records[module].get("error"):
                continue
            print(f"[{i}/{len(modules)}] {module}", flush=True)
            records[module] = measure(a.video, module, a, fps, n_frames)
            save_records(a.video, records)
            r = records[module]
            print("   ", r.get("skipped") or r.get("error") or
                  {k: (r["ms_per_frame"].get(k) or {}).get("mean") for k in ("gm", "tracker", "module", "total")},
                  r.get("machine"), flush=True)
    if a.predict:
        print(json.dumps(predict(records, [m for m in a.predict.split(",") if m]), indent=1))
        return 0
    out = os.path.join(ROOT, "out", "rt", "cost", os.path.splitext(a.video)[0], "modules.md")
    io.open(out, "w", encoding="utf-8").write(report(a.video, records))
    print(f"table: {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
