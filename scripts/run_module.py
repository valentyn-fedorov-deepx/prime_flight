"""Run a production CV module (as is, from external/<repo>) on a directory of per-frame inferences — the L2 gate.

Ported from the gat-streaming stand runner (`streaming/runner.py`) and generalised: any module repo, any inference
directory, optional --no-video meta worker for modules that do not read pixels. Used to prove that a new GM/tracker
version does not change module verdicts: run the module on the production inferences and on the v2 inferences of the
same video and diff the results.

    python scripts/run_module.py --module beltloader-chocks --video DjwtQRdZyt0sSk.mp4 \
        --inferences-dir out/l2/prod --no-video --out out/l2/prod_beltloader-chocks.json

The module's `cv_common/` and `db_worker/` submodule folders must be populated (copied from external/) at the pin the
module expects (`git -C external/<module> ls-tree HEAD cv_common db_worker`).

Robustness (every outcome lands in the JSON, so a batch never stops and never reports a missing run as "equal"):
  * the module's `output/` folder (logs) is created;
  * with --no-video the worker returns a stub dataset (`nframes`, `cap.get()` → fps); pixel access raises a clear error;
  * import errors are recorded like runtime errors;
  * any `detect()` return shape is accepted: status, report, smart timeline = the first three values, the rest in
    `extra_returns`;
  * `--airplane-type` is passed to `detect()` only for modules whose signature accepts it (db_worker's model_starter does
    the same for cones-placed-in-proper-positions-and-timely);
  * NumPy 1.x scalar conversion: the production images run NumPy 1.x, where `float(array([x]))` / `int(array([x]))` of a
    one-element array return the element; NumPy 2.x raises TypeError (lead-marshaller, wing-walkers and pushback-does-not-
    start all call `float(np.rad2deg(np.arctan(lin_reg.coef_)))`). The runner rebinds `float` and `int` in the module's
    namespace to subclasses that restore exactly that conversion and delegate everything else (isinstance, dtype) to the
    builtins. Opt-in with --numpy1-scalars, used only for the modules that need it.
  * `--drop-state-keys`: tracker files carry the stage fields of cv_common's newer `transport.Airplane`
    (`_moving_counter`, `_stopped_counter`, `have_pre_arrival_stage`, `have_arrival_stage`, `departure_frame`,
    `_height_mode`) and, on beltloader / gse records, `_bl_type_bbox` / `_bl_type_frames`; the
    `TrackedObject.from_state_dict` of an older cv_common copy raises on them. Modules that define their own
    `Airplane` / `Beltloader(TrackedObject)` and never read those fields (the post-arrival and pre-departure walk-arounds)
    get them removed before the call - the treatment that copy already gives `arrival_frame`. Recorded in the JSON.
"""

from __future__ import annotations

import argparse
import builtins
import importlib
import inspect
import json
import os
import sys
import time
import traceback
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_stub_dataset(nframes: int, fps: int):
    """What pixel-free modules touch on the dataset: `nframes` (default stop frame) and `cap.get(CAP_PROP_FPS)`."""

    def get_im0s(frame_number):
        raise RuntimeError("--no-video: the module asked for pixels (get_im0s); run it with --videos-dir instead")

    return SimpleNamespace(nframes=nframes, frame=0, cap=SimpleNamespace(get=lambda prop: fps), get_im0s=get_im0s)


def make_meta_worker(VideoWorker, fps=8):
    """VideoWorker without a video file — for modules that never touch pixels (stand `workers/meta_worker.py`)."""

    class MetaOnlyWorker(VideoWorker):
        def load_source(self, source=None):
            if source:
                self.source = source
            name = os.path.basename(self.source)
            gm = os.path.join(self.inferences_dir, "general_model" + name + ".ndjson")
            n = 0
            with open(gm, "rb") as fh:
                for _ in fh:
                    n += 1
            self.number_of_frames = n
            self.fps = fps
            return make_stub_dataset(n, fps)

    return MetaOnlyWorker


def numpy1_scalar_types():
    """`float` / `int` replacements with NumPy 1.x conversion of one-element arrays; isinstance/issubclass/dtype unchanged."""
    import numpy as np

    def unwrap(args):
        if args and isinstance(args[0], np.ndarray) and args[0].ndim > 0 and args[0].size == 1:
            return (args[0].reshape(-1)[0],) + tuple(args[1:])
        return args

    class _FloatMeta(type):
        def __instancecheck__(cls, obj):
            return isinstance(obj, builtins.float)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, builtins.float)

    class _IntMeta(type):
        def __instancecheck__(cls, obj):
            return isinstance(obj, builtins.int)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, builtins.int)

    class float(builtins.float, metaclass=_FloatMeta):  # noqa: A001
        dtype = np.dtype(builtins.float)  # np.dtype(float) / astype(float) / dtype=float keep meaning float64

        def __new__(cls, *args):
            return builtins.float(*unwrap(args))

    class int(builtins.int, metaclass=_IntMeta):  # noqa: A001
        dtype = np.dtype(builtins.int)

        def __new__(cls, *args, **kw):
            return builtins.int(*unwrap(args), **kw)

    return float, int


