"""GM second-pass probe: v1 main-aircraft state machine (arrival / departure → `frame_stopped`) and camera-type votes.

GM v2 does not produce `frame_stopped` and `camera_type` yet (tasks/notes/PF-Q1-16.md, "Known gaps"). This script reproduces
general_model @a0157a4 `main.py:762-947` for exactly those outputs on a full video, to measure their cost and to have values
to compare against production:

  * frames with the main aircraft = frames with a class-2 row in the second-run file (v1 `max_time_plane_history`); the box
    and `mode_plane_height` come from that row;
  * `Plane(cv_common.Airplane)` is created on the first such frame and updated on the following ones with MobileSAM masks,
    `nose_list` (airplane_nose rows) and `worker_bboxes` = boxes of person / trailer / fuel_truck / gse rows;
  * every frame goes through `ImagePreprocessor.update`; once the aircraft object exists the second pass works on the
    preprocessed frame; `prev_im0s` is the previous working frame;
  * `frame_stopped = main_plane.arrival_frame` once arrived; one camera-classifier vote (`pf.gm.camera`) per frame with the
    aircraft after arrival; majority and confidence at the end.

Deviation (documented): GM's cv_common pin d74eb096 is not in the local archive. The Airplane / TrackedObject classes are the
vendored 2759daf ones with the MobileSAM segmenter (the ac5098d2 code path); 2759daf repairs out-of-frame boxes where
ac5098d2 raised.

Comparison available offline: the airplane `arrival_frame` / `departure_frame` of the production tracker file (the same
state-machine family, YOLO-seg masks on non-preprocessed frames). The authoritative values are the production GM reports.

    python scripts/gm_second_pass_probe.py --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 \
        --second-run G:/gat_stages/atlc5_inferences/general_modelDjwtQRdZyt0sSk.mp4.ndjson \
        --tracker G:/gat_stages/atlc5_inferences/trackersDjwtQRdZyt0sSk.mp4.ndjson --out out/gm_second_pass_Djwt.json
"""

from __future__ import annotations

import argparse
import functools
import io
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TIMES = defaultdict(float)
CALLS = defaultdict(int)
REMOVE_CLASSES = ("person", "trailer", "fuel_truck", "gse")


def timed(name):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            t0 = time.perf_counter()
            try:
                return fn(*a, **kw)
            finally:
                TIMES[name] += time.perf_counter() - t0
                CALLS[name] += 1

        return wrapper

    return deco


def gm_config(gm_repo: str) -> dict:
    """cv_common global_config (vendored 2759daf copy) updated by the GM repo's local_config.yaml, like parse_config()."""
    import yaml

    with open(os.path.join(ROOT, "pf", "tracker", "_v1", "config", "global_config.yaml"), encoding="utf-8") as fh:
        cfg = yaml.load(fh, Loader=yaml.FullLoader)
    local = os.path.join(gm_repo, "local_config.yaml")
    if os.path.isfile(local):
        with open(local, encoding="utf-8") as fh:
            cfg.update(yaml.load(fh, Loader=yaml.FullLoader) or {})
    return cfg


def iter_rows(path: str):
    with io.open(path, "rb") as fh:
        for line in fh:
            ((k, v),) = json.loads(line).items()
            yield int(k), v


def tracker_airplane_events(path: str) -> dict:
    """First non-null arrival_frame / departure_frame of the airplane record in a tracker ndjson (keys = frames)."""
    arrival = departure = None
    first_arrival_line = first_departure_line = None
    with io.open(path, "rb") as fh:
        for line in fh:
            if b'"airplane"' not in line:
                continue
            ((k, recs),) = json.loads(line).items()
            for r in recs:
                if r.get("cls_str") != "airplane":
                    continue
                sd = r.get("state_dict") or {}
                if arrival is None and sd.get("arrival_frame") is not None:
                    arrival, first_arrival_line = sd["arrival_frame"], int(k)
                if departure is None and sd.get("departure_frame") is not None:
                    departure, first_departure_line = sd["departure_frame"], int(k)
            if arrival is not None and departure is not None:
                break
    return {"arrival_frame": arrival, "arrival_published_at_line": first_arrival_line,
            "departure_frame": departure, "departure_published_at_line": first_departure_line}


