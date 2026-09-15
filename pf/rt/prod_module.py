"""Run a production CV module unchanged inside the real-time branch.

The module's detect() runs in its own thread with a live VideoWorker: its dataset (a look-alike of cv_common LoadImages) and
its metadata generator block until the real-time branch has delivered the frame they need. The module therefore processes
frames as they arrive and returns its verdict the moment it decides — when the session closes, or earlier for modules that
stop by themselves. `on_frame` hands a frame over and waits until the module has moved past it (asked for a later frame or
metadata row, or returned), so the runtime's per-frame timings measure the module itself.

What real time does not have is recorded, not hidden:
  * the session's total frame count (`dataset.nframes`, `cap.get(CAP_PROP_FRAME_COUNT)`, `video_worker.number_of_frames`):
    served from the manifest, every read counted with its first call site;
  * frames the module asks for after they left the look-back window (`lookback_frames`): an error naming the frame.
The module never gets the video file: `source` points to a path that does not exist, so a module that opens the file behind
the branch's back fails visibly. Metadata rows per frame come from GM / tracker ndjson files (`inferences_dir`: GM and
tracker assumed to deliver in step with the frames), are empty (`metadata="empty"`, for modules that do not read them), or
are produced by GM + tracker in the loop (`metadata="live"`: `pf.rt.pipeline` hands each frame over with `push`).
One production module per process: its `main`, `cv_common` and `db_worker` packages are imported by name.
A `hook` can observe the module's own state without changing it (e.g. `pf.rt.hooks.vests:install`) and emit outputs
while the session runs.
"""

from __future__ import annotations

import importlib
import inspect
import io
import json
import os
import queue
import sys
import threading
import time
import traceback

import numpy as np

from pf.rt.runtime import Adapter, Frame, Output

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class EndOfSession(Exception):
    pass


class NonCausalUsage:
    """Counts reads of information a real-time module cannot have, with the first call site of each."""

    def __init__(self):
        self.hits: dict = {}
        self._lock = threading.Lock()

    def hit(self, name: str) -> None:
        with self._lock:
            rec = self.hits.setdefault(name, {"count": 0, "first_call_site": None})
            rec["count"] += 1
            if rec["first_call_site"] is None:
                caller = traceback.extract_stack(limit=4)[0]
                rec["first_call_site"] = f"{caller.filename}:{caller.lineno} {caller.line}"


class LiveFeed:
    """Frames and metadata rows delivered by the branch; the module side blocks until what it asks for exists."""

    def __init__(self, lookback_frames: int = 64):
        self.lookback = lookback_frames
        self._cv = threading.Condition()
        self._frames: dict = {}
        self._meta: dict = {}
        self.last_id = 0
        self.requested = 0  # highest frame id the module asked for (pixels or metadata)
        self.closed = False
        self.lookback_misses: list = []

    def put(self, frame_id: int, image, meta: dict) -> None:
        with self._cv:
            self._frames[frame_id] = image
            self._meta[frame_id] = meta
            self.last_id = frame_id
            floor = max(self.requested, frame_id) - self.lookback
            for k in [k for k in self._frames if k < floor]:
                del self._frames[k]
            self._cv.notify_all()

    def close(self) -> None:
        with self._cv:
            self.closed = True
            self._cv.notify_all()

    def _ask(self, frame_id: int) -> None:
        if frame_id > self.requested:
            self.requested = frame_id
            self._cv.notify_all()

    def frame(self, frame_id: int):
        with self._cv:
            self._ask(frame_id)
            while frame_id > self.last_id and not self.closed:
                self._cv.wait()
            if frame_id > self.last_id:
                raise EndOfSession(frame_id)
            if frame_id not in self._frames:
                self.lookback_misses.append(frame_id)
                raise IndexError(f"frame {frame_id} left the look-back window of {self.lookback} frames")
            return self._frames[frame_id]

    def meta(self, frame_id: int):
        with self._cv:
            self._ask(frame_id)
            while frame_id > self.last_id and not self.closed:
                self._cv.wait()
            if frame_id > self.last_id:
                return None
            return self._meta.pop(frame_id)

    def wait_past(self, frame_id: int, done: threading.Event) -> None:
        with self._cv:
            while self.requested <= frame_id and not done.is_set():
                self._cv.wait(0.5)

    def wake(self) -> None:
        with self._cv:
            self._cv.notify_all()


