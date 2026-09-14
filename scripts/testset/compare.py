"""Compare module verdicts of one inference set with the monthly CI report.

Reads `<runs-root>/<video>/<module>.json` (written by `scripts/run_module.py`) for every run of the plan, builds per-event
task verdicts exactly as the report does (two-camera merge Fail > Pass > Not observed; the derived stop-brake + hand-signals
task), and compares them with the report's "New output" (the reference), "Previous test output" and "True output (val)".

A task counts as comparable only when every module run it needs exists without an error; missing or failed runs are listed
separately, never counted as agreement.

    python scripts/testset/compare.py --runs-root out/testset/modules/prod --label prod --out out/testset/compare_prod.json
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", default=os.path.join(ROOT, "out", "testset", "plan.json"))
    ap.add_argument("--runs-root", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--events", default=None, help="comma-separated event ids (default: all)")
    ap.add_argument("--only-complete-videos", action="store_true", help="skip events with any video not processed at all")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    plan = json.load(io.open(a.plan, encoding="utf-8"))
    module_tasks = plan["module_tasks"]
    wanted = set(a.events.split(",")) if a.events else None

    run_cache = {}

    def run_result(module, video):
        key = (module, video)
        if key not in run_cache:
            p = os.path.join(a.runs_root, video, f"{module}.json")
            run_cache[key] = json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else None
        return run_cache[key]

    rows = []
    for e in plan["events"]:
        if wanted and e["event_id"] not in wanted:
            continue
        if a.only_complete_videos and not all(os.path.isdir(os.path.join(a.runs_root, v)) for v in e["videos"]):
            continue
        merged = {}
        detail = {}
        for task, t in e["tasks"].items():
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
                    problems.append(f"{v}: {r.get('error', 'no status')[:160]}")
                    continue
                per_video[v] = st[task]
            if not t["videos"]:
                merged[task] = ""
            elif problems:
                merged[task] = None
            else:
                merged[task] = merge_cameras(list(per_video.values()))
            detail[task] = {"per_video": per_video, "problems": problems}
        for task, (x, y) in [(k, v["derived_from"]) for k, v in e["tasks"].items() if v.get("derived_from")]:
            merged[task] = derive_stopbrake_handsignals(merged.get(x) or None, merged.get(y) or None)
            detail[task] = {"per_video": {}, "problems": [] if merged[task] is not None else ["inputs missing"]}
        for task, t in e["tasks"].items():
            ours = merged.get(task)
            exp = t["expected"]
            rows.append({
                "event_id": e["event_id"], "task": task, "videos": t["videos"], "ours": ours,
                "new": exp["new"], "previous": exp["previous"], "true": exp["true"],
                "comparable": ours is not None, **detail.get(task, {}),
            })

    per_task = collections.defaultdict(collections.Counter)
    for r in rows:
        c = per_task[r["task"]]
        c["expected"] += 1
        if not r["comparable"]:
            c["missing"] += 1
            continue
        c["comparable"] += 1
        c["equal_new"] += r["ours"] == r["new"]
        c["equal_previous"] += r["ours"] == r["previous"]
        if r["true"] not in ("", None):
            c["with_truth"] += 1
            c["ours_correct"] += r["ours"] == r["true"]
            c["new_correct"] += r["new"] == r["true"]
    tot = collections.Counter()
    for c in per_task.values():
        tot.update(c)

    print(f"[{a.label}] comparable {tot['comparable']} of {tot['expected']} task verdicts; equal to New output "
          f"{tot['equal_new']} ({100*tot['equal_new']/max(tot['comparable'],1):.1f} %); accuracy vs truth: ours "
          f"{100*tot['ours_correct']/max(tot['with_truth'],1):.1f} % vs New output {100*tot['new_correct']/max(tot['with_truth'],1):.1f} % "
          f"on {tot['with_truth']} verdicts with truth")
    print(f"{'task':70s} comp  =new  =prev  ours_acc  new_acc  missing")
    for task, c in per_task.items():
        wt = max(c["with_truth"], 1)
        print(f"{task[:70]:70s} {c['comparable']:4d} {c['equal_new']:5d} {c['equal_previous']:5d} "
              f"{100*c['ours_correct']/wt:8.1f} {100*c['new_correct']/wt:8.1f} {c['missing']:8d}")
    mism = [r for r in rows if r["comparable"] and r["ours"] != r["new"]]
    print(f"mismatches vs New output: {len(mism)}")
    for r in mism[:40]:
        print(f"  {r['event_id']} {r['task']}: ours={r['ours']} new={r['new']} true={r['true']} per_video={r['per_video']}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with io.open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"label": a.label, "totals": dict(tot), "per_task": {k: dict(v) for k, v in per_task.items()},
                       "rows": rows}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
