"""How late the real-time branch hands the arriving aircraft to the tracker, over the test set (no GPU: replays first-run rows).

The batch second-run file carries the box of the main aircraft = the longest aircraft track of the WHOLE video. The causal
rows (`pf/pipeline/causal_rows.py`) have to choose at frame t. With `longest_so_far` an aircraft that taxied past earlier
keeps the title until the arriving aircraft has more frames than it, and until then the tracker and the modules do not get
the arriving aircraft at all. Found live on MwCSLbQ7QvXQ (223 frames = 28 s; lead-marshaller reported the start of the
arrival 27 s late, verdict unchanged). This replays the first-run rows of the batch GM v2 runs of every test-set video through
the aircraft tracker and scores the causal rules against the batch choice:

  * `longest_so_far`   the rule the branch runs by default;
  * `hold_let_go`      keep the held track while it has boxes, let it go after `--alive-frames` without one;
  * `largest_alive`    the largest box among the tracks seen within `--alive-frames`, replaced only by a box
                       `--switch-factor` times larger (`CausalSecondRun(main_rule="largest_alive")`);
  * `largest_alive_gated`  the same, but a track counts only once its box has been `--gate-height` px tall (does a size
                       gate tell the aircraft at this stand from neighbours and traffic? it does not).

    python scripts/rt_main_aircraft_delay.py [--videos a.mp4,b.mp4] [--alive-frames 16] [--switch-factor 1.5] [--redo]
    python scripts/rt_main_aircraft_delay.py --live-check <run tag>,<run tag>     # anchors of runs made with the rows written
"""

from __future__ import annotations

import argparse
import bisect
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pf.gm.plane_tracker import NorfairPlaneTracker  # noqa: E402
from pf.gm.rows import ClassMap  # noqa: E402
from scripts.gm_v2_run import load_str2id  # noqa: E402
from scripts.testset import orchestrate as o  # noqa: E402

FPS = 8.0
RULES = ("longest_so_far", "hold_let_go", "largest_alive", "largest_alive_gated")


