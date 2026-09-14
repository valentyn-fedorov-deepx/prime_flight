"""YOLOv8 ONNX detector — numerically faithful port of `general_model/scripts/new_model.py:231-439` (`YOLOv8_onnx`).

What is kept identical (required for bitwise parity of raw rows, ADR-001 §2):
  * static square input (1088 for GM / vehicle, 1280 for chocks), letterbox geometry computed once from the first frame
    (`pf.gm.geometry.letterbox_geometry`), bilinear resize with `align_corners=False`, pad value 114/255;
  * fp16 input via IO binding, fp16 output tensor;
  * confidence = max over class scores (columns 4:), threshold `>` conf_thres, boxes rebuilt from cx/cy/w/h in the
    SAME dtype order as v1 (fp16 arithmetic, then `- padding` and `* factor` → float32);
  * class-agnostic `torchvision.ops.nms` at iou_thres (v1: 0.7), detections ordered by NMS output (score-descending).

What changed (no effect on values): a single vectorized gather + one device→host copy instead of a Python loop over
indices with per-element synchronisations; no per-frame prints; optional timing counters. torch / onnxruntime are
imported lazily so the package stays importable on machines without a GPU stack (fast CI gates).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from pf.gm.geometry import Letterbox, letterbox_geometry


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
    # production GM (commit a0157a4, deployment_v_py3_10) converts BGR→RGB before normalisation
    # (`scripts/new_model.py:308-309`); the reviewed master pin (13a4ddc) fed BGR. Default = production.
    bgr_to_rgb: bool = True
    providers: list = field(
        default_factory=lambda: [
            (
                "CUDAExecutionProvider",
                {"cudnn_conv_use_max_workspace": "1", "cudnn_conv_algo_search": "DEFAULT"},
            ),
            "CPUExecutionProvider",
        ]
    )


class YoloV8Onnx:
    """Stateless per frame except the cached letterbox geometry (v1 caches it from the first frame too)."""

    def __init__(self, cfg: YoloV8OnnxConfig, session_options=None):
        import onnxruntime  # lazy
        import torch  # lazy

        self.cfg = cfg
        self._torch = torch
        opts = session_options
        if opts is None:
            opts = onnxruntime.SessionOptions()
            opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = onnxruntime.InferenceSession(cfg.weights, opts, providers=cfg.providers)
        self.binding = self.session.io_binding()
        self._input_name = self.session.get_inputs()[0].name
        self._output_name = self.session.get_outputs()[0].name
        self._output_shape = tuple(self.session.get_outputs()[0].shape)
        self.geometry: Letterbox | None = None
        self._x_factor = None
        self._y_factor = None
        self._iou_t = torch.tensor(cfg.iou_thres, dtype=torch.float32, device=self._device)
        self.timings = DetectorTimings()

    # ---------------------------------------------------------------- helpers
    @property
    def _device(self):
        return self._torch.device(self.cfg.device_type, self.cfg.device_id)

    def _ensure_geometry(self, img_h: int, img_w: int) -> Letterbox:
        if self.geometry is None:
            self.geometry = letterbox_geometry(img_w, img_h, self.cfg.input_shape[0], self.cfg.input_shape[1])
            t = self._torch
            self._x_factor = t.tensor(self.geometry.x_factor, dtype=t.float32, device=self._device)
            self._y_factor = t.tensor(self.geometry.y_factor, dtype=t.float32, device=self._device)
        return self.geometry

    def to_device_tensor(self, image_bgr_hwc: np.ndarray):
        """Same conversion as v1 `main.py:529-532`: numpy HWC uint8 → float32 → device → float16."""
        t = self._torch
        return t.from_numpy(image_bgr_hwc).float().to(self._device).half()

    def preprocess(self, image_hwc_half, geom: Letterbox):
        """Exact op sequence of v1 `preprocess()`: clone, HWC→CHW, [BGR→RGB in production], /255 in fp16, bilinear resize, constant pad."""
        t = self._torch
        x = image_hwc_half.clone().permute(2, 0, 1)
        if self.cfg.bgr_to_rgb:
            x = x[[2, 1, 0], :, :]
        x /= 255.0
        x = t.nn.functional.interpolate(
            x.unsqueeze(0), size=(geom.new_h, geom.new_w), mode="bilinear", align_corners=False
        )
        x = t.nn.functional.pad(x, geom.padding, value=114 / 255)
        return x.contiguous()

    # ---------------------------------------------------------------- inference
    def predict(self, image) -> np.ndarray:
        """image: numpy HWC uint8 BGR frame, or a device tensor already produced by `to_device_tensor`.

        Returns float32 ndarray (N, 6): [x1, y1, x2, y2, conf, class_id] in source pixels, NMS order.
        """
        t = self._torch
        t0 = time.perf_counter()
        if isinstance(image, np.ndarray):
            image = self.to_device_tensor(image)
        geom = self._ensure_geometry(int(image.shape[0]), int(image.shape[1]))
        x = self.preprocess(image, geom)

        self.binding.bind_input(
            name=self._input_name,
            device_type=self.cfg.device_type,
            device_id=self.cfg.device_id,
            element_type=np.float16,
            shape=tuple(x.shape),
            buffer_ptr=x.data_ptr(),
        )
        pred = t.empty(self._output_shape, dtype=t.float16, device=self._device).contiguous()
        self.binding.bind_output(
            name=self._output_name,
            device_type=self.cfg.device_type,
            device_id=self.cfg.device_id,
            element_type=np.float16,
            shape=tuple(pred.shape),
            buffer_ptr=pred.data_ptr(),
        )
        self.binding.synchronize_inputs()
        t1 = time.perf_counter()
        self.session.run_with_iobinding(self.binding)
        t2 = time.perf_counter()

        rows = self.postprocess(pred, geom)
        t3 = time.perf_counter()
        self.timings.frames += 1
        self.timings.preprocess_s += t1 - t0
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

        keep = torchvision.ops.nms(boxes, filtered_scores.float(), float(self._iou_t))
        out = t.cat(
            [
                boxes[keep],
                filtered_scores[keep].float().unsqueeze(1),
                filtered_class_ids[keep].float().unsqueeze(1),
            ],
            dim=1,
        )
        return out.cpu().numpy()
