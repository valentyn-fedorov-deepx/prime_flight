"""Port of `cv_common/image_preprocessing.py` (ImagePreprocessor) — noise-adaptive frame preprocessing.

v1 feeds EVERY first-run frame through `image_preprocessor.get_preprocessed()` (`general_model/main.py:514-528`), so
GM v2 must reproduce it for parity on noisy (night) videos. Behaviour (cv_common @ ac5098d):
  * every ``frame_interval`` (48) frames the noise sigma is estimated with skimage's ``estimate_sigma`` (average over
    channels) and a running mean is kept; the mode is chosen from the running mean:
        < 0.30 CLEAR · < 0.35 LIGHT · < 0.45 MIDDLE · else HEAVY
  * CLEAR / LIGHT → frame unchanged; MIDDLE → ``cv2.medianBlur(frame, 5)``; HEAVY → ``medianBlur(GaussianBlur(frame, (5,5), 0), 5)``.
  * ``is_heavy()`` switches on the airplane bbox stabilizer in v1; ``is_broken()`` = mean > 0.6 and std < 0.1.
The cucim/cupy imports of the original are unused there and are not needed here.
"""

from __future__ import annotations

import enum
import math

import numpy as np


class Mode(enum.Enum):
    CLEAR = 0
    LIGHT = 1
    MIDDLE = 2
    HEAVY = 3


THRESHOLDS = ((0.3, Mode.CLEAR), (0.35, Mode.LIGHT), (0.45, Mode.MIDDLE), (math.inf, Mode.HEAVY))


def estimate_noise(frame: np.ndarray) -> float:
    """skimage `estimate_sigma(image, average_sigmas=True, multichannel=True)` (channel_axis=-1 in new versions)."""
    from skimage.restoration import estimate_sigma  # lazy

    try:
        return float(estimate_sigma(frame, average_sigmas=True, channel_axis=-1))
    except TypeError:  # older skimage
        return float(estimate_sigma(frame, average_sigmas=True, multichannel=True))


class ImagePreprocessor:
    def __init__(self, frame_interval: int = 48, noise_fn=estimate_noise):
        self.frame_interval = frame_interval
        self._noise_fn = noise_fn
        self._last_frame = None
        self.mean_noise = 0.0
        self._ssd_noise = 0.0
        self.samples = 0
        self.mode = Mode.CLEAR
        self.decided_at: int | None = None  # first frame on which the mode left CLEAR (v2 addition)

    def update(self, frame_id: int, frame: np.ndarray) -> None:
        if frame_id % self.frame_interval == 0:
            noise = self._noise_fn(frame)
            self.samples += 1
            new_mean = self.mean_noise + (noise - self.mean_noise) / self.samples
            self._ssd_noise += (noise - self.mean_noise) * (noise - new_mean)
            self.mean_noise = new_mean
            self._update_mode(frame_id)
        self._last_frame = frame

    def _update_mode(self, frame_id: int) -> None:
        for threshold, mode in THRESHOLDS:
            if self.mean_noise < threshold:
                if mode is not Mode.CLEAR and self.decided_at is None:
                    self.decided_at = frame_id
                self.mode = mode
                break

    def get_preprocessed(self) -> np.ndarray:
        import cv2  # lazy

        f = self._last_frame
        if self.mode in (Mode.CLEAR, Mode.LIGHT):
            return f
        if self.mode is Mode.MIDDLE:
            return cv2.medianBlur(f, 5)
        return cv2.medianBlur(cv2.GaussianBlur(f, (5, 5), 0), 5)

    def get_noise_std(self) -> float:
        if self.samples > 1:
            return math.sqrt(self._ssd_noise / (self.samples - 1))
        return float("nan")

    def is_broken(self) -> bool:
        return self.mean_noise > 0.6 and self.get_noise_std() < 0.1

    def is_heavy(self) -> bool:
        return self.mode is Mode.HEAVY

    def get_current_preprocessing(self) -> str:
        return self.mode.name

    def snapshot(self) -> dict:
        return {
            "video_type_by_noise": self.mode.name,
            "noise_mean": self.mean_noise,
            "noise_std": self.get_noise_std(),
            "is_broken": self.is_broken(),
            "noise_samples": self.samples,
            "noise_mode_decided_at": self.decided_at,
        }
