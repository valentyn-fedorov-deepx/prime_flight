"""Run the tracker stream (`pf.tracker.stream.TrackerStream`) on a video slice and compare it with the production pin.

Outputs in --out-dir:
  trackers<video>.ndjson          v1-compat file, byte-compatible with production (`{"<write counter>": [records]}`,
                                  json.dumps default separators, counter from 1 in publish order — `VideoWorker.model_pub`)
  trackers<video>-v2bus.ndjson    v2 bus: `{"frame_id": <absolute 1-based frame>, "records": [...]}` without `_p0`/`_st`
  tracker_v2_report<video>.json   timings (per stage and per component), identities, parity vs every --compare file

Parity (per --compare file, normally the production-pin outputs of `scripts/tracker_v1_profile.py --pin prod` on the
same slice): `pf.eval.compare_tracker_ndjson` on the consumed fields + line-level identity (raw, and with the private
optical-flow fields removed). With the same `--seed` on both sides a faithful port must be byte-identical; so must the
`--exact-fast` paths.

    python scripts/tracker_v2_run.py --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 \
        --gm-ndjson G:/gat_stages/atlc5_inferences/general_modelDjwtQRdZyt0sSk.mp4.ndjson --start 9000 --frames 1200 \
        --seed 0 --compare out/tracker_profile_prod/trackers_busy_seed0.ndjson [--exact-fast]
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


def install_component_timers() -> None:
    import cv2
    import skimage.restoration as restoration

    cv2.calcOpticalFlowPyrLK = timed("cv2.calcOpticalFlowPyrLK")(cv2.calcOpticalFlowPyrLK)
    cv2.cvtColor = timed("cv2.cvtColor")(cv2.cvtColor)
    restoration.estimate_sigma = timed("estimate_sigma")(restoration.estimate_sigma)
    import pf.tracker.fast_sigma as fs

    fs.estimate_sigma_rgb = timed("estimate_sigma_rgb")(fs.estimate_sigma_rgb)
    try:
        from ultralytics.engine.model import Model

        Model.predict = timed("yolo_seg.predict")(Model.predict)
    except Exception:  # pragma: no cover
        pass
    from pf.tracker._v1.deep_sort_pytorch.deep_sort import DeepSort
    from pf.tracker._v1.tracked_object import TrackedObject

    DeepSort.update = timed("deepsort.update")(DeepSort.update)
    TrackedObject.update_params = timed("tracked_object.update_params")(TrackedObject.update_params)
    # DeepSORT internals: ReID forward (GPU) vs Kalman / matching (Python)
    from pf.tracker._v1.deep_sort_pytorch.deep_sort.deep import feature_extractor as fe
    from pf.tracker._v1.deep_sort_pytorch.deep_sort.sort import tracker as sort_tracker

    fe.ResNetExtractor.__call__ = timed("deepsort.reid_resnet34")(fe.ResNetExtractor.__call__)
    fe.ResNetExtractor._preprocess = timed("deepsort.reid_resnet34_preprocess")(fe.ResNetExtractor._preprocess)
    fe.Extractor.__call__ = timed("deepsort.reid_person_net")(fe.Extractor.__call__)
    sort_tracker.Tracker.predict = timed("deepsort.kalman_predict")(sort_tracker.Tracker.predict)
    sort_tracker.Tracker.update = timed("deepsort.match_update")(sort_tracker.Tracker.update)
    try:
        import ultralytics.engine.predictor as up

        up.BasePredictor.preprocess = timed("yolo_seg.preprocess")(up.BasePredictor.preprocess)
        up.BasePredictor.inference = timed("yolo_seg.inference")(up.BasePredictor.inference)
    except Exception:  # pragma: no cover
        pass


def iter_gm_rows(path: str, start: int, n: int | None):
    with io.open(path, "rb") as fh:
        for i, line in enumerate(fh):
            if i < start:
                continue
            if n is not None and i >= start + n:
                break
            rec = json.loads(line)
            yield next(iter(rec.values()))


def _strip_line(line: bytes) -> str:
    from pf.tracker.stream import strip_private

    rec = json.loads(line)
    ((k, v),) = rec.items()
    return json.dumps({k: [strip_private(r) for r in v]}, sort_keys=True)


def compare_lines(path_ref: str, path_new: str) -> dict:
    """Line identity with normalised newlines (the v1 pin writes CRLF on Windows), raw and without `_p0`/`_st`."""
    total = same_raw = same_stripped = 0
    first_raw = first_stripped = None
    with io.open(path_ref, "rb") as fa, io.open(path_new, "rb") as fb:
        for i, (la, lb) in enumerate(zip(fa, fb), 1):
            total += 1
            la, lb = la.rstrip(b"\r\n"), lb.rstrip(b"\r\n")
            if la == lb:
                same_raw += 1
                same_stripped += 1
                continue
            if first_raw is None:
                first_raw = i
            if _strip_line(la) == _strip_line(lb):
                same_stripped += 1
            elif first_stripped is None:
                first_stripped = i
        extra_ref = sum(1 for _ in fa)
        extra_new = sum(1 for _ in fb)
    return {
        "lines_compared": total,
        "lines_identical": same_raw,
        "lines_identical_without_private": same_stripped,
        "first_different_line": first_raw,
        "first_different_line_without_private": first_stripped,
        "extra_lines_ref": extra_ref,
        "extra_lines_new": extra_new,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--gm-ndjson", required=True, help="production second-run GM ndjson of the same video")
    ap.add_argument("--start", type=int, default=0, help="first frame (0-based)")
    ap.add_argument("--frames", type=int, default=None, help="number of frames (default: to the end)")
    ap.add_argument("--weights-dir", default=os.path.join(ROOT, "external", "cv_trackers_prod", "weights"))
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--cone-camera", action="store_true", help="same flag semantics as tracker_v1_profile.py")
    ap.add_argument("--seed", type=int, default=None, help="np.random seed set right before the first frame")
    ap.add_argument("--exact-fast", action="store_true", help="output-identical performance paths")
    ap.add_argument("--fast-noise-gate", action="store_true", help="NOT exact: half-resolution noise estimate")
    ap.add_argument("--no-profile", action="store_true", help="do not install per-component timers")
    ap.add_argument("--no-compat", action="store_true", help="write only the v2 bus (skip the v1-compat serialisation)")
    ap.add_argument("--out-dir", default="out/tracker_v2")
    ap.add_argument("--compare", nargs="*", default=[], help="reference tracker ndjson files (same slice)")
    a = ap.parse_args()

    import cv2
    import torch

    if not a.no_profile:
        install_component_timers()
    from pf.eval.tracker_parity import compare_tracker_ndjson
    from pf.tracker.stream import TrackerOptions, TrackerStream, strip_private

    name = os.path.basename(a.video)
    os.makedirs(a.out_dir, exist_ok=True)
    compat_path = os.path.join(a.out_dir, f"trackers{name}.ndjson")
    bus_path = os.path.join(a.out_dir, f"trackers{name}-v2bus.ndjson")

    t_init = time.perf_counter()
    stream = TrackerStream(
        TrackerOptions(
            weights_dir=a.weights_dir, device=a.device, cone_camera=a.cone_camera, exact_fast=a.exact_fast,
            fast_noise_gate=a.fast_noise_gate,
        )
    )
    init_s = time.perf_counter() - t_init
    cap = cv2.VideoCapture(a.video)
    if a.start > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, a.start)
    if a.seed is not None:
        np.random.seed(a.seed)

    counter = 1
    frames = 0
    t_decode = 0.0
    t_write = 0.0
    bus_bytes = compat_bytes = 0
    fc = None if a.no_compat else io.open(compat_path, "w", encoding="utf-8", newline="\n")
    fb = io.open(bus_path, "w", encoding="utf-8", newline="\n")
    try:

        def publish(items):
            nonlocal counter, bus_bytes, compat_bytes, t_write
            tw = time.perf_counter()
            for fno, records in items:
                if fc is not None:
                    line = json.dumps({str(counter): records}) + "\n"
                    fc.write(line)
                    compat_bytes += len(line)
                bl = json.dumps({"frame_id": a.start + fno, "records": [strip_private(r) for r in records]}) + "\n"
                fb.write(bl)
                bus_bytes += len(bl)
                counter += 1
            t_write += time.perf_counter() - tw

        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for frame_number, rows in enumerate(iter_gm_rows(a.gm_ndjson, a.start, a.frames), 1):
            td = time.perf_counter()
            ok, img = cap.read()
            t_decode += time.perf_counter() - td
            if not ok:
                break
            publish(stream.update(frame_number, img, rows))
            frames += 1
        publish(stream.finish())
        torch.cuda.synchronize()
        total = time.perf_counter() - t0
    finally:
        if fc is not None:
            fc.close()
        fb.close()
        stream.close()
        cap.release()

    report = {
        "video": name,
        "start": a.start,
        "frames": frames,
        "seed": a.seed,
        "cone_camera": a.cone_camera,
        "exact_fast": a.exact_fast,
        "fast_noise_gate": a.fast_noise_gate,
        "init_s": round(init_s, 2),
        "total_s": round(total, 2),
        "ms_per_frame_total": round(1000 * total / max(frames, 1), 3),
        "decode_ms_per_frame": round(1000 * t_decode / max(frames, 1), 3),
        "serialise_ms_per_frame": round(1000 * t_write / max(frames, 1), 3),
        "stream": stream.report(),
        "components_ms_per_frame": {
            k: round(1000 * v / max(frames, 1), 3) for k, v in sorted(TIMES.items(), key=lambda kv: -kv[1])
        },
        "calls_per_frame": {k: round(v / max(frames, 1), 3) for k, v in CALLS.items()},
        "compat_lines": counter - 1,
        "compat_mb": round(compat_bytes / 1e6, 2),
        "v2bus_mb": round(bus_bytes / 1e6, 2),
        "parity": {},
    }
    if not a.no_compat:
        for ref in a.compare:
            s = compare_tracker_ndjson(ref, compat_path).summary()
            s["first_diffs"] = s.get("first_diffs", [])[:10]
            report["parity"][ref] = {"consumed_fields": s, "lines": compare_lines(ref, compat_path)}
    out = os.path.join(a.out_dir, f"tracker_v2_report{name}.json")
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    brief = {
        k: report[k]
        for k in ("frames", "exact_fast", "ms_per_frame_total", "decode_ms_per_frame", "serialise_ms_per_frame", "compat_mb", "v2bus_mb")
    }
    brief["stages"] = report["stream"]["timings_ms_per_frame"]
    brief["components"] = report["components_ms_per_frame"]
    print(json.dumps(brief, indent=1))
    for ref, p in report["parity"].items():
        cf = dict(p["consumed_fields"])
        cf.pop("first_diffs", None)
        print("parity vs", ref, json.dumps(cf), json.dumps(p["lines"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
