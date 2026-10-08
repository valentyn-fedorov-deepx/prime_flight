"""Run the production General Model as it is and measure where its time goes; compare the outputs of two such runs.

`run` imports `main.py` of a General Model checkout (default: production a0157a4 in `external/general_model_prod`) and calls
its `detect()` exactly as `db_worker/model_starter.py` does (VideoWorker in testing mode, `torch.no_grad`, `save_video` on as
the job's default), in a run directory that receives the files the job writes: the first-run and second-run ndjson, the
annotated video, the video-selection report. Nothing in the checkout is modified; the instrumentation wraps functions from
outside:

  * one timer per component and per phase — startup, first run, between the runs, second run, after, third pass — with a
    CUDA synchronisation around GPU work so the time lands where it is spent;
  * phase boundaries come from the three readers `detect()` opens (`load_source` is called three times, in order);
  * `print` is counted and written to `stdout.log`, as the pod's stdout goes to the job log;
  * `np.random` is seeded before the first run and re-seeded before the second, so two checkouts can be compared byte for
    byte (production itself is unseeded; the cv_common optical flow samples key points at random).

Local deviations from the job, the same for every run: GM's cv_common pin d74eb096 is not in the archive, the archive
master (`external/cv_common`) is used; `norfair==0.2.0` (the production pin) is the vendored core `pf/gm/_norfair020.py`;
cupy / cuCIM come from `scripts/win_shims` (imported, unused by this preprocessor); `skimage.estimate_sigma(multichannel=)`
is mapped to `channel_axis=-1` (removed from scikit-image 0.21).

    python scripts/gm_prod_profile.py run --video out/rt/slices/zHxIAF2vUGxJ_2071_4964.mp4 --out out/gm_prod/slice_prod
    python scripts/gm_prod_profile.py run --gm-root external/general_model_opt --video ... --out out/gm_prod/slice_opt
    python scripts/gm_prod_profile.py compare out/gm_prod/slice_prod out/gm_prod/slice_opt
"""

from __future__ import annotations

import argparse
import builtins
import functools
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------------------------ environment
def junction(link: str, target: str) -> None:
    if os.path.exists(link):
        return
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", link, target], check=True, stdout=subprocess.DEVNULL)
    else:
        os.symlink(target, link)


def write_norfair_shim(shim_root: str) -> None:
    """A `norfair` package exposing the vendored norfair 0.2.0 core (the version the production GM pins)."""
    pkg = os.path.join(shim_root, "norfair")
    os.makedirs(pkg, exist_ok=True)
    src = os.path.join(ROOT, "pf", "gm", "_norfair020.py").replace("\\", "/")
    loader = (
        "import importlib.util as _u\n"
        f"_s = _u.spec_from_file_location('_pf_norfair020', r'{src}')\n"
        "_m = _u.module_from_spec(_s)\n_s.loader.exec_module(_m)\n"
        "Detection, Tracker, TrackedObject = _m.Detection, _m.Tracker, _m.TrackedObject\n"
        "\n\nclass Color:  # norfair 0.2.0 drawing palette (BGR); cv_common only uses it to colour drawings\n"
        "    green, white, olive, black = (0, 128, 0), (255, 255, 255), (0, 128, 128), (0, 0, 0)\n"
        "    navy, red, maroon, grey = (128, 0, 0), (0, 0, 255), (0, 0, 128), (128, 128, 128)\n"
        "    purple, yellow, lime, fuchsia = (128, 0, 128), (0, 255, 255), (0, 255, 0), (255, 0, 255)\n"
        "    aqua, blue, teal, silver = (255, 255, 0), (255, 0, 0), (128, 128, 0), (192, 192, 192)\n"
    )
    io.open(os.path.join(pkg, "__init__.py"), "w", encoding="utf-8").write(loader)
    io.open(os.path.join(pkg, "tracker.py"), "w", encoding="utf-8").write(
        "from norfair import Detection, Tracker, TrackedObject  # noqa: F401\n")


