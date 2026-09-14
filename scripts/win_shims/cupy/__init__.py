"""NumPy-backed stand-in for the few cupy calls the DXGAT tracker makes (see ../README.md)."""

import numpy as _np


class ndarray(_np.ndarray):  # noqa: N801  (cupy name)
    """ndarray with the `.device` attribute the tracker logs."""

    @property
    def device(self):
        return "cpu (cupy shim → torch denoise on cuda)"


float = _np.float64  # noqa: A001


def asarray(a, dtype=None):
    return _np.asarray(a, dtype=dtype).view(ndarray)


def asnumpy(a):
    return _np.asarray(a)


def array(a, dtype=None):
    return _np.array(a, dtype=dtype).view(ndarray)
