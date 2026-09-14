"""Replay recorded first-run rows through the GM v2 context and v1-compat writer — no detectors, no GPU.

Use it to (a) iterate on the context / compat logic against a production file without re-running inference, and (b)
compare the regenerated second-run file with production on ALL rows, including the synthesized ones (class 2 main
aircraft, 29/30 obstacles), which need the whole video.

With `--video --second-pass` it then runs the GM second pass (`pf.gm.second_pass.SecondPass`: MobileSAM main-aircraft
state machine + camera classifier, v1 semantics, GPU) over the video with the regenerated second-run rows and adds
`camera_type`, `confidence_camera` and `frame_stopped` to the report — the fields `model_starter.py` hands to the modules.

    python scripts/gm_v2_replay.py --first-run out/<run>/general_model<video>.mp4.ndjson \
        --compare G:/gat_stages/atlc5_inferences/general_model<video>.mp4.ndjson --out-dir out/<run>_replay \
        [--video G:/gat_stages/atlc5_videos/<video>.mp4 --second-pass]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pf.eval.parity import compare_gm_ndjson, compare_gm_ndjson_tolerant, iter_ndjson
from pf.gm.rows import ClassMap
from pf.pipeline import GmStream
from scripts.gm_v2_run import load_str2id


def run_second_pass(a, compat_path: str) -> dict:
    import cv2
    import torch

    from pf.gm.second_pass import SecondPass, load_gm_config
    from pf.tracker.fast_sigma import estimate_sigma_rgb

    t0 = time.perf_counter()
    sp = SecondPass(load_gm_config(a.gm_repo), a.weights_dir, device=a.device,
                    noise_fn=lambda img: float(estimate_sigma_rgb(img)))
    cap = cv2.VideoCapture(a.video)
    frames = 0
    for frame_id, rows in iter_ndjson(compat_path):
        ok, img = cap.read()
        if not ok:
            break
        sp.update(frame_id, img, rows)
        frames += 1
    cap.release()
    torch.cuda.synchronize()
    res = sp.result().as_dict()
    res["frames"] = frames
    res["seconds"] = round(time.perf_counter() - t0, 1)
    res["ms_per_frame"] = round(1000 * res["seconds"] / max(frames, 1), 2)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--first-run", required=True, help="first-run ndjson written by scripts/gm_v2_run.py")
    ap.add_argument("--str2id", default=os.path.join(ROOT, "external", "cv_common", "global_config.yaml"))
    ap.add_argument("--variant", default="prod", choices=["prod", "master"])
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--out-dir", default="out/replay")
    ap.add_argument("--compare", default=None, help="production second-run ndjson")
    ap.add_argument(
        "--arrived-at",
        type=int,
        default=None,
        help="frame of T_arr to gate camera/aircraft-type votes (until the stage detector exists)",
    )
    ap.add_argument("--departured-at", type=int, default=None)
    ap.add_argument("--video", default=None, help="the video, for --second-pass")
    ap.add_argument("--second-pass", action="store_true", help="run the GM second pass (GPU) and add its report fields")
    ap.add_argument("--weights-dir", default=os.path.join(ROOT, "external", "general_model_prod", "weights"))
    ap.add_argument("--gm-repo", default=os.path.join(ROOT, "external", "general_model_prod"))
    ap.add_argument("--device", default="cuda:0")
    a = ap.parse_args()
    if a.second_pass and not a.video:
        raise SystemExit("--second-pass needs --video")

    cm = ClassMap(load_str2id(a.str2id))
    rows_by_frame = {}
    for frame_no, rows in iter_ndjson(a.first_run):
        rows_by_frame[frame_no] = rows
    frames = sorted(rows_by_frame)
    video_name = os.path.basename(a.first_run).replace("general_model", "", 1).replace(".ndjson", "")
    os.makedirs(a.out_dir, exist_ok=True)

    stream = GmStream(cm, event_id=video_name, fps=a.fps, rows_provider=lambda f, _img: rows_by_frame[f])
    stream.context.variant = a.variant
    t0 = time.perf_counter()
    for f in frames:
        stream.process(
            f,
            None,
            arrived=(a.arrived_at is not None and f >= a.arrived_at),
            departured=(a.departured_at is not None and f >= a.departured_at),
        )
    compat_path = os.path.join(a.out_dir, f"general_model{video_name}-second_run.ndjson")
    stream.write_v1_compat(compat_path)
    elapsed = time.perf_counter() - t0

    report = stream.report()
    report["replay_seconds"] = round(elapsed, 1)
    report["frames"] = len(frames)
    snap = stream.context.snapshot()
    report["context"] = {
        k: snap.get(k)
        for k in (
            "main_plane_track",
            "mode_plane_height",
            "frame_of_beginning",
            "frame_of_ending",
            "first_aircraft_track",
            "main_front_wheel",
            "main_nose",
            "left_side_obstacles_roi",
            "right_side_obstacles_roi",
        )
    }
    report["events"] = [vars(e) for e in stream.events]
    if a.second_pass:
        sp = run_second_pass(a, compat_path)
        report["second_pass"] = sp
        report["camera_type"] = sp["camera_type_cone"]
        report["confidence_camera"] = sp["confidence_camera"]
        report["frame_stopped"] = sp["frame_stopped"]
    if a.compare:
        report["parity_exact_all_classes"] = compare_gm_ndjson(a.compare, compat_path).summary()
        report["parity_tolerant_all_classes"] = compare_gm_ndjson_tolerant(a.compare, compat_path).summary()
        for name, classes in (
            ("class2_main_aircraft", (2,)),
            ("class29_obstacle", (29,)),
            ("class30_side_obstacle", (30,)),
        ):
            ignore = tuple(sorted(set(range(32)) - set(classes)))
            report[f"parity_{name}"] = compare_gm_ndjson_tolerant(
                a.compare, compat_path, ignore_classes=ignore
            ).summary()
    with open(os.path.join(a.out_dir, f"gm_v2_replay{video_name}.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    keys = ["frames", "replay_seconds", "context", "decided_at"] + (["second_pass"] if a.second_pass else [])
    print(json.dumps({k: report[k] for k in keys}, indent=1, default=str))
    if a.compare:
        for k in (
            "parity_exact_all_classes",
            "parity_tolerant_all_classes",
            "parity_class2_main_aircraft",
            "parity_class29_obstacle",
            "parity_class30_side_obstacle",
        ):
            s = dict(report[k])
            s.pop("first_diffs", None)
            s.pop("per_class_a", None)
            s.pop("per_class_b", None)
            print(k, json.dumps(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
