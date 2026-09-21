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
"""

from __future__ import annotations

import argparse
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="zHxIAF2vUGxJ.mp4")
    ap.add_argument("--modules", default="", help="comma list: size this set and exit")
    a = ap.parse_args()
    d = Data(a.video)
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
    io.open(os.path.join(ROOT, "docs", "analysis", "rt_environment.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    json.dump({"price_list": price, "sets": sized}, io.open(os.path.join(ROOT, "docs", "analysis", "rt_environment.json"), "w",
                                                             encoding="utf-8", newline="\n"), indent=1, default=str)
    for name, s in sized.items():
        print(name, "| frame path", s["frame_path_ms"], "ms | streams", s["streams_per_gpu_by_frame_time"], "| cpu", s["cpu_cores_mean_per_stream"],
              "| ram", s["ram_gb_per_stream"], "| post s", s["post_processing_s_per_event"], "| rt/post", s["real_time_over_post_one_stream_per_gpu"],
              s["real_time_over_post_gpu_shared"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