class _LiveCap:
    """The `dataset.cap` / `vid_cap` modules query for fps and frame counts."""

    def __init__(self, dataset, fps: float, total: int, usage: NonCausalUsage):
        self._ds, self._fps, self._total, self._usage = dataset, fps, total, usage

    def get(self, prop):
        import cv2

        if prop == cv2.CAP_PROP_FPS:
            return float(self._fps)
        if prop == cv2.CAP_PROP_FRAME_COUNT:
            self._usage.hit("cap.get(CAP_PROP_FRAME_COUNT)")
            return float(self._total)
        if prop == cv2.CAP_PROP_POS_FRAMES:
            return float(self._ds.frame)
        self._usage.hit(f"cap.get({prop})")
        return 0.0

    def isOpened(self) -> bool:
        return True

    def release(self) -> None:
        pass


class LiveDataset:
    """cv_common.utils.datasets.LoadImages for one video, fed frame by frame: iteration, get_frame / get_im0s (forward only),
    letterbox + CHW RGB conversion as in the original."""

    def __init__(self, feed: LiveFeed, path: str, total: int, fps: float, letterbox, img_size: int, usage: NonCausalUsage,
                 stride: int = 64, auto: bool = True):
        self.feed, self.files, self.nf, self.video_flag, self.mode = feed, [path], 1, [True], "video"
        self.img_size, self.stride, self.auto, self._letterbox = img_size, stride, auto, letterbox
        self.count, self.frame, self._total, self._usage = 0, 0, total, usage
        self._loaded_frame, self._loaded_items = None, None
        self.cap = _LiveCap(self, fps, total, usage)

    @property
    def nframes(self) -> int:
        self._usage.hit("dataset.nframes")
        return self._total

    def _items(self, img0):
        img = self._letterbox(img0, self.img_size, stride=self.stride, auto=self.auto)[0]
        img = np.ascontiguousarray(img.transpose((2, 0, 1))[::-1])
        return [self.files[0], img, img0, self.cap]

    def __iter__(self):
        self.count = 0
        return self

    def __next__(self):
        try:
            img0 = self.feed.frame(self.frame + 1)
        except EndOfSession:
            raise StopIteration
        self.frame += 1
        return tuple(self._items(img0))

    def get_frame(self, frame_number: int):
        if self._loaded_frame == frame_number:
            return self._loaded_items
        assert frame_number > 0, f"Requested frame number {frame_number} is out of bounds"
        assert frame_number >= self.frame, "Requested frame number must be greater than or equal to the last loaded frame"
        try:
            img0 = self.feed.frame(frame_number)
        except EndOfSession:
            raise IndexError(f"Requested frame number {frame_number} is out of bounds for the session")
        self.frame = frame_number
        self._loaded_frame, self._loaded_items = frame_number, self._items(img0)
        return self._loaded_items

    def get_im0s(self, frame_number: int):
        return self.get_frame(frame_number)[2]

    def __len__(self) -> int:
        return self.nf


def make_live_worker(VideoWorker, feed: LiveFeed, dataset_factory, total: int, fps: float, usage: NonCausalUsage):
    """The module's own db_worker VideoWorker with the live dataset and metadata generator."""

    class LiveVideoWorker(VideoWorker):
        def load_source(self, source=None):
            if source:
                self.source = source
            self.fps = int(fps)
            return dataset_factory(self.source)

        def load_metadata(self):
            def rows():
                fid = 1
                while True:
                    m = feed.meta(fid)
                    if m is None:
                        return
                    yield m
                    fid += 1

            return rows()

        @property
        def number_of_frames(self):
            usage.hit("video_worker.number_of_frames")
            return total

        @number_of_frames.setter
        def number_of_frames(self, value):
            pass

    return LiveVideoWorker


