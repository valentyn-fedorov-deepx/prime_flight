"""Decide the per-video GM report fields from buffered single-pass votes once Tracker v2 has run (ADR-002, opt-in path).

Inputs
  --gm-report   a GM v2 report written with `scripts/gm_v2_run.py --buffered-decisions` (or `scripts/gm_v2_replay.py
                --video --buffered-decisions`, or `scripts/gm_buffered_votes.py` on a second-run file): `buffered_votes`
  --tracker     the Tracker v2 output of the same video, `trackers<video>.ndjson` or `trackers<video>-v2bus.ndjson`
                (T_ARR / T_DEP derived by `pf.tracker.events`; the frame on which T_ARR is published downstream — the
                tracker's own stop decision plus its N_INIT publish delay — from the published airplane state)
  --first-run / --second-run   the GM v2 row files (default: next to the report), for the aircraft-type replay

Output (JSON)
  report_fields                camera_type, confidence_camera, frame_stopped (= T_ARR), airplane_type, entity
  camera                       the ADR-002 rule on votes of the final main-aircraft track (v1's class-2 frames)
  camera_running_membership    the same rule on the causal running main-aircraft membership (the RT variant)
  frame_stopped / airplane_type / entity / buffer   values, semantics and cost
  reference_exact_second_pass  with --reference: an exact v1 second-pass dump (`scripts/gm_second_pass_probe.py --impl
                               module --dump-votes`): camera and frame_stopped, per-frame probability parity on the common
                               frames, and the same rule applied to the exact votes on the sampling grid
  plan                         with --plan: the camera recorded in the test-set plan (routing evidence)

    python scripts/gm_decide_buffered.py --gm-report out/gm_buffered/<video>/gm_v2_report<video>.json \
        --tracker out/testset/trk_v2/<video>/trackers<video>-v2bus.ndjson \
        --reference out/gm_buffered/<video>/second_pass_exact.json --plan out/testset/plan.json \
        --out out/gm_buffered/<video>/decisions<video>.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pf.gm.buffered import CameraRule, CameraVote, decide_camera, replay_aircraft_type, votes_from_report  # noqa: E402

FRAME_STOPPED_SEMANTICS = (
    "Tracker v2 T_ARR = the airplane track's arrival_frame, rewritten back to the first stopping frame (YOLO-seg masks on raw "
    "frames). v1 GM frame_stopped = the frame on which GM's own Airplane stop counter completes (> 4 s of STOPPED status, "
    "MobileSAM masks on noise-preprocessed frames), so it is normally later."
)
ENTITY_REASON = (
    "not produced by GM v2: v1 takes the entity from a separate classifier (a0157a4 EntityClassifier; 8576299 "
    "EntityClipClassifier on main-aircraft crops, whose sampler also reads frame_stopped) that is not ported, and "
    "pf.gm.context.EntityVoter needs entity-detector class ids the GM v2 pass does not produce"
)


def video_name_from_report(path: str) -> str:
    base = os.path.basename(path)
    for prefix in ("gm_v2_report", "gm_v2_replay", "gm_buffered_votes"):
        if base.startswith(prefix):
            base = base[len(prefix):]
            break
    return base[:-5] if base.endswith(".json") else base


def iter_rows_with_main(first_run: str, second_run: str, airplane_id: int):
    """(frame_id, first-run rows, class-2 box of the second-run file or None), both files read in lockstep."""
    with io.open(first_run, "rb") as f1, io.open(second_run, "rb") as f2:
        for l1, l2 in zip(f1, f2):
            ((k1, r1),) = json.loads(l1).items()
            ((k2, r2),) = json.loads(l2).items()
            if k1 != k2:
                raise SystemExit(f"row files out of step: frame {k1} vs {k2}")
            box = None
            for *xyxy, _conf, cls_id in r2:
                if int(cls_id) == airplane_id:
                    box = [int(x) for x in xyxy]
            yield int(k1), r1, box


def tracker_events(path: str) -> dict:
    from pf.tracker.events import derive_events

    out = {}
    for e in derive_events(path).events:
        if e.name in ("T_ARR", "T_DEP") and e.name not in out:
            out[e.name] = {"frame": e.frame, "decided_at": e.decided_at}
    return out


def workers_n_init() -> int:
    """N_INIT of the workers' DeepSORT = the publish delay of Tracker v2 (`pf.tracker.stream`: `n_init_delay`)."""
    import yaml

    with io.open(os.path.join(ROOT, "pf", "tracker", "_v1", "config", "deep_sort.yaml"), encoding="utf-8") as fh:
        return int(yaml.safe_load(fh)["DEEPSORT_WORKER"]["N_INIT"])


