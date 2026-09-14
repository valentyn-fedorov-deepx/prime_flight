"""YOLOv8 ONNX detector — numerically faithful port of `general_model/scripts/new_model.py:231-439` (`YOLOv8_onnx`,
production commit a0157a4) with zero-output-change speedups.

Kept identical (required for parity of raw rows, ADR-001 §2):
  * static square input (1088 GM / vehicle, 1280 chocks), letterbox geometry computed once from the first frame
    (`pf.gm.geometry.letterbox_geometry`), BGR→RGB (production), /255 in fp16, bilinear resize `align_corners=False`,
    pad value 114/255;
  * fp16 input via IO binding, fp16 output tensor;
  * confidence = max over class scores, threshold `>` conf_thres, boxes rebuilt in the SAME dtype order as v1
    (fp16 arithmetic, then `- padding`, `* factor` → float32);
  * class-agnostic `torchvision.ops.nms` at iou_thres (0.7), detections in NMS order (score-descending).

Speedups that do not change values:
  * the frame is uploaded as uint8 (6 MB) and converted to fp16 on the GPU — v1 converted to float32 on the CPU and
    uploaded 24 MB (uint8 → fp16 is exact either way);
  * a letterboxed input tensor can be shared by heads with the same input size (`prepare()` / `predict_prepared()`),
    so GM and the vehicle head preprocess once;
  * the output buffer is allocated once and rebound, not allocated per frame;
  * a vectorized gather + one device→host copy instead of a Python loop with per-element synchronisations.
`provider="cuda"` is the production path with the SAME session options as v1 (`scripts/new_model.py:232` passes plain
provider names, i.e. onnxruntime defaults: `cudnn_conv_algo_search=EXHAUSTIVE`). Forcing the "DEFAULT" heuristic search
instead made cuDNN 9.19 run every conv in "Fallback mode" on sm_120 — 2.6× slower AND different fp16 rounding
(`scripts/gm_ep_probe.py`); keep the v1 options. `provider="tensorrt"` is the fast path (fp16 engines, ~2.3× faster than
CUDA EP on the 5070 Ti) with different kernels → small numeric differences; it is validated with the tolerant parity
metric + the L2 module gate, never with exact parity. torch / onnxruntime are imported lazily.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import numpy as np

from pf.gm.geometry import Letterbox, letterbox_geometry

def cuda_provider(cudnn_conv_algo_search: str = "EXHAUSTIVE") -> tuple:
    """v1-equivalent CUDA provider. EXHAUSTIVE and max workspace are the onnxruntime defaults v1 relies on."""
    return (
        "CUDAExecutionProvider",
        {"cudnn_conv_use_max_workspace": "1", "cudnn_conv_algo_search": cudnn_conv_algo_search},
    )


CUDA_PROVIDER = cuda_provider()


def add_tensorrt_dll_dir() -> str | None:
    """Make the pip TensorRT libraries (`tensorrt_cu13_libs` → site-packages/tensorrt_libs/nvinfer_10.dll) loadable.

    onnxruntime's TensorRT provider DLL is resolved through the Windows DLL search path, which does not include that
    package directory; without this the provider silently falls back to CUDA (and prints an error to stderr).
    """
    try:
        import tensorrt_libs  # noqa: F401  (pip package, Windows/Linux)

        d = os.path.dirname(tensorrt_libs.__file__)
    except Exception:
        return None
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(d)
    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    return d


def tensorrt_provider(cache_dir: str) -> tuple:
    os.makedirs(cache_dir, exist_ok=True)
    add_tensorrt_dll_dir()
    return (
        "TensorrtExecutionProvider",
        {
            "trt_fp16_enable": True,
            "trt_engine_cache_enable": True,
            "trt_engine_cache_path": cache_dir,
            "trt_timing_cache_enable": True,
            "trt_timing_cache_path": cache_dir,
        },
    )


@dataclass
class DetectorTimings:
    frames: int = 0
    preprocess_s: float = 0.0
    inference_s: float = 0.0
    postprocess_s: float = 0.0

    def as_ms_per_frame(self) -> dict:
        n = max(self.frames, 1)
        return {
            "preprocess_ms": round(1000 * self.preprocess_s / n, 3),
            "inference_ms": round(1000 * self.inference_s / n, 3),
            "postprocess_ms": round(1000 * self.postprocess_s / n, 3),
        }


@dataclass
class YoloV8OnnxConfig:
    weights: str
    input_shape: tuple = (1088, 1088)  # (width, height) as in v1 `input_shape=[1088, 1088]`
    conf_thres: float = 0.35
    iou_thres: float = 0.7
    device_type: str = "cuda"
    device_id: int = 0
    provider: str = "cuda"  # "cuda" (production path, v1 session options) | "tensorrt" (fast path, tolerant parity)
    cudnn_conv_algo_search: str = "EXHAUSTIVE"  # onnxruntime default = v1; "DEFAULT"/"HEURISTIC" only for experiments
    trt_cache_dir: str = "out/trt_cache"
    # production GM (commit a0157a4, deployment_v_py3_10) converts BGR→RGB before normalisation
    # (`scripts/new_model.py:308-309`); the reviewed master pin (13a4ddc) fed BGR. Default = production.
    bgr_to_rgb: bool = True
    providers: list = field(default_factory=list)

    def resolved_providers(self) -> list:
        if self.providers:
            return self.providers
        cuda = cuda_provider(self.cudnn_conv_algo_search)
        if self.provider == "tensorrt":
            return [tensorrt_provider(self.trt_cache_dir), cuda, "CPUExecutionProvider"]
        return [cuda, "CPUExecutionProvider"]


class YoloV8Onnx:
    """One ONNX head. Stateless per frame except the cached letterbox geometry and the reusable output buffer."""

    def __init__(self, cfg: YoloV8OnnxConfig, session_options=None):
        import onnxruntime  # lazy
        import torch  # lazy

        self.cfg = cfg
        self._torch = torch
        opts = session_options
        if opts is None:
            opts = onnxruntime.SessionOptions()
            opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = onnxruntime.InferenceSession(cfg.weights, opts, providers=cfg.resolved_providers())
        self.providers_used = list(self.session.get_providers())
        if cfg.provider == "tensorrt" and self.providers_used[0] != "TensorrtExecutionProvider":
            raise RuntimeError(
                f"TensorRT provider requested but the session runs on {self.providers_used[0]} "
                "(TensorRT libraries not loadable?) — refusing to report TensorRT numbers for a CUDA run"
            )
        self.binding = self.session.io_binding()
        self._input_name = self.session.get_inputs()[0].name
        self._output_name = self.session.get_outputs()[0].name
        self._output_shape = tuple(self.session.get_outputs()[0].shape)
        self.geometry: Letterbox | None = None
        self._x_factor = None
        self._y_factor = None
        self._pred = torch.empty(self._output_shape, dtype=torch.float16, device=self._device).contiguous()
        self.timings = DetectorTimings()

    # ---------------------------------------------------------------- helpers
    @property
    def _device(self):
        return self._torch.device(self.cfg.device_type, self.cfg.device_id)

    @property
    def input_size(self) -> tuple:
        return tuple(self.cfg.input_shape)

    def _ensure_geometry(self, img_h: int, img_w: int) -> Letterbox:
        if self.geometry is None:
            self.geometry = letterbox_geometry(img_w, img_h, self.cfg.input_shape[0], self.cfg.input_shape[1])
            t = self._torch
            self._x_factor = t.tensor(self.geometry.x_factor, dtype=t.float32, device=self._device)
            self._y_factor = t.tensor(self.geometry.y_factor, dtype=t.float32, device=self._device)
        return self.geometry

    def to_device_tensor(self, image_bgr_hwc: np.ndarray):
        """uint8 HWC → device → fp16 (same values as v1's `float().cuda().half()`, a quarter of the PCIe traffic)."""
        t = self._torch
        return t.from_numpy(image_bgr_hwc).to(self._device).half()

    def prepare(self, image):
        """Letterboxed model input for this head's input size; shareable by every head with the same size.

        `image`: numpy HWC uint8 BGR frame or a device fp16 HWC tensor from `to_device_tensor`.
        Exact op sequence of v1 `preprocess()`: clone, HWC→CHW, [BGR→RGB], /255 in fp16, bilinear resize, constant pad.
        """
        t = self._torch
        if isinstance(image, np.ndarray):
            image = self.to_device_tensor(image)
        geom = self._ensure_geometry(int(image.shape[0]), int(image.shape[1]))
        x = image.clone().permute(2, 0, 1)
        if self.cfg.bgr_to_rgb:
            x = x[[2, 1, 0], :, :]
        x /= 255.0
        x = t.nn.functional.interpolate(
            x.unsqueeze(0), size=(geom.new_h, geom.new_w), mode="bilinear", align_corners=False
        )
        x = t.nn.functional.pad(x, geom.padding, value=114 / 255)
        return x.contiguous()

    def adopt_geometry(self, other: YoloV8Onnx) -> None:
        """Share the letterbox geometry of a head with the same input size (needed before `predict_prepared`)."""
        if self.geometry is None and other.geometry is not None:
            self._ensure_geometry(other.geometry.img_h, other.geometry.img_w)

    # ---------------------------------------------------------------- inference
    def predict(self, image) -> np.ndarray:
        """Full path for one head: preprocess → run → postprocess. Returns float32 (N, 6) rows in NMS order."""
        t0 = time.perf_counter()
        x = self.prepare(image)
        self.timings.preprocess_s += time.perf_counter() - t0
        return self.predict_prepared(x)

    def run(self, x) -> None:
        """Bind the prepared input and run the session; the result lands in `self._pred` (fp16, output shape)."""
        self.binding.bind_input(
            name=self._input_name,
            device_type=self.cfg.device_type,
            device_id=self.cfg.device_id,
            element_type=np.float16,
            shape=tuple(x.shape),
            buffer_ptr=x.data_ptr(),
        )
        self.binding.bind_output(
            name=self._output_name,
            device_type=self.cfg.device_type,
            device_id=self.cfg.device_id,
            element_type=np.float16,
            shape=tuple(self._pred.shape),
            buffer_ptr=self._pred.data_ptr(),
        )
        self.binding.synchronize_inputs()
        self.session.run_with_iobinding(self.binding)

    def predict_prepared(self, x) -> np.ndarray:
        """Run + postprocess on an input prepared by `prepare()` of a head with the same input size."""
        t1 = time.perf_counter()
        self.run(x)
        t2 = time.perf_counter()
        rows = self.postprocess(self._pred, self.geometry)
        t3 = time.perf_counter()
        self.timings.frames += 1
        self.timings.inference_s += t2 - t1
        self.timings.postprocess_s += t3 - t2
        return rows

    def postprocess(self, pred, geom: Letterbox) -> np.ndarray:
        """v1 `predict()` lines 400-432 with a vectorized gather (same values, same order)."""
        t = self._torch
        import torchvision  # lazy

        pred = t.squeeze(pred).permute(1, 0)  # (rows, 4 + nc), fp16
        classes_scores = pred[:, 4:]
        max_scores, class_ids = t.max(classes_scores, dim=1)
        mask = max_scores > self.cfg.conf_thres
        filtered_scores = max_scores[mask]
        filtered_class_ids = class_ids[mask]
        fb = pred[mask]
        if fb.shape[0] == 0:
            return np.zeros((0, 6), dtype=np.float32)

        px, py = geom.pad_x, geom.pad_y
        x = (((fb[:, 0] - fb[:, 2] / 2) - px) * self._x_factor).float()
        y = (((fb[:, 1] - fb[:, 3] / 2) - py) * self._y_factor).float()
        x2 = (((fb[:, 0] + fb[:, 2] / 2) - px) * self._x_factor).float()
        y2 = (((fb[:, 1] + fb[:, 3] / 2) - py) * self._y_factor).float()
        boxes = t.stack([x, y, x2, y2], dim=1).float()

        keep = torchvision.ops.nms(boxes, filtered_scores.float(), float(self.cfg.iou_thres))
        out = t.cat(
            [
                boxes[keep],
                filtered_scores[keep].float().unsqueeze(1),
                filtered_class_ids[keep].float().unsqueeze(1),
            ],
            dim=1,
        )
        return out.cpu().numpy()
