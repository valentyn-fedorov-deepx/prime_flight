"""cucim.skimage.restoration stand-in: GPU torch port of `denoise_tv_chambolle` (see ../../../tv_chambolle_torch.py)."""

import os
import sys

_here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _here not in sys.path:
    sys.path.insert(0, _here)
from tv_chambolle_torch import denoise_tv_chambolle  # noqa: E402, F401