def tracker_arrival_publication(path: str, t_arr: int, fps: int) -> dict:
    """When T_ARR becomes known downstream. The tracker's Airplane decides arrival on the frame its stopped counter
    exceeds 4·fps (`_stopped_counter` > 32 with `_moving_counter` reset to 0; the published record of that frame is a
    snapshot of it) and rewrites `arrival_frame` back to the first stopping frame held in its airplane buffer; the deciding
    frame's record leaves the N_INIT publish buffer N_INIT - 1 frames later, and the rewritten records with it."""
    thresh = 4 * fps
    n_init = workers_n_init()
    with io.open(path, "rb") as fh:
        for line in fh:
            if b'"airplane"' not in line:
                continue
            rec = json.loads(line)
            if "records" in rec and "frame_id" in rec:
                frame_id, records = int(rec["frame_id"]), rec["records"]
            else:
                ((key, records),) = rec.items()
                frame_id = int(key)
            if frame_id < t_arr:
                continue
            for r in records:
                if r.get("cls_str") != "airplane":
                    continue
                sd = r.get("state_dict") or {}
                if sd.get("arrival_frame") is not None and (sd.get("_stopped_counter") or 0) > thresh \
                        and sd.get("_moving_counter") == 0:
                    return {"tracker_decided_frame": frame_id, "published_at": frame_id + n_init - 1,
                            "publish_delay_frames": n_init - 1}
    return {"tracker_decided_frame": None, "published_at": None, "publish_delay_frames": n_init - 1}


def plan_camera(plan_path: str, video: str):
    with io.open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    for ev in plan.get("events", []):
        cam = (ev.get("cameras") or {}).get(video)
        if cam:
            return {"camera": cam.get("camera"), "evidence": cam.get("evidence"), "event_id": ev.get("event_id"),
                    "event_videos": len(ev.get("videos") or [])}
    return None


def with_timing(decision: dict, t_arr, fps: int) -> dict:
    d = dict(decision)
    if t_arr is not None and d.get("decided_at") is not None:
        d["decided_after_t_arr_frames"] = d["decided_at"] - t_arr
        d["decided_after_t_arr_s"] = round((d["decided_at"] - t_arr) / fps, 1)
    return d


def classifier_calls_until(votes, frame) -> int:
    return sum(1 for v in votes if frame is not None and v.frame_id <= frame)