def _jsonable(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return str(v)


class ProductionModuleAdapter(Adapter):
    def __init__(self, module: str, module_dir: str | None = None, inferences_dir: str | None = None, metadata: str = "files",
                 video_name: str | None = None, total_frames: int | None = None, device: str = "cuda:0",
                 cone_camera: bool = True, airplane_type: str | None = None, weights_dir: str = "weights",
                 numpy1_scalars: bool = False, drop_state_keys: str = "", prepend_path=(), lookback_frames: int = 64,
                 work_dir: str | None = None, env: dict | None = None, hook: str | None = None):
        if metadata not in ("files", "empty", "live"):
            raise ValueError("metadata must be 'files', 'empty' or 'live'")
        self.module, self.name = module, f"prod:{module}"
        self.module_dir = os.path.abspath(module_dir) if module_dir else os.path.join(ROOT, "external", module)
        self.inferences_dir = os.path.abspath(inferences_dir) if inferences_dir else None
        self.metadata, self.video_name, self.total_frames = metadata, video_name, total_frames
        self.device, self.cone_camera, self.airplane_type, self.weights_dir = device, cone_camera, airplane_type, weights_dir
        self.numpy1_scalars, self.drop_state_keys = numpy1_scalars, [k for k in drop_state_keys.split(",") if k]
        self.prepend_path = [os.path.abspath(p) for p in prepend_path]
        self.lookback_frames = lookback_frames
        self.work_dir = os.path.abspath(work_dir or os.path.join(ROOT, "out", "rt", "work", module))
        self.env = env or {}
        self.hook = hook  # "package.module:function" called as function(prod_main_module, emit) after import
        self.usage = NonCausalUsage()
        self.done = threading.Event()
        self._outbox: queue.Queue = queue.Queue()
        self._gm = self._trk = None
        self._blank = None

    def configure(self, manifest: dict) -> None:
        """Session facts from the chunk manifest (the runner calls this before start)."""
        self.video_name = self.video_name or os.path.basename(manifest["video"])
        self.total_frames = self.total_frames or manifest["n_frames"]

    def start(self, fps: float) -> None:
        super().start(fps)
        os.environ.update({k: str(v) for k, v in self.env.items()})
        os.makedirs(self.work_dir, exist_ok=True)
        for p in reversed(self.prepend_path):
            sys.path.insert(0, p)
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        os.chdir(self.module_dir)
        sys.path.insert(0, self.module_dir)
        import torch  # noqa: F401  (modules expect it loaded)

        native_windows_path = None
        if os.name == "nt":
            import pathlib

            native_windows_path = pathlib.WindowsPath
        prod = importlib.import_module("main")
        if native_windows_path is not None:
            import pathlib

            pathlib.WindowsPath = native_windows_path
        from scripts.run_module import drop_tracker_state_keys, numpy1_scalar_types

        if self.numpy1_scalars:
            prod.float, prod.int = numpy1_scalar_types()
        if self.drop_state_keys:
            drop_tracker_state_keys(self.drop_state_keys)
        if self.hook:
            hook_module, hook_fn = self.hook.split(":")
            getattr(importlib.import_module(hook_module), hook_fn)(prod, self._emit)
        from cv_common.common import parse_config
        from cv_common.log_utils import JsonLogger
        import cv_common.utils.datasets as datasets
        import db_worker.ML_worker as ml_worker

        self.feed = LiveFeed(self.lookback_frames)
        img_size = ml_worker.cv_config["img_size"] if hasattr(ml_worker, "cv_config") else 1280
        factory = lambda src: LiveDataset(self.feed, src, self.total_frames, fps, datasets.letterbox, img_size, self.usage)
        Worker = make_live_worker(ml_worker.VideoWorker, self.feed, factory, self.total_frames, fps, self.usage)
        source = os.path.join(self.work_dir, "no_video_file", self.video_name)  # never opened: pixels come from the feed
        vw = Worker(model_name="model-name", load_tracks=True, source=source, testing=True, auto_download_inference=False,
                    inferences_dir=os.path.join(self.work_dir, "inferences"))
        config = parse_config()
        kwargs = dict(source=source, output_path=os.path.join(self.work_dir, self.video_name + ".mkv"), device=self.device,
                      video_worker=vw, write_video=False, cone_camera=self.cone_camera, weights_dir=self.weights_dir,
                      json_logger=JsonLogger(config["status2id"], config["str2id"], None))
        params = inspect.signature(prod.detect).parameters
        if "airplane_type" in params:
            kwargs["airplane_type"] = self.airplane_type
        if "cache_folder" in params:
            kwargs["cache_folder"] = os.path.join(self.work_dir, "cache")
        if self.metadata == "files":
            self._gm = io.open(os.path.join(self.inferences_dir, f"general_model{self.video_name}.ndjson"), encoding="utf-8")
            self._trk = io.open(os.path.join(self.inferences_dir, f"trackers{self.video_name}.ndjson"), encoding="utf-8")
        self._t_start = time.perf_counter()
        self._thread = threading.Thread(target=self._run, args=(prod.detect, kwargs), name=self.name, daemon=True)
        self._thread.start()

    def _run(self, detect, kwargs) -> None:
        import torch

        try:
            with torch.no_grad():
                ret = detect(**kwargs)
            values = list(ret) if isinstance(ret, (tuple, list)) else [ret]
            self._outbox.put(Output("verdict", self.module, self.feed.requested or None, {
                "status": _jsonable(values[0]) if values else None,
                "report": _jsonable(values[1]) if len(values) > 1 else None,
                "decided_after_frame": self.feed.requested, "frames_delivered": self.feed.last_id,
                "session_closed": self.feed.closed, "module_seconds": round(time.perf_counter() - self._t_start, 1)}))
        except Exception as e:
            self._outbox.put(Output("note", "module_error", self.feed.requested or None, {
                "error": f"{type(e).__name__}: {str(e)[:400]}", "traceback": traceback.format_exc()[-3000:]}))
        finally:
            self.done.set()
            self.feed.wake()

    def _emit(self, kind: str, name: str, frame_id, payload: dict) -> None:
        """Called by hooks from the module thread; the output is emitted after the current frame is processed."""
        self._outbox.put(Output(kind, name, frame_id, payload))

    def _row(self) -> dict:
        if self.metadata == "empty":
            return {"general_model": [], "trackers": []}
        gm = json.loads(self._gm.readline() or "{}")
        trk = json.loads(self._trk.readline() or "{}")
        return {"general_model": next(iter(gm.values()), []), "trackers": next(iter(trk.values()), [])}

    def _drain(self) -> list:
        out = []
        while True:
            try:
                out.append(self._outbox.get_nowait())
            except queue.Empty:
                return out

    def push(self, frame_id: int, image, meta: dict) -> list:
        """metadata='live': one frame with the rows the branch produced for it, in frame order. `image` None = a module that
        never reads pixels (a shared blank frame is handed over)."""
        if image is None:
            if self._blank is None:
                self._blank = np.zeros((1080, 1920, 3), np.uint8)
            image = self._blank
        self.feed.put(frame_id, image, meta)
        if not self.done.is_set():
            self.feed.wait_past(frame_id, self.done)
        return self._drain()

    def on_frame(self, frame: Frame) -> list:
        if self.metadata == "live":
            raise RuntimeError("metadata='live': the branch hands frames over with push()")
        image = frame.image if not frame.missing else np.zeros((1080, 1920, 3), np.uint8)
        self.feed.put(frame.frame_id, image, self._row())
        if not self.done.is_set():
            self.feed.wait_past(frame.frame_id, self.done)
        return self._drain()

    def close(self) -> list:
        self.feed.close()
        self._thread.join()
        for fh in (self._gm, self._trk):
            if fh:
                fh.close()
        out = self._drain()
        out.append(Output("note", "real_time_audit", None, {
            "non_causal_reads": self.usage.hits, "lookback_misses": self.feed.lookback_misses[:20],
            "lookback_frames": self.lookback_frames}))
        return out
