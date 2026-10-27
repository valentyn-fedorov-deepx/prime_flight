"""Replay the wing walkers' hand-signal rule (M27) on the poses recorded by `scripts/ww_pose_record.py`, for any pose
variant and threshold set, and score it against the monthly test set's truth.

The rule is the module's own (`main.py` `performs_hand_signals`, `check_wing_walkers`, obstruction_hand_signals @ 3460afc):
a frame signals when a wrist is less than margin x box height below its elbow and both points score at least
`conf_thr`; a wing walker signals with min(`min_frames`, 0.2 x his frames) such frames; a side passes when one of its
walkers signals. Side statuses (walker present / blocked / absent) come from the run and do not depend on the pose.
Events are merged over cameras as the report does (Fail > Pass > Not observed); videos without a recording (no walker on
any side, or no departure) keep the verdict of the recorded runs, which no pose model changes.

    python scripts/ww_pose_replay.py                 # check: hrnet and rtm with the module's thresholds = the runs
    python scripts/ww_pose_replay.py --sweep         # thresholds per variant, against the truth and against HRNet
"""

from __future__ import annotations

import argparse
import glob
import io
import itertools
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.testset.common import merge_cameras  # noqa: E402

TASK = MODULE = "wing-walkers-in-proper-position-and-using-approved-wands"
DUMPS = os.path.join(ROOT, "out", "pose", "ww")
RUNS = os.path.join(ROOT, "out", "testset", "modules")
COMPARE = os.path.join(ROOT, "out", "testset", "compare_pose_rtm_vs_pose_ctl_interim.json")
MARGINS = {  # local_config.yaml handsignals: plane type -> walker side -> (left wrist, right wrist)
    "aircraft": {"left_side": (0.08, 0.08), "right_side": (0.048, 0.048)},
    "jet": {"left_side": (0.08, 0.08), "right_side": (0.07, 0.07)},
}
DEFAULT = {"conf_thr": 0.2, "margin_scale": 1.0, "min_frames": 8}
VOCAB = {"Pass": "pass", "Fail": "fail", "Not observed": "notObserved"}


def jload(path: str):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def signals(row: list, conf_thr: float, m_l: float, m_r: float) -> bool:
    _, wl, el, wr, er, box = row
    h = box[3] - box[1]
    left = wl[1] < el[1] + h * m_l and min(wl[2], el[2]) >= conf_thr
    right = wr[1] < er[1] + h * m_r and min(wr[2], er[2]) >= conf_thr
    return left or right


def decide(dump: dict, variant: str, conf_thr: float, margin_scale: float, min_frames: int) -> str | None:
    """The module's verdict with this variant's poses; None when the run never reached the walker decision."""
    cap = dump["captured"]
    if "side_wing_walker" not in cap:
        return None
    plane = cap.get("airplane_type") or "aircraft"
    plane = plane.lower() if plane.lower() in MARGINS else "aircraft"
    start, stop = cap["start_moving"], cap["stop_frame"]
    rows = dump["rows"][variant]
    side_status, hands = {}, {}
    for side in ("left_side", "right_side"):
        if cap["side_wing_walker"][side]:
            side_status[side] = "Pass"
        else:
            side_status[side] = "Not observed" if cap["blocked_share"][side] >= 0.6 else "Fail"
        m_l, m_r = (m * margin_scale for m in MARGINS[plane][side])
        hands[side] = False
        for walker in cap["wing_walkers"][side]:
            kept = [r for r in rows.get(str(walker), []) if start <= r[0] <= stop]
            n = sum(signals(r, conf_thr, m_l, m_r) for r in kept)
            if n >= min(min_frames, 0.2 * cap["frames_observed"][str(walker)]):
                hands[side] = True
                break
    left, right = side_status["left_side"], side_status["right_side"]
    if left == "Pass" and right == "Pass":
        return "Pass" if hands["left_side"] and hands["right_side"] else "Fail"
    if left == right == "Not observed":
        return "Not observed"
    if left == right == "Fail":
        return "Fail"
    if left == "Fail" or right == "Fail" or (left == "Pass" and not hands["left_side"]) or (
            right == "Pass" and not hands["right_side"]):
        return "Fail"
    return "Not observed"


