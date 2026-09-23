"""Sizing one real-time environment: what each module adds to it, and what a chosen set of modules needs to run without delay.

A real-time environment = one GPU host that runs, per camera stream, one GM with the heads the chosen modules read, one
tracker with the classes they read, and every module as a process of its own. Built from what the campaign measured on one
event (`scripts/rt_module_cost.py`, `scripts/rt_post_cost.py`, `scripts/rt_joint_run.py`):

  * the frame path of a stream (what has to fit into 125 ms) = GM[heads] + tracker[classes] + hand-off; the modules work
    beside it, so they cost CPU cores and memory, not frame time;
  * a module therefore has two prices: what it DRAGS IN (a head or a tracked class nobody else in the set needs) and what it
    costs ITSELF (CPU, memory, its slowest frames);
  * post-processing of the same set = the same GM and tracker work plus the module jobs, done back to back.

    python scripts/rt_environment.py                         # the price list and three example sets -> docs/analysis/rt_environment.md
    python scripts/rt_environment.py --modules a,b,c,d,e     # size this set
    python scripts/rt_environment.py --gates 40              # the environment for 40 gates (the default)
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BUDGET_MS, FPS, HEADROOM, DECODE_MS = 125.0, 8.0, 0.8, 2.9
HEAD_ORDER, CLASS_ORDER = ("gm", "chocks", "vehicle"), ("airplane", "beltloader", "gse", "person")
EXAMPLES = {
    "pushback and belt loader, no pixels": [
        "3-stop-brake-check", "pushback-pathway-confirmed-clear-of-obstacles",
        "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready", "beltloader-chocks", "bl_rear_cone",
        "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked"],
    "arrival": [
        "crew-present-10-minutes-prior-to-aircraft-arrival", "chocks-and-cones-available-and-staged-for-arrival",
        "cones-placed-in-proper-positions-and-timely", "fod-walk-completed", "pre-arrival-safety-huddle",
        "lead-marshaller-and-wing-walkers-in-position"],
    "pushback trio + the three heavy pixel modules": [
        "3-stop-brake-check", "pushback-pathway-confirmed-clear-of-obstacles",
        "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready", "safety-vests-secured-to-body",
        "safety-handrails-fully-extended", "handrails-on-gse-being-used"],
}


def load(path: str):
    return json.load(io.open(path, encoding="utf-8")) if os.path.exists(path) else None


def lookup(table: dict, wanted: set, order: tuple) -> float:
    key = "+".join(x for x in order if x in wanted)
    if key in table:
        return table[key]
    supersets = [v for k, v in table.items() if wanted <= set(k.split("+"))]
    return min(supersets) if supersets else max(table.values())


class Data:
    def __init__(self, video: str):
        stem = os.path.splitext(video)[0]
        cost = os.path.join(ROOT, "out", "rt", "cost", stem)
        self.report = load(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"))
        self.rows = {r["module"]: r for r in self.report["modules"]}
        self.post = load(os.path.join(cost, "post_jobs.json")) or {}
        joint = load(os.path.join(cost, "joint_all_ready_x1.json")) or {}
        self.hosts = joint.get("module_hosts") or {}
        self.joint = joint
        self.gm, self.trk = self.report["gm_by_head_set_ms"], self.report["tracker_by_tracked_classes_ms"]
        self.frames = self.report["frames"]
        self.event_s = self.frames / FPS

    def module(self, m: str) -> dict:
        r, job = self.rows[m], (self.post.get(m) or {}).get("as_production") or {}
        host = (self.hosts.get(m) or {}).get("per_frame") or {}
        heads, classes = set(r["heads"] or []), set(r["tracked"] or [])
        cpu_s, wall = job.get("cpu_seconds"), job.get("wall_s")
        return {
            "module": m, "runs_as_is": r["runs_in_real_time_as_is"], "pixels": bool(r.get("pixels")),
            "heads": sorted(heads, key=HEAD_ORDER.index), "classes": sorted(classes, key=CLASS_ORDER.index),
            # what the set pays if this module is the only one that needs them
            "drags_in_gm_ms": round(lookup(self.gm, heads | {"gm"}, HEAD_ORDER) - self.gm["gm"], 1),
            "drags_in_tracker_ms": round(lookup(self.trk, classes | {"airplane"}, CLASS_ORDER) - self.trk["airplane"], 1),
            "own_ms_alone": r["whole_event_ms"].get("module"),
            "own_ms_together": host.get("mean_ms"), "own_p95_ms_together": host.get("p95_ms"), "own_max_ms_together": host.get("max_ms"),
            # CPU and memory of the module process: the instrumented joint run when there is one, else the post job of the
            # same code as the estimate (same models, same buffers; its CPU seconds include parsing the files)
            "cpu_cores_mean": round((host.get("cpu_s_after_ready") or cpu_s or 0.0) / self.event_s, 2) if (host.get("cpu_s_after_ready") or cpu_s) else None,
            "cpu_cores_burst": round(cpu_s / wall, 1) if cpu_s and wall else None,
            "ram_gb": host.get("rss_peak_gb") or (job.get("machine") or {}).get("rss_peak_gb"),
            "measured_in_real_time": bool(host.get("cpu_s_after_ready")),
            "post_job_s": wall, "post_cpu_s": cpu_s, "verdict_arrives": r.get("verdict_arrives"),
        }

    def size(self, modules: list) -> dict:
        mods = [self.module(m) for m in modules]
        heads = {h for m in mods for h in m["heads"]} | {"gm"}
        classes = {c for m in mods for c in m["classes"]} | {"airplane"}
        gm_ms, trk_ms = lookup(self.gm, heads, HEAD_ORDER), lookup(self.trk, classes, CLASS_ORDER)
        hand_off = 5.0 + 0.12 * len(mods)  # decode, causal rows, records and pixels to every module (7.3 ms measured with 19)
        frame_path = gm_ms + trk_ms + hand_off
        worst_case = frame_path + sum(m["own_ms_alone"] or 0.0 for m in mods)  # if every module sat on the frame path
        streams = int(HEADROOM * BUDGET_MS / frame_path)
        cpu_mean = 0.4 + sum(m["cpu_cores_mean"] or 0.0 for m in mods)  # 0.3-0.5 cores: decoder, GM host side, tracker
        ram = 3.5 + sum(m["ram_gb"] or 0.0 for m in mods)  # the pipeline process with every head: 3-3.5 GB
        post_s = (gm_ms + trk_ms + 2 * DECODE_MS) * self.frames / 1000.0 + sum(m["post_job_s"] or 0.0 for m in mods)
        return {
            "modules": modules, "heads": sorted(heads, key=HEAD_ORDER.index), "classes": sorted(classes, key=CLASS_ORDER.index),
            "gm_ms": gm_ms, "tracker_ms": trk_ms, "hand_off_ms": round(hand_off, 1), "frame_path_ms": round(frame_path, 1),
            "of_budget": round(frame_path / BUDGET_MS, 2), "frame_path_if_modules_were_inline_ms": round(worst_case, 1),
            "streams_per_gpu_by_frame_time": streams,
            "cpu_cores_mean_per_stream": round(cpu_mean, 1),
            "cpu_cores_burst_of_the_heaviest_module": max((m["cpu_cores_burst"] or 0.0 for m in mods), default=0.0),
            "ram_gb_per_stream": round(ram, 1),
            "post_processing_s_per_event": round(post_s), "event_s": self.event_s,
            "real_time_over_post_one_stream_per_gpu": round(self.event_s / post_s, 2),
            "real_time_over_post_gpu_shared": round(self.event_s / max(streams, 1) / post_s, 2),
            "not_ready": [m["module"] for m in mods if not m["runs_as_is"].startswith("yes")],
        }


def per_stream_measured(d: Data) -> dict:
    """GPU share, GPU memory, CPU and RAM of one camera stream running a set of about six modules, from the joint runs."""
    pixel = {m for m, r in d.rows.items() if r.get("pixels")}
    light, heavy = "light: six pixel-free modules", "with pixel modules: three pixel-free + three pixel modules"
    groups: dict = {light: [], heavy: []}
    for path in sorted(glob.glob(os.path.join(ROOT, "out", "rt", "cost", "*", "joint_*_x8.json"))):
        j = load(path)
        if not j or j.get("error") or j.get("exit_code") or j.get("runtime_error") or not j.get("ms_per_frame"):
            continue
        mc, total = j.get("machine") or {}, j["ms_per_frame"]["total"]["mean"]
        if not total or not mc.get("gpu_util_mean") or len(j["modules"]) >= 18:  # the twenty-module set is not a 6-module set
            continue
        times_real_time = BUDGET_MS / total
        groups[heavy if any(m in pixel for m in j["modules"]) else light].append({
            "gpu": mc["gpu_util_mean"] / 100.0 / times_real_time, "vram": mc.get("gpu_mem_over_baseline_gb") or 0.0,
            "cpu": (mc.get("cpu_cores_used") or 0.0) / times_real_time})
    ram = {light: 3.0 + 0.6 * 5, heavy: 3.0 + 0.6 * 3 + 2.0 * 3}  # pipeline + module processes (pixel modules 1.3-3 GB each)
    out = {}
    for key, runs in groups.items():
        if not runs:
            continue
        gpu, cpu = sorted(r["gpu"] for r in runs), sorted(r["cpu"] for r in runs)
        # the sampler reads the memory of the whole card: a browser on the desktop shows up in single runs (one light run
        # read 6.3 GB against 2.8-3.2 in the other 29), so the 90th percentile, not the maximum
        vram = sorted(r["vram"] for r in runs if r["vram"] > 0)
        out[key] = {"runs": len(runs), "gpu_median": gpu[len(gpu) // 2], "gpu_max": gpu[-1],
                    "vram": vram[min(len(vram) - 1, round(0.9 * (len(vram) - 1)))], "cpu": round(cpu[len(cpu) // 2] * 1.75, 2),
                    "ram": ram[key]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="zHxIAF2vUGxJ.mp4")
    ap.add_argument("--modules", default="", help="comma list: size this set and exit")
    ap.add_argument("--gates", type=int, default=40, help="how many gates to size the environment for")
    a = ap.parse_args()
    d = Data(a.video)
    cost_dir = os.path.join(ROOT, "out", "rt", "cost", os.path.splitext(a.video)[0])
    if a.modules:
        print(json.dumps(d.size([m for m in a.modules.split(",") if m]), indent=1))
        return 0

    def n(v, digits=1):
        return "—" if v is None else f"{v:.{digits}f}"

    price = [d.module(m) for m, r in d.rows.items() if r["whole_event_ms"].get("total") is not None]
    price.sort(key=lambda m: -((m["drags_in_gm_ms"] + m["drags_in_tracker_ms"]) + (m["own_ms_together"] or m["own_ms_alone"] or 0.0)))
    measured = sum(1 for m in price if m["measured_in_real_time"])
    L = ["# Sizing one real-time environment", "",
         "Generated by `scripts/rt_environment.py`; the measurements are those of `docs/analysis/rt_module_cost.md` (one event, "
         f"{d.event_s:.0f} s, RTX 5070 Ti, 8 cores at 4.7 GHz, 27 GB). Do not edit by hand.", "",
         "## How a real-time environment spends its resources", "",
         "Per camera stream: one GM with the heads the chosen modules read, one tracker with the classes they read, every module a "
         "process of its own.", "",
         "- **The frame path** (what has to fit into 125 ms per frame, or the stream falls behind): `GM[heads] + tracker[classes] + "
         "hand-off`. It is set by the heads and classes of the set, not by how many modules read them.",
         "- **The modules** work beside the frame path: they cost CPU cores and memory. A slow module delays its own verdict, and "
         "only when it is slower than the camera for long does it hold the others (the pixel hand-off waits for it).",
         "- **Post-processing of the same set** is the same GM and tracker work plus the module jobs, done back to back; real time "
         f"holds the environment for the {d.event_s / 60:.0f} minutes of the event instead.", "",
         "| shared part | ms per frame | | shared part | ms per frame |", "|---|---|---|---|---|"]
    gm_items, trk_items = list(d.gm.items()), list(d.trk.items())
    for i in range(max(len(gm_items), len(trk_items))):
        g = gm_items[i] if i < len(gm_items) else ("", "")
        t = trk_items[i] if i < len(trk_items) else ("", "")
        L.append(f"| {'GM: ' + g[0] if g[0] else ''} | {g[1]} | | {'tracker: ' + t[0] if t[0] else ''} | {t[1]} |")

    L += ["", "## What each module adds", "",
          "`drags in` = what the frame path grows by if this module is the only one in the set that needs that head or class (nothing, "
          "if another module already needs it). `own work` = inside the module process, all twenty running together at real-time speed. "
          "`CPU` and `RAM` of the module process: "
          + (f"measured in the joint run for {measured} modules, " if measured else "")
          + "otherwise taken from the post job of the same code (same models and buffers; an estimate until the instrumented joint run). "
          "`burst` = cores it takes while it works on a frame.", "",
          "| module | runs as it is | drags in: GM ms | drags in: tracker ms | own work ms: mean · p95 | CPU cores: mean · burst | RAM GB | "
          "post job s | verdict arrives |", "|---|---|---|---|---|---|---|---|---|"]
    for m in price:
        L.append(f"| {m['module']} | {m['runs_as_is']} | {'+' + n(m['drags_in_gm_ms']) if m['drags_in_gm_ms'] else '0'} "
                 f"({'+'.join(h for h in m['heads'] if h != 'gm') or 'gm only'}) | "
                 f"{'+' + n(m['drags_in_tracker_ms']) if m['drags_in_tracker_ms'] else '0'} "
                 f"({'+'.join(c for c in m['classes'] if c != 'airplane') or 'airplane only'}) | "
                 f"{n(m['own_ms_together'] if m['own_ms_together'] is not None else m['own_ms_alone'], 2)} · {n(m['own_p95_ms_together'])} | "
                 f"{n(m['cpu_cores_mean'], 2)} · {n(m['cpu_cores_burst'])} | {n(m['ram_gb'])} | {n(m['post_job_s'], 0)} | "
                 f"{m['verdict_arrives'] or '—'} |")
    L += ["", "Reading it: the expensive thing a module can do to a real-time environment is to be the only reason for belt loader "
          "tracking (+15.7 ms on every frame of the stream) or for the chocks and vehicle heads (+3 to +10.7 ms); after that come the "
          "pixel modules with their own networks, which take 3–5 cores in bursts and 1.3–3 GB each (safety-vests, handrails-on-gse, "
          "wing-walkers, safety-handrails, lead-marshaller). A module that reads no pixels costs a fraction of a core and 0.8 GB."]

    L += ["", "## Example sets", "",
          f"`streams per GPU` = how many camera streams of this set one card carries by frame time (80 % of 125 ms / frame path); CPU and RAM "
          "are per stream and have to be multiplied. `real time ÷ post` = the time the environment is held for one event against the "
          "post-processing work of the same set on the same machine.", "",
          "| set | modules | heads | tracked | frame path ms (of 125) | streams per GPU | CPU cores per stream: mean · heaviest burst | RAM GB per stream | "
          "post-processing s per event | real time ÷ post: one stream per GPU · GPU shared |", "|---|---|---|---|---|---|---|---|---|---|"]
    sized = {}
    for name, modules in EXAMPLES.items():
        s = d.size(modules)
        sized[name] = s
        L.append(f"| {name} | {len(modules)} | {'+'.join(s['heads'])} | {'+'.join(s['classes'])} | **{s['frame_path_ms']}** ({round(100 * s['of_budget'])} %) | "
                 f"**{s['streams_per_gpu_by_frame_time']}** | {s['cpu_cores_mean_per_stream']} · {s['cpu_cores_burst_of_the_heaviest_module']} | "
                 f"{s['ram_gb_per_stream']} | {s['post_processing_s_per_event']} | {s['real_time_over_post_one_stream_per_gpu']}× · "
                 f"**{s['real_time_over_post_gpu_shared']}×** |")
    every = [m["module"] for m in price if m["runs_as_is"].startswith("yes")]
    s = d.size(every)
    sized["every module that runs as it is"] = s
    L.append(f"| every module that runs as it is | {len(every)} | {'+'.join(s['heads'])} | {'+'.join(s['classes'])} | **{s['frame_path_ms']}** "
             f"({round(100 * s['of_budget'])} %) | **{s['streams_per_gpu_by_frame_time']}** | {s['cpu_cores_mean_per_stream']} · "
             f"{s['cpu_cores_burst_of_the_heaviest_module']} | {s['ram_gb_per_stream']} | {s['post_processing_s_per_event']} | "
             f"{s['real_time_over_post_one_stream_per_gpu']}× · **{s['real_time_over_post_gpu_shared']}×** |")
    if d.joint.get("ms_per_frame"):
        jt = d.joint["ms_per_frame"]["total"]
        L += ["", f"Check of the model against the measured joint run of the {len(d.joint['modules'])} modules at real-time speed: frame path "
              f"{jt['mean']} ms mean, {jt['p95']} ms p95 (the model says {s['frame_path_ms']} ms with the card kept busy; at 8 fps this card "
              f"clocks down and the same work takes longer), {d.joint['machine'].get('cpu_cores_used')} cores on average, "
              f"{d.joint['machine'].get('rss_peak_gb')} GB RAM, GPU {d.joint['machine'].get('gpu_util_mean')} % busy."]
    L += ["", "The CPU and RAM columns are estimates from the post jobs and they miss in opposite directions: for the twenty modules "
          f"together they give {s['cpu_cores_mean_per_stream']} cores and {s['ram_gb_per_stream']} GB, the joint run measured "
          f"{d.joint.get('machine', {}).get('cpu_cores_used')} cores (handing rows and pixels to every process costs CPU the post jobs do "
          f"not have) and {d.joint.get('machine', {}).get('rss_peak_gb')}–23 GB (a post job also holds the parsed files). Read RAM as an upper "
          "bound and CPU as a lower one.",
          "", "What this does not tell yet: how many streams one card really carries before frames start to wait (the number above is by frame "
          "time only; two pipelines contend for the card and for the cores), and the CPU and RAM of every module process measured in real "
          "time rather than taken from its post job. Both are one night of runs: `scripts/rt_joint_run.py` now records CPU seconds and "
          "peak memory per module process."]
    # ------------------------------------------------------------------ the production pod envelope
    pod_envelope: dict = {}
    env = load(os.path.join(ROOT, "docs", "analysis", "production_envelope.json"))
    fits = {os.path.basename(p)[len("resource_fit_"):-len(".json")]: load(p)
            for p in sorted(glob.glob(os.path.join(cost_dir, "resource_fit_*.json")))}
    fits = {k: v for k, v in fits.items() if v and v.get("runs") and (v.get("seconds") or 0) >= 120}
    if env and fits:
        gpu_pod, cpu_pod = env["pools"]["gpu-pool"], env["pools"]["cpu-pool"]
        per = env["per_video"]
        L += ["", "## What it takes to fit in a production-like pod", "",
              f"The envelope is what a pod can actually reach in the cluster (`{env['source']['pods']}`, measured 23.09 on a test "
              "node of each pool):", "",
              "| pool | vCPU | CPU | RAM GB | GPU | GPU memory | scratch GB | modules there |", "|---|---|---|---|---|---|---|---|"]
        for pool, spec in env["pools"].items():
            L.append(f"| {pool} | {spec['max CPU (vCPU)']} | {spec['CPU']} | {spec['max RAM (GB)']} | {spec['GPU']} | "
                     f"{spec['GPU memory (GB)'] or '—'} | {spec['max scratch disk (GB)']} | {len(env['modules_per_pool'][pool])} |")
        L += ["", "**What post-processing does inside that envelope today** "
              f"({env['source']['time_to_result']}, videos about {env['video_minutes']} min long): GM runs "
              f"{env['time_to_result_h']['GM running']} h per video = **{per['gm_ms_per_frame']} ms per frame** "
              f"({per['gm_x_real_time']}× the recording), the tracker {env['time_to_result_h']['tracker running']} h = "
              f"**{per['tracker_ms_per_frame']} ms per frame** ({per['tracker_x_real_time']}×), the modules finish "
              f"{env['time_to_result_h']['modules, until the video is done']} h after the tracker. Those two jobs alone are "
              f"**{per['gpu_pod_hours_gm_and_tracker']} GPU-pod hours per video**, {per['gpu_pod_hours_per_recorded_hour']} per "
              "recorded hour; a real-time stream holds one host for one hour per recorded hour. So the question is not whether "
              "real time costs more machine time — it costs less — but what a host has to be for the frame path to stay under "
              "125 ms. On this pod it does not: the GM job alone spends 1.7 times the whole real-time budget on a frame.", "",
              "**The same branch, measured here inside an emulated envelope** (`scripts/rt_resource_fit.py`: the run pinned to "
              f"N cores of this machine, the detector heads made k times slower than this card). The T4 by the published rates "
              f"({gpu_pod['GPU FP16 tensor (TFLOPS)']} against about 176 FP16 tensor TFLOPS here, "
              f"{gpu_pod['GPU memory speed (GB/s)']} against 896 GB/s) is **k ≈ 3**; `+ tracker` makes the tracker k times slower "
              "too, which is the pessimistic end (part of it is CPU work that a card cannot change); `TRT` runs the heads through "
              "TensorRT, where three heads take 8 ms on this card instead of 19 (`gm_speed.md`, tolerant parity).", "",
              "| modules | cores here | GPU | keeps 8 fps | frame path ms, mean · p95 | GM | tracker | CPU used, cores | RAM GB |",
              "|---|---|---|---|---|---|---|---|---|"]
        rows_fit = []
        for name, fit in fits.items():
            for key, r in sorted(fit["runs"].items(), key=lambda kv: (kv[1].get("provider") or "", -(kv[1].get("cpu_cores") or 0),
                                                                     kv[1].get("gpu_slowdown") or 0)):
                if r.get("error") or r.get("speed") != 1:
                    continue
                ms, mc = r.get("ms_per_frame") or {}, r.get("machine") or {}
                gpu = ("this card" if r["gpu_slowdown"] == 1 else f"{r['gpu_slowdown']:g}× slower") + \
                      (" + tracker" if r.get("tracker_slowed_too") else "") + \
                      (", TRT" if r.get("provider") == "tensorrt" else "")
                rows_fit.append({"set": name, "modules": len(fit["modules"]), "cores": r["cpu_cores"], "gpu": gpu,
                                 "keeps_up": bool(r.get("keeps_up")), "mean": (ms.get("total") or {}).get("mean"),
                                 "p95": (ms.get("total") or {}).get("p95"), "cpu": mc.get("cpu_cores_used"),
                                 "ram": mc.get("rss_peak_gb")})
                L.append(f"| {name[:24]} ({len(fit['modules'])}) | {r['cpu_cores']} | {gpu} | **{'yes' if r.get('keeps_up') else 'no'}** | "
                         f"{n((ms.get('total') or {}).get('mean'))} · {n((ms.get('total') or {}).get('p95'))} | "
                         f"{n((ms.get('gm') or {}).get('mean'))} | {n((ms.get('tracker') or {}).get('mean'))} | "
                         f"{n(mc.get('cpu_cores_used'), 2)} | {n(mc.get('rss_peak_gb'))} |")
        def fitting(set_name: str, tensorrt: bool = False, k: float = 3.0):
            """The cheapest run of that set that keeps 8 fps with the heads k times slower (no pessimistic tracker)."""
            rows = [r for r in rows_fit if r["set"] == set_name and r["keeps_up"] and "tracker" not in r["gpu"]
                    and ("TRT" in r["gpu"]) == tensorrt and f"{k:g}× slower" in r["gpu"]]
            return min(rows, key=lambda r: (r["cores"], r["mean"])) if rows else None

        t4_cuda, t4_trt = fitting("trio"), fitting("trio_trt", tensorrt=True)
        core_factor = 0.6  # a pod's 4 Haswell threads at 2.30 GHz against one core here (4.7 GHz): an estimate, node_bench.py measures it
        L += ["", f"Reading the CPU column: the pod's {gpu_pod['max CPU (vCPU)']} vCPU of an Intel Haswell at 2.30 GHz are worth "
              f"about **{core_factor} of one core of this machine** in throughput (an estimate from clock and generation; "
              "`scripts/node_bench.py`, two minutes in a pod, replaces it with a measurement). So the pod gives less CPU than the "
              "single pinned core that already failed here, and it gives it as four slow threads instead of one fast one.", "",
              "**What one camera stream needs to fit**, from the rows above:", "",
              "| | production GPU pod today | needed for a set of 3–6 modules |", "|---|---|---|",
              f"| GPU | Tesla T4, {gpu_pod['GPU FP16 tensor (TFLOPS)']} FP16 TFLOPS, {gpu_pod['GPU memory speed (GB/s)']} GB/s, 70 W | "
              + (f"a T4-class card is enough **with TensorRT heads** (measured: {t4_trt['mean']:.0f} ms of 125, p95 "
                 f"{t4_trt['p95']:.0f}, on {t4_trt['cores']} cores) and only just without them "
                 f"({t4_cuda['mean']:.0f} ms, p95 {t4_cuda['p95']:.0f}); a card 1.5–2× slower than this one (L4 24 GB on GCP, "
                 "A10 on Azure) fits either way |" if t4_trt and t4_cuda else
                 "a card no more than about 3× slower than an RTX 5070 Ti |"),
              f"| GPU memory | {gpu_pod['GPU memory (GB)']} GB (14.6 free) | 3 GB for a pixel-free set, 5+ GB with pixel modules — "
              "the T4 has room for 2–4 streams, the limit is its speed, not its memory |",
              f"| CPU | {gpu_pod['max CPU (vCPU)']} vCPU Haswell 2.30 GHz ≈ {core_factor} core here | **2 cores of this machine keep "
              "8 fps, 1 does not** (the mean load is 0.7 of a core; the peaks need the rest) → about 3–4 pods' worth of CPU: "
              "12–16 vCPU on the current Haswell nodes, 6–8 vCPU on a modern server generation (Ice Lake and later, Azure v5) |",
              f"| RAM | {gpu_pod['max RAM (GB)']} GB | 5 GB for three modules, 7 GB for six, 10.7 GB for ten pixel-free — the pod fits "
              "about ten light modules; the full twenty with the pixel ones need 18–23 GB |",
              f"| scratch disk | {gpu_pod['max scratch disk (GB)']} GB | almost none: the frames live in memory and nothing "
              "downloads an 87-minute video |", "",
              "Two things are still estimates rather than measurements, and both are one run away: **how slow the T4 really is** on "
              "these heads (k = 3 comes from the published rates) and **what the tracker's own GPU work costs there** — the rows "
              "with `+ tracker` slow the whole tracker by k and do not fit, so if the T4 is that hard on the tracker's segmentors "
              "and re-id, a T4-class card is out even with TensorRT. `scripts/node_bench.py` answers the first in two minutes "
              "inside a pod (it prints the factor against this machine, for the card and for a core); the second needs the tracker "
              "weights in that pod."]
        pod_envelope = {"pools": env["pools"], "post_processing_per_video": per, "runs": rows_fit,
                        "core_factor_estimate": core_factor}

    # ------------------------------------------------------------------ sizing for N gates
    per = per_stream_measured(d)
    gates, cams = a.gates, 2
    L += ["", f"## Sizing for {gates} gates", "",
          f"Assumptions: **{cams} camera streams per gate** (cone + wing: the pushback and belt loader checks run on both cameras, "
          "`docs/05_module_logic.md`), **every gate busy at the same time** (no delay at the peak; fewer if the schedule says the peak "
          "is lower), the branch **as it is** (one GM + tracker pipeline per camera, every module a process of its own), 20 % headroom "
          "on the card.", "",
          "Per camera stream, measured in the joint runs of section 4 of `rt_module_cost.md` on this machine (RTX 5070 Ti 16 GB). The "
          "GPU share comes from the runs fed faster than real time (the card at full clock): GPU busy % ÷ how many times real time "
          "the run went. CPU at real-time speed is 1.6–1.9 times the same division (measured on the twenty-module runs: at 8 fps the "
          "processes also wait on the card, and the waits spin), so the CPU column is the division × 1.75. RAM of a light set is the "
          "pipeline (3 GB) plus 0.6 GB per module process; the fed-faster runs overstate RAM with their backlog.", "",
          "| set | runs | GPU share of a 5070 Ti: median · max | GPU memory GB (p90) | CPU cores (4.7 GHz) | RAM GB | streams per 16 GB card | "
          "limited by |", "|---|---|---|---|---|---|---|---|"]
    sizing = {}
    for name, p in per.items():
        if not p:
            continue
        by_gpu = int(0.8 / p["gpu_max"])
        by_mem = int((16 - 1.5) / p["vram"])
        per_card = max(1, min(by_gpu, by_mem))
        L.append(f"| {name} | {p['runs']} | {100 * p['gpu_median']:.0f} % · {100 * p['gpu_max']:.0f} % | {p['vram']:.1f} | "
                 f"{p['cpu']:.1f} | {p['ram']:.0f} | **{per_card}** | {'GPU memory' if by_mem < by_gpu else 'GPU time'} |")
        streams = gates * cams
        cards = -(-streams // per_card)
        sizing[name] = {"per_stream": p, "streams_per_card": per_card, "streams": streams, "cards_16gb": cards,
                        "cpu_cores": round(streams * p["cpu"]), "ram_gb": round(streams * p["ram"]),
                        "gpu_memory_gb": round(streams * p["vram"])}
    L += ["", f"For {gates} gates = {gates * cams} camera streams:", "",
          "| set | cards like this one (16 GB) | CPU cores (4.7 GHz) | RAM GB | the same per card |", "|---|---|---|---|---|"]
    for name, s in sizing.items():
        per_card = s["streams_per_card"]
        L.append(f"| {name} | **{s['cards_16gb']}** | {s['cpu_cores']} | {s['ram_gb']} | {per_card} streams: "
                 f"{per_card * s['per_stream']['cpu']:.0f} cores, {per_card * s['per_stream']['ram']:.0f} GB RAM |")
    L += ["", "What moves these numbers:", "",
          f"- **Cameras**: checks that run on the cone camera only need one stream per gate: halve every number ({gates} streams).",
          "- **The peak**: the environment is sized for the gates that are busy at the same time. How many that is at the peak hour "
          "comes from the flight schedule (the event documents in MongoDB have the times); a cloud fleet can follow the schedule "
          "instead of holding the peak all day.",
          "- **The card**: a 24 GB card (L4 on GCP, A10 on Azure) lifts the memory limit (about 7 light streams by memory). Its speed "
          "against this card is **not measured**; if it is 1.5–2 times slower (an estimate), it carries about as many light streams "
          "as this card by GPU time. A T4 (16 GB, an estimated 3–4 times slower) carries one light stream at most.",
          "- **The architecture**: every stream loads its own copy of the three detector heads and the tracker networks, and every "
          "module is a Python process of its own. One set of models per card serving all its streams in batches (TensorRT: the three "
          "heads in 8 ms instead of 19, `gm_speed.md`) and fewer module processes are the levers of PF-Q4-02; they are not in these "
          "numbers.",
          "- **Not measured yet**: several streams on one card at the same time. The streams-per-card column is derived from one stream "
          "at a time; the check is 1, 2, 3, 4 light streams on this card until frames start to wait (one night, the RAM of this "
          "machine allows about three)."]
    out_sizing = {"gates": gates, "cameras_per_gate": cams, "sets": sizing}

    io.open(os.path.join(ROOT, "docs", "analysis", "rt_environment.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    json.dump({"price_list": price, "sets": sized, "gates": out_sizing, "pod_envelope": pod_envelope}, io.open(os.path.join(ROOT, "docs", "analysis", "rt_environment.json"), "w",
                                                             encoding="utf-8", newline="\n"), indent=1, default=str)
    for name, s in sized.items():
        print(name, "| frame path", s["frame_path_ms"], "ms | streams", s["streams_per_gpu_by_frame_time"], "| cpu", s["cpu_cores_mean_per_stream"],
              "| ram", s["ram_gb_per_stream"], "| post s", s["post_processing_s_per_event"], "| rt/post", s["real_time_over_post_one_stream_per_gpu"],
              s["real_time_over_post_gpu_shared"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