def reference_block(ref: dict, votes, t_arr, t_arr_known_at, rule: CameraRule, every_n: int, end_frame, fps: int) -> dict:
    cam = ref.get("camera") or {}
    out = {
        "impl": ref.get("impl"),
        "camera_type": cam.get("camera_type_cone"),
        "confidence_camera": cam.get("confidence_camera"),
        "votes": cam.get("votes"),
        "decided_at": ref.get("frames"),
        "frame_stopped": ref.get("frame_stopped"),
        "first_frame_with_arrived": ref.get("first_frame_with_arrived"),
        "departure_frame": ref.get("departure_frame"),
        "ms_per_frame": ref.get("ms_per_frame"),
        "components_ms_per_frame": ref.get("components_ms_per_frame"),
        "camera_split_ms_per_call": ref.get("camera_split_ms_per_call"),
        "preprocessed_frames": ref.get("preprocessed_frames"),
        "sam_calls": ref.get("sam_calls"),
    }
    frames, probs = ref.get("all_vote_frames"), ref.get("all_probs")
    if frames and probs:
        exact = {int(f): float(p) for f, p in zip(frames, probs)}
        common = [v for v in votes if v.frame_id in exact]
        diffs = [abs(v.prob - exact[v.frame_id]) for v in common]
        grid = {f for f in exact if f % every_n == 0}
        first_arrived = ref.get("first_frame_with_arrived") or 0
        buffered = {v.frame_id for v in votes if v.main_final and v.frame_id >= first_arrived}
        out["probability_parity"] = {
            "common_frames": len(common),
            "bit_identical": sum(1 for v in common if v.prob == exact[v.frame_id]),
            "max_abs_diff": max(diffs) if diffs else None,
            "vote_flips": sum(1 for v in common if v.is_cone != (exact[v.frame_id] >= 0.5)),
            "exact_votes_on_the_sampling_grid": len(grid),
            "grid_votes_missing_in_buffer": len(grid - buffered),
            "buffer_votes_not_in_exact": len(buffered - grid),
        }
        out["exact_votes_with_prob_in_0.4_0.6"] = sum(1 for p in exact.values() if 0.4 < p < 0.6)
        sampled = [CameraVote(f, exact[f], True, True) for f in sorted(grid)]
        out["rule_on_exact_grid_votes"] = with_timing(
            decide_camera(sampled, t_arr, t_arr_known_at=t_arr_known_at, end_frame=end_frame, rule=rule).as_dict(), t_arr, fps
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gm-report", required=True, help="GM v2 report with buffered_votes")
    ap.add_argument("--tracker", required=True, help="Tracker v2 output: trackers<video>.ndjson or -v2bus.ndjson")
    ap.add_argument("--first-run", default=None, help="first-run GM ndjson (default: next to --gm-report)")
    ap.add_argument("--second-run", default=None, help="second-run GM ndjson (default: next to --gm-report)")
    ap.add_argument("--variant", default=None, choices=["prod", "entity_clip", "master"],
                    help="aircraft-type voter (default: the variant recorded in buffered_votes)")
    ap.add_argument("--str2id", default=os.path.join(ROOT, "external", "cv_common", "global_config.yaml"))
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--min-votes", type=int, default=CameraRule.min_votes)
    ap.add_argument("--cone-share-hi", type=float, default=CameraRule.cone_share_hi)
    ap.add_argument("--cone-share-lo", type=float, default=CameraRule.cone_share_lo)
    ap.add_argument("--reference", default=None, help="exact second-pass dump (gm_second_pass_probe.py --dump-votes)")
    ap.add_argument("--plan", default=None, help="test-set plan.json (camera from routing evidence)")
    ap.add_argument("--no-aircraft-type", action="store_true", help="skip the aircraft-type replay")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    from pf.gm.rows import ClassMap
    from scripts.gm_v2_run import load_str2id

    with io.open(a.gm_report, encoding="utf-8") as fh:
        report = json.load(fh)
    buffered = report.get("buffered_votes")
    if not buffered:
        raise SystemExit(f"{a.gm_report}: no buffered_votes (run scripts/gm_v2_run.py with --buffered-decisions)")
    video = video_name_from_report(a.gm_report)
    votes = votes_from_report(buffered)
    every_n = int(buffered.get("every_n_frames", 8))
    variant = a.variant or buffered.get("variant") or "prod"
    end_frame = report.get("number_of_frames") or report.get("frames")
    rule = CameraRule(a.min_votes, a.cone_share_hi, a.cone_share_lo)

    events = tracker_events(a.tracker)
    t_arr = (events.get("T_ARR") or {}).get("frame")
    t_dep = (events.get("T_DEP") or {}).get("frame")
    t_arr_known = None
    if t_arr is not None:
        events["T_ARR"].update(tracker_arrival_publication(a.tracker, t_arr, a.fps))
        t_arr_known = events["T_ARR"]["published_at"] or events["T_ARR"]["decided_at"]

    cam = decide_camera(votes, t_arr, t_arr_known_at=t_arr_known, end_frame=end_frame, rule=rule)
    cam_running = decide_camera(votes, t_arr, t_arr_known_at=t_arr_known, end_frame=end_frame, rule=rule, membership="running")

    atype = None
    if not a.no_aircraft_type:
        gm_dir = os.path.dirname(os.path.abspath(a.gm_report))
        first_run = a.first_run or os.path.join(gm_dir, f"general_model{video}.ndjson")
        second_run = a.second_run or os.path.join(gm_dir, f"general_model{video}-second_run.ndjson")
        cm = ClassMap(load_str2id(a.str2id))
        atype = replay_aircraft_type(iter_rows_with_main(first_run, second_run, cm.id("airplane")), cm, variant=variant,
                                     t_arr=t_arr, t_dep=t_dep, fps=a.fps)
        atype["inputs"] = {"first_run": first_run, "second_run": second_run}

    cost = report.get("buffered_decisions_cost_ms_per_frame") or {}
    ms_call = cost.get("ms_per_classifier_call")
    frames_total = max(int(end_frame or 1), 1)

    def stop_projection(decision) -> dict:
        calls = classifier_calls_until(votes, decision.decided_at)
        return {"classifier_calls_until_decision": calls,
                "ms_per_frame_if_voting_stops_at_decision": round(calls * ms_call / frames_total, 3) if ms_call else None}

    ref_block = None
    if a.reference:
        with io.open(a.reference, encoding="utf-8") as fh:
            ref_block = reference_block(json.load(fh), votes, t_arr, t_arr_known, rule, every_n, end_frame, a.fps)
    frame_stopped = {"value": t_arr, "t_arr_published_at": t_arr_known, "source": "Tracker v2 T_ARR (pf.tracker.events)",
                     "semantics": FRAME_STOPPED_SEMANTICS}
    if ref_block and ref_block.get("frame_stopped") is not None and t_arr is not None:
        frame_stopped["v1_port"] = ref_block["frame_stopped"]
        frame_stopped["t_arr_minus_v1_frames"] = t_arr - ref_block["frame_stopped"]
        frame_stopped["t_arr_minus_v1_s"] = round((t_arr - ref_block["frame_stopped"]) / a.fps, 1)
    plan = plan_camera(a.plan, video) if a.plan else None

    out = {
        "video": video,
        "inputs": {"gm_report": a.gm_report, "tracker": a.tracker, "reference": a.reference, "plan": a.plan},
        "rule": {"every_n_frames": every_n, "min_votes": rule.min_votes, "cone_share_hi": rule.cone_share_hi,
                 "cone_share_lo": rule.cone_share_lo},
        "tracker_events": events,
        "report_fields": {
            "camera_type": cam.camera_type_cone,
            "confidence_camera": cam.confidence_camera,
            "frame_stopped": t_arr,
            "airplane_type": atype.get("airplane_type") if atype else None,
            "entity": None,
        },
        "camera": {**with_timing(cam.as_dict(), t_arr, a.fps), **stop_projection(cam)},
        "camera_running_membership": {**with_timing(cam_running.as_dict(), t_arr, a.fps), **stop_projection(cam_running)},
        "frame_stopped": frame_stopped,
        "airplane_type": atype,
        "entity": {"value": None, "reason": ENTITY_REASON},
        "buffer": {
            "votes": len(votes),
            "votes_before_t_arr": sum(1 for v in votes if t_arr is not None and v.frame_id < t_arr),
            "votes_off_the_final_main_aircraft": sum(1 for v in votes if v.main_final is False),
            "running_vs_final_membership_disagreements": sum(1 for v in votes if v.main_final is not None
                                                             and v.main_running != v.main_final),
            "working_frame": buffered.get("working_frame"),
            "first_aircraft_track_frame": buffered.get("first_aircraft_track_frame"),
            "cost_ms_per_frame": cost,
            "number_of_frames": end_frame,
        },
        "reference_exact_second_pass": ref_block,
        "plan": plan,
    }
    if plan and plan.get("camera") in ("cone", "wing"):
        out["plan"]["matches_camera"] = cam.camera_type_cone is not None and cam.camera_type_cone == (plan["camera"] == "cone")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    summary = {
        "video": video,
        "report_fields": out["report_fields"],
        "camera": {k: out["camera"].get(k) for k in ("rule", "votes_used", "decided_at", "decided_after_t_arr_s")},
        "running": {k: out["camera_running_membership"].get(k) for k in ("camera_type_cone", "rule", "decided_at")},
        "t_arr": events.get("T_ARR"),
        "reference": {k: (ref_block or {}).get(k) for k in ("camera_type", "confidence_camera", "votes", "frame_stopped")}
        if ref_block else None,
        "plan": plan,
    }
    print(json.dumps(summary, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