def prepare(a) -> tuple:
    gm_root = os.path.abspath(a.gm_root)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    weights = os.path.abspath(a.weights_dir or os.path.join(gm_root, "weights"))
    cv_parent = os.path.abspath(a.cv_common_parent)
    shutil.copy(os.path.join(gm_root, "local_config.yaml"), os.path.join(out, "local_config.yaml"))
    junction(os.path.join(out, "weights"), weights)  # UModel / EntityClassifier read ./weights
    junction(os.path.join(out, "cv_common"), os.path.join(cv_parent, "cv_common"))  # parse_config reads cv_common/global_config.yaml
    shim_root = os.path.join(out, "_shims")
    write_norfair_shim(shim_root)
    # the checkout first (its `scripts` package, `main`, the vendored craft_text_detector), then the shims, then the
    # parent of cv_common / db_worker; this repository's own directories stay off the path
    sys.path[:] = [p for p in sys.path if os.path.abspath(p) not in (os.path.join(ROOT, "scripts"), ROOT)]
    for p in reversed([gm_root, shim_root, os.path.join(ROOT, "scripts", "win_shims"), cv_parent]):
        sys.path.insert(0, p)
    import skimage.restoration as skr

    orig = skr.estimate_sigma

    @functools.wraps(orig)
    def estimate_sigma(image, *args, multichannel=None, **kw):
        if multichannel is not None and "channel_axis" not in kw:
            kw["channel_axis"] = -1 if multichannel else None
        return orig(image, *args, **kw)

    skr.estimate_sigma = estimate_sigma
    os.chdir(out)
    return gm_root, out, weights


# ------------------------------------------------------------------------------------------------ instrumentation
class Profile:
    def __init__(self):
        self.phase = "startup"
        self.t_phase = {}
        self.t0 = time.perf_counter()
        self.mark("startup")
        self.comp = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))  # phase -> name -> [seconds, calls]
        self.frames = defaultdict(int)
        self.readers = []
        self.prints = defaultdict(int)

    def mark(self, phase: str) -> None:
        now = time.perf_counter()
        if getattr(self, "_current", None):
            name, start = self._current
            self.t_phase[name] = self.t_phase.get(name, 0.0) + now - start
        self._current = (phase, now)
        self.phase = phase

    def close(self) -> None:
        self.mark("done")

    def add(self, name: str, seconds: float, phase: str | None = None) -> None:
        c = self.comp[phase or self.phase][name]
        c[0] += seconds
        c[1] += 1


P = Profile()


def timed(name, fn, sync: bool = False, per_phase_name=None):
    import torch

    @functools.wraps(fn)
    def wrapper(*args, **kw):
        if sync:
            torch.cuda.synchronize()
        t = time.perf_counter()
        try:
            return fn(*args, **kw)
        finally:
            if sync:
                torch.cuda.synchronize()
            P.add(per_phase_name(args) if per_phase_name else name, time.perf_counter() - t)

    return wrapper


