"""Pose unification gate: module verdicts and pose cost of run labels against v2 (the modules' own pose models).

Reads `out/testset/modules/<label>/<video>/<module>.json` of the pose modules, pairs every run with `modules/v2` (same
inferences, same flags, the module's own model), and reports per module: runs, identical statuses, the changed ones, the
module wall time and the pose time (calls, boxes, seconds) from the `pose` record that `scripts/run_module.py` writes with
`--pose-override` / `--pose-timing`. Event verdicts against the CI report's truth come from
`out/testset/compare_<label>_vs_v2.json` (`scripts/testset/compare.py`: tasks merged over the event's cameras).

    python scripts/pose_gate_summary.py --labels pose_rtm,pose_ctl --out out/pose/gate_summary.json
    python scripts/pose_gate_summary.py --labels pose_rtm,pose_dw --baseline pose_ctl --compare-suffix _full         --out out/pose/full_summary.json      # the whole validation set (scripts/testset/pose_full_run.py)
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS = os.path.join(ROOT, "out", "testset")
MODULES = {
    "hand-signals": "HRNet-W48",
    "steering-by-pass-pin-installed-or-steering-otherwise-bypassed": "HRNet-W48",
    "pin-verification": "SimCC ResNet-50",
    "lead-marshaller-and-wing-walkers-in-position": "HRNet-W48",
    "wing-walkers-in-proper-position-and-using-approved-wands": "HRNet-W48",
    "fod-walk-completed": "MoveNet Thunder",
    "gse-chocks": "RTMPose-l (own runner)",
}


def jload(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def summarise(label: str, baseline: str = "v2", suffix: str = "") -> dict:
    out = {"label": label, "baseline": baseline, "modules": {}, "changed": []}
    for module, own in MODULES.items():
        runs = []
        for p in sorted(glob.glob(os.path.join(TS, "modules", label, "*", f"{module}.json"))):
            video = os.path.basename(os.path.dirname(p))
            base_p = os.path.join(TS, "modules", baseline, video, f"{module}.json")
            if not os.path.exists(base_p):
                continue
            r, b = jload(p), jload(base_p)
            pose = (r.get("pose") or {}).get("timings") or {}
            bpose = (b.get("pose") or {}).get("timings") or {}
            runs.append({"video": video, "status": r.get("status"), "v2": b.get("status"),
                         "error": r.get("error") or b.get("error"),
                         "seconds": r.get("seconds"), "v2_seconds": b.get("seconds"), "pose_calls": pose.get("calls"),
                         "pose_boxes": pose.get("boxes"), "pose_s": pose.get("total_s"), "base_pose_s": bpose.get("total_s")})
        if not runs:
            continue
        ok = [x for x in runs if not x["error"]]
        changed = [x for x in ok if x["status"] != x["v2"]]
        out["changed"] += [{"module": module, **x} for x in changed]
        out["modules"][module] = {
            "own_model": own, "runs": len(runs), "errors": len(runs) - len(ok),
            "identical": len(ok) - len(changed),
            "seconds_total": round(sum(x["seconds"] or 0 for x in ok), 1),
            "v2_seconds_total": round(sum(x["v2_seconds"] or 0 for x in ok), 1),
            "pose_calls": sum(x["pose_calls"] or 0 for x in ok), "pose_boxes": sum(x["pose_boxes"] or 0 for x in ok),
            "pose_s": round(sum(x["pose_s"] or 0 for x in ok), 2),
            "base_pose_s": round(sum(x["base_pose_s"] or 0 for x in ok), 2),
            "pose_ms_per_call_median_run": (round(statistics.median(
                [1000 * x["pose_s"] / x["pose_calls"] for x in ok if x["pose_calls"]]), 2)
                if any(x["pose_calls"] for x in ok) else None),
            "runs_detail": runs,
        }
    cmp_path = os.path.join(TS, f"compare_{label}_vs_{baseline}{suffix}.json")
    if os.path.exists(cmp_path):
        rep = jload(cmp_path)
        tasks = {t for m in MODULES for t in jload(os.path.join(TS, "plan.json"))["module_tasks"].get(m, [])}
        rows = [r for r in rep["rows"] if r["task"] in tasks and r["comparable"] and r.get("baseline") is not None]
        truth = [r for r in rows if r["true"] not in ("", None)]
        per_task = {}
        for r in rows:
            t = per_task.setdefault(r["task"], {"paired": 0, "identical": 0, "with_truth": 0, "correct": 0, "base_correct": 0})
            t["paired"] += 1
            t["identical"] += r["ours"] == r["baseline"]
            if r["true"] not in ("", None):
                t["with_truth"] += 1
                t["correct"] += r["ours"] == r["true"]
                t["base_correct"] += r["baseline"] == r["true"]
        out["events"] = {
            "per_task": per_task,
            "paired_task_verdicts": len(rows), "identical": sum(r["ours"] == r["baseline"] for r in rows),
            "with_truth": len(truth), "correct": sum(r["ours"] == r["true"] for r in truth),
            "v2_correct": sum(r["baseline"] == r["true"] for r in truth),
            "changed": [{k: r[k] for k in ("event_id", "task", "ours", "baseline", "true", "videos")}
                        for r in rows if r["ours"] != r["baseline"]],
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default="pose_rtm,pose_ctl")
    ap.add_argument("--baseline", default="v2", help="run label the labels are paired with")
    ap.add_argument("--compare-suffix", default="", help="compare file name suffix: compare_<label>_vs_<baseline><suffix>.json")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "pose", "gate_summary.json"))
    a = ap.parse_args()
    res = {}
    for label in [x for x in a.labels.split(",") if x]:
        s = res[label] = summarise(label, a.baseline, a.compare_suffix)
        print(f"== {label} vs {a.baseline}")
        print(f"{'module':58s} own model              runs  same  err  module s (v2 s)   pose calls  boxes  pose s  ms/call")
        for m, d in s["modules"].items():
            print(f"{m[:58]:58s} {d['own_model'][:22]:22s} {d['runs']:4d} {d['identical']:5d} {d['errors']:4d}  "
                  f"{d['seconds_total']:8.1f} ({d['v2_seconds_total']:7.1f}) {d['pose_calls']:9d} {d['pose_boxes']:6d} "
                  f"{d['pose_s']:7.2f}  {d['pose_ms_per_call_median_run']}")
        for c in s["changed"]:
            print(f"  CHANGED {c['module']} {c['video']}: {c['status']} ({a.baseline} {c['v2']})")
        ev = s.get("events")
        if ev:
            print(f"  events: paired {ev['paired_task_verdicts']}, identical {ev['identical']}; with truth {ev['with_truth']}: "
                  f"{label} correct {ev['correct']}, {a.baseline} correct {ev['v2_correct']}")
            for t, c in sorted(ev["per_task"].items()):
                print(f"    {t[:40]:40s} paired {c['paired']:3d} same {c['identical']:3d} correct {a.baseline} {c['base_correct']:3d} -> {label} {c['correct']:3d} (of {c['with_truth']})")
            for c in ev["changed"][:40]:
                print(f"    {c['event_id']} {c['task']}: {label}={c['ours']} {a.baseline}={c['baseline']} true={c['true']}")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
