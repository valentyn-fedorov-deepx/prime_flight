"""Build the test-set run plan from the monthly CI report: per event the aircraft type and each video's camera, per task
the module and videos to run, and the de-duplicated list of module runs (module, video, cone_camera, airplane_type).

Routing is taken from the report itself (the "Task videos" column is what the CI ran). What the report does not state is
inferred and recorded with its evidence:
  * camera of a video — 'cone' if a cone-only check (Cone for both aircraft types, or Cone / -) ran on it; in a two-video
    event the other video is then 'wing'; a video with no evidence defaults to 'cone' (flagged);
  * aircraft type of an event — 'JET' if a check the client does not run for jets (Jet column '-') has no video while other
    checks ran, or if a check that jets run on the wing camera only (Both / Wing) ran on one of two videos; 'AIRCRAFT' if
    such a Both / Wing check ran on both videos; otherwise unknown (None — cones-placed treats None as AIRCRAFT).

    python scripts/testset/plan.py --out out/testset/plan.json
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
    DERIVED,
    ROOT,
    TASK_CHECK,
    load_report,
    load_task_modules,
    parse_camera_split,
)


def infer_event(event: dict, split: dict) -> dict:
    videos = event["videos"]
    cone_evidence = collections.Counter()
    wing_evidence = collections.Counter()
    jet_votes, aircraft_votes = [], []
    for task, t in event["tasks"].items():
        check = TASK_CHECK.get(task)
        if not check or check not in split:
            continue
        air, jet = split[check]
        tv = t["videos"]
        if air == "Cone" and jet in ("Cone", "-"):
            for v in tv:
                cone_evidence[v] += 1
        if jet == "-" and not tv and any(x["videos"] for x in event["tasks"].values()):
            jet_votes.append(f"{task}: no video (jets skip it)")
        if air == "Both" and jet == "Wing" and len(videos) == 2:
            if len(tv) == 1:
                jet_votes.append(f"{task}: one of two videos (jets: wing only)")
                wing_evidence[tv[0]] += 1
            elif len(tv) == 2:
                aircraft_votes.append(f"{task}: both videos")
    cameras = {}
    for v in videos:
        if cone_evidence[v]:
            cameras[v] = {"camera": "cone", "evidence": f"{cone_evidence[v]} cone-only checks"}
    for v in videos:
        if v in cameras:
            continue
        others_cone = [o for o in videos if o != v and cameras.get(o, {}).get("camera") == "cone"]
        if others_cone:
            cameras[v] = {"camera": "wing", "evidence": "the other video of the event is the cone video"}
        elif wing_evidence[v]:
            cameras[v] = {"camera": "wing", "evidence": f"{wing_evidence[v]} wing-only jet checks"}
        else:
            cameras[v] = {"camera": "cone", "evidence": "no evidence; default", "uncertain": True}
    if jet_votes and not aircraft_votes:
        airplane_type = "JET"
    elif aircraft_votes and not jet_votes:
        airplane_type = "AIRCRAFT"
    elif not jet_votes and not aircraft_votes:
        airplane_type = None
    else:
        airplane_type = "JET" if len(jet_votes) > len(aircraft_votes) else "AIRCRAFT"
    return {"cameras": cameras, "airplane_type": airplane_type, "jet_evidence": jet_votes, "aircraft_evidence": aircraft_votes}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "testset", "plan.json"))
    a = ap.parse_args()

    report = load_report(a.report)
    task_module, module_tasks = load_task_modules()
    split = parse_camera_split()
    missing_checks = sorted({t for e in report["events"] for t in e["tasks"] if TASK_CHECK.get(t) and TASK_CHECK[t] not in split})
    unmapped = sorted({t for e in report["events"] for t in e["tasks"] if t not in task_module and t not in DERIVED})

    events, runs = [], {}
    for e in report["events"]:
        info = infer_event(e, split)
        tasks = {}
        for task, t in e["tasks"].items():
            module = task_module.get(task)
            tasks[task] = {
                "module": module,
                "derived_from": DERIVED.get(task),
                "videos": t["videos"],
                "expected": {"previous": t["previous"], "new": t["new"], "true": t["true"]},
            }
            if module is None:
                continue
            for v in t["videos"]:
                key = (module, v)
                cam = info["cameras"].get(v, {"camera": "cone", "uncertain": True})
                run = runs.setdefault(key, {
                    "module": module, "video": v, "cone_camera": cam["camera"] == "cone",
                    "camera_uncertain": bool(cam.get("uncertain")), "airplane_type": info["airplane_type"],
                    "events": [], "tasks": set(),
                })
                if e["event_id"] not in run["events"]:
                    run["events"].append(e["event_id"])
                run["tasks"].add(task)
        events.append({"event_id": e["event_id"], "videos": e["videos"], **info, "tasks": tasks, "accuracy": e["accuracy"]})

    run_list = []
    for (module, v), r in sorted(runs.items()):
        r["tasks"] = sorted(r["tasks"])
        run_list.append(r)
    plan = {"events": events, "runs": run_list, "module_tasks": module_tasks,
            "unmapped_tasks": unmapped, "checks_missing_in_split": missing_checks}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1)

    by_module = collections.Counter(r["module"] for r in run_list)
    print(f"events {len(events)}, videos {len({v for e in events for v in e['videos']})}, module runs {len(run_list)}")
    print("unmapped tasks:", unmapped, "| checks missing in the split table:", missing_checks)
    print("aircraft types:", dict(collections.Counter(e["airplane_type"] for e in events)))
    cams = collections.Counter((c["camera"], bool(c.get("uncertain"))) for e in events for c in e["cameras"].values())
    print("video cameras (camera, uncertain):", dict(cams))
    print("runs per module:")
    for m, n in sorted(by_module.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d}  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