def instrument(main, log_fh) -> None:
    import cv2
    import torch
    import cv_common.utils.datasets as ds
    from cv_common.image_preprocessing import ImagePreprocessor
    from db_worker.ML_worker import VideoWorker
    from mobile_sam import SamPredictor
    import scripts.new_model as new_model
    import scripts.tracker as gm_tracker
    from scripts.entity.entity_classifier import EntityClassifier

    # readers: detect() opens three in order -> first run, second run, third pass (video selection)
    phase_of_reader = ("run1", "run2", "third_pass")
    orig_load = VideoWorker.load_source

    def load_source(self, *args, **kw):
        dataset = orig_load(self, *args, **kw)
        dataset._pf_phase = phase_of_reader[min(len(P.readers), 2)]
        P.readers.append(dataset._pf_phase)
        return dataset

    VideoWorker.load_source = load_source

    orig_next = ds.LoadImages.__next__

    def next_frame(self):
        phase = getattr(self, "_pf_phase", P.phase)
        if P.phase != phase:
            P.mark(phase)
        t = time.perf_counter()
        try:
            item = orig_next(self)
        except StopIteration:
            P.add("decode + letterbox (reader)", time.perf_counter() - t)
            P.mark({"run1": "between", "run2": "after", "third_pass": "after_third"}[phase])
            raise
        P.add("decode + letterbox (reader)", time.perf_counter() - t)
        P.frames[phase] += 1
        return item

    ds.LoadImages.__next__ = next_frame
    ds.letterbox = timed("letterbox of the unused `img` (inside the reader)", ds.letterbox)

    ImagePreprocessor.update = timed("noise preprocessor: update", ImagePreprocessor.update)
    ImagePreprocessor.get_preprocessed = timed("noise preprocessor: get_preprocessed", ImagePreprocessor.get_preprocessed)

    def head_name(args):
        self = args[0]
        shape = getattr(self, "_input_shape", [0])[0]
        return {1280: "head: chocks @1280", 1088: None}.get(shape) or f"head @{shape}"

    names = {}
    orig_predict = new_model.YOLOv8_onnx.predict

    def predict(self, image):
        torch.cuda.synchronize()
        t = time.perf_counter()
        try:
            return orig_predict(self, image)
        finally:
            P.add(names.get(id(self), "head"), time.perf_counter() - t)

    new_model.YOLOv8_onnx.predict = predict
    orig_init = new_model.YOLOv8_onnx.__init__

    def init(self, weights, *args, **kw):
        orig_init(self, weights, *args, **kw)
        base = os.path.basename(weights)
        names[id(self)] = ("head: GM @1088" if base.startswith("GM_") else "head: vehicle @1088" if base.startswith("VM_")
                           else "head: chocks @1280" if "chocks" in base else f"head: {base}")

    new_model.YOLOv8_onnx.__init__ = init

    gm_tracker.FeaturedTracker.update = timed("aircraft tracker (norfair + features)", gm_tracker.FeaturedTracker.update)
    for cls_name in ("FeaturedTrackedObject",):
        cls = getattr(gm_tracker, cls_name, None)
        if cls is not None and hasattr(cls, "update_features"):
            cls.update_features = timed("FAST / ORB features of tracked aircraft", cls.update_features)

    main.Plane.update_params = timed("", main.Plane.update_params, sync=True,
                                     per_phase_name=lambda a: "aircraft motion analysis (optical flow + MobileSAM)")
    SamPredictor.set_image = timed("MobileSAM encoder (inside motion analysis)", SamPredictor.set_image, sync=True)
    SamPredictor.predict = timed("MobileSAM decoder (inside motion analysis)", SamPredictor.predict, sync=True)
    main.classifier_inference = timed("camera classifier (EfficientNet-B0)", main.classifier_inference, sync=True)
    EntityClassifier.process_image = timed("airline classifier (CRAFT + classifiers)", EntityClassifier.process_image, sync=True)
    VideoWorker.model_pub = timed("ndjson writer (model_pub)", VideoWorker.model_pub)
    orig_meta = VideoWorker.load_metadata

    def load_metadata(self):
        gen = orig_meta(self)

        def timed_gen():
            while True:
                t = time.perf_counter()
                try:
                    item = next(gen)
                except StopIteration:
                    return
                finally:
                    P.add("ndjson reader (first-run rows)", time.perf_counter() - t)
                yield item

        return timed_gen()

    VideoWorker.load_metadata = load_metadata
    main.plot_one_box = timed("drawing boxes on the annotated video", main.plot_one_box)
    main.save_plane_type_frame_data = timed("aircraft type vote", main.save_plane_type_frame_data)
    main.select_video = timed("third pass: video selection (decode + frame differences)", main.select_video)

    real_cv2 = cv2

    class TimedWriter:
        def __init__(self, *args):
            self._w = real_cv2.VideoWriter(*args)

        def write(self, frame):
            t = time.perf_counter()
            self._w.write(frame)
            P.add("annotated video: encode", time.perf_counter() - t)

        def release(self):
            self._w.release()

        def __getattr__(self, item):
            return getattr(self._w, item)

    class Cv2Proxy:
        VideoWriter = TimedWriter

        def __getattr__(self, item):
            return getattr(real_cv2, item)

    main.cv2 = Cv2Proxy()

    def counted_print(*args, **kw):
        t = time.perf_counter()
        kw.pop("file", None)
        builtins.print(*args, file=log_fh, **kw)
        P.add("print to the job log", time.perf_counter() - t)
        P.prints[P.phase] += 1

    for mod in (main, new_model, sys.modules.get("db_worker.ML_worker"), sys.modules.get("scripts.videos_selection_script"),
                sys.modules.get("scripts.engine_script"), sys.modules.get("scripts.entity.entity_classifier")):
        if mod is not None:
            mod.print = counted_print

    # The retired YOLOv5 airline detector (`UModel`, its calls commented out in main.py) is a pickled YOLOv5 model: it
    # unpickles only with the YOLOv5 `models` package of the production base image, which is not installed here. The
    # object is never used; its load is recorded as skipped instead of crashing the run.
    def retired_umodel_init(self, weights, *args, **kw):
        P.add("retired YOLOv5 airline detector: load (skipped here, needs the base image's YOLOv5)", 0.0)
        self._weights = weights

    new_model.UModel.__init__ = retired_umodel_init

    # the second run starts right after this call: re-seed so two checkouts can be compared byte for byte
    orig_init_writer = VideoWorker.init_writer

    def init_writer(self, file_prefix=""):
        if file_prefix == "second_run":
            import numpy as np

            np.random.seed(P.seed + 1)
        return orig_init_writer(self, file_prefix)

    VideoWorker.init_writer = init_writer


