"""The exact fast noise estimate must be bit-identical to scikit-image's estimate_sigma (the tracker's denoise gate)."""

import numpy as np
import pytest

pytest.importorskip("pywt")
skimage_restoration = pytest.importorskip("skimage.restoration")

from pf.tracker.fast_sigma import estimate_sigma_rgb  # noqa: E402


def _images():
    rng = np.random.default_rng(7)
    noisy = rng.integers(0, 256, size=(123, 217, 3), dtype=np.uint8)
    yy, xx = np.mgrid[0:96, 0:160]
    gradient = np.stack([(xx * 1.5) % 256, (yy * 2.7) % 256, (xx + yy) % 256], axis=-1).astype(np.uint8)
    flat = np.full((64, 64, 3), 128, dtype=np.uint8)
    flat[10:20, 30:40] = 3  # a few non-zero detail coefficients only
    return [noisy, gradient, flat]


@pytest.mark.parametrize("threads", [1, 3])
def test_bit_identical_to_skimage(threads):
    for img in _images():
        ref = skimage_restoration.estimate_sigma(img, average_sigmas=True, channel_axis=-1)
        got = estimate_sigma_rgb(img, threads=threads)
        assert got == ref, (img.shape, float(ref), float(got))


def test_threshold_decision_matches_on_scaled_noise():
    rng = np.random.default_rng(11)
    base = rng.normal(128, 1.0, size=(90, 150, 3))
    for scale in (0.2, 0.45, 0.5, 0.55, 2.0):
        img = np.clip(128 + (base - 128) * scale, 0, 255).astype(np.uint8)
        ref = skimage_restoration.estimate_sigma(img, average_sigmas=True, channel_axis=-1)
        assert (estimate_sigma_rgb(img) > 0.5) == (ref > 0.5)