def run_status(label: str, video: str) -> str | None:
    p = os.path.join(RUNS, label, video, f"{MODULE}.json")
    return jload(p).get("status") if os.path.exists(p) else None


def events() -> list:
    rows = jload(COMPARE)["rows"]
    return [r for r in rows if r["task"] == TASK and r.get("true") and r.get("baseline") and r.get("ours")]


def score(dumps: dict, evs: list, variant: str, params: dict) -> dict:
    per_video = {v: decide(d, variant, **params) for v, d in dumps.items()}
    out = {"correct": 0, "events": 0, "fail_passed": 0, "same_as_hrnet": 0, "changed": []}
    for e in evs:
        vs = []
        for v in e["videos"]:
            s = per_video.get(v)
            vs.append(VOCAB.get(s or run_status("pose_ctl", v)))
        ours = merge_cameras(vs)
        hr = merge_cameras([VOCAB.get(decide(dumps[v], "hrnet", **DEFAULT) if v in dumps and per_video.get(v)
                                      else run_status("pose_ctl", v)) for v in e["videos"]])
        out["events"] += 1
        out["correct"] += ours == e["true"]
        out["fail_passed"] += e["true"] == "fail" and ours == "pass"
        out["same_as_hrnet"] += ours == hr
        if ours != hr:
            out["changed"].append({"videos": e["videos"], "true": e["true"], "hrnet": hr, "ours": ours})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "pose", "ww_replay.json"))
    a = ap.parse_args()

    dumps = {os.path.basename(p)[:-5]: jload(p) for p in sorted(glob.glob(os.path.join(DUMPS, "*.json")))}
    report = {"recordings": len(dumps), "check": [], "sweep": {}}
    # 1. the replay must give the recorded runs' verdicts
    for v, d in dumps.items():
        hr, rtm = decide(d, "hrnet", **DEFAULT), decide(d, "rtm", **DEFAULT)
        row = {"video": v, "run": d["captured"].get("decision", {}).get("status"), "replay_hrnet": hr,
               "pose_ctl": run_status("pose_ctl", v), "replay_rtm": rtm, "pose_rtm": run_status("pose_rtm", v)}
        row["ok"] = (hr is None or hr == row["run"] == row["pose_ctl"]) and (rtm is None or rtm == row["pose_rtm"])
        report["check"].append(row)
        print(("ok  " if row["ok"] else "DIFF") + f" {v}: run {row['run']}, hrnet {hr} (pose_ctl {row['pose_ctl']}), "
              f"rtm {rtm} (pose_rtm {row['pose_rtm']})")
    evs = events()
    variants = sorted({k for d in dumps.values() for k in d["rows"]})
    for variant in variants:
        s = score(dumps, evs, variant, DEFAULT)
        print(f"{variant:9s} module thresholds: correct {s['correct']}/{s['events']}, same as HRNet {s['same_as_hrnet']}, "
              f"fail labels passed {s['fail_passed']}")
    if a.sweep:
        grid = {"conf_thr": [0.0, 0.05, 0.1, 0.15, 0.2, 0.25], "margin_scale": [0.5, 1.0, 1.5, 2.0, 3.0],
                "min_frames": [2, 4, 6, 8, 12]}
        for variant in variants:
            rows = []
            for c, m, f in itertools.product(*grid.values()):
                params = {"conf_thr": c, "margin_scale": m, "min_frames": f}
                s = score(dumps, evs, variant, params)
                rows.append({**params, **{k: s[k] for k in ("correct", "same_as_hrnet", "fail_passed")}})
            rows.sort(key=lambda r: (-r["same_as_hrnet"], -r["correct"], r["fail_passed"]))
            report["sweep"][variant] = rows
            print(f"\n{variant}: best by agreement with HRNet")
            for r in rows[:8]:
                print("  ", r)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
