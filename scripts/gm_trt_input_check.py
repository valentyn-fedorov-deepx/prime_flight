"""Why do the TensorRT heads produce different rows: is it the input colour order?

Runs the GM and chocks heads on the same frames of one video, on the CUDA provider and on TensorRT, for both input colour
orders (bgr_to_rgb True = the `prod` variant that ADR-003 measured, False = the `entity_clip` variant the test set and the
real-time pipeline use). Writes one first-run ndjson per configuration, compares the two providers within each colour
order with the tolerant comparator, and prints the detections per class.

    python scripts/gm_trt_input_check.py --video out/testset/videos/zHxIAF2vUGxJ.mp4 --frames 300 --start 6000
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

HEADS = {"gm": ("GM_yolov8m_best_augmentation_march2024.onnx", (1088, 1088), 0.35),
         "chocks": ("chocks_v4.3_200ep_yolov8.onnx", (1280, 1280), 0.10)}


def main() -> int:
    import cv2

    from pf.eval.parity import compare_gm_ndjson_tolerant
    from pf.gm.compat_writer import ndjson_line
    from pf.gm.onnx_detector import YoloV8Onnx, YoloV8OnnxConfig
    from pf.gm.rows import ClassMap
    from pf.pipeline.gm_stream import Detectors
    from scripts.gm_v2_run import load_str2id

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--start", type=int, default=6000)
    ap.add_argument("--weights-dir", default=os.path.join(ROOT, "external", "general_model_prod", "weights"))
    ap.add_argument("--trt-cache", default=os.path.join(ROOT, "out", "trt_cache"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "out", "rt", "scope", "trt_check"))
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    cm = ClassMap(load_str2id(os.path.join(ROOT, "external", "cv_common", "global_config.yaml")))
    id2name = {v: k for k, v in cm.str2id.items()}

    cap = cv2.VideoCapture(a.video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, a.start)
    frames = []
    for _ in range(a.frames):
        ok, img = cap.read()
        if not ok:
            break
        frames.append(img)
    cap.release()
    print("frames", len(frames), "from", a.start, flush=True)

    counts = {}
    paths = {}
    for rgb in (True, False):
        for provider in ("cuda", "tensorrt"):
            tag = ("rgb" if rgb else "bgr") + "_" + provider
            heads = {name: YoloV8Onnx(YoloV8OnnxConfig(weights=os.path.join(a.weights_dir, f), input_shape=shape,
                                                       conf_thres=thr, iou_thres=0.7, provider=provider, bgr_to_rgb=rgb,
                                                       trt_cache_dir=a.trt_cache))
                     for name, (f, shape, thr) in HEADS.items()}
            dets = Detectors(gm=heads["gm"], chocks=heads["chocks"], vehicle=None, parallel=False)
            per_class = collections.Counter()
            path = os.path.join(a.out_dir, tag + ".ndjson")
            with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
                for i, img in enumerate(frames, 1):
                    rows = dets.rows(img, cm)
                    fh.write(ndjson_line(i, rows))
                    for r in rows:
                        per_class[id2name.get(int(r[5]), int(r[5]))] += 1
            counts[tag], paths[tag] = per_class, path
            print(tag, "rows", sum(per_class.values()), flush=True)
            del dets, heads

    result = {"video": os.path.basename(a.video), "frames": len(frames), "start": a.start, "counts": {},
              "cuda_vs_tensorrt": {}}
    for rgb in ("rgb", "bgr"):
        summary = compare_gm_ndjson_tolerant(paths[rgb + "_cuda"], paths[rgb + "_tensorrt"]).summary()
        summary.pop("first_diffs", None)
        result["cuda_vs_tensorrt"][rgb] = summary
        print(rgb, "cuda vs tensorrt:", {k: summary.get(k) for k in ("pair_recall", "frame_parity_tolerant", "dets_a", "dets_b")},
              flush=True)
    for tag, per_class in counts.items():
        result["counts"][tag] = dict(per_class.most_common())
    names = sorted({n for c in counts.values() for n in c}, key=lambda n: -abs(counts["bgr_tensorrt"][n] - counts["bgr_cuda"][n]))
    print(f"{'class':<18}{'rgb cuda':>10}{'rgb trt':>9}{'bgr cuda':>10}{'bgr trt':>9}")
    for n in names[:14]:
        print(f"{str(n):<18}{counts['rgb_cuda'][n]:>10}{counts['rgb_tensorrt'][n]:>9}{counts['bgr_cuda'][n]:>10}{counts['bgr_tensorrt'][n]:>9}")
    with io.open(os.path.join(a.out_dir, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