def drop_tracker_state_keys(keys: list) -> None:
    """Remove `keys` from a state dict (in place, like the method itself) before `TrackedObject.from_state_dict`."""
    from cv_common import tracked_object

    original = tracked_object.TrackedObject.from_state_dict

    def from_state_dict(self, state_dict, *args, **kwargs):
        for k in keys:
            state_dict.pop(k, None)
        return original(self, state_dict, *args, **kwargs)

    tracked_object.TrackedObject.from_state_dict = from_state_dict


def _jsonable(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", required=True, help="repo folder name under external/")
    ap.add_argument("--entry", default="main", help="python module with detect(): main | main_stream")
    ap.add_argument("--video", required=True, help="video file name (basename is used for the ndjson names)")
    ap.add_argument("--videos-dir", default=None, help="folder with the mp4 (needed unless --no-video)")
    ap.add_argument("--inferences-dir", required=True)
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--device", default="cuda", help="some modules (YOLOv5 select_device) need '0' instead of 'cuda'")
    ap.add_argument("--cone-camera", default="true", choices=["true", "false"])
    ap.add_argument("--airplane-type", default=None, help="JET | AIRCRAFT, passed only if detect() accepts it")
    ap.add_argument("--weights-dir", default="weights")
    ap.add_argument("--numpy1-scalars", action="store_true", help="NumPy 1.x float()/int() of one-element arrays")
    ap.add_argument("--write-video", action="store_true")
    ap.add_argument("--prepend-path", action="append", default=[], help="folder put before site-packages (repeatable)")
    ap.add_argument("--drop-state-keys", default="", help="comma list of tracker state keys removed before cv_common TrackedObject.from_state_dict")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    moddir = os.path.join(ROOT, "external", a.module)
    inf = os.path.abspath(a.inferences_dir)
    out = os.path.abspath(a.out)
    src = os.path.join(os.path.abspath(a.videos_dir), a.video) if a.videos_dir else a.video
    if not a.no_video and not os.path.exists(src):
        raise SystemExit(f"video not found: {src} (use --videos-dir or --no-video)")

    prepend = [os.path.abspath(p) for p in a.prepend_path]
    os.makedirs(os.path.join(moddir, "output"), exist_ok=True)
    os.chdir(moddir)
    for p in reversed(prepend):
        sys.path.insert(0, p)
    sys.path.insert(0, moddir)
    t0 = time.time()
    result = {
        "module": a.module,
        "entry": a.entry,
        "video": a.video,
        "inferences_dir": inf,
        "no_video": a.no_video,
        "device": a.device,
        "cone_camera": a.cone_camera,
        "airplane_type": a.airplane_type,
        "numpy1_scalar_shim": a.numpy1_scalars,
        "prepend_path": prepend,
        "drop_state_keys": [k for k in a.drop_state_keys.split(",") if k],
    }
    substituted = os.path.join(moddir, "cv_common", "SUBSTITUTED_PIN.txt")
    if os.path.exists(substituted):
        result["cv_common_substituted"] = open(substituted, encoding="utf-8").read().strip()
    try:
        import torch

        prod = importlib.import_module(a.entry)
        if a.numpy1_scalars:
            prod.float, prod.int = numpy1_scalar_types()
        if result["drop_state_keys"]:
            drop_tracker_state_keys(result["drop_state_keys"])
        from cv_common.common import parse_config
        from cv_common.log_utils import JsonLogger
        from db_worker.ML_worker import VideoWorker

        Worker = make_meta_worker(VideoWorker, a.fps) if a.no_video else VideoWorker
        config = parse_config()
        vw = Worker(
            model_name="model-name",
            load_tracks=True,
            source=src,
            testing=True,
            auto_download_inference=False,
            inferences_dir=inf,
        )
        jl = JsonLogger(config["status2id"], config["str2id"], None)
        kwargs = dict(
            source=src,
            output_path=os.path.join(moddir, "output", a.video + ".mkv"),
            device=a.device,
            video_worker=vw,
            write_video=a.write_video,
            cone_camera=(a.cone_camera == "true"),
            weights_dir=a.weights_dir,
            json_logger=jl,
        )
        if "airplane_type" in inspect.signature(prod.detect).parameters:
            kwargs["airplane_type"] = a.airplane_type
            result["airplane_type_passed"] = True
        with torch.no_grad():
            ret = prod.detect(**kwargs)
        values = list(ret) if isinstance(ret, (tuple, list)) else [ret]
        result.update(
            {
                "status": _jsonable(values[0]) if values else None,
                "report": _jsonable(values[1]) if len(values) > 1 else None,
                "smart_timeline": _jsonable(values[2]) if len(values) > 2 else None,
                "extra_returns": _jsonable(values[3:]) if len(values) > 3 else None,
                "n_returns": len(values),
                "seconds": round(time.time() - t0, 1),
            }
        )
    except Exception as e:  # keep the failure in the artefact instead of crashing the batch
        result.update(
            {
                "error": f"{type(e).__name__}: {str(e)[:500]}",
                "traceback": traceback.format_exc()[-3000:],
                "seconds": round(time.time() - t0, 1),
            }
        )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: result.get(k) for k in ("module", "video", "status", "seconds", "error")}, default=str))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
