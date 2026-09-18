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
  * Windows path alias (automatic): steering-by-pass-pin's main.py runs `pathlib.WindowsPath = pathlib.PosixPath` at
    import, so that its fastai learner (pickled on Windows, holds a `pathlib.WindowsPath`) unpickles on the Linux prod image.
    On Windows that alias makes every `pathlib.Path()` raise NotImplementedError (matplotlib inside the mmpose visualizer,
    fastai load_learner). The runner restores the native class right after importing any module that replaced it - the
    same end state as on Linux (native path objects; the learner's path is not used for prediction). Recorded in the
    JSON as `native_pathlib_restored`; `--native-pathlib` is still accepted and changes nothing.
  * `--keras-torch-shim` (opt-in): the walk-around `tdv_cone` branches load `weights/best_acc.keras` with
    `tf.keras.models.load_model`, and the pinned TensorFlow 2.15 / Keras 2.15 cannot read that archive's weight layout
    ("Layer 'conv2d' expected 2 variables, but received 0 variables during loading"). The branch's own `single_run.py`
    (commit e407de2) replaces `tf.keras.models.load_model` with `keras_torch_shim.KerasCompatModel` from the module folder
    (the same weights in a torch twin of the network); the flag applies exactly that hook right after the module import.
    One difference: the shim's `<weights>_torch.pth` cache is not written next to the weights (the checkout stays
    read-only; a cache would hold the same tensors). Every load is recorded in the JSON as `keras_torch_shim_loads`.
    Needs a TensorFlow that imports: the `out/envs/np1_walkaround` venv (README inside).
  * Per-run module cache (automatic): modules whose `detect()` takes `cache_folder` (the walk-around tdv_cone branches keep
    per-video artefacts in `./data/<video>/` inside the checkout and skip the work when they already exist) get a folder of
    their own next to the result JSON (`<out>.cache/`); one left by an earlier attempt is renamed aside first. Every run
    computes from scratch and the control and v2 runs of a video never share results. Recorded as `cache_folder`.
