"""Camera type classifier (cone / wing) — exact port of general_model @a0157a4.

Source: `scripts/classifier_utils.py` (`trans`, `classifier_inference`) and `main.py:730-735` (model), `:924-947` (per-frame
vote), `:904-908` + `:1062-1063` (majority and confidence at the end of the video).

v1 behaviour kept on purpose:
  * timm `efficientnet_b0`, one output, weights `camera_cls_effnet_b0_october_v1.8.1.pt` (config key
    `camera_classifier_weights`). v1 creates the model with `pretrained=True`, which only downloads ImageNet weights that
    `load_state_dict` then overwrites entirely; the port uses `pretrained=False` — same parameters, no network access;
  * one vote per second-pass frame where the main aircraft is present and has arrived (the caller decides that);
  * crop rows 150:930 of the frame the second pass works on (the noise-preprocessed frame once an aircraft was seen);
  * `Image.fromarray(crop).convert('RGB')` on a BGR array — PIL treats the bytes as RGB, so the network sees BGR channel
    order, exactly like v1;
  * torchvision `Resize((224, 224))` on the PIL image, `ToTensor`, ImageNet `Normalize`, batch of one, `sigmoid >= 0.5` on
    the float32 output → cone.
Opt-in `transform="numpy"`: the same resize, then `ToTensor` + `Normalize` as float32 numpy operations — a bit-identical model
input computed on one thread (`numpy_input`).
"""

from __future__ import annotations

import os
import time

import numpy as np

CAMERA_WEIGHTS = "camera_cls_effnet_b0_october_v1.8.1.pt"
CROP_ROWS = (150, 930)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
TRANSFORMS = ("torchvision", "numpy")
_MEAN32 = np.array(IMAGENET_MEAN, dtype=np.float32).reshape(3, 1, 1)
_STD32 = np.array(IMAGENET_STD, dtype=np.float32).reshape(3, 1, 1)


def numpy_input(pil_resized, torch):
    """v1's `ToTensor` + `Normalize` as float32 numpy operations on the resized PIL image: /255, minus the float32 mean,
    divided by the float32 std. These are element-wise IEEE operations, so the tensor is bit-identical to torchvision's, and
    they run on one thread (torch's CPU intra-op threads made the same two ops cost ~40 ms per call on a saturated 8-thread
    CPU, against ~7.5 ms for the resize plus this; bit-identical on 40 real frames and in `tests/test_gm_camera.py`)."""
    a = np.asarray(pil_resized, dtype=np.uint8).transpose(2, 0, 1).astype(np.float32) / np.float32(255)
    return torch.from_numpy(np.ascontiguousarray((a - _MEAN32) / _STD32)).unsqueeze(0)


class CameraClassifier:
    def __init__(self, weights_dir: str, device: str = "cuda:0", weights_name: str = CAMERA_WEIGHTS,
                 transform: str = "torchvision"):
        """`transform`: 'torchvision' = v1's Compose (the exact port, default); 'numpy' = the same PIL resize followed by
        `numpy_input` — a bit-identical model input without torch CPU threads."""
        if transform not in TRANSFORMS:
            raise ValueError(f"transform must be one of {TRANSFORMS}, not {transform!r}")
        import timm
        import torch
        from torchvision import transforms

        self.torch = torch
        self.device = torch.device("cpu" if device == "cpu" else ("cuda:0" if device == "cuda" else device))
        model = timm.create_model("efficientnet_b0", pretrained=False, num_classes=1)
        state = torch.load(os.path.join(weights_dir, weights_name), map_location=self.device, weights_only=False)
        model.load_state_dict(state)
        model.to(self.device)
        model.eval()
        self.model = model
        self.trans = transforms.Compose(
            [transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)]
        )
        self.transform = transform
        self.resize = self.trans.transforms[0]  # the same Resize((224, 224)) for the numpy path
        self.sigmoid = torch.nn.Sigmoid()
        self.calls = 0
        self.prep_s = 0.0  # timers only (no effect on outputs): crop + PIL + transforms on the CPU
        self.gpu_s = 0.0  # upload + forward + sigmoid + the synchronising .item()
        self._t_prep_end = 0.0

    def input_tensor(self, frame_bgr: np.ndarray):
        """The (1, 3, 224, 224) float32 CPU model input for a BGR frame: crop, PIL on the BGR bytes, transforms."""
        from PIL import Image

        crop = frame_bgr[CROP_ROWS[0] : CROP_ROWS[1], :, :]
        pil = Image.fromarray(crop).convert("RGB")
        if self.transform == "numpy":
            return numpy_input(self.resize(pil), self.torch)
        return self.trans(pil).unsqueeze(0)

    def _output(self, frame_bgr: np.ndarray):
        torch = self.torch
        t0 = time.perf_counter()
        with torch.set_grad_enabled(False):
            x = self.input_tensor(frame_bgr)
            self._t_prep_end = time.perf_counter()
            self.prep_s += self._t_prep_end - t0
            out = self.sigmoid(self.model(x.to(self.device)))
        self.calls += 1
        return out

    def predict(self, frame_bgr: np.ndarray) -> tuple:
        """(is_cone, probability) for one frame — `is_cone` uses v1's tensor comparison `outputs >= 0.5`."""
        out = self._output(frame_bgr)
        result = bool((out >= 0.5)[0][0].item()), float(out[0][0].item())
        self.gpu_s += time.perf_counter() - self._t_prep_end
        return result


def majority_vote(votes: list) -> tuple:
    """v1 end-of-video decision: `camera_type_cone` = majority of the per-frame booleans, `confidence_camera` = its share.

    Without votes v1 reports no camera type and `confidence_camera = 1 - 0 = 1` (`main.py:1117-1118`: `cone_conf` is 0 and
    the `else` branch is taken for `None`), so the port returns (None, 1.0)."""
    if not votes:
        return None, 1.0
    cone_share = sum(bool(v) for v in votes) / len(votes)
    is_cone = cone_share > 0.5
    return is_cone, (cone_share if is_cone else 1 - cone_share)
