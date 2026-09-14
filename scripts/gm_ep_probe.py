"""Probe which execution provider / cuDNN algorithm search really runs the GM heads, and what each costs.

Background: the first 600-frame benchmark printed `Conv ... running in Fallback mode` for the CUDA provider with
`cudnn_conv_algo_search=DEFAULT` and `nvinfer_10.dll is missing` for the TensorRT provider — so neither the baseline
nor the "tensorrt" numbers can be trusted until the provider that actually executed is known.

For every configuration it creates a fresh session for ONE head, prints `session.get_providers()`, runs N frames and
reports ms/frame plus exact-row parity against the first configuration.

    python scripts/gm_ep_probe.py --video ... --weights external/general_model_prod/weights/GM_yolov8m_best_augmentation_march2024.onnx
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def add_tensorrt_dll_dir() -> str | None:
    """pip `tensorrt_cu13_libs` puts nvinfer_10.dll under site-packages/tensorrt_libs — not on the DLL search path."""
    try:
        import tensorrt_libs  # noqa: F401

        d = os.path.dirname(tensorrt_libs.__file__)
    except Exception:
        hits = glob.glob(os.path.join(sys.prefix, "Lib", "site-packages", "tensorrt_libs"))
        if not hits:
            return None
        d = hits[0]
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(d)
    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--input", type=int, default=1088)
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--start", type=int, default=3600)
    ap.add_argument("--trt-cache", default="out/trt_cache")
    ap.add_argument("--out", default="out/gm_ep_probe.json")
    a = ap.parse_args()

    trt_dir = add_tensorrt_dll_dir()
    import onnxruntime as ort
    import torch

    from pf.gm.onnx_detector import YoloV8Onnx, YoloV8OnnxConfig, tensorrt_provider
    from scripts.gm_bench import read_frames, rows_equal

    info = {
        "ort_version": ort.__version__,
        "ort_build": ort.get_build_info(),
        "ort_available_providers": ort.get_available_providers(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "torch_cudnn": torch.backends.cudnn.version(),
        "gpu": torch.cuda.get_device_name(0),
        "tensorrt_dll_dir": trt_dir,
    }
    print(json.dumps(info, indent=1))
    frames = read_frames(a.video, a.start, a.frames)

    configs = {
        "cuda_default": [("CUDAExecutionProvider", {"cudnn_conv_use_max_workspace": "1", "cudnn_conv_algo_search": "DEFAULT"}), "CPUExecutionProvider"],
        "cuda_heuristic": [("CUDAExecutionProvider", {"cudnn_conv_use_max_workspace": "1", "cudnn_conv_algo_search": "HEURISTIC"}), "CPUExecutionProvider"],
        "cuda_exhaustive": [("CUDAExecutionProvider", {"cudnn_conv_use_max_workspace": "1", "cudnn_conv_algo_search": "EXHAUSTIVE"}), "CPUExecutionProvider"],
        "cuda_v1_plain": [("CUDAExecutionProvider", {}), "CPUExecutionProvider"],
        "tensorrt": [tensorrt_provider(a.trt_cache), ("CUDAExecutionProvider", {"cudnn_conv_algo_search": "EXHAUSTIVE"}), "CPUExecutionProvider"],
    }
    results = {"info": info, "frames": len(frames), "configs": {}}
    ref = None
    for name, providers in configs.items():
        print("=== config", name, flush=True)
        try:
            cfg = YoloV8OnnxConfig(weights=a.weights, input_shape=(a.input, a.input), providers=providers)
            t0 = time.perf_counter()
            head = YoloV8Onnx(cfg)
            build_s = time.perf_counter() - t0
            used = head.session.get_providers()
            for img in frames[:15]:
                head.predict(img)
            head.timings.__init__()
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            out = [head.predict(img) for img in frames]
            torch.cuda.synchronize()
            total = time.perf_counter() - t0
            r = {
                "providers_used": used,
                "session_build_s": round(build_s, 1),
                "ms_per_frame": round(1000 * total / len(frames), 3),
                **head.timings.as_ms_per_frame(),
            }
            if ref is None:
                ref = out
                r["identical_to_first"] = len(frames)
            else:
                r["identical_to_first"] = sum(1 for x, y in zip(ref, out) if rows_equal(x, y))
            del head
        except Exception as e:  # noqa: BLE001
            r = {"error": f"{type(e).__name__}: {str(e)[:400]}"}
        results["configs"][name] = r
        print(json.dumps(r), flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