"""

from __future__ import annotations

import argparse
import builtins
import importlib
import inspect
import json
import os
import pathlib
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



def subscribed_worker(Worker, module: str, parts=("gm", "tracker", "state"), extra_gm=()):
    """The module sees only what it declared: the rows of a GM and the records of a tracker scoped to it alone.

    Head scoping is exact (the heads are independent models and neither the tracker nor the causal context reads the
    chocks or vehicle rows), so filtering the full files IS what a scoped GM would have produced. The counters say how
    much was withheld; a module that turns out to need more than it declared shows up as a changed verdict.
    """
    sys.path.insert(0, ROOT) if ROOT not in sys.path else None
    from pf.gm.rows import ClassMap
    from pf.rt.component import ComponentSpec
    from scripts.gm_v2_run import load_str2id

    cm = ClassMap(load_str2id(os.path.join(ROOT, "external", "cv_common", "global_config.yaml")))
    import dataclasses

    from pf.rt.component import Subscription

    spec = ComponentSpec.for_module(module)
    if extra_gm:
        spec = dataclasses.replace(spec, gm_classes=tuple(sorted(set(spec.gm_classes) | set(extra_gm))))
    full = spec.subscription(lambda name: cm.str2id.get(name))
    sub = Subscription(gm_class_ids=full.gm_class_ids if "gm" in parts else None,
                       tracker_classes=full.tracker_classes if "tracker" in parts else None,
                       pixels=full.pixels, keep_private=full.keep_private if "state" in parts else True)
    detail = {"declared": spec.declared, "parts": list(parts), "gm_classes": list(spec.gm_classes), "tracker_classes": list(spec.tracker_classes),
              "optical_flow_state_kept": spec.reads_optical_flow_state(), "frames": 0, "rows_given": 0, "rows_withheld": 0}

    class SubscribedWorker(Worker):
        def load_metadata(self, *args, **kwargs):
            for meta in super().load_metadata(*args, **kwargs):
                if isinstance(meta, dict) and "general_model" in meta:
                    before = sub.size(meta)
                    meta = sub.filter(meta)
                    detail["frames"] += 1
                    detail["rows_given"] += sub.size(meta)
                    detail["rows_withheld"] += before - sub.size(meta)
                yield meta

    return SubscribedWorker, detail

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


def apply_keras_torch_shim() -> list:
    """`single_run.py` hook of the walk-around tdv_cone branches: tf.keras.models.load_model -> KerasCompatModel.

    Returns the list that records the path of every load (kept in the result JSON)."""
    import tensorflow as tf
    import torch

    import keras_torch_shim  # module folder, sys.path[0]

    loads = []

    def load_model(keras_path):
        loads.append(str(keras_path))
        save = torch.save
        torch.save = lambda *args, **kwargs: None  # no <weights>_torch.pth cache next to the .keras file
        try:
            return keras_torch_shim.KerasCompatModel(keras_path)
        finally:
            torch.save = save

    tf.keras.models.load_model = load_model
    return loads


def module_source(moddir: str) -> str:
    """`PF_SOURCE.txt` of a branch export (`<branch>@<commit>`), else the git HEAD of the clone."""
    marker = os.path.join(moddir, "PF_SOURCE.txt")
    if os.path.exists(marker):
        return open(marker, encoding="utf-8").read().strip()
    import subprocess

    out = subprocess.run(["git", "-C", moddir, "log", "-1", "--format=%h"], capture_output=True, text=True)
    return out.stdout.strip()


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
    ap.add_argument("--module-dir", default=None, help="module checkout to run instead of external/<module> "
                    "(e.g. a branch export with PF_SOURCE.txt)")
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
    ap.add_argument("--subscription-parts", default="gm,tracker,state",
                    help="which parts of the declaration to apply (diagnosis): gm = GM classes, tracker = tracked classes, "
                         "state = empty the tracker's optical-flow state")
    ap.add_argument("--subscription-extra-gm", default="", help="comma list of GM class names added to the declaration")
    ap.add_argument("--subscription", action="store_true",
                    help="hand the module only the GM classes, tracked classes and tracker state it declared (pf.rt.component): the inputs a GM and a tracker scoped to this module alone would give it")
    ap.add_argument("--native-pathlib", action="store_true", help="accepted for compatibility; the runner always undoes a "
                    "module's import-time `pathlib.WindowsPath = pathlib.PosixPath` alias on Windows")
    ap.add_argument("--keras-torch-shim", action="store_true", help="route tf.keras.models.load_model through the module's "
                    "keras_torch_shim.KerasCompatModel, as the walk-around tdv_cone single_run.py does")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    moddir = os.path.abspath(a.module_dir) if a.module_dir else os.path.join(ROOT, "external", a.module)
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
        "module_dir_arg": a.module_dir or "",
        "module_source": module_source(moddir),
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
        "subscription": bool(a.subscription),
        "native_pathlib": a.native_pathlib,
        "keras_torch_shim": a.keras_torch_shim,
    }
    substituted = os.path.join(moddir, "cv_common", "SUBSTITUTED_PIN.txt")
    if os.path.exists(substituted):
        result["cv_common_substituted"] = open(substituted, encoding="utf-8").read().strip()
    try:
        import torch

        native_windows_path = pathlib.WindowsPath
        prod = importlib.import_module(a.entry)
        if os.name == "nt" and pathlib.WindowsPath is not native_windows_path:
            pathlib.WindowsPath = native_windows_path
            result["native_pathlib_restored"] = True
        if a.keras_torch_shim:
            result["keras_torch_shim_loads"] = apply_keras_torch_shim()
        if a.numpy1_scalars:
            prod.float, prod.int = numpy1_scalar_types()
        if result["drop_state_keys"]:
            drop_tracker_state_keys(result["drop_state_keys"])
        from cv_common.common import parse_config
        from cv_common.log_utils import JsonLogger
        from db_worker.ML_worker import VideoWorker

        Worker = make_meta_worker(VideoWorker, a.fps) if a.no_video else VideoWorker
        if a.subscription:
            Worker, result["subscription_detail"] = subscribed_worker(
                Worker, a.module, parts=[x for x in a.subscription_parts.split(",") if x],
                extra_gm=[x for x in a.subscription_extra_gm.split(",") if x])
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
        if "cache_folder" in inspect.signature(prod.detect).parameters:
            cache = os.path.splitext(out)[0] + ".cache"
            if os.path.exists(cache):
                os.replace(cache, f"{cache}.old-{time.strftime('%Y%m%d-%H%M%S')}")
            os.makedirs(cache)
            kwargs["cache_folder"] = cache
            result["cache_folder"] = cache
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
