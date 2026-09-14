"""Compare module verdicts of one run set with the monthly CI report and, optionally, pairwise with a baseline run set.

Reads `<runs-root>/<video>/<module>.json` (written by `scripts/run_module.py`) for every run of the plan, builds per-event
task verdicts exactly as the report does (two-camera merge Fail > Pass > Not observed; the derived stop-brake + hand-signals
task), and compares them with the report's "New output" (the reference), "Previous test output" and "True output (val)".

With `--baseline-root` the same verdicts are built from a second run set (the modules on the production inferences, same
machine and flags) and compared pairwise. The paired agreement isolates the inference change (GM v2 + Tracker v2) from
everything else that differs from the CI: module environment, substituted cv_common copies, tracker nondeterminism.

A task counts only when every module run it needs exists without an error; missing or failed runs are listed separately,
never counted as agreement. Tasks the CI did not run (no videos) are not applicable and are skipped.

    python scripts/testset/compare.py --runs-root out/testset/modules/v2 --label v2 \
        --baseline-root out/testset/modules/ctl --baseline-label ctl --out out/testset/compare_v2_vs_ctl.json
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.testset.common import (  # noqa: E402
    ROOT,
    derive_stopbrake_handsignals,
    merge_cameras,
    task_statuses_from_run,
)


def run_loader(root: str):
    cache = {}

    def get(module: str, video: str):
        key = (module, video)
        if key not in cache:
            p = os.path.join(root, video, f"{module}.json")
            cache[key] = json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else None
        return cache[key]

    return get


def event_verdicts(event: dict, run_result, module_tasks: dict) -> tuple[dict, dict]:
    """task -> merged verdict ('' when the CI ran the task on no video, None when a needed run is missing or failed)."""
    merged, detail = {}, {}
    for task, t in event["tasks"].items():
        if t["module"] is None:
            continue
        per_video, problems = {}, []
        for v in t["videos"]:
            r = run_result(t["module"], v)
            if r is None:
                problems.append(f"{v}: no run")
                continue
            st = task_statuses_from_run(r, module_tasks[t["module"]])
            if task not in st:
                problems.append(f"{v}: {str(r.get('error', 'no status'))[:160]}")
                continue
            per_video[v] = st[task]
        if not t["videos"]:
            merged[task] = ""
        elif problems:
            merged[task] = None
        else:
            merged[task] = merge_cameras(list(per_video.values()))
        detail[task] = {"per_video": per_video, "problems": problems}
    for task, t in event["tasks"].items():
        if t.get("derived_from"):
            x, y = t["derived_from"]
            merged[task] = derive_stopbrake_handsignals(merged.get(x) or None, merged.get(y) or None)
            detail[task] = {"per_video": {}, "problems": [] if merged[task] is not None else ["inputs missing"]}
    return merged, detail


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f} %" if d else "n/a"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", default=os.path.join(ROOT, "out", "testset", "plan.json"))
    ap.add_argument("--runs-root", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--baseline-root", default=None, help="second run set for the paired comparison")
    ap.add_argument("--baseline-label", default="baseline")
    ap.add_argument("--events", default=None, help="comma-separated event ids (default: all)")
    ap.add_argument("--only-complete-videos", action="store_true", help="skip events with any video not processed at all")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    plan = json.load(io.open(a.plan, encoding="utf-8"))
    module_tasks = plan["module_tasks"]
    wanted = set(a.events.split(",")) if a.events else None
    ours_get = run_loader(a.runs_root)
    base_get = run_loader(a.baseline_root) if a.baseline_root else None

    rows = []
    for e in plan["events"]:
        if wanted and e["event_id"] not in wanted:
            continue
        if a.only_complete_videos and not all(os.path.isdir(os.path.join(a.runs_root, v)) for v in e["videos"]):
            continue
        merged, detail = event_verdicts(e, ours_get, module_tasks)
        bmerged, bdetail = event_verdicts(e, base_get, module_tasks) if base_get else ({}, {})
        for task, t in e["tasks"].items():
            if not t["videos"] and not t.get("derived_from"):
                continue  # the CI did not run it
            exp = t["expected"]
            row = {
                "event_id": e["event_id"], "task": task, "videos": t["videos"], "ours": merged.get(task),
                "new": exp["new"], "previous": exp["previous"], "true": exp["true"],
                "comparable": merged.get(task) is not None, **detail.get(task, {}),
            }
            if base_get:
                row["baseline"] = bmerged.get(task)
                row["baseline_per_video"] = bdetail.get(task, {}).get("per_video", {})
            rows.append(row)

    per_task = collections.defaultdict(collections.Counter)
    for r in rows:
        c = per_task[r["task"]]
        c["expected"] += 1
        has_truth = r["true"] not in ("", None)
        if base_get and r["comparable"] and r.get("baseline") is not None:
            c["paired"] += 1
            c["paired_equal"] += r["ours"] == r["baseline"]
            c["paired_baseline_equal_new"] += r["baseline"] == r["new"]
            c["paired_ours_equal_new"] += r["ours"] == r["new"]
            if has_truth:
                c["paired_with_truth"] += 1
                c["paired_ours_correct"] += r["ours"] == r["true"]
                c["paired_baseline_correct"] += r["baseline"] == r["true"]
                c["paired_new_correct"] += r["new"] == r["true"]
        if not r["comparable"]:
            c["missing"] += 1
            continue
        c["comparable"] += 1
        c["equal_new"] += r["ours"] == r["new"]
        c["equal_previous"] += r["ours"] == r["previous"]
        if has_truth:
            c["with_truth"] += 1
            c["ours_correct"] += r["ours"] == r["true"]
            c["new_correct"] += r["new"] == r["true"]
    tot = collections.Counter()
    for c in per_task.values():
        tot.update(c)

    print(f"[{a.label}] comparable {tot['comparable']} of {tot['expected']} task verdicts; equal to New output "
          f"{tot['equal_new']} ({pct(tot['equal_new'], tot['comparable'])}); accuracy vs truth: {a.label} "
          f"{pct(tot['ours_correct'], tot['with_truth'])} vs New output {pct(tot['new_correct'], tot['with_truth'])} "
          f"on {tot['with_truth']} verdicts with truth")
    if base_get:
        print(f"[{a.label} vs {a.baseline_label}] paired {tot['paired']} task verdicts; identical {tot['paired_equal']} "
              f"({pct(tot['paired_equal'], tot['paired'])}); equal to New output: {a.label} "
              f"{pct(tot['paired_ours_equal_new'], tot['paired'])}, {a.baseline_label} "
              f"{pct(tot['paired_baseline_equal_new'], tot['paired'])}; accuracy vs truth on {tot['paired_with_truth']}: "
              f"{a.label} {pct(tot['paired_ours_correct'], tot['paired_with_truth'])}, {a.baseline_label} "
              f"{pct(tot['paired_baseline_correct'], tot['paired_with_truth'])}, New output "
              f"{pct(tot['paired_new_correct'], tot['paired_with_truth'])}")
    head = f"{'task':62s} comp  =new  =prev  acc     newacc  miss"
    print(head + ("  pair  =base" if base_get else ""))
    for task, c in sorted(per_task.items()):
        line = (f"{task[:62]:62s} {c['comparable']:4d} {c['equal_new']:5d} {c['equal_previous']:5d}  "
                f"{pct(c['ours_correct'], c['with_truth']):7s} {pct(c['new_correct'], c['with_truth']):7s} {c['missing']:4d}")
        if base_get:
            line += f"  {c['paired']:4d} {c['paired_equal']:5d}"
        print(line)
    mism = [r for r in rows if r["comparable"] and r["ours"] != r["new"]]
    print(f"mismatches vs New output: {len(mism)}")
    for r in mism[:40]:
        print(f"  {r['event_id']} {r['task']}: {a.label}={r['ours']} new={r['new']} true={r['true']} per_video={r['per_video']}")
    if base_get:
        pm = [r for r in rows if r["comparable"] and r.get("baseline") is not None and r["ours"] != r["baseline"]]
        print(f"mismatches vs {a.baseline_label}: {len(pm)}")
        for r in pm[:60]:
            print(f"  {r['event_id']} {r['task']}: {a.label}={r['ours']} {a.baseline_label}={r['baseline']} new={r['new']} "
                  f"true={r['true']} per_video={r['per_video']} vs {r['baseline_per_video']}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with io.open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"label": a.label, "baseline_label": a.baseline_label if base_get else None, "totals": dict(tot),
                       "per_task": {k: dict(v) for k, v in per_task.items()}, "rows": rows}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
