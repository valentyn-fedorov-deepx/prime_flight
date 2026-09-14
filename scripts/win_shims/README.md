# Windows shims for Linux-only tracker dependencies

`cv_trackers/tracker.py` imports `cupy` and `cucim.skimage.restoration.denoise_tv_chambolle` (GPU total-variation
denoising used only when the frame noise estimate exceeds the configured threshold). `cucim` (RAPIDS) has no Windows
wheels. These stubs map both onto NumPy / scikit-image (`denoise_tv_chambolle` in cuCIM is a port of the scikit-image
implementation), so the tracker runs unmodified on a Windows workstation for profiling and parity runs.

They are only put on `sys.path` by the profiling scripts when the real packages are missing; the denoise calls are counted
and timed separately because the CPU version is far slower than the GPU one.