def arrival_frame(trk_path: str):
    """T_arr from the batch tracker file (sparse scan: the anchor stays in the airplane record once set)."""
    if not os.path.exists(trk_path):
        return None
    with io.open(trk_path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if n % 80:
                continue
            for rec in next(iter(json.loads(line).values()), []):
                value = (rec.get("state_dict") or {}).get("arrival_frame")
                if rec.get("cls_str") == "airplane" and isinstance(value, int):
                    return value
    return None


def aircraft_tracks(first_run_path: str, cm: ClassMap, heavy: bool) -> tuple:
    """(frames, {track: {frame: xyxy}}, the track batch calls the main aircraft). Aliased norfair ids count once."""
    trk = NorfairPlaneTracker(drop_tiny=False, stabilize_when_heavy=True)
    n = 0
    with io.open(first_run_path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            trk.update(n, next(iter(json.loads(line).values()), []), cm, heavy=heavy)
    tracks, seen = {}, {}
    for tid, hist in trk.planes.items():
        if id(hist) not in seen:
            seen[id(hist)] = tid
            tracks[tid] = hist.frames
    final = trk.longest()
    return n, tracks, (seen[id(trk.planes[final])] if final is not None else None)


def area(box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def choose(frames: int, tracks: dict, rule: str, alive_frames: int, switch_factor: float, gate_height: int = 0) -> dict:
    """The track each rule holds at every frame, using only what was known at that frame."""
    keys = {tid: sorted(fr) for tid, fr in tracks.items()}
    gate = gate_height if rule == "largest_alive_gated" else 0
    reached = {tid: next((f for f in keys[tid] if fr[f][3] - fr[f][1] >= gate), None) for tid, fr in tracks.items()}
    out, held, held_last = {}, None, 0
    for t in range(1, frames + 1):
        length = {tid: bisect.bisect_right(k, t) for tid, k in keys.items()}
        seen = {tid: n for tid, n in length.items() if n}
        if not seen:
            out[t] = None
            continue
        last = {tid: keys[tid][seen[tid] - 1] for tid in seen}
        if rule == "longest_so_far":
            out[t] = max(seen, key=lambda k: seen[k])
        elif rule == "hold_let_go":
            now = [tid for tid in seen if last[tid] == t]
            if held is not None and held in now:
                held_last = t
            elif now and (held is None or t - held_last > alive_frames):
                held, held_last = max(now, key=lambda k: seen[k]), t
            out[t] = held
        else:  # largest_alive, with or without the size gate
            alive = [tid for tid in seen if t - last[tid] <= alive_frames and reached[tid] is not None and reached[tid] <= t]
            if alive:
                big = max(alive, key=lambda k: area(tracks[k][last[k]]))
                if held not in alive or (big != held and area(tracks[big][last[big]]) > switch_factor * area(tracks[held][last[held]])):
                    held = big
                out[t] = held
            else:
                out[t] = None
    return out


def longest_run(frames: list) -> int:
    best = cur = 0
    prev = None
    for f in frames:
        cur = cur + 1 if prev is not None and f == prev + 1 else 1
        best, prev = max(best, cur), f
    return best


def score(tracks: dict, final, choice: dict, arrival) -> dict:
    frames_of_final = sorted(tracks[final])
    first = frames_of_final[0]
    # another aircraft in the rows before the main one appears: 4 s of it standing still is enough for the tracker to call
    # an arrival, and the anchors of the event are then spent before the real aircraft comes
    other_before = [n for n in range(1, first) if choice.get(n) is not None and n in tracks[choice[n]]]
    handed = next((n for n in frames_of_final if choice.get(n) == final), None)
    rec = {"handed_over_at": handed, "delay_frames": (handed - first) if handed is not None else None,
           "withheld_frames": sum(1 for n in frames_of_final if choice.get(n) != final),
           "frames_with_another_aircraft_handed": sum(1 for n, t in choice.items() if t is not None and t != final and n in tracks[t]),
           "longest_run_of_another_aircraft_before_the_main_one": longest_run(other_before)}
    if arrival:
        # the 30 s before T_arr and the 4 s stop rule after it: does the tracker get the aircraft batch gave it?
        window = [n for n in frames_of_final if arrival - 240 <= n <= arrival + 32]
        rec["arrival_window_frames_in_batch"] = len(window)
        rec["arrival_window_same_box"] = sum(1 for n in window if choice.get(n) == final)
        if handed is not None:
            rec["handed_over_before_arrival_s"] = round((arrival - handed) / FPS, 1)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", default="", help="comma list; default: every video of the plan with a batch GM v2 run")
    ap.add_argument("--alive-frames", type=int, default=16)
    ap.add_argument("--switch-factor", type=float, default=1.5)
    ap.add_argument("--gate-height", type=int, default=300)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--live-check", default="", help="comma list of run tags under out/rt/runs made WITH the rows written: "
                                                     "record their live and batch anchors next to the replay")
    a = ap.parse_args()
    cm = ClassMap(load_str2id(os.path.join(ROOT, "external", "cv_common", "global_config.yaml")))
    plan = o.Plan()
    videos = [v for v in a.videos.split(",") if v] or sorted({v for e in plan.events for v in e["videos"]})
    out_path = os.path.join(ROOT, "docs", "analysis", "rt_main_aircraft_delay.json")
    result = json.load(io.open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {"videos": {}}
    result["rule_parameters"] = {"alive_frames": a.alive_frames, "switch_factor": a.switch_factor, "gate_height": a.gate_height}
    for i, video in enumerate(videos, 1):
        p = o.paths(video)
        first_run = os.path.join(p["gm_dir"], f"general_model{video}.ndjson")
        if not os.path.exists(first_run) or (not a.redo and all(r in result["videos"].get(video, {}) for r in RULES)):
            continue
        report = json.load(io.open(p["gm_report"], encoding="utf-8")) if os.path.exists(p["gm_report"]) else {}
        heavy = ((report.get("noise") or {}).get("video_type_by_noise") or "CLEAR") != "CLEAR"
        t0 = time.time()
        frames, tracks, final = aircraft_tracks(first_run, cm, heavy)
        rec = {"frames": frames, "aircraft_tracks": len(tracks), "heavy_noise_mode": heavy,
               "arrival_frame": arrival_frame(p["trk_compat"])}
        if final is not None:
            rec["main_aircraft_first_frame"] = min(tracks[final])
            rec["main_aircraft_frames"] = len(tracks[final])
            for rule in RULES:
                rec[rule] = score(tracks, final, choose(frames, tracks, rule, a.alive_frames, a.switch_factor, a.gate_height),
                                  rec["arrival_frame"])
        result["videos"][video] = rec
        print(f"[{i}/{len(videos)}] {video} {time.time() - t0:.0f} s  delay "
              + "  ".join(f"{rule} {(rec.get(rule) or {}).get('delay_frames')}" for rule in RULES), flush=True)
        json.dump(result, io.open(out_path, "w", encoding="utf-8", newline="\n"), indent=1)

    for tag in [t for t in a.live_check.split(",") if t]:
        summary = json.load(io.open(os.path.join(ROOT, "out", "rt", "runs", tag, "summary.json"), encoding="utf-8"))
        parity = summary.get("tracker_vs_batch_v2") or {}
        anchors = {side: {k: v.get("value") for k, v in (parity.get("anchors") or {}).get(side, {}).items()} for side in ("batch", "live")}
        verdicts = [{"module": summary.get("module"), **(summary.get("batch_v2") or {})}]
        verdicts += [{"module": v["module"], **(v.get("batch_v2") or {})} for v in summary.get("extra_module_verdicts") or []]
        result.setdefault("live_checks", {})[summary["video"]] = {
            "tag": tag, "anchors": anchors, "airplane_frames_with_records": parity.get("frames_with_records"),
            "airplane_frames_same_boxes": parity.get("same_boxes"),
            "modules": len(verdicts), "verdicts_identical": sum(1 for v in verdicts if v.get("status_identical")),
            "reports_identical": sum(1 for v in verdicts if v.get("report_identical"))}

    recs = [r for r in result["videos"].values() if r.get("main_aircraft_first_frame")]
    result["summary"] = {}
    for rule in RULES:
        scored = [r[rule] for r in recs if r.get(rule)]
        delays = sorted((s["delay_frames"] or 0) for s in scored)
        windows = [s for s in scored if s.get("arrival_window_frames_in_batch")]
        result["summary"][rule] = {
            "videos": len(scored), "videos_with_an_arrival": len(windows),
            "arrival_window_fully_the_same": sum(1 for s in windows if s["arrival_window_same_box"] == s["arrival_window_frames_in_batch"]),
            "arrival_window_less_than_half_the_same": sum(
                1 for s in windows if s["arrival_window_same_box"] < 0.5 * s["arrival_window_frames_in_batch"]),
            "handed_over_only_after_the_arrival": sum(1 for s in scored if (s.get("handed_over_before_arrival_s") or 0) < 0),
            "another_aircraft_for_4_s_before_the_main_one": sum(
                1 for s in scored if s.get("longest_run_of_another_aircraft_before_the_main_one", 0) >= 32),
            "handed_over_more_than_2_s_late": sum(1 for d in delays if d > 16),
            "median_delay_s": round(delays[len(delays) // 2] / FPS, 1) if delays else None,
            "p90_delay_s": round(delays[min(len(delays) - 1, round(0.9 * (len(delays) - 1)))] / FPS, 1) if delays else None,
            "max_delay_s": round(max(delays) / FPS, 1) if delays else None,
            "share_of_batch_rows_kept": round(1 - sum(s["withheld_frames"] for s in scored)
                                              / max(sum(r["main_aircraft_frames"] for r in recs), 1), 4),
            "frames_with_another_aircraft_handed": sum(s["frames_with_another_aircraft_handed"] for s in scored)}
    json.dump(result, io.open(out_path, "w", encoding="utf-8", newline="\n"), indent=1)
    print(json.dumps(result["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
