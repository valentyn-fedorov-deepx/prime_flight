"""The answer table: what each module costs in real time, and whether it runs there as it is with batch quality.

Reads what the campaign measured and writes `docs/analysis/rt_module_cost.md` + `.json`:
  * `out/rt/cost/<event>/modules.json`     every module alone behind its scoped GM and tracker (`scripts/rt_module_cost.py`):
                                           its decisive minutes at real-time speed, and the whole event live against batch;
  * `out/rt/cost/<event>/joint_*.json`     the modules that run as they are, together (`scripts/rt_joint_run.py`);
  * `out/testset/modules/{sub,v2}`         every module over the test set with scoped inputs against full inputs;
  * `out/testset/compare_*.json`           the same as task verdicts against the labels (`scripts/testset/compare.py`).

    python scripts/rt_module_report.py [--video zHxIAF2vUGxJ.mp4]
    python scripts/rt_module_report.py --set 3-stop-brake-check,beltloader-chocks,bl_rear_cone   # these together, predicted
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BUDGET_MS = 125.0
FPS = 8.0
HEADROOM = 0.8     # a stream may take 80 % of its share: the busy minutes cost more than the mean
OVERHEAD_MS = 5.0  # decode + causal rows + hand-off, measured 4-6 ms
ORDER = {"yes": 0, "yes, verdict at session end": 1, "yes, report shifts": 2, "no: two passes": 3,
         "no: verdict differs": 4, "no: fails live": 5, "not hosted": 6}


def load(path: str):
    return json.load(io.open(path, encoding="utf-8")) if os.path.exists(path) else None


def anchors(video: str) -> dict:
    """T_arr and T_dep of the event from the batch tracker file (sparse scan: the anchors stay in the records once set)."""
    from scripts.testset import orchestrate as o

    path, found = o.paths(video)["trk_compat"], {}
    if not os.path.exists(path):
        return found
    with io.open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if n % 50 or len(found) == 2:
                continue
            for rec in next(iter(json.loads(line).values()), []):
                state = rec.get("state_dict") or {}
                for key in ("arrival_frame", "departure_frame"):
                    if rec.get("cls_str") == "airplane" and key not in found and isinstance(state.get(key), int):
                        found[key] = state[key]
    return found


def testset_identity() -> dict:
    """Per module: on how many video runs the scoped-input pass equals the full-input pass in status AND report."""
    out: dict = {}
    sub_root = os.path.join(ROOT, "out", "testset", "modules", "sub")
    for path in glob.glob(os.path.join(sub_root, "*", "*.json")):
        full = path.replace(os.path.join("modules", "sub"), os.path.join("modules", "v2"))
        if not os.path.exists(full):
            continue
        a, b = load(path), load(full)
        if "error" in a or "error" in b:
            continue
        rec = out.setdefault(a["module"], {"runs": 0, "status_same": 0, "report_same": 0})
        rec["runs"] += 1
        rec["status_same"] += a.get("status") == b.get("status")
        rec["report_same"] += a.get("status") == b.get("status") and a.get("report") == b.get("report")
    return out


def classify(rec: dict) -> tuple:
    w = rec.get("whole_event") or {}
    if w.get("skipped") or rec.get("skipped"):
        return "not hosted", (w.get("skipped") or rec.get("skipped"))
    errors = w.get("module_error")
    err = " ".join(str(e) for e in errors if e) if isinstance(errors, list) else str(errors or "")
    if "KeyError: 1" in err:
        return "no: two passes", ("reads the session a second time from frame 1, and in real time that frame is gone; the "
                                  "cost below covers its first pass only. Planned: a stage-detector event instead of the second "
                                  "pass for aircraft-chocks and pin-verification (PF-Q3-04), single-pass hand-signals and "
                                  "safety-zone (PF-Q2-11)")
    if err or w.get("error"):
        return "no: fails live", (err or str(w.get("error")))[:160]
    if w.get("status_identical") and w.get("report_identical"):
        if w.get("decided_after_frame") and w.get("frames") and w["decided_after_frame"] > w["frames"]:
            return "yes, verdict at session end", ("runs and gives the batch verdict, but only when the session closes: "
                                                   "to alert during the turn it needs a hook for an interim verdict")
        return "yes", ""
    if w.get("status_identical"):
        return "yes, report shifts", ("same verdict; the window or the count in the report moves slightly because the "
                                      "tracker follows only this module's classes (with the full tracker it does not)")
    return "no: verdict differs", f"live {w.get('live_status')} vs batch {w.get('batch_status')}"


def when(frame, frames, anc: dict) -> str:
    if frame is None:
        return "—"
    if frames and frame > frames:
        return "session end"
    clock = f"{int(frame / FPS) // 60}:{int(frame / FPS) % 60:02d}"
    arr, dep = anc.get("arrival_frame"), anc.get("departure_frame")
    if dep and frame >= dep - 8:
        return f"{clock} (T_dep + {round((frame - dep) / FPS)} s)"
    if arr and frame >= arr - 8:
        return f"{clock} (T_arr + {round((frame - arr) / FPS)} s)"
    return clock


def shared_tables(records: dict) -> tuple:
    gm, trk = {}, {}
    for rec in records.values():
        w = rec.get("whole_event") or {}
        ms = w.get("ms_per_frame_at_this_speed") or {}
        if ms.get("gm") is None:
            continue
        gm.setdefault("+".join(w["heads"]), []).append(ms["gm"])
        trk.setdefault("+".join(w["tracker_classes"]), []).append(ms["tracker"])

    def med(d):
        return {k: round(statistics.median(v), 1) for k, v in sorted(d.items(), key=lambda kv: statistics.median(kv[1]))}

    def spread(d):
        return {k: f"{min(v):.1f}–{max(v):.1f}, {len(v)} runs" if len(v) > 1 else "1 run" for k, v in d.items()}

    return med(gm), med(trk), {**spread(gm), **spread(trk)}


def lookup(table: dict, wanted: set, order: tuple) -> tuple:
    key = "+".join(x for x in order if x in wanted)
    if key in table:
        return table[key], key
    supersets = [(k, v) for k, v in table.items() if wanted <= set(k.split("+"))]
    k, v = min(supersets, key=lambda kv: kv[1]) if supersets else max(table.items(), key=lambda kv: kv[1])
    return v, f"{k} (nearest measured)"


def together(records: dict, modules: list, gm_table: dict, trk_table: dict) -> dict:
    whole = {m: records[m].get("whole_event") or {} for m in modules}
    heads = {h for w in whole.values() for h in w.get("heads", [])}
    classes = {c for w in whole.values() for c in w.get("tracker_classes", [])}
    gm_ms, gm_key = lookup(gm_table, heads, ("gm", "chocks", "vehicle"))
    trk_ms, trk_key = lookup(trk_table, classes, ("airplane", "beltloader", "gse", "person"))
    own = sum((w.get("ms_per_frame_at_this_speed") or {}).get("module") or 0.0 for w in whole.values())
    alone = sum((w.get("ms_per_frame_at_this_speed") or {}).get("total") or 0.0 for w in whole.values())
    total = gm_ms + trk_ms + own + OVERHEAD_MS
    return {"modules": len(modules), "heads": gm_key, "gm_ms": gm_ms, "tracked": trk_key, "tracker_ms": trk_ms,
            "modules_own_ms": round(own, 1), "together_ms": round(total, 1), "sum_of_single_runs_ms": round(alone, 1),
            "saved_by_sharing_ms": round(alone - total, 1), "of_budget": round(total / BUDGET_MS, 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="zHxIAF2vUGxJ.mp4")
    ap.add_argument("--set", default="", help="comma list of modules: print what they cost together and exit")
    a = ap.parse_args()
    stem = os.path.splitext(a.video)[0]
    cost_dir = os.path.join(ROOT, "out", "rt", "cost", stem)
    records = load(os.path.join(cost_dir, "modules.json"))
    if a.set:
        chosen = [m for m in a.set.split(",") if m]
        unknown = [m for m in chosen if not (records.get(m, {}).get("whole_event") or {}).get("ms_per_frame_at_this_speed")]
        if unknown:
            raise SystemExit(f"not measured live on the whole event: {unknown}")
        print(json.dumps(together(records, chosen, *shared_tables(records)[:2]), indent=1))
        return 0
    identity, anc = testset_identity(), anchors(a.video)
    gm_table, trk_table, spread = shared_tables(records)
    frames = max((r.get("whole_event") or {}).get("frames") or 0 for r in records.values())

    rows = []
    for module, rec in records.items():
        verdict, why = classify(rec)
        w = rec.get("whole_event") or {}
        busy, slice_ms, mach = w.get("ms_per_frame_at_this_speed") or {}, rec.get("ms_per_frame") or {}, rec.get("machine") or {}
        total = busy.get("total")
        streams = int(HEADROOM * BUDGET_MS / total) if total else None
        rows.append({
            "module": module, "runs_in_real_time_as_is": verdict, "why": why, "pixels": rec.get("pixels"),
            "heads": rec.get("heads") or w.get("heads"), "tracked": rec.get("tracker_classes") or w.get("tracker_classes"),
            "whole_event_ms": {k: busy.get(k) for k in ("gm", "tracker", "module", "total")},
            "of_budget": round(total / BUDGET_MS, 2) if total else None,
            "streams_per_gpu": streams,
            "gpu_time_against_packed_post": round(BUDGET_MS / streams / total, 2) if streams else None,
            "decisive_minutes": {"total_ms": (slice_ms.get("total") or {}).get("mean"),
                                 "module_ms": (slice_ms.get("module") or {}).get("mean"),
                                 "module_p95_ms": (slice_ms.get("module") or {}).get("p95"),
                                 "keeps_up": rec.get("keeps_up"),
                                 "frame_latency_p95_s": (rec.get("frame_latency_s") or {}).get("p95"),
                                 "gpu_util_mean": mach.get("gpu_util_mean"), "gpu_mem_gb": mach.get("gpu_mem_over_baseline_gb"),
                                 "cpu_cores": mach.get("cpu_cores_used"), "ram_gb": mach.get("rss_peak_gb")},
            "live_vs_batch": {k: w.get(k) for k in ("live_status", "batch_status", "status_identical", "report_identical",
                                                    "decided_after_frame", "frames")},
            "verdict_arrives": when(w.get("decided_after_frame"), w.get("frames"), anc),
            "testset_scoped_inputs": identity.get(module) or {},
            "post_job_module_ms": (rec.get("batch") or {}).get("module_ms_per_frame"),
            "post_job_module_s": (rec.get("batch") or {}).get("module_seconds"),
        })
    rows.sort(key=lambda r: (ORDER.get(r["runs_in_real_time_as_is"], 9), r["whole_event_ms"].get("total") or 1e9))

    ready = [r["module"] for r in rows if r["runs_in_real_time_as_is"].startswith("yes")]
    sets = {"every module that runs as it is": ready,
            "the pixel-free ones among them": [m for m in ready if not records[m].get("pixels")],
            "3-stop + pushback-pathway + pushback-wing-walkers": [
                "3-stop-brake-check", "pushback-pathway-confirmed-clear-of-obstacles",
                "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready"]}
    combos = {name: together(records, mods, gm_table, trk_table) for name, mods in sets.items() if mods}
    joint = {os.path.basename(p)[len("joint_"):-len(".json")]: load(p) for p in sorted(glob.glob(os.path.join(cost_dir, "joint_*.json")))}
    joint = {k: v for k, v in joint.items() if not k.startswith("smoke") and v and not v.get("error")}
    quality = {"scoped_vs_full_inputs": (load(os.path.join(ROOT, "out", "testset", "compare_sub_vs_v2.json")) or {}).get("totals"),
               "rt_inputs_vs_production_inputs": (load(os.path.join(ROOT, "out", "testset", "compare_v2_vs_ctl_final.json")) or {}).get("totals")}
    post_s = sum(r["post_job_module_s"] or 0 for r in rows if r["module"] in ready)
    live_s = sum((r["whole_event_ms"].get("module") or 0) * frames / 1000.0 for r in rows if r["module"] in ready)

    out = {"video": a.video, "frames": frames, "anchors": anc, "budget_ms": BUDGET_MS, "modules": rows,
           "gm_by_head_set_ms": gm_table, "tracker_by_tracked_classes_ms": trk_table, "together_predicted": combos,
           "together_measured": joint, "testset": quality,
           "ready_modules_own_seconds_on_this_event": {"as_post_jobs": round(post_s), "as_live_components": round(live_s)}}
    every_own = combos["every module that runs as it is"]["modules_own_ms"]

    def n(v, d=1):
        return "—" if v is None else f"{v:.{d}f}"

    count = {k: sum(1 for r in rows if r["runs_in_real_time_as_is"] == k) for k in ORDER}
    L = ["# What each module costs in real time, and whether it runs there as it is", "",
         "Generated by `scripts/rt_module_report.py` from the measurements under `out/rt/cost/` and `out/testset/`; do not edit by hand.",
         "",
         f"Event `{a.video}`: {frames} frames = {frames / FPS / 60:.0f} min, arrival at frame {anc.get('arrival_frame')}, departure at "
         f"{anc.get('departure_frame')}. Machine: RTX 5070 Ti 16 GB, 8 CPU cores, 27 GB RAM. Budget: 125 ms per frame at 8 fps.",
         "Every module was run **alone as a component**: the unchanged production module behind a GM with only the heads it reads "
         "and a tracker with only the classes it reads (its pseudo-GM), fed live: causal rows, a live tracker, the session length unknown.",
         "", "## 1. Does it run in real time as it is, with the batch verdict", "",
         f"**{count['yes'] + count['yes, verdict at session end'] + count['yes, report shifts']} of {len(rows)} run as they are** "
         f"({count['yes']} with the same verdict and report during the turn, {count['yes, verdict at session end']} only at session end, "
         f"{count['yes, report shifts']} with a small shift in the report), **{count['no: two passes']} cannot** (two passes over the "
         f"session), {count['not hosted']} are not hosted by the branch yet.", "",
         "| module | runs in real time as it is | live verdict = batch | same report | verdict arrives | test set, scoped inputs = full inputs |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        lb, ts = r["live_vs_batch"], r["testset_scoped_inputs"]
        live = "—" if lb.get("live_status") is None else (
            f"{lb['live_status']} = {lb['batch_status']}" if lb.get("status_identical") else f"{lb['live_status']} ≠ {lb['batch_status']}")
        same = "—" if lb.get("report_identical") is None else ("yes" if lb["report_identical"] else "no")
        L.append(f"| {r['module']} | **{r['runs_in_real_time_as_is']}** | {live} | {same} | {r['verdict_arrives']} | "
                 f"{str(ts['report_same']) + ' / ' + str(ts['runs']) if ts else '—'} |")
    seen, notes = set(), []
    for r in rows:
        if r["why"] and r["runs_in_real_time_as_is"] not in seen and r["runs_in_real_time_as_is"] != "not hosted":
            seen.add(r["runs_in_real_time_as_is"])
            names = ", ".join(x["module"] for x in rows if x["runs_in_real_time_as_is"] == r["runs_in_real_time_as_is"])
            note = f"- **{r['runs_in_real_time_as_is']}** ({names}): {r['why']}"
            if r["runs_in_real_time_as_is"] == "yes, report shifts":
                full = [v for j in joint.values() for v in j.get("verdicts") or []
                        if v["module"] in names and (v.get("batch_v2") or {}).get("report_identical")]
                if full:
                    note += ". Checked: in the joint run with the full tracker (section 4) their reports are identical to batch"
            notes.append(note)
    hosted_not = [f"{r['module']} ({'runs under WSL' if 'wsl' in str(r['why']).lower() else 'runs in its own Python environment'})"
                  for r in rows if r["runs_in_real_time_as_is"] == "not hosted"]
    if hosted_not:
        notes.append("- **not hosted**: " + "; ".join(hosted_not))
    L += ["", *notes, "",
          "The last column: the module over the whole test set (video runs) with only the rows of its pseudo-GM against the full rows, "
          "same status and same report. Modules that read pixels were run on the videos still on disk."]

    L += ["", "## 2. Load of each module alone", "",
          "*Whole event, GPU kept busy* is the work per frame (the GPU does not clock down): this is what adds up and what a second "
          "stream on the same GPU competes for. *Decisive minutes at real-time speed* is the stretch where the module decides (up to 6 min), "
          "played at 1×: what one stream looks like on the machine. `streams per GPU` = 80 % of 125 ms / total. "
          "`GPU time vs packed post` = GPU time this stream holds (125 ms / streams) against the same work done back to back.", "",
          "| module | heads | tracked | GM | tracker | module | **total ms** | of budget | streams per GPU | GPU time vs packed post | "
          "1×: total ms | 1×: latency p95 s | GPU util % | GPU mem GB | CPU cores | RAM GB | same module as a post job, ms/frame |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["whole_event_ms"].get("total") or 1e9):
        ms, dm = r["whole_event_ms"], r["decisive_minutes"]
        if ms.get("total") is None:
            continue
        mark = " (first pass only)" if r["runs_in_real_time_as_is"] == "no: two passes" else ""
        L.append(f"| {r['module']}{mark} | {'+'.join(r['heads'] or [])} | {'+'.join(r['tracked'] or [])} | {n(ms.get('gm'))} | "
                 f"{n(ms.get('tracker'))} | {n(ms.get('module'), 2)} | **{n(ms.get('total'))}** | {round(100 * r['of_budget'])} % | "
                 f"{r['streams_per_gpu']} | {n(r['gpu_time_against_packed_post'], 2)}× | {n(dm.get('total_ms'))} | "
                 f"{n(dm.get('frame_latency_p95_s'), 2)} | {n(dm.get('gpu_util_mean'))} | {n(dm.get('gpu_mem_gb'))} | "
                 f"{n(dm.get('cpu_cores'), 2)} | {n(dm.get('ram_gb'))} | {n(r['post_job_module_ms'], 2)} |")

    L += ["", "## 3. What is shared", "",
          "Heads and tracked classes are paid once for all the modules of a session (median over the single-module runs, GPU kept busy):", "",
          "| GM head set | ms per frame | | tracked classes | ms per frame |", "|---|---|---|---|---|"]
    gm_items, trk_items = list(gm_table.items()), list(trk_table.items())
    for i in range(max(len(gm_items), len(trk_items))):
        g = gm_items[i] if i < len(gm_items) else ("", "")
        t = trk_items[i] if i < len(trk_items) else ("", "")
        L.append(f"| {g[0]} | {g[1]}{' (' + spread[g[0]] + ')' if g[0] else ''} | | {t[0]} | {t[1]}{' (' + spread[t[0]] + ')' if t[0] else ''} |")

    shared = load(os.path.join(cost_dir, "shared.json"))
    if shared:
        gm_1x = [v["gm_ms"] for v in [*shared["tracker"].values(), shared["gm"].get("gm") or {}] if v.get("gm_ms")]
        L += ["", f"The same on one common stretch at real-time speed (`{shared['slice']}`, {shared['seconds']:.0f} s, "
              "`scripts/rt_shared_cost.py`):", "",
              "| GM head set (tracker: airplane) | GM ms | | tracked classes (GM: `gm` head) | tracker ms | GM ms in the same run |",
              "|---|---|---|---|---|---|"]
        g_items, t_items = list(shared["gm"].items()), list(shared["tracker"].items())
        for i in range(max(len(g_items), len(t_items))):
            g = (g_items[i][0].replace(",", "+"), n(g_items[i][1].get("gm_ms"))) if i < len(g_items) else ("", "")
            t = (t_items[i][0].replace(",", "+"), n(t_items[i][1].get("tracker_ms")), n(t_items[i][1].get("gm_ms")))                 if i < len(t_items) else ("", "", "")
            L.append(f"| {g[0]} | {g[1]} | | {t[0]} | {t[1]} | {t[2]} |")
        L += ["", f"At 8 fps the GPU clocks down between frames: the single `gm` head cost {min(gm_1x):.1f}–{max(gm_1x):.1f} ms for "
              "the same work depending on how busy the tracker kept the card (last column), and three heads came out cheaper than one. "
              "At real-time speed GM milliseconds measure the clock, not the work, so the sums below use the busy-GPU table. "
              "The tracker is monotone in both."]

    L += ["", "## 4. Modules together", "",
          "`cost = GM[union of heads] + tracker[union of classes] + sum of the modules' own cost + 5 ms (decode, rows, hand-off)`", "",
          "Predicted from the single runs:", "",
          "| set | modules | GM | tracker | modules' own | **together** | sum of single runs | saved by sharing | of budget |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name, c in combos.items():
        L.append(f"| {name} | {c['modules']} | {c['gm_ms']} | {c['tracker_ms']} | {c['modules_own_ms']} | **{c['together_ms']}** | "
                 f"{c['sum_of_single_runs_ms']} | {c['saved_by_sharing_ms']} | {round(100 * c['of_budget'])} % |")
    if joint:
        L += ["", "Measured: the same set in one run on the whole event, one GM with every head, one tracker with every class, every module "
              "a component in its own process with only its declared rows. The modules work in parallel with the frame path, so `hand-off` "
              "is rows, pixels and waiting for a slow reader, not the sum of their work:", "",
              "| run | modules | keeps up | GM | tracker | hand-off | **frame path ms** (mean · p95) | frame latency p95 s | GPU util % | "
              "GPU mem GB | CPU cores | RAM GB | verdict = batch | report = batch |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, j in joint.items():
            ms, mc = j.get("ms_per_frame") or {}, j.get("machine") or {}
            speed = "real-time speed" if j.get("speed") == 1 else f"GPU kept busy ({j.get('speed'):g}×)"
            total_ms = (ms.get("total") or {}).get("mean")
            keeps = str(j.get("keeps_up")) if j.get("speed") == 1 else (
                f"fed faster than it can go: {BUDGET_MS / total_ms:.2f}× real time" if total_ms else "—")
            latency = n((j.get("frame_latency_s") or {}).get("p95"), 2) if j.get("speed") == 1 else "—"
            L.append(f"| {speed} | {len(j['modules'])} | {keeps} | {n((ms.get('gm') or {}).get('mean'))} | "
                     f"{n((ms.get('tracker') or {}).get('mean'))} | {n((ms.get('module') or {}).get('mean'))} | "
                     f"**{n((ms.get('total') or {}).get('mean'))}** · {n((ms.get('total') or {}).get('p95'))} | "
                     f"{latency} | {n(mc.get('gpu_util_mean'))} | "
                     f"{n(mc.get('gpu_mem_over_baseline_gb'))} | {n(mc.get('cpu_cores_used'), 2)} | {n(mc.get('rss_peak_gb'))} | "
                     f"{j.get('verdicts_identical_to_batch_v2')} / {len(j['modules'])} | {j.get('reports_identical_to_batch_v2')} / {len(j['modules'])} |")
            diff = [v["module"] for v in j.get("verdicts") or [] if not (v.get("batch_v2") or {}).get("report_identical")]
            if diff:
                L.append(f"| ↳ not identical | {', '.join(diff)} | | | | | | | | | | | | |")
        rt_run = next((j for j in joint.values() if j.get("speed") == 1), None)
        if rt_run and rt_run.get("module_hosts"):
            hosts = rt_run["module_hosts"]
            own = sum((h.get("per_frame") or {}).get("mean_ms") or 0.0 for h in hosts.values())
            L += ["", f"The prediction puts every module on the frame path, so it is the upper bound. In the branch a module is a process "
                  f"of its own: at real-time speed their work added up to {own:.0f} ms of CPU time per frame across {len(hosts)} processes "
                  f"({every_own:.1f} ms when each ran alone: together they contend for the 8 cores), none of it on the frame path. "
                  "What binds a session with every module is CPU and memory, not the GPU. Own work per frame, alone and together:", "",
                  "| module | alone, ms | together at 1×, ms (mean · p95) | waits for a free frame slot |", "|---|---|---|---|"]
            by_module = {r["module"]: r for r in rows}
            for m, h in sorted(hosts.items(), key=lambda kv: -((kv[1].get("per_frame") or {}).get("mean_ms") or 0.0)):
                pf = h.get("per_frame") or {}
                L.append(f"| {m} | {n(by_module[m]['whole_event_ms'].get('module'), 2)} | {n(pf.get('mean_ms'), 2)} · {n(pf.get('p95_ms'))} | "
                         f"{h.get('ring_waits') or 0} |")
    more = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "out", "rt", "cost", "*", "joint_all_ready_x*.json"))):
        j = load(path)
        if j and not j.get("error") and j.get("verdicts"):
            more.setdefault(j["video"], []).append(j)
    if more:
        L += ["", "### Live against batch, modules together, every event still on disk", "",
              "One GM, one tracker, the modules the plan runs on that camera, each in its own process with its declared rows.", "",
              "| event | speed | modules | verdict = batch | report = batch | not identical |", "|---|---|---|---|---|---|"]
        pairs: dict = {}
        for video, runs in more.items():
            for j in sorted(runs, key=lambda x: x.get("speed") or 0):
                bad = [f"{v['module']} (live {v.get('live_status')}, batch {(v.get('batch_v2') or {}).get('status')})"
                       for v in j["verdicts"] if not (v.get("batch_v2") or {}).get("report_identical")]
                for v in j["verdicts"]:
                    b, pair = v.get("batch_v2") or {}, pairs.setdefault((video, v["module"]), [True, True])
                    pair[0] &= bool(b.get("status_identical"))
                    pair[1] &= bool(b.get("report_identical"))
                L.append(f"| `{video}` | {j.get('speed'):g}× | {len(j['verdicts'])} | {j.get('verdicts_identical_to_batch_v2')} | "
                         f"{j.get('reports_identical_to_batch_v2')} | {'; '.join(bad) or '—'} |")
        tn, tv, tr = len(pairs), sum(1 for x in pairs.values() if x[0]), sum(1 for x in pairs.values() if x[1])
        L.append(f"| **module × event pairs** | | **{tn}** | **{tv}** | **{tr}** | |")
        out["live_vs_batch_together"] = {"events": len(more), "module_event_pairs": tn, "verdict_identical": tv,
                                         "report_identical": tr}

    every = combos["every module that runs as it is"]
    premium = [r["gpu_time_against_packed_post"] for r in rows if r["gpu_time_against_packed_post"] and r["module"] in ready]
    rt = next((j for j in joint.values() if j.get("speed") == 1), None)
    machine = (f" Together at real-time speed the {len(rt['modules'])} modules took {rt['machine'].get('rss_peak_gb')} GB RAM, "
               f"{rt['machine'].get('gpu_mem_over_baseline_gb')} GB GPU memory and {rt['machine'].get('cpu_cores_used')} CPU cores."
               if rt and rt.get("machine") else "")
    L += ["", "## 5. Against post-processing", "",
          "- **Work per frame is not higher.** GM and tracker are the same code in both branches; the causal second-run rows add 0.1 ms. "
          f"The modules are cheaper live: as post jobs the {len(ready)} modules above took **{post_s:.0f} s** on this event (each job parses "
          f"the GM and tracker files and decodes the video again), as live components **{live_s:.0f} s** (decoded once, rows handed over in memory).",
          "- **What real time pays for is the reservation.** A stream holds its share of the GPU for the length of the event, whatever the "
          "scene; post-processing packs the same work back to back. With 20 % headroom that is the `GPU time vs packed post` column: "
          f"{min(premium):.2f}–{max(premium):.2f}× for one module, and it falls as modules share a session: "
          + (f"all {len(rt['modules'])} together measured {rt['ms_per_frame']['total']['mean']:.1f} ms on the frame path (p95 "
             f"{rt['ms_per_frame']['total']['p95']:.1f}) with the GPU {rt['machine'].get('gpu_util_mean')} % busy, so the card has room "
             "for a second stream while the 8 cores and the RAM of this machine do not."
             if rt and rt.get("machine") else
             f"all {len(ready)} together: {every['together_ms']} ms predicted of 125, one stream per GPU."),
          "- **It cannot be deferred or preempted**: post jobs can wait for a free GPU or run on spot capacity, a live stream cannot.",
          "- **The GPU class.** Production runs on a Tesla T4 (one GPU, 3.3 vCPU, 8 GiB per job). A T4 is an estimated 3–4× slower than this "
          "card (not measured): single light modules would fit, the full set would not." + machine]

    q1, q2 = quality["scoped_vs_full_inputs"], quality["rt_inputs_vs_production_inputs"]
    if q1 and q2:
        L += ["", "## 6. Quality on the test set (69 events, 90 videos)", "",
              "| step | compared task verdicts | identical | accuracy against the labels |", "|---|---|---|---|",
              f"| real-time GM + tracker (v2) against the production inputs | {q2['paired']} | {q2['paired_equal']} "
              f"({100 * q2['paired_equal'] / q2['paired']:.1f} %) | v2 {100 * q2['paired_ours_correct'] / q2['paired_with_truth']:.1f} %, "
              f"production inputs {100 * q2['paired_baseline_correct'] / q2['paired_with_truth']:.1f} %, "
              f"the monthly CI output {100 * q2['paired_new_correct'] / q2['paired_with_truth']:.1f} % |",
              f"| scoped inputs (pseudo-GM rows only) against the full v2 inputs | {q1['paired']} | {q1['paired_equal']} "
              f"({100 * q1['paired_equal'] / q1['paired']:.1f} %) | scoped {100 * q1['paired_ours_correct'] / q1['paired_with_truth']:.1f} %, "
              f"full {100 * q1['paired_baseline_correct'] / q1['paired_with_truth']:.1f} %, "
              f"the monthly CI output {100 * q1['paired_new_correct'] / q1['paired_with_truth']:.1f} % |", "",
              "The gap to the monthly CI output is the module build on this machine (substituted `cv_common` copies, 3-stop above all), "
              "present with the production inputs as well; it is not introduced by the real-time inputs."]

    L += ["", "## 7. What this does not cover", "",
          "- Live against batch was run on **one event**; the test-set pass checks the inputs (real-time GM + tracker, scoped rows) on all "
          "events, with the modules run over files, not live.",
          "- Scoping the GM heads is exact (the same rows a filter would leave). Scoping the **tracker classes is not**: the tracker's "
          "association sees fewer objects, which moved T_dep by up to 42 frames in one case. The session the branch actually runs has one "
          "full tracker, where this does not occur; the single-module numbers are a lower bound on cost, not a deployment proposal.",
          "- The two-pass modules fail at the start of their second pass, so their cost here is the first pass only.",
          "- At real-time speed with one head the GPU clocks down and a frame costs more milliseconds than under load; the per-frame work "
          "is the busy-GPU number, the 1× number is what the latency looks like.",
          "- Walk-arounds (another interpreter) and hair-policy (WSL) are not hosted by the branch.", "",
          "## How to reproduce", "", "```",
          "python scripts/rt_module_cost.py --video zHxIAF2vUGxJ.mp4 --cap-minutes 6        # every module alone, decisive minutes at 1x",
          "python scripts/rt_module_cost.py --video zHxIAF2vUGxJ.mp4 --parity               # every module alone, whole event, live vs batch",
          "python scripts/rt_shared_cost.py                                                 # GM by head set, tracker by class set, one stretch at 1x",
          "python scripts/rt_joint_run.py --speed 1 && python scripts/rt_joint_run.py --speed 8   # the ready modules together",
          "python scripts/testset/compare.py --runs-root out/testset/modules/sub --label sub --baseline-root out/testset/modules/v2 \\",
          "    --baseline-label v2 --out out/testset/compare_sub_vs_v2.json",
          "python scripts/rt_module_report.py                                               # this file", "```"]
    json.dump(out, io.open(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"), "w", encoding="utf-8", newline="\n"),
              indent=1, default=str)
    io.open(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print(json.dumps({"counts": count, "together_predicted": {k: v["together_ms"] for k, v in combos.items()},
                      "together_measured": {k: (v.get("ms_per_frame") or {}).get("total") for k, v in joint.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
