"""Multi-head runner: the three production detector heads (GM, chocks, vehicle) on one uploaded frame.

Zero-output-change optimizations over running each head with `predict()`:
  * one host→device upload per frame (uint8) shared by all heads;
  * one letterbox preparation per distinct input size (GM and vehicle share 1088×1088; chocks is 1280×1280);
  * optional thread-level parallelism: each ONNX session runs on its own CUDA stream, so with batch-1 models the
    GPU work of the heads overlaps (the postprocess still happens on torch's default stream, one head at a time).
Results are byte-identical to the sequential path because every head sees exactly the same input tensor and runs the
same session; only scheduling changes.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np


@dataclass
class MultiHeadRunner:
    heads: dict  # name -> YoloV8Onnx (insertion order = output order)
    parallel: bool = False
    _pool: ThreadPoolExecutor | None = field(default=None, repr=False)
    frames: int = 0
    upload_s: float = 0.0
    prepare_s: float = 0.0
    run_s: float = 0.0

    def __post_init__(self):
        if self.parallel and self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=len(self.heads))

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None

    # ---------------------------------------------------------------- per frame
    def predict_all(self, image_bgr_hwc: np.ndarray) -> dict:
        """Returns {head name: float32 (N, 6) rows} for one frame."""
        first = next(iter(self.heads.values()))
        t0 = time.perf_counter()
        dev = first.to_device_tensor(image_bgr_hwc)
        t1 = time.perf_counter()

        # one letterbox per distinct input size; heads of the same size share the tensor and the geometry
        prepared: dict = {}
        for name, head in self.heads.items():
            size = head.input_size
            if size not in prepared:
                prepared[size] = (head, head.prepare(dev))
            else:
                head.adopt_geometry(prepared[size][0])
        t2 = time.perf_counter()

        if self.parallel and len(self.heads) > 1:
            futures = {
                name: self._pool.submit(head.predict_prepared, prepared[head.input_size][1])
                for name, head in self.heads.items()
            }
            rows = {name: fut.result() for name, fut in futures.items()}
        else:
            rows = {
                name: head.predict_prepared(prepared[head.input_size][1]) for name, head in self.heads.items()
            }
        t3 = time.perf_counter()

        self.frames += 1
        self.upload_s += t1 - t0
        self.prepare_s += t2 - t1
        self.run_s += t3 - t2
        return rows

    def timings(self) -> dict:
        n = max(self.frames, 1)
        return {
            "upload_ms": round(1000 * self.upload_s / n, 3),
            "prepare_ms": round(1000 * self.prepare_s / n, 3),
            "run_ms_all_heads": round(1000 * self.run_s / n, 3),
            "parallel": self.parallel,
            "heads": {name: head.timings.as_ms_per_frame() for name, head in self.heads.items()},
        }
