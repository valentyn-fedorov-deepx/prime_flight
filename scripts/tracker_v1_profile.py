"""Measure the real per-frame cost of the v1 tracker, component by component — the number the stand never had
(`tracker 0.11 ms` was a placeholder).

Two pins:
  --pin master  cv_trackers b5d350c (review pin) + cv_common ac5098d2 (its submodule pointer): MobileSAM masks,
                full-frame `estimate_sigma` on every frame with tracked objects.  Runs unmodified.
  --pin prod    cv_trackers bd43c3c (branch `optimization`, the production image): YOLO-seg masks, patch-based
                `estimate_sigma` every N seconds.  Its submodule pointer (cv_common ac5098d2) cannot run it; the calls
                match `Vehicle.update_params` of cv_common `tracker_optimization` @2759daf (BL and GSE are `Vehicle`
                objects there), so the prod pin runs with that revision.  Whether the image carried exactly 2759daf or an
                earlier commit of that line is an open question to Ihor/Yurii (`docs/analysis/tracker_current.md` §12);
                the adapter below only covers the (unused in practice) `TrackedObject.update_params` call shape.

The unmodified `tracker.detect()` runs on a truncated inference directory (N lines of the production GM ndjson, renumbered
from 1, the video seeked to the same frame) with timing wrappers around the expensive calls:
    SamPredictor.set_image / predict        (MobileSAM masks, master pin)
    ultralytics Model.predict               (YOLO-seg masks, prod pin)
    skimage estimate_sigma                  (noise gate for the TV denoiser)
    denoise_tv_chambolle                    (GPU torch port on Windows, see scripts/win_shims)
    cv2.calcOpticalFlowPyrLK / goodFeaturesToTrack
    DeepSort.update                         (3 instances: BL, GSE, workers)
    TrackedObject.update_params             (the per-object state machine incl. the above)
    VideoWorker.model_pub                   (JSON serialisation of the state, incl. _p0)

    python scripts/tracker_v1_profile.py --pin master --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 \
        --gm-ndjson G:/gat_stages/atlc5_inferences/general_modelDjwtQRdZyt0sSk.mp4.ndjson --start 3400 --frames 1200
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
TIMES = defaultdict(float)
CALLS = defaultdict(int)
PINS = {"master": "cv_trackers", "prod": "cv_trackers_prod"}


def draw_obj_mask_roi(self, img_to_draw, color=None):
    """TrackedObject.draw_obj_mask on the bounding box of the mask only: outside it the full-frame version leaves the
    pixels unchanged ((colour & 0) | (pixel & 255)), inside it runs the same three bitwise operations; drawn in
    place, as the caller reassigns the returned frame and holds no other reference to it."""
    import cv2
    import numpy as np
    mask = self._TrackedObject__segmenter.mask
    if mask is None:
        return img_to_draw
    if color is None:
        color = (0, 255, 0)
    x, y, w, h = cv2.boundingRect(mask)
    if w and h:
        roi_mask = mask[y:y + h, x:x + w]
        roi = img_to_draw[y:y + h, x:x + w]
        colour = np.full((h, w, 3), color, dtype=np.uint8)
        fg = cv2.bitwise_or(colour, colour, mask=roi_mask)
        bk = cv2.bitwise_or(roi, roi, mask=cv2.bitwise_not(roi_mask))
        img_to_draw[y:y + h, x:x + w] = cv2.bitwise_or(fg, bk)
    return img_to_draw


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


def truncate_ndjson(src: str, dst: str, start: int, n: int) -> int:
    """Write lines [start, start+n) of the GM ndjson, renumbered 1..n (the tracker zips frames positionally)."""
    written = 0
    with io.open(src, "rb") as fi, io.open(dst, "wb") as fo:
        for i, line in enumerate(fi):
            if i < start:
                continue
            if written >= n:
                break
            rec = json.loads(line)
            rows = next(iter(rec.values()))
            fo.write((json.dumps({str(written + 1): rows}) + "\n").encode("utf-8"))
            written += 1
    return written


def install_windows_shims() -> list:
    """cupy / cuCIM (GPU TV denoise) have no Windows builds → NumPy / torch stand-ins (scripts/win_shims)."""
    used = []
    for mod in ("cupy", "cucim"):
        try:
            __import__(mod)
        except ImportError:
            shims = os.path.join(ROOT, "scripts", "win_shims")
            if shims not in sys.path:
                sys.path.insert(0, shims)
            used.append(mod)
    return used


def adapt_prod_pin_to_cv_common_2759daf(TrackedObject, ObjectSegmenter) -> None:
    """bd43c3c calls `update_params(xyxy, prev, im0s, frame_number, segmentor, bboxes_to_remove=, yolo_idx=)`;
    cv_common 2759daf declares `(xyxy, prev, im0s, predictor, bboxes_to_remove=None, is_noised=False, frame_number=None,
    invoker=None, yolo_idx=None)` and selects YOLO-seg masks per `tracking_params['model_type']`, which no config sets.
    """
    orig = TrackedObject.update_params

    @functools.wraps(orig)
    def update_params(self, xyxy, prev_im0s, im0s, *args, **kw):
        if args and isinstance(args[0], (int, np.integer)) and len(args) >= 2:
            frame_number, predictor = args[0], args[1]
            rest = args[2:]
            if rest:
                kw.setdefault("bboxes_to_remove", rest[0])
            kw.setdefault("frame_number", frame_number)
            kw.setdefault("invoker", self)  # cache key = invoker class → one YOLO-seg call per class per frame
            return orig(self, xyxy, prev_im0s, im0s, predictor, **kw)
        return orig(self, xyxy, prev_im0s, im0s, *args, **kw)

    TrackedObject.update_params = update_params

    seg_init = ObjectSegmenter.__init__

    @functools.wraps(seg_init)
    def seg_init_yolo(self, segm_points=None, model_type="yolo_seg"):
        seg_init(self, segm_points=segm_points, model_type=model_type)

    ObjectSegmenter.__init__ = seg_init_yolo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pin", default="master", choices=sorted(PINS))
    ap.add_argument("--video", required=True)
    ap.add_argument("--gm-ndjson", required=True, help="production second-run GM ndjson of the same video")
    ap.add_argument("--start", type=int, default=0, help="first frame (0-based) of the slice")
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--tracker-dir", default=None, help="default external/<pin repo>")
    ap.add_argument("--weights-dir", default="weights")
    ap.add_argument("--cone-camera", action="store_true")
    ap.add_argument("--device", default="0")
    ap.add_argument("--seed", type=int, default=None, help="np.random seed set when the first frame is pulled")
    ap.add_argument("--fast-mask-draw", action="store_true",
                    help="draw each object mask on its bounding box only (the same pixels as the full-frame draw)")
    ap.add_argument("--variant", default="base", help="label of the debug video file")
    ap.add_argument("--save-video", action="store_true",
                    help="draw and encode the debug video, as the production job does by default (--write_video t)")
    ap.add_argument("--out", default=None, help="default out/tracker_v1_profile_<pin>.json")
    a = ap.parse_args()
    tracker_dir = a.tracker_dir or os.path.join(ROOT, "external", PINS[a.pin])
    out = a.out or f"out/tracker_v1_profile_{a.pin}.json"

    workdir = os.path.abspath(os.path.join(ROOT, "out", f"tracker_profile_{a.pin}"))
    os.makedirs(workdir, exist_ok=True)
    name = os.path.basename(a.video)
    gm_slice = os.path.join(workdir, f"general_model{name}.ndjson")
    n = truncate_ndjson(a.gm_ndjson, gm_slice, a.start, a.frames)

    os.chdir(tracker_dir)
    sys.path.insert(0, tracker_dir)
    shims = install_windows_shims()
    import cv2
    import torch

    import tracker as trk  # noqa: E402  (external/<pin>/tracker.py)
    from db_worker.ML_worker import VideoWorker  # noqa: E402

    # --- timing wrappers ------------------------------------------------------------------------------
    try:
        from mobile_sam import SamPredictor

        SamPredictor.set_image = timed("sam.set_image")(SamPredictor.set_image)
        SamPredictor.predict = timed("sam.predict")(SamPredictor.predict)
    except Exception as e:  # pragma: no cover
        print("mobile_sam not wrapped:", e)
    try:
        from ultralytics.engine.model import Model as UltralyticsModel

        UltralyticsModel.predict = timed("yolo_seg.predict")(UltralyticsModel.predict)
    except Exception as e:  # pragma: no cover
        print("ultralytics not wrapped:", e)
    cv2.calcOpticalFlowPyrLK = timed("cv2.calcOpticalFlowPyrLK")(cv2.calcOpticalFlowPyrLK)
    cv2.goodFeaturesToTrack = timed("cv2.goodFeaturesToTrack")(cv2.goodFeaturesToTrack)
    try:
        from deep_sort_pytorch.deep_sort import DeepSort

        DeepSort.update = timed("deepsort.update")(DeepSort.update)
    except Exception as e:  # pragma: no cover
        print("DeepSort not wrapped:", e)
    trk.denoise_tv_chambolle = timed("denoise_tv_chambolle")(trk.denoise_tv_chambolle)
    trk.estimate_sigma = timed("estimate_sigma")(trk.estimate_sigma)
    from cv_common.tracked_object import TrackedObject

    if a.pin == "prod":
        from cv_common.tracked_object import ObjectSegmenter

        adapt_prod_pin_to_cv_common_2759daf(TrackedObject, ObjectSegmenter)
    TrackedObject.update_params = timed("tracked_object.update_params")(TrackedObject.update_params)
    VideoWorker.model_pub = timed("video_worker.model_pub")(VideoWorker.model_pub)
    # the optical-flow point colours of the debug video are drawn at import from the unseeded np.random
    # (tracked_object.py:103), so no two runs give the same video; a fixed palette makes the videos comparable
    import numpy as np
    import cv_common.tracked_object as cto
    cto.FeatureTracker._OF_color = np.random.RandomState(12345).randint(0, 255, cto.FeatureTracker._OF_color.shape)
    if a.fast_mask_draw:
        TrackedObject.draw_obj_mask = draw_obj_mask_roi
    # the debug video: drawing per object and the encoder (cv2.VideoWriter is a C type, so the writer is wrapped)
    for name in ("draw_obj_mask", "draw_OF_points", "draw_bbox"):
        setattr(TrackedObject, name, timed(f"video.{name}")(getattr(TrackedObject, name)))
    trk.plot_one_box = timed("video.plot_one_box")(trk.plot_one_box)
    _writer_cls = cv2.VideoWriter
    _encode = timed("video.encode")(lambda w, frame: w.write(frame))

    class TimedWriter:
        def __init__(self, *args, **kw):
            self._w = _writer_cls(*args, **kw)

        def write(self, frame):
            return _encode(self._w, frame)

        def __getattr__(self, item):
            return getattr(self._w, item)

    trk.cv2.VideoWriter = TimedWriter
    trk.logging.info = timed("logging.info")(trk.logging.info)

    class SlicedWorker(VideoWorker):
        def load_source(self, source=None):
            dataset = super().load_source(source)
            if a.start > 0:
                dataset.cap.set(cv2.CAP_PROP_POS_FRAMES, a.start)
            if a.seed is not None:
                # seed np.random when the first frame is pulled — after all models are loaded inside detect(), i.e.
                # at the same logical point as scripts/tracker_v2_run.py --seed (keypoint subsampling is unseeded in v1)
                cls = type(dataset)
                orig_next = cls.__next__
                state = {"seeded": False}

                def seeded_next(self_):
                    if not state["seeded"]:
                        np.random.seed(a.seed)
                        state["seeded"] = True
                    return orig_next(self_)

                cls.__next__ = seeded_next
            return dataset

    vw = SlicedWorker(
        model_name="trackers",
        testing=True,
        source=a.video,
        load_tracks=False,
        auto_download_inference=False,
        inferences_dir=workdir,
    )
    t0 = time.perf_counter()
    with torch.no_grad():
        trk.detect(
            source=a.video,
            output_path=os.path.join(workdir, f"debug_{a.variant}.mp4" if a.save_video else "out"),
            video_worker=vw,
            to_csv=False,
            device=a.device,
            weights_dir=a.weights_dir,
            cone_camera=a.cone_camera,
            save_video=a.save_video,
        )
    torch.cuda.synchronize()
    total = time.perf_counter() - t0

    report = {
        "pin": a.pin,
        "save_video": a.save_video,
        "tracker_dir": tracker_dir,
        "windows_shims": shims,
        "video": name,
        "start": a.start,
        "frames": n,
        "total_s": round(total, 2),
        "ms_per_frame_total": round(1000 * total / max(n, 1), 3),
        "components_ms_per_frame": {
            k: round(1000 * v / max(n, 1), 3) for k, v in sorted(TIMES.items(), key=lambda kv: -kv[1])
        },
        "calls": dict(CALLS),
        "calls_per_frame": {k: round(v / max(n, 1), 3) for k, v in CALLS.items()},
    }
    out = os.path.abspath(os.path.join(ROOT, out)) if not os.path.isabs(out) else out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps(report, indent=1))
    tracker_out = os.path.join(workdir, f"trackers{name}.ndjson")
    if os.path.exists(tracker_out):
        print("tracker ndjson written:", tracker_out, os.path.getsize(tracker_out), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