def h2d_probe(video: str, n: int = 200) -> dict:
    """What `torch.from_numpy(im0s).float().cuda()` costs per frame against uploading the uint8 frame (same fp16 values)."""
    import cv2
    import numpy as np
    import torch

    cap = cv2.VideoCapture(video)
    ok, im = cap.read()
    cap.release()
    out = {}
    for name, fn in (("float32 on the CPU, then upload (as written)", lambda: torch.from_numpy(im).float().cuda().half()),
                     ("upload the uint8 frame, convert on the GPU", lambda: torch.from_numpy(im).cuda().half())):
        for _ in range(10):
            fn()
        torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(n):
            fn()
        torch.cuda.synchronize()
        out[name] = round(1000 * (time.perf_counter() - t) / n, 2)
    a = torch.from_numpy(im).float().cuda().half()
    b = torch.from_numpy(im).cuda().half()
    out["identical"] = bool(torch.equal(a, b))
    return out


# ------------------------------------------------------------------------------------------------ run / compare
def run(a) -> int:
    gm_root, out, weights = prepare(a)
    video = os.path.abspath(os.path.join(ROOT, a.video)) if not os.path.isabs(a.video) else a.video
    log_fh = io.open(os.path.join(out, "stdout.log"), "w", encoding="utf-8")
    os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")  # the production torch predates weights-only loading
    import numpy as np
    import torch

    P.seed = a.seed
    np.random.seed(a.seed)
    spec = importlib.util.spec_from_file_location("main", os.path.join(gm_root, "main.py"))
    main = importlib.util.module_from_spec(spec)
    sys.modules["main"] = main
    spec.loader.exec_module(main)
    if a.cudnn_search:
        # main.py asks cuDNN for its DEFAULT (heuristic) algorithm search. On the production T4 the heuristic returns
        # usable kernels; on this card + cuDNN 9 it returns none and every convolution runs in fallback mode, 2.6x slower
        # (docs/analysis/gm_speed.md). HEURISTIC / EXHAUSTIVE give the kernels the T4 gets; the same on both sides of a
        # comparison.
        opts = dict(main.onnx_provider[0][1], cudnn_conv_algo_search=a.cudnn_search)
        main.onnx_provider = [("CUDAExecutionProvider", opts), "CPUExecutionProvider"]
    instrument(main, log_fh)
    from db_worker.ML_worker import VideoWorker

    for f in os.listdir(out):  # outputs of an earlier run in this directory
        if f.endswith(".ndjson") or f.startswith("report_video_selection") or f.startswith("gm-output"):
            os.remove(os.path.join(out, f))
    vw = VideoWorker(source=video, model_name="general_model", load_tracks=False, load_from_file=True, testing=True,
                     auto_download_inference=False)
    t0 = time.perf_counter()
    with torch.no_grad():
        result = main.detect(source=video, output_path=os.path.join(out, "gm-output.mp4") if a.save_video else "",
                             device="gpu", weights_dir=weights, video_worker=vw, save_video=a.save_video)
    total = time.perf_counter() - t0
    P.close()
    log_fh.close()
    probe = h2d_probe(video)

    frames = dict(P.frames)
    phases = {k: round(v, 2) for k, v in P.t_phase.items()}
    comp = {}
    for phase, d in P.comp.items():
        n = frames.get(phase) or 0
        comp[phase] = {name: {"seconds": round(s, 2), "calls": c, "ms_per_frame": round(1000 * s / n, 2) if n else None}
                       for name, (s, c) in sorted(d.items(), key=lambda kv: -kv[1][0])}
    report = {"gm_root": os.path.relpath(gm_root, ROOT), "video": os.path.relpath(video, ROOT), "seed": a.seed,
              "cudnn_search": a.cudnn_search or "DEFAULT (as in main.py)",
              "save_video": a.save_video, "total_s": round(total, 1), "frames": frames, "phases_s": phases,
              "components": comp, "prints": dict(P.prints), "h2d_probe_ms": probe, "readers": P.readers}
    json.dump(result, io.open(os.path.join(out, "result.json"), "w", encoding="utf-8"), indent=1, default=str, sort_keys=True)
    json.dump(report, io.open(os.path.join(out, "profile.json"), "w", encoding="utf-8"), indent=1)
    print(f"total {total:.1f} s, frames {frames}, phases {phases}")
    for phase in ("run1", "run2", "third_pass", "between", "startup", "after"):
        if phase in comp:
            n = frames.get(phase)
            print(f"--- {phase} ({phases.get(phase)} s{f', {n} frames, {1000 * phases.get(phase, 0) / n:.1f} ms/frame' if n else ''})")
            for name, c in comp[phase].items():
                print(f"   {c['seconds']:8.2f} s  {c['ms_per_frame'] if c['ms_per_frame'] is not None else '':>7} ms/f  {c['calls']:7d}  {name}")
    print("h2d probe (ms per frame):", probe)
    return 0


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def video_frames_hash(path: str) -> tuple:
    import cv2

    cap = cv2.VideoCapture(path)
    h, n = hashlib.sha256(), 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h.update(frame.tobytes())
        n += 1
    cap.release()
    return h.hexdigest()[:16], n