def run_module_impl(a, cfg, cv2, torch, noise_fn, init_s) -> int:
    """The same probe through `pf.gm.second_pass.SecondPass` (models are loaded again inside the class)."""
    from pf.gm.second_pass import SecondPass

    t_init = time.perf_counter()
    sp = SecondPass(cfg, a.weights_dir, device=a.device, noise_fn=noise_fn)
    init_s += time.perf_counter() - t_init
    cap = cv2.VideoCapture(a.video)
    frames = 0
    t0 = time.perf_counter()
    for frame_id, rows in iter_rows(a.second_run):
        if a.max_frames is not None and frame_id > a.max_frames:
            break
        ok, im0s = cap.read()
        if not ok:
            break
        frames += 1
        sp.update(frame_id, im0s, rows)
    torch.cuda.synchronize()
    total = time.perf_counter() - t0
    cap.release()
    res = sp.result()
    report = {
        "video": os.path.basename(a.video),
        "second_run": a.second_run,
        "impl": "module",
        "frames": frames,
        "plane_frames": res.plane_frames,
        "first_plane_frame": res.first_plane_frame,
        "frame_stopped": res.frame_stopped,
        "first_frame_with_arrived": res.first_frame_with_arrived,
        "departure_frame": res.departure_frame,
        "camera": {"votes": res.camera_votes, "camera_type_cone": res.camera_type_cone,
                   "confidence_camera": round(res.confidence_camera, 4)},
        "preprocessed_frames": res.preprocessed_frames,
        "sam_calls": CALLS.get("sam.set_image", 0),
        "fast_sigma": a.fast_sigma,
        "init_s": round(init_s, 1),
        "total_s": round(total, 1),
        "ms_per_frame": round(1000 * total / max(frames, 1), 3),
        "components_ms_per_frame": {k: round(1000 * v / max(frames, 1), 3) for k, v in sorted(TIMES.items(), key=lambda kv: -kv[1])},
        "calls": dict(CALLS),
        "all_votes": [bool(v) for v in sp.votes] if a.dump_votes else None,
        "all_probs": [float(x) for x in sp.probs] if a.dump_votes else None,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    print(json.dumps({k: report[k] for k in ("impl", "frames", "plane_frames", "frame_stopped", "camera", "preprocessed_frames", "ms_per_frame")}, default=str))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--second-run", required=True, help="GM second-run ndjson (production or v1-compat from GM v2)")
    ap.add_argument("--tracker", default=None, help="production tracker ndjson of the same video (for comparison)")
    ap.add_argument("--weights-dir", default=os.path.join(ROOT, "external", "general_model_prod", "weights"))
    ap.add_argument("--gm-repo", default=os.path.join(ROOT, "external", "general_model_prod"))
    ap.add_argument("--fast-sigma", action="store_true", help="bit-identical threaded noise estimate in the preprocessor")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--impl", default="inline", choices=["inline", "module"],
                    help="inline = the reference loop below; module = pf.gm.second_pass.SecondPass (on-demand preprocessing)")
    ap.add_argument("--dump-votes", action="store_true", help="store every camera vote and probability in the JSON")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--out", default="out/gm_second_pass_probe.json")
    a = ap.parse_args()

    import cv2
    import torch
    from mobile_sam import SamPredictor, sam_model_registry

    from pf.gm.camera import CameraClassifier, majority_vote
    from pf.gm.preprocessor import ImagePreprocessor, estimate_noise
    from pf.tracker._v1 import tracked_object as to_mod
    from pf.tracker._v1.transport import Airplane

    cfg = gm_config(a.gm_repo)
    s2i = cfg["str2id"]
    remove_ids = {s2i[c] for c in REMOVE_CLASSES}
    plane_params = cfg["tracking"]["airplane"]["tracked_object"]

    SamPredictor.set_image = timed("sam.set_image")(SamPredictor.set_image)
    SamPredictor.predict = timed("sam.predict")(SamPredictor.predict)
    cv2.calcOpticalFlowPyrLK = timed("cv2.calcOpticalFlowPyrLK")(cv2.calcOpticalFlowPyrLK)
    Airplane.update_params = timed("airplane.update_params")(Airplane.update_params)
    CameraClassifier.predict = timed("camera.predict")(CameraClassifier.predict)

    t_init = time.perf_counter()
    sam = sam_model_registry["vit_t"](checkpoint=os.path.join(a.weights_dir, "mobile_sam.pt"))
    sam.to(device=a.device)
    sam.eval()
    predictor = SamPredictor(sam)
    camera = CameraClassifier(a.weights_dir, device=a.device)
    noise_fn = estimate_noise
    if a.fast_sigma:
        from pf.tracker.fast_sigma import estimate_sigma_rgb

        noise_fn = lambda img: float(estimate_sigma_rgb(img))  # noqa: E731
    pre = ImagePreprocessor(noise_fn=timed("preprocessor.noise")(noise_fn))
    init_s = time.perf_counter() - t_init

    if a.impl == "module":
        return run_module_impl(a, cfg, cv2, torch, timed("preprocessor.noise")(noise_fn), init_s)

    cap = cv2.VideoCapture(a.video)
    main_plane = None
    airplane_detected = False
    prev_im0s = None
    frame_stopped = None
    first_arrived_frame = None
    departure_frame = None
    first_plane_frame = None
    plane_frames = 0
    votes, probs = [], []
    frames = 0
    t_decode = t_pre = 0.0
    t0 = time.perf_counter()
    for frame_id, rows in iter_rows(a.second_run):
        if a.max_frames is not None and frame_id > a.max_frames:
            break
        td = time.perf_counter()
        ok, im0s = cap.read()
        t_decode += time.perf_counter() - td
        if not ok:
            break
        frames += 1
        tp = time.perf_counter()
        pre.update(frame_id, im0s)
        if airplane_detected:
            im0s = pre.get_preprocessed()
        t_pre += time.perf_counter() - tp

        nose_list, bboxes_to_remove, largest_plane, mode_height = [], [], None, None
        for *xyxy, conf, cls_id in rows or []:
            cls_id = int(cls_id)
            box = list(map(int, xyxy))
            if cls_id == s2i["airplane"]:
                largest_plane, mode_height = box, int(conf)
                continue
            if cls_id == s2i["airplane_nose"]:
                nose_list.append(box)
            if cls_id in remove_ids:
                bboxes_to_remove.append(box)

        plane_available = largest_plane is not None
        if plane_available:
            plane_frames += 1
            if main_plane is None:
                main_plane = Airplane(obj_id=0, xyxy=largest_plane, tracking_params=dict(plane_params), height_mode=mode_height)
                # v1 GM (cv_common before YOLO-seg): MobileSAM segmentation of the aircraft
                main_plane._TrackedObject__segmenter = to_mod.ObjectSegmenter(model_type="mobile_sam")
                first_plane_frame = frame_id
            else:
                main_plane.update_params(largest_plane, prev_im0s, im0s, frame_id, predictor, nose_list,
                                         bboxes_to_remove=bboxes_to_remove)
            airplane_detected = True

        if main_plane is not None and main_plane.arrived:
            frame_stopped = main_plane.arrival_frame
            if first_arrived_frame is None:
                first_arrived_frame = frame_id
        if main_plane is not None and main_plane.departured and departure_frame is None:
            departure_frame = main_plane.departure_frame

        prev_im0s = im0s.copy()

        if plane_available and main_plane.arrived:
            is_cone, p = camera.predict(im0s)
            votes.append(is_cone)
            probs.append(p)
    torch.cuda.synchronize()
    total = time.perf_counter() - t0
    cap.release()

    cone, confidence = majority_vote(votes)
    probs_np = np.array(probs, dtype=np.float64) if probs else np.zeros(0)
    report = {
        "video": os.path.basename(a.video),
        "second_run": a.second_run,
        "frames": frames,
        "plane_frames": plane_frames,
        "first_plane_frame": first_plane_frame,
        "frame_stopped": frame_stopped,
        "first_frame_with_arrived": first_arrived_frame,
        "departure_frame": departure_frame,
        "camera": {
            "votes": len(votes),
            "camera_type_cone": cone,
            "confidence_camera": round(confidence, 4),
            "cone_share": round(float(np.mean(votes)), 4) if votes else None,
            "prob_min_mean_max": [round(float(probs_np.min()), 4), round(float(probs_np.mean()), 4), round(float(probs_np.max()), 4)] if probs else None,
            "votes_with_prob_in_0.4_0.6": int(((probs_np > 0.4) & (probs_np < 0.6)).sum()) if probs else 0,
        },
        "impl": "inline",
        "sam_calls": CALLS.get("sam.set_image", 0),
        "all_votes": [bool(v) for v in votes] if a.dump_votes else None,
        "all_probs": [float(x) for x in probs] if a.dump_votes else None,
        "deviation": "cv_common d74eb096 unavailable: vendored 2759daf Airplane with MobileSAM segmenter",
        "fast_sigma": a.fast_sigma,
        "init_s": round(init_s, 1),
        "total_s": round(total, 1),
        "ms_per_frame": round(1000 * total / max(frames, 1), 3),
        "decode_ms_per_frame": round(1000 * t_decode / max(frames, 1), 3),
        "preprocess_ms_per_frame": round(1000 * t_pre / max(frames, 1), 3),
        "components_ms_per_frame": {k: round(1000 * v / max(frames, 1), 3) for k, v in sorted(TIMES.items(), key=lambda kv: -kv[1])},
        "calls": dict(CALLS),
        "preprocessor": pre.snapshot(),
    }
    if a.tracker:
        report["production_tracker_airplane"] = tracker_airplane_events(a.tracker)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    print(json.dumps({k: report[k] for k in ("frames", "plane_frames", "first_plane_frame", "frame_stopped", "departure_frame", "camera", "ms_per_frame", "components_ms_per_frame")}, indent=1, default=str))
    if a.tracker:
        print("production tracker airplane:", json.dumps(report["production_tracker_airplane"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
