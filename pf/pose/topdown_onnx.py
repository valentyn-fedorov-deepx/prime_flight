"""Top-down SimCC pose on ONNX Runtime (RTMPose / DWPose exports) with mmpose 1.x pre- and post-processing.

The pose modules call `inference_topdown(model, full_image, boxes, bbox_format='xyxy')`. The crop mmpose makes there is
reproduced exactly: box -> centre and scale with padding 1.25 (GetBBoxCenterScale), the scale widened to the model's
aspect ratio, one affine warp of the full image with INTER_LINEAR (TopdownAffine), BGR->RGB and the ImageNet mean/std
(PoseDataPreprocessor). Decoding is mmpose's SimCC rule (`get_simcc_maximum`): argmax per axis, score = the smaller of
the two maxima, location -1 where the score is <= 0, divided by the split ratio, then mapped back to the image with the
crop's centre and scale (`TopdownPoseEstimator.add_pred_to_datasample`). One forward pass per box: the exports carry no
flip test (`flip_test=True` optional, mmpose's RTMCCHead rule).

gse-chocks runs the same RTMPose-l file differently (`onnx_model_utils.py`): it cuts the box out first (the padding is
then black, not image) and feeds BGR. This runner follows mmpose, i.e. what the HRNet / SimCC modules feed today.

    pose = SimccTopdown(MODELS["rtmpose-l"])
    keypoints, scores, centers, scales = pose(frame_bgr, boxes_xyxy)   # (N,K,2) image px, (N,K)
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Weight files already used by production modules (not in git; the module checkouts under external/ hold them).
MODELS = {
    # RTMPose-l body7 256x192, COCO-17 (gse-chocks@per_component_improvement, weights/rtmpose-l-4dba18fc.onnx)
    "rtmpose-l": os.path.join(ROOT, "external", "_branches", "gse-chocks@per_component_improvement", "weights",
                              "rtmpose-l-4dba18fc.onnx"),
    # DWPose-l whole body 384x288, COCO-WholeBody 133 (first 17 = COCO body) (handrails-on-gse-being-used)
    "dwpose-l": os.path.join(ROOT, "external", "handrails-on-gse-being-used", "weights", "dw-ll_ucoco_384.onnx"),
}

COCO_FLIP_INDICES = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)


def resolve_model(name_or_path: str) -> str:
    path = MODELS.get(name_or_path, name_or_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"pose model not found: {name_or_path} ({path})")
    return path


def bbox_xyxy2cs(bboxes: np.ndarray, padding: float = 1.25) -> tuple[np.ndarray, np.ndarray]:
    """mmpose `bbox_xyxy2cs` for (N, 4) boxes."""
    x1, y1, x2, y2 = np.hsplit(bboxes[:, :4], [1, 2, 3])
    center = np.hstack([x1 + x2, y1 + y2]) * 0.5
    scale = np.hstack([x2 - x1, y2 - y1]) * padding
    return center, scale


def fix_aspect_ratio(scale: np.ndarray, aspect_ratio: float) -> np.ndarray:
    """mmpose `TopdownAffine._fix_aspect_ratio`."""
    w, h = np.hsplit(scale, [1])
    return np.where(w > h * aspect_ratio, np.hstack([w, w / aspect_ratio]), np.hstack([h * aspect_ratio, h]))


def warp_matrix(center: np.ndarray, scale: np.ndarray, output_size: tuple[int, int]) -> np.ndarray:
    """mmpose `get_warp_matrix` with rot = 0, shift = 0, fix_aspect_ratio = True."""
    src_w = scale[0]
    dst_w, dst_h = output_size
    src = np.zeros((3, 2), dtype=np.float32)
    dst = np.zeros((3, 2), dtype=np.float32)
    src[0, :] = center
    src[1, :] = center + np.array([src_w * -0.5, 0.0])
    dst[0, :] = [dst_w * 0.5, dst_h * 0.5]
    dst[1, :] = np.array([dst_w * 0.5, dst_h * 0.5]) + np.array([dst_w * -0.5, 0.0])
    for m in (src, dst):  # third point: (a - b) rotated by 90 degrees around b
        d = m[0, :] - m[1, :]
        m[2, :] = m[1, :] + np.r_[-d[1], d[0]]
    return cv2.getAffineTransform(np.float32(src), np.float32(dst))


def simcc_maximum(simcc_x: np.ndarray, simcc_y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """mmpose `get_simcc_maximum` (no softmax) for (N, K, Wx) / (N, K, Wy)."""
    n, k, _ = simcc_x.shape
    sx = simcc_x.reshape(n * k, -1)
    sy = simcc_y.reshape(n * k, -1)
    locs = np.stack((np.argmax(sx, axis=1), np.argmax(sy, axis=1)), axis=-1).astype(np.float32)
    max_x = np.amax(sx, axis=1)
    max_y = np.amax(sy, axis=1)
    vals = np.minimum(max_x, max_y)
    locs[vals <= 0.0] = -1
    return locs.reshape(n, k, 2), vals.reshape(n, k)


@dataclass
class PoseTimings:
    calls: int = 0
    boxes: int = 0
    preprocess_s: float = 0.0
    run_s: float = 0.0
    decode_s: float = 0.0
    batch_sizes: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        total = self.preprocess_s + self.run_s + self.decode_s
        return {
            "calls": self.calls, "boxes": self.boxes,
            "preprocess_s": round(self.preprocess_s, 3), "run_s": round(self.run_s, 3),
            "decode_s": round(self.decode_s, 3), "total_s": round(total, 3),
            "ms_per_call": round(1000 * total / self.calls, 3) if self.calls else None,
            "ms_per_box": round(1000 * total / self.boxes, 3) if self.boxes else None,
            "batch_sizes": dict(sorted(self.batch_sizes.items())),
        }


class SimccTopdown:
    """One ONNX SimCC top-down model; call with a BGR image and (N, 4+) xyxy boxes."""

    def __init__(self, model: str, device: str = "cuda", keypoints: int | None = 17, to_rgb: bool = True,
                 flip_test: bool = False, padding: float = 1.25, fixed_batch: int = 4):
        import onnxruntime as ort  # lazy: unit tests of the geometry do not need it

        self.path = resolve_model(model)
        with open(self.path, "rb") as fh:
            self.sha256_16 = hashlib.sha256(fh.read()).hexdigest()[:16]
        providers = ["CPUExecutionProvider"] if device == "cpu" else ["CUDAExecutionProvider", "CPUExecutionProvider"]
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(self.path, opts, providers=providers)
        self.providers = list(self.session.get_providers())
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.input_size = (int(inp.shape[3]), int(inp.shape[2]))  # (w, h)
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.keypoints = keypoints
        self.to_rgb = to_rgb
        self.flip_test = flip_test
        self.padding = padding
        self.fixed_batch = fixed_batch
        self.split_ratio: float | None = None  # read from the first output: simcc_x width / input width
        self.timings = PoseTimings()

    def describe(self) -> dict:
        return {"model": self.path, "sha256_16": self.sha256_16, "providers": self.providers,
                "input_size_wh": list(self.input_size), "keypoints_out": self.keypoints, "to_rgb": self.to_rgb,
                "flip_test": self.flip_test, "padding": self.padding, "fixed_batch": self.fixed_batch,
                "split_ratio": self.split_ratio}

    def crops(self, img: np.ndarray, bboxes: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        w, h = self.input_size
        center, scale = bbox_xyxy2cs(np.asarray(bboxes, dtype=np.float64).reshape(-1, np.shape(bboxes)[-1]), self.padding)
        scale = fix_aspect_ratio(scale, w / h)
        batch = np.empty((len(center), h, w, 3), dtype=np.uint8)
        for i in range(len(center)):
            batch[i] = cv2.warpAffine(img, warp_matrix(center[i], scale[i], (w, h)), (w, h), flags=cv2.INTER_LINEAR)
        return batch, center, scale

    def _forward(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Every run has the same input shape: chunks of `fixed_batch` boxes, the last one padded with zeros.

        ONNX Runtime's CUDA provider pays about 30 ms whenever a session's input shape differs from its previous run
        (measured: batch sizes alternating 1-6 -> 33 ms per run; a fixed batch of 4 -> 5 ms), whatever the cuDNN
        search mode. The boxes are independent in the network, so padding does not change their outputs."""
        b = self.fixed_batch or len(x)
        sx, sy = [], []
        for i in range(0, len(x), b):
            chunk = x[i:i + b]
            m = len(chunk)
            if m < b:
                chunk = np.concatenate([chunk, np.zeros((b - m,) + chunk.shape[1:], dtype=chunk.dtype)])
            ox, oy = self.session.run(self.output_names, {self.input_name: chunk})[:2]
            sx.append(ox[:m])
            sy.append(oy[:m])
        return (np.concatenate(sx), np.concatenate(sy)) if len(sx) > 1 else (sx[0], sy[0])

    def __call__(self, img: np.ndarray, bboxes) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        bboxes = np.asarray(bboxes)
        n = 0 if bboxes.size == 0 else len(bboxes.reshape(-1, bboxes.shape[-1]))
        k = self.keypoints or 0
        if n == 0:
            return (np.zeros((0, k, 2), np.float32), np.zeros((0, k), np.float32),
                    np.zeros((0, 2)), np.zeros((0, 2)))
        t0 = time.perf_counter()
        batch, center, scale = self.crops(img, bboxes)
        if self.to_rgb:
            batch = batch[..., ::-1]
        x = ((batch.astype(np.float32) - MEAN) / STD).transpose(0, 3, 1, 2)
        if self.flip_test:
            x = np.concatenate([x, x[..., ::-1]])
        x = np.ascontiguousarray(x)
        t1 = time.perf_counter()
        sx, sy = self._forward(x)
        t2 = time.perf_counter()
        if self.split_ratio is None:
            self.split_ratio = sx.shape[-1] / self.input_size[0]
        if self.flip_test:  # mmpose RTMCCHead: flip_vectors(x[:, flip_indices].flip(-1), y[:, flip_indices]), mean
            if sx.shape[1] != 17 and not (self.keypoints and self.keypoints <= 17):
                raise ValueError("flip test is implemented for the COCO-17 body keypoints only")
            fi = COCO_FLIP_INDICES + list(range(len(COCO_FLIP_INDICES), sx.shape[1]))  # body part is exact
            sx = (sx[:n] + sx[n:][:, fi, ::-1]) * 0.5
            sy = (sy[:n] + sy[n:][:, fi]) * 0.5
        if self.keypoints:
            sx, sy = sx[:, :self.keypoints], sy[:, :self.keypoints]
        locs, scores = simcc_maximum(sx, sy)
        kpts = locs / self.split_ratio
        inp = np.array(self.input_size, dtype=np.float32)
        kpts = (kpts / inp * scale[:, None, :] + center[:, None, :] - 0.5 * scale[:, None, :]).astype(np.float32)
        t3 = time.perf_counter()
        tm = self.timings
        tm.calls += 1
        tm.boxes += n
        tm.preprocess_s += t1 - t0
        tm.run_s += t2 - t1
        tm.decode_s += t3 - t2
        tm.batch_sizes[n] = tm.batch_sizes.get(n, 0) + 1
        return kpts, scores.astype(np.float32), center, scale