def first_diff_line(a: str, b: str):
    with io.open(a, encoding="utf-8") as fa, io.open(b, encoding="utf-8") as fb:
        for i, (la, lb) in enumerate(zip(fa, fb), 1):
            if la != lb:
                return i, la[:200], lb[:200]
    return None


def compare(a_dir: str, b_dir: str) -> int:
    same = True
    files = sorted(f for f in os.listdir(a_dir) if f.endswith(".ndjson") or f in ("result.json",)
                   or f.startswith("report_video_selection") or f.endswith(".mp4"))
    for f in files:
        pa, pb = os.path.join(a_dir, f), os.path.join(b_dir, f)
        if not os.path.exists(pb):
            print(f"{f}: missing in B")
            same = False
            continue
        if f.endswith(".mp4"):
            ha, hb = video_frames_hash(pa), video_frames_hash(pb)
            ok = ha == hb
            print(f"{f}: decoded frames {'IDENTICAL' if ok else 'DIFFERENT'} ({ha[1]} frames; {ha[0]} vs {hb[0]})")
        else:
            sa, sb = sha(pa), sha(pb)
            ok = sa == sb
            print(f"{f}: {'IDENTICAL' if ok else 'DIFFERENT'} ({sa} vs {sb})")
            if not ok and not f.endswith(".json"):
                print("   first differing line:", first_diff_line(pa, pb))
            if not ok and f == "result.json":
                ra, rb = json.load(io.open(pa, encoding="utf-8")), json.load(io.open(pb, encoding="utf-8"))
                for k in sorted(set(ra) | set(rb)):
                    if ra.get(k) != rb.get(k):
                        print(f"   {k}: {str(ra.get(k))[:120]} vs {str(rb.get(k))[:120]}")
        same &= ok
    pa, pb = (json.load(io.open(os.path.join(d, "profile.json"), encoding="utf-8")) for d in (a_dir, b_dir))
    print(f"total: {pa['total_s']} s -> {pb['total_s']} s ({100 * (1 - pb['total_s'] / pa['total_s']):.1f} % less)")
    for ph in sorted(set(pa["phases_s"]) | set(pb["phases_s"])):
        print(f"   {ph:12s} {pa['phases_s'].get(ph)} -> {pb['phases_s'].get(ph)} s")
    print("ALL OUTPUTS IDENTICAL" if same else "OUTPUTS DIFFER")
    return 0 if same else 1


def main_cli() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--video", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--gm-root", default=os.path.join(ROOT, "external", "general_model_prod"))
    r.add_argument("--weights-dir", default=None)
    r.add_argument("--cv-common-parent", default=os.path.join(ROOT, "external"))
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--no-save-video", dest="save_video", action="store_false")
    r.add_argument("--cudnn-search", default="", choices=["", "DEFAULT", "HEURISTIC", "EXHAUSTIVE"],
                   help="override the cuDNN algorithm search of the GM heads (default: as main.py asks, DEFAULT)")
    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    a = ap.parse_args()
    if a.cmd == "run":
        a.out = os.path.abspath(a.out)
        return run(a)
    return compare(os.path.abspath(a.a), os.path.abspath(a.b))


if __name__ == "__main__":
    raise SystemExit(main_cli())
