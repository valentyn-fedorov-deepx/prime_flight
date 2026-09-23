"""Benchmark one node against the machine the real-time measurements were taken on. Copy this file into a pod and run it.

The real-time numbers of `docs/analysis/rt_module_cost.md` and `rt_environment.md` were measured on an RTX 5070 Ti with
8 cores at 4.7 GHz. Sizing a production pod (`cluster_pod_max_resources.xlsx`: Tesla T4, 3.92 vCPU of an Intel Haswell at
2.30 GHz, 12 GB) from them needs two factors that were estimated, not measured: how much slower the T4 is on the GM heads,
and how much slower a pod core is. This script measures both in one run, with no dependency on this repository:

  * GPU: the three production detector heads (the same ONNX files the GM job already has) at their production input sizes,
    one by one and all three from threads the way the branch runs them, after a warm-up;
  * CPU: one thread and four threads of the same integer/float loop, so a core of the node can be compared with a core here.

    pip install onnxruntime-gpu numpy            # in the pod, if they are not there already
    python node_bench.py --weights-dir /path/to/weights [--frames 200] [--out node_bench.json]

Send back the JSON (or the printed summary). The reference numbers of this machine are in the script (`REFERENCE`), so the
output already carries the factors.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HEADS = {  # name: (weights file, input size, what the real-time branch runs)
    "gm": ("GM_yolov8m_best_augmentation_march2024.onnx", 1088),
    "chocks": ("chocks_v4.3_200ep_yolov8.onnx", 1280),
    "vehicle": ("VM_yolov8m_last_september2023.onnx", 1088),
}
# measured on the machine of the real-time campaign (RTX 5070 Ti 16 GB, Ryzen 8 x 4.7 GHz, onnxruntime-gpu 1.29,
# fp16 ONNX, CUDA EP): ms per frame with the card kept busy, and the CPU loop below
REFERENCE = {  # this script, 23.09, on the machine of the real-time campaign
    "machine": "RTX 5070 Ti 16 GB (300 W) + 8 cores at 4.7 GHz, onnxruntime-gpu 1.29, CUDA EP, fp16 ONNX",
    "heads_ms": {"gm": 4.27, "chocks": 5.59, "vehicle": 8.31, "all_three_parallel": 13.63},
    "cpu_loop_per_s_1_thread": 17_100_000, "cpu_loop_per_s_4_workers": 67_200_000,
    "budget_ms_per_frame": 125.0,
    "note": "the heads here are pure inference on a tensor already on the card; the branch also pays upload, letterbox and "
            "post-processing, which is why its GM step is 19.2 ms with the three heads",
}


def cpu_loop(seconds_target: float = 2.0) -> float:
    """Iterations per second of a plain mixed integer/float loop (one thread)."""
    n, acc, t0 = 0, 0.0, time.perf_counter()
    while time.perf_counter() - t0 < seconds_target:
        for i in range(10000):
            acc += (i * i % 7) ** 0.5
        n += 10000
    return n / (time.perf_counter() - t0)


def cpu_bench(workers: int) -> float:
    """The same loop in `workers` processes: what the node's threads really add (the branch runs process per module)."""
    from concurrent.futures import ProcessPoolExecutor

    try:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            return sum(pool.map(cpu_loop, [2.0] * workers))
    except Exception as e:
        print(f"parallel CPU loop failed ({type(e).__name__}); threads instead", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return sum(pool.map(cpu_loop, [2.0] * workers))


def add_dll_dirs() -> list:
    """Windows only: the CUDA and cuDNN libraries of the pip nvidia packages are not on the DLL search path."""
    added = []
    if not hasattr(os, "add_dll_directory"):
        return added
    import site

    for root in site.getsitepackages():
        for folder in ("nvidia", "tensorrt_libs"):
            base = os.path.join(root, folder)
            for path, dirs, files in os.walk(base) if os.path.isdir(base) else []:
                if any(f.endswith(".dll") for f in files):
                    try:
                        os.add_dll_directory(path)
                        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
                        added.append(path)
                    except OSError:
                        pass
    return added


def gpu_bench(weights_dir: str, frames: int) -> dict:
    add_dll_dirs()
    try:  # torch ships the CUDA and cuDNN libraries and loads them into the process; onnxruntime then finds them
        import torch  # noqa: F401
    except Exception:
        pass
    import onnxruntime as ort

    providers = [("CUDAExecutionProvider", {"device_id": 0, "cudnn_conv_algo_search": "EXHAUSTIVE"}), "CPUExecutionProvider"]
    sessions, inputs = {}, {}
    for name, (weights, size) in HEADS.items():
        path = os.path.join(weights_dir, weights)
        if not os.path.exists(path):
            print(f"missing: {path}", flush=True)
            continue
        opts = ort.SessionOptions()
        sessions[name] = ort.InferenceSession(path, opts, providers=providers)
        meta = sessions[name].get_inputs()[0]
        dtype = np.float16 if "float16" in meta.type else np.float32
        inputs[name] = {meta.name: np.random.rand(1, 3, size, size).astype(dtype)}
    if not sessions:
        return {"error": "no weights found"}
    used = sessions[next(iter(sessions))].get_providers()

    def run(name: str) -> None:
        sessions[name].run(None, inputs[name])

    out: dict = {"providers": used, "frames": frames, "heads_ms": {}}
    for name in sessions:  # warm-up: the first calls build the plan
        for _ in range(10):
            run(name)
    for name in sessions:
        times = []
        for _ in range(frames):
            t0 = time.perf_counter()
            run(name)
            times.append(1000 * (time.perf_counter() - t0))
        out["heads_ms"][name] = {"mean": round(statistics.mean(times), 2), "p95": round(sorted(times)[int(0.95 * len(times))], 2)}
    with ThreadPoolExecutor(max_workers=len(sessions)) as pool:  # the branch runs the heads from threads, one frame at a time
        for _ in range(10):
            list(pool.map(run, sessions))
        times = []
        for _ in range(frames):
            t0 = time.perf_counter()
            list(pool.map(run, sessions))
            times.append(1000 * (time.perf_counter() - t0))
    out["heads_ms"]["all_three_parallel"] = {"mean": round(statistics.mean(times), 2),
                                             "p95": round(sorted(times)[int(0.95 * len(times))], 2)}
    return out


def gpu_facts() -> dict:
    try:
        fields = "name,memory.total,memory.used,clocks.max.graphics,power.limit,driver_version"
        text = subprocess.run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=30).stdout.strip()
        return dict(zip(fields.split(","), [x.strip() for x in text.split(",")]))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights-dir", default="weights", help="folder with the three production ONNX heads")
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--cpu-threads", type=int, default=4, help="threads of the CPU loop (the pod has 4)")
    ap.add_argument("--out", default="node_bench.json")
    a = ap.parse_args()

    result = {"when": time.strftime("%Y-%m-%d %H:%M"), "host": platform.node(), "python": sys.version.split()[0],
              "cpu": platform.processor(), "cpu_count": os.cpu_count(), "gpu": gpu_facts(), "reference": REFERENCE}
    print("CPU...", flush=True)
    result["cpu_loop_per_s_1_thread"] = round(cpu_loop(), 1)
    result[f"cpu_loop_per_s_{a.cpu_threads}_workers"] = round(cpu_bench(a.cpu_threads), 1)
    if REFERENCE["cpu_loop_per_s_1_thread"]:
        result["cpu_core_against_the_reference"] = round(result["cpu_loop_per_s_1_thread"] / REFERENCE["cpu_loop_per_s_1_thread"], 2)
    print("GPU...", flush=True)
    result["gpu_bench"] = gpu_bench(a.weights_dir, a.frames)

    heads = (result["gpu_bench"].get("heads_ms") or {}).get("all_three_parallel", {}).get("mean")
    if heads:
        result["slower_than_the_reference_card"] = round(heads / REFERENCE["heads_ms"]["all_three_parallel"], 2)
        result["frames_per_second_the_heads_alone_allow"] = round(1000.0 / heads, 1)
        result["heads_share_of_the_125_ms_budget"] = round(heads / REFERENCE["budget_ms_per_frame"], 2)
    json.dump(result, open(a.out, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: v for k, v in result.items() if k != "reference"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
