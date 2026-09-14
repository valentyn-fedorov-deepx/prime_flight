"""Torch (GPU) port of scikit-image / cuCIM `denoise_tv_chambolle` — same algorithm, same stopping rule, same dtype.

The DXGAT tracker denoises whole 1080p frames with cuCIM (weight=5, eps=5e-5, max_num_iter=50, channel_axis=-1). cuCIM
has no Windows build and the scikit-image CPU version needs seconds per frame, so the profiling shim runs Chambolle's
projection algorithm on the GPU with torch, mirroring `skimage.restoration._denoise._denoise_tv_chambolle_nd` line by
line (float64 in → float64 out; per-channel independent runs; early stop on |E_prev − E| < eps·E_init).
`selftest()` checks it against scikit-image.
"""

from __future__ import annotations

import numpy as np


def _chambolle_nd_torch(image, weight: float, eps: float, max_num_iter: int):
    import torch

    ndim = image.ndim
    p = torch.zeros((ndim,) + tuple(image.shape), dtype=image.dtype, device=image.device)
    g = torch.zeros_like(p)
    d = torch.zeros_like(image)
    out = image
    E_init = E_previous = None
    for i in range(max_num_iter):
        if i > 0:
            d = -p.sum(0)
            for ax in range(ndim):
                sl_d = [slice(None)] * ndim
                sl_d[ax] = slice(1, None)
                sl_p = [slice(None)] * ndim
                sl_p[ax] = slice(0, -1)
                d[tuple(sl_d)] += p[ax][tuple(sl_p)]
            out = image + d
        E = (d * d).sum()
        for ax in range(ndim):
            sl_g = [slice(None)] * ndim
            sl_g[ax] = slice(0, -1)
            g[ax][tuple(sl_g)] = torch.diff(out, dim=ax)
        norm = torch.sqrt((g * g).sum(dim=0)).unsqueeze(0)
        E = E + weight * norm.sum()
        tau = 1.0 / (2.0 * ndim)
        norm = norm * (tau / weight) + 1.0
        p = (p - tau * g) / norm
        E = E / float(image.numel())
        if i == 0:
            E_init = E
            E_previous = E
        else:
            if torch.abs(E_previous - E) < eps * E_init:
                break
            E_previous = E
    return out


def denoise_tv_chambolle(image, weight=0.1, eps=2.0e-4, max_num_iter=200, channel_axis=None, device="cuda"):
    """Signature of skimage/cucim. `image` numpy (float64 as the tracker passes it; uint8 is scaled like img_as_float)."""
    import torch

    img = np.asarray(image)
    if img.dtype == np.uint8:
        img = img.astype(np.float64) / 255.0
    elif img.dtype != np.float64:
        img = img.astype(np.float64)
    x = torch.from_numpy(np.ascontiguousarray(img)).to(device)
    if channel_axis is not None:
        ch = channel_axis % x.ndim
        x = x.movedim(ch, 0)
        out = torch.stack([_chambolle_nd_torch(x[c], weight, eps, max_num_iter) for c in range(x.shape[0])], 0)
        out = out.movedim(0, ch)
    else:
        out = _chambolle_nd_torch(x, weight, eps, max_num_iter)
    return out.cpu().numpy()


def selftest(h=48, w=64, seed=0) -> float:
    from skimage.restoration import denoise_tv_chambolle as ref

    rng = np.random.default_rng(seed)
    img = (rng.random((h, w, 3)) * 255.0).astype(np.float64)
    a = ref(img, weight=5, eps=0.00005, max_num_iter=50, channel_axis=-1)
    b = denoise_tv_chambolle(img, weight=5, eps=0.00005, max_num_iter=50, channel_axis=-1)
    return float(np.abs(a - b).max())


if __name__ == "__main__":
    import time

    print("max |skimage - torch| on random 48x64x3:", selftest())
    frame = (np.random.default_rng(1).random((1080, 1920, 3)) * 255.0).astype(np.float64)
    denoise_tv_chambolle(frame, weight=5, eps=0.00005, max_num_iter=50, channel_axis=-1)
    t0 = time.perf_counter()
    for _ in range(3):
        denoise_tv_chambolle(frame, weight=5, eps=0.00005, max_num_iter=50, channel_axis=-1)
    print("1080p frame, 3 channels, 50 iters:", round(1000 * (time.perf_counter() - t0) / 3, 1), "ms")
