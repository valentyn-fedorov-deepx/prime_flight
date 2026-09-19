"""Does accuracy change when the modules run live? Task verdicts with the LIVE verdicts put in place of the batch ones.

Every joint live run (`scripts/rt_joint_run.py`) leaves, per video, the live status of each module next to its batch status.
This builds a run set `out/testset/modules/live` = the batch set on the real-time inputs (`v2`) with the live status
substituted wherever a live run exists, and compares it with `v2` and with the labels exactly as the monthly comparison does
(two-camera merge, derived tasks): `scripts/testset/compare.py`.

    python scripts/rt_live_accuracy.py [--name all_ready]        # the runs of `rt_joint_run.py --name ...` to take
    python scripts/rt_live_accuracy.py --name largest_alive      # the same events run with the candidate main-aircraft rule
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FPS = 8.0


def batch_anchors(video: str) -> dict:
    from scripts.testset import orchestrate as o

    path, found = o.paths(video)["trk_compat"], {}
    if not os.path.exists(path):
        return found
    with io.open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if n % 40:
                continue
            for rec in next(iter(json.loads(line).values()), []):
                state = rec.get("state_dict") or {}
                for key in ("arrival_frame", "departure_frame"):
                    if rec.get("cls_str") == "airplane" and key not in found and isinstance(state.get(key), int):
                        found[key] = state[key]
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="all_ready", help="the --name of the joint runs to take")
    a = ap.parse_args()
    v2_root = os.path.join(ROOT, "out", "testset", "modules", "v2")
    live_root = os.path.join(ROOT, "out", "testset", "modules", f"live_{a.name}")
    live: dict = {}
    runs, failed, no_verdict = [], [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "out", "rt", "cost", "*", f"joint_{a.name}_x*.json"))):
        j = json.load(io.open(path, encoding="utf-8"))
        if j.get("error") or not j.get("verdicts"):
            continue
        if j.get("exit_code") or j.get("runtime_error"):  # a run that died (out of memory) says nothing about verdicts
            failed.append({"video": j["video"], "speed": j.get("speed"), "error": j.get("runtime_error") or f"exit {j.get('exit_code')}"})
            continue
        anchors = {k: (v or {}).get("value") for k, v in (j.get("tracker_anchors") or {}).items()}
        runs.append({"video": j["video"], "speed": j.get("speed"), "modules": len(j["verdicts"]), "live_anchors": anchors or None})
        for v in j["verdicts"]:
            if v.get("live_status") is None:  # the module gave no verdict in this run: nothing to substitute
                no_verdict.append({"video": j["video"], "module": v["module"]})
                continue
            key = (j["video"], v["module"])
            if key in live and live[key] != v.get("live_status"):
                print("two live runs disagree:", key, live[key], v.get("live_status"))
            live[key] = v.get("live_status")

    if os.path.isdir(live_root):
        shutil.rmtree(live_root)
    changed = []
    for path in glob.glob(os.path.join(v2_root, "*", "*.json")):
        video, module = os.path.basename(os.path.dirname(path)), os.path.basename(path)[:-5]
        run = json.load(io.open(path, encoding="utf-8"))
        if (video, module) in live and "error" not in run:
            if run.get("status") != live[(video, module)]:
                changed.append({"video": video, "module": module, "batch": run.get("status"), "live": live[(video, module)]})
            run = {**run, "status": live[(video, module)], "source": "live"}
        target = os.path.join(live_root, video, f"{module}.json")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        json.dump(run, io.open(target, "w", encoding="utf-8"))

    out_path = os.path.join(ROOT, "out", "testset", f"compare_live_{a.name}_vs_v2.json")
    subprocess.run([sys.executable, os.path.join("scripts", "testset", "compare.py"), "--runs-root", live_root, "--label", "live",
                    "--baseline-root", v2_root, "--baseline-label", "v2", "--out", out_path],
                   cwd=ROOT, stdout=subprocess.DEVNULL, check=True)
    totals = json.load(io.open(out_path, encoding="utf-8"))["totals"]

    videos = sorted({v for v, _ in live})
    anchors = []
    for r in runs:
        if r["live_anchors"]:
            b = batch_anchors(r["video"])
            anchors.append({"video": r["video"], "batch": b, "live": r["live_anchors"],
                            "t_arr_shift_s": round((r["live_anchors"]["arrival_frame"] - b["arrival_frame"]) / FPS, 1)
                            if isinstance(r["live_anchors"].get("arrival_frame"), int) and isinstance(b.get("arrival_frame"), int) else None,
                            "t_dep_shift_s": round((r["live_anchors"]["departure_frame"] - b["departure_frame"]) / FPS, 1)
                            if isinstance(r["live_anchors"].get("departure_frame"), int) and isinstance(b.get("departure_frame"), int) else None})
    result = {
        "videos_run_live": len(videos), "module_runs_live": len(live),
        "runs_that_died": failed, "modules_without_a_live_verdict": no_verdict,
        "module_verdicts_changed": changed,
        "task_verdicts": {"paired": totals["paired"], "identical": totals["paired_equal"],
                          "accuracy_live": round(100 * totals["paired_ours_correct"] / totals["paired_with_truth"], 2),
                          "accuracy_batch": round(100 * totals["paired_baseline_correct"] / totals["paired_with_truth"], 2),
                          "accuracy_monthly_ci_output": round(100 * totals["paired_new_correct"] / totals["paired_with_truth"], 2)},
        "anchors": anchors,
    }
    doc_path = os.path.join(ROOT, "docs", "analysis", "rt_live_accuracy.json")
    doc = json.load(io.open(doc_path, encoding="utf-8")) if os.path.exists(doc_path) else {}
    if "task_verdicts" in doc:  # the first layout of this file: one result, no names
        doc = {}
    doc[a.name] = result
    json.dump(doc, io.open(doc_path, "w", encoding="utf-8", newline="\n"), indent=1)
    print(json.dumps({k: v for k, v in result.items() if k != "anchors"}, indent=1))
    for item in anchors:
        print(item["video"], "T_arr shift", item["t_arr_shift_s"], "s | T_dep shift", item["t_dep_shift_s"], "s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
