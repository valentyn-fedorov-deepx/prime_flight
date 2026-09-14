"""Benchmark GM v2 head scheduling on N frames of a video and prove the optimizations do not change the rows.

Configurations (all three production heads, fp16 ONNX, production preprocessing):
  baseline   each head `predict()` on its own (v1-like: upload + preprocess per head, sequential)
  shared     one upload, one letterbox per input size, sequential heads
  parallel   shared + the heads run concurrently in threads (one CUDA stream per ORT session)
  tensorrt   shared + TensorRT execution provider (fp16 engines; first run builds and caches the engines) — EXPERIMENT

For every configuration the rows of every frame are compared with the baseline: exact for shared/parallel (must be
byte-identical), tolerant for tensorrt. Output: JSON with ms/frame per component and the parity summary.

    python scripts/gm_bench.py --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 \
        --weights-dir external/general_model_prod/weights --frames 600 --start 3600 --out out/bench.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pf.eval.parity import TolerantParity, compare_gm_frame_tolerant
from pf.gm.heads import MultiHeadRunner
from pf.gm.onnx_detector import YoloV8Onnx, YoloV8OnnxConfig

HEADS = {
    "gm": ("GM_yolov8m_best_augmentation_march2024.onnx", (1088, 1088), 0.35),
    "chocks": ("chocks_v4.3_200ep_yolov8.onnx", (1280, 1280), 0.10),
    "vehicle": ("VM_yolov8m_last_september2023.onnx", (1088, 1088), 0.40),
}


def make_heads(weights_dir: str, provider: str, trt_cache: str) -> dict:
    heads = {}
    for name, (fname, shape, thr) in HEADS.items():
        heads[name] = YoloV8Onnx(
            YoloV8OnnxConfig(
                weights=os.path.join(weights_dir, fname),
                input_shape=shape,
                conf_thres=thr,
                iou_thres=0.7,
                provider=provider,
                trt_cache_dir=trt_cache,
            )
        )
    return heads


def read_frames(video: str, start: int, n: int) -> list:
    import cv2  # lazy

    cap = cv2.VideoCapture(video)
    if start > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    frames = []
    while len(frames) < n:
        ok, img = cap.read()
        if not ok:
            break
        frames.append(img)
    cap.release()
    return frames


def rows_equal(a: np.ndarray, b: np.ndarray) -> bool:
    return a.shape == b.shape and (a.shape[0] == 0 or bool(np.array_equal(a, b)))


def run_config(name: str, heads: dict, frames: list, parallel: bool, warmup: int = 20):
    import torch  # lazy

    runner = MultiHeadRunner(heads, parallel=parallel)
    for img in frames[:warmup]:
        runner.predict_all(img)
    for h in heads.values():
        h.timings.__init__()
    runner.frames = 0
    runner.upload_s = runner.prepare_s = runner.run_s = 0.0
    out = []
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for img in frames:
        out.append(runner.predict_all(img))
    torch.cuda.synchronize()
    total = time.perf_counter() - t0
    runner.close()
    return out, {
        "config": name,
        "end_to_end_ms": round(1000 * total / len(frames), 3),
        "fps": round(len(frames) / total, 2),
        **runner.timings(),
    }


def run_baseline(heads: dict, frames: list, warmup: int = 20):
    import torch  # lazy

    for img in frames[:warmup]:
        for h in heads.values():
            h.predict(img)
    for h in heads.values():
        h.timings.__init__()
    out = []
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for img in frames:
        out.append({name: h.predict(img) for name, h in heads.items()})
    torch.cuda.synchronize()
    total = time.perf_counter() - t0
    return out, {
        "config": "baseline",
        "end_to_end_ms": round(1000 * total / len(frames), 3),
        "fps": round(len(frames) / total, 2),
        "heads": {name: h.timings.as_ms_per_frame() for name, h in heads.items()},
    }


def compare_exact(ref: list, other: list) -> dict:
    per_head = {}
    for name in ref[0].keys():
        eq = sum(1 for a, b in zip(ref, other) if rows_equal(a[name], b[name]))
        per_head[name] = {"frames": len(ref), "identical": eq}
    return per_head


def compare_tolerant(ref: list, other: list) -> dict:
    per_head = {}
    for name in ref[0].keys():
        res = TolerantParity(match_iou=0.5, coord_tol_px=2.0, conf_tol=0.02)
        for i, (a, b) in enumerate(zip(ref, other)):
            ra = [list(map(float, r)) for r in a[name]]
            rb = [list(map(float, r)) for r in b[name]]
            if compare_gm_frame_tolerant(ra, rb, i, res):
                res.frames_within_tolerance += 1
            res.frames_compared += 1
        s = res.summary()
        s.pop("first_diffs", None)
        per_head[name] = s
    return per_head


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--weights-dir", required=True)
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument(
        "--configs", default="baseline,shared,parallel", help="comma list incl. optional tensorrt"
    )
    ap.add_argument("--trt-cache", default="out/trt_cache")
    ap.add_argument("--out", default="out/gm_bench.json")
    a = ap.parse_args()

    frames = read_frames(a.video, a.start, a.frames)
    print(f"frames: {len(frames)} from {a.video} (start {a.start})")
    configs = [c.strip() for c in a.configs.split(",") if c.strip()]
    report = {
        "video": a.video,
        "start": a.start,
        "frames": len(frames),
        "results": [],
        "parity_vs_baseline": {},
    }

    heads = make_heads(a.weights_dir, "cuda", a.trt_cache)
    ref, res = run_baseline(heads, frames)
    report["results"].append(res)
    print(json.dumps(res))
    for cfg in configs:
        if cfg == "baseline":
            continue
        if cfg in ("shared", "parallel"):
            out, res = run_config(cfg, heads, frames, parallel=(cfg == "parallel"))
            report["parity_vs_baseline"][cfg] = compare_exact(ref, out)
        elif cfg == "tensorrt":
            trt_heads = make_heads(a.weights_dir, "tensorrt", a.trt_cache)
            out, res = run_config("tensorrt", trt_heads, frames, parallel=False)
            report["parity_vs_baseline"]["tensorrt"] = compare_tolerant(ref, out)
            out2, res2 = run_config("tensorrt_parallel", trt_heads, frames, parallel=True)
            report["parity_vs_baseline"]["tensorrt_parallel"] = compare_exact(out, out2)
            report["results"].append(res2)
            print(json.dumps(res2))
        else:
            raise SystemExit(f"unknown config {cfg}")
        report["results"].append(res)
        print(json.dumps(res))
        print("parity:", json.dumps(report["parity_vs_baseline"][cfg])[:600])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
