"""How late the real-time branch hands the arriving aircraft to the tracker, over the test set (no GPU: replays first-run rows).

The batch second-run file carries the box of the main aircraft = the longest aircraft track of the WHOLE video. The causal
rows (`pf/pipeline/causal_rows.py`) carry the box of the track that is longest AT FRAME t. An aircraft that taxied past
earlier keeps that title until the arriving aircraft has more frames than it, and until then the tracker and the modules do
not get the arriving aircraft at all. Found live on MwCSLbQ7QvXQ (223 frames = 28 s; lead-marshaller reported the start of
the arrival 27 s late, verdict unchanged). This measures the same on every video of the test set from the first-run rows of
the batch GM v2 runs, and compares the rule with one that lets go of a track that has had no box for a while.

    python scripts/rt_main_aircraft_delay.py [--videos a.mp4,b.mp4] [--let-go-after 16]
"""

from __future__ import annotations

import argparse
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


def replay(first_run_path: str, cm: ClassMap, heavy: bool, let_go_after: int, arrival=None) -> dict:
    trk = NorfairPlaneTracker(drop_tiny=False, stabilize_when_heavy=True)
    longest_at, alive_at = {}, {}
    held, held_last_box = None, None  # the alternative rule: keep the held track while it has boxes, let go after a gap
    with io.open(first_run_path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            rows = next(iter(json.loads(line).values()), [])
            trk.update(n, rows, cm, heavy=heavy)
            tid = trk.longest()
            longest_at[n] = tid
            with_box = [k for k, p in trk.planes.items() if n in p.frames]
            if held is not None and held in with_box:
                held_last_box = n
            elif with_box and (held is None or n - (held_last_box or 0) > let_go_after):
                held = max(with_box, key=lambda k: len(trk.planes[k].frames))  # the longest among those visible now
                held_last_box = n
            alive_at[n] = held
    final = trk.longest()
    if final is None:
        return {"frames": len(longest_at), "main_aircraft": None}
    frames_of_final = sorted(trk.planes[final].frames)
    first = frames_of_final[0]

    def summary(choice: dict) -> dict:
        withheld = [n for n in frames_of_final if choice.get(n) != final]
        handed = next((n for n in frames_of_final if choice.get(n) == final), None)
        others = sum(1 for n, t in choice.items() if t is not None and t != final and n in trk.planes[t].frames)
        rec = {"handed_over_at": handed, "delay_frames": (handed - first) if handed is not None else None,
               "withheld_frames": len(withheld), "frames_with_another_aircraft_handed": others}
        if arrival:
            # the 30 s before T_arr and the 4 s stop rule after it: does the tracker get the aircraft batch gave it?
            window = [n for n in frames_of_final if arrival - 240 <= n <= arrival + 32]
            rec["arrival_window_frames_in_batch"] = len(window)
            rec["arrival_window_same_box"] = sum(1 for n in window if choice.get(n) == final)
            rec["arrival_window_other_box"] = sum(1 for n in window if choice.get(n) not in (None, final)
                                                  and n in trk.planes[choice[n]].frames)
        return rec

    return {"frames": len(longest_at), "aircraft_tracks": len(trk.planes), "main_aircraft_first_frame": first,
            "main_aircraft_frames": len(frames_of_final), "longest_so_far": summary(longest_at),
            f"let_go_after_{let_go_after}": summary(alive_at)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", default="", help="comma list; default: every video of the plan with a batch GM v2 run")
    ap.add_argument("--let-go-after", type=int, default=16, help="frames without a box before the held track is let go")
    a = ap.parse_args()
    cm = ClassMap(load_str2id(os.path.join(ROOT, "external", "cv_common", "global_config.yaml")))
    plan = o.Plan()
    videos = [v for v in a.videos.split(",") if v] or sorted({v for e in plan.events for v in e["videos"]})
    out_path = os.path.join(ROOT, "docs", "analysis", "rt_main_aircraft_delay.json")
    result = json.load(io.open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {"videos": {}}
    rule = f"let_go_after_{a.let_go_after}"
    for i, video in enumerate(videos, 1):
        p = o.paths(video)
        first_run = os.path.join(p["gm_dir"], f"general_model{video}.ndjson")
        if not os.path.exists(first_run) or (video in result["videos"] and rule in result["videos"][video]):
            continue
        report = json.load(io.open(p["gm_report"], encoding="utf-8")) if os.path.exists(p["gm_report"]) else {}
        heavy = ((report.get("noise") or {}).get("video_type_by_noise") or "CLEAR") != "CLEAR"
        t0 = time.time()
        arrival = arrival_frame(p["trk_compat"])
        rec = replay(first_run, cm, heavy, a.let_go_after, arrival)
        rec["heavy_noise_mode"] = heavy
        rec["arrival_frame"] = arrival
        for key in ("longest_so_far", rule):
            s = rec.get(key) or {}
            if rec.get("arrival_frame") and s.get("handed_over_at"):
                s["handed_over_before_arrival_s"] = round((rec["arrival_frame"] - s["handed_over_at"]) / FPS, 1)
        result["videos"][video] = rec
        print(f"[{i}/{len(videos)}] {video} {time.time() - t0:.0f} s  longest-so-far delay "
              f"{(rec.get('longest_so_far') or {}).get('delay_frames')}  let-go delay {(rec.get(rule) or {}).get('delay_frames')}  "
              f"T_arr {rec.get('arrival_frame')}", flush=True)
        json.dump(result, io.open(out_path, "w", encoding="utf-8", newline="\n"), indent=1)

    recs = [r for r in result["videos"].values() if r.get("main_aircraft_first_frame")]
    for key in ("longest_so_far", rule):
        delays = sorted((r[key]["delay_frames"] or 0) for r in recs if r.get(key))
        late = [d for d in delays if d > 16]
        after_arrival = sum(1 for r in recs if (r.get(key) or {}).get("handed_over_before_arrival_s") is not None
                            and r[key]["handed_over_before_arrival_s"] < 0)
        result.setdefault("summary", {})[key] = {
            "videos": len(delays), "handed_over_more_than_2_s_late": len(late),
            "median_delay_s": round(delays[len(delays) // 2] / FPS, 1) if delays else None,
            "p90_delay_s": round(delays[min(len(delays) - 1, round(0.9 * (len(delays) - 1)))] / FPS, 1) if delays else None,
            "max_delay_s": round(max(delays) / FPS, 1) if delays else None,
            "handed_over_only_after_the_arrival": after_arrival,
            "arrival_window_fully_the_same": sum(1 for r in recs if (r.get(key) or {}).get("arrival_window_frames_in_batch")
                                                 and r[key]["arrival_window_same_box"] == r[key]["arrival_window_frames_in_batch"]),
            "arrival_window_less_than_half_the_same": sum(
                1 for r in recs if (r.get(key) or {}).get("arrival_window_frames_in_batch")
                and r[key]["arrival_window_same_box"] < 0.5 * r[key]["arrival_window_frames_in_batch"]),
            "videos_with_an_arrival": sum(1 for r in recs if (r.get(key) or {}).get("arrival_window_frames_in_batch")),
            "frames_with_another_aircraft_handed": sum((r.get(key) or {}).get("frames_with_another_aircraft_handed") or 0 for r in recs)}
    json.dump(result, io.open(out_path, "w", encoding="utf-8", newline="\n"), indent=1)
    print(json.dumps(result.get("summary"), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
