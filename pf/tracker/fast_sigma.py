"""Exact, faster noise estimate for the tracker's TV-denoise gate.

Production (`cv_trackers/tracker.py` @bd43c3c) calls `skimage.restoration.estimate_sigma(frame, average_sigmas=True,
channel_axis=-1)` on the full 1080p frame every `estimate_sigma_interval` seconds while objects are tracked (≈107 ms per
call on the reference workstation). scikit-image computes, per channel, the full 2-D `pywt.dwtn(channel, 'db2')`
(four sub-bands) and keeps only the diagonal detail band `dd`, then `median(|dd[dd != 0]|) / Φ⁻¹(0.75)`, and averages
the channel sigmas.

`estimate_sigma_rgb` computes only the `dd` path with the same PyWavelets C routine in the same axis order (`dwtn`
transforms axis 0, then axis 1) — so `dd` is bit-identical — and processes the three channels in threads (PyWavelets and
NumPy release the GIL). The median of a multiset does not depend on element order, and the channel mean is taken in the
same order, so the result is bit-identical to scikit-image (verified on real ATL-C5 frames; `tests/test_fast_sigma.py`),
at ≈ 45 % of the wall time.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np

_POOL: ThreadPoolExecutor | None = None
_DENOM: float | None = None


def _denominator() -> float:
    global _DENOM
    if _DENOM is None:
        import scipy.stats

        _DENOM = scipy.stats.norm.ppf(0.75)
    return _DENOM


def channel_sigma(channel: np.ndarray) -> float:
    """`skimage.restoration._denoise._sigma_est_dwt(pywt.dwtn(channel, 'db2')['dd'])` without the unused sub-bands."""
    import pywt

    x = np.asarray(channel, dtype=np.float64)
    d0 = pywt.dwt(x, "db2", mode="symmetric", axis=0)[1]
    dd = pywt.dwt(d0, "db2", mode="symmetric", axis=1)[1]
    dd = dd[np.nonzero(dd)]
    return np.median(np.abs(dd)) / _denominator()


def estimate_sigma_rgb(image: np.ndarray, threads: int = 3):
    """Bit-identical to `estimate_sigma(image, average_sigmas=True, channel_axis=-1)` for an HWC image."""
    global _POOL
    channels = [image[:, :, c] for c in range(image.shape[2])]
    if threads > 1:
        if _POOL is None:
            _POOL = ThreadPoolExecutor(max_workers=threads, thread_name_prefix="pf-sigma")
        sigmas = list(_POOL.map(channel_sigma, channels))
    else:
        sigmas = [channel_sigma(c) for c in channels]
    return np.mean(sigmas)
