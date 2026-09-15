"""GM v2 + Tracker v2 inside the real-time branch: decoded frames in, production modules fed with rows produced live.

    decoded frame ─► GM heads ─► first-run rows ─► VideoContextV2 ─► causal second-run rows (pf.pipeline.causal_rows)
                                                                          │
                          Tracker v2 (one per event, scoped classes) ◄────┘  records final after the N_INIT delay (1 s)
                                  │ (frame_id, records), in frame order
                                  ├─► primary production module in this process (pf.rt.prod_module, metadata="live")
                                  └─► extra pixel-free modules, one process each (pf.rt.module_host), fed without waiting

A real-time GM and tracker are scoped to the modules they serve:
  * `heads` keeps only the detector heads whose rows are read (downstream: the causal second run, the tracker, the modules);
  * `tracker_classes` keeps only the tracked classes the modules read (`TrackerOptions.classes` says what dropping changes).
The adapter writes exactly what it handed to the modules — the streaming second-run GM file and the v1-compat tracker file —
so a run can be compared with the batch files, and it reports the cost per frame of every component (`pipeline_report.json`).
"""

from __future__ import annotations

import io
import json
import os
import sys
import time

import numpy as np

from pf.rt.prod_module import ProductionModuleAdapter
from pf.rt.runtime import Adapter, Frame, Output

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HEADS = {  # name -> (weights file, input size, confidence threshold): the production GM heads (scripts/gm_v2_run.py defaults)
    "gm": ("GM_yolov8m_best_augmentation_march2024.onnx", (1088, 1088), 0.35),
    "chocks": ("chocks_v4.3_200ep_yolov8.onnx", (1280, 1280), 0.10),
    "vehicle": ("VM_yolov8m_last_september2023.onnx", (1088, 1088), 0.40),
}
ALL_TRACKER_CLASSES = ("airplane", "beltloader", "gse", "person")


def _ms(values) -> dict:
    if not values:
        return {}
    a = np.asarray(values, dtype=float) * 1000.0
    return {"mean": round(float(a.mean()), 2), "p50": round(float(np.percentile(a, 50)), 2),
            "p95": round(float(np.percentile(a, 95)), 2), "p99": round(float(np.percentile(a, 99)), 2),
            "max": round(float(a.max()), 2)}


class RtPipelineAdapter(Adapter):
    def __init__(self, module: str, module_args: dict | None = None, heads=("gm", "chocks", "vehicle"),
                 gm_weights_dir: str | None = None, gm_variant: str = "entity_clip", gm_provider: str = "cuda",
                 str2id: str | None = None, tracker_weights_dir: str | None = None, tracker_classes=None,
                 exact_fast: bool = True, seed: int = 0, cone_camera: bool = True, refresh_every: int = 60,
                 pixels: bool = True, out_dir: str | None = None, write_rows: bool = True, extra_modules=None):
        unknown = set(heads) - set(HEADS)
        if unknown:
            raise ValueError(f"unknown heads {sorted(unknown)}; known: {sorted(HEADS)}")
        self.module_name, self.heads = module, tuple(heads)
        self.name = f"pipeline:{module}"
        self.gm_weights_dir = os.path.abspath(gm_weights_dir or os.path.join(ROOT, "external", "general_model_prod", "weights"))
        self.gm_variant, self.gm_provider = gm_variant, gm_provider
        self.str2id = os.path.abspath(str2id or os.path.join(ROOT, "external", "cv_common", "global_config.yaml"))
        self.tracker_weights_dir = os.path.abspath(
            tracker_weights_dir or os.path.join(ROOT, "external", "cv_trackers_prod", "weights"))
        self.tracker_classes = tuple(tracker_classes or ALL_TRACKER_CLASSES)
        self.exact_fast, self.seed, self.cone_camera, self.refresh_every = exact_fast, seed, cone_camera, refresh_every
        self.pixels = pixels
        self.out_dir = os.path.abspath(out_dir) if out_dir else None
        self.write_rows = bool(write_rows and self.out_dir)
        args = dict(module_args or {})
        args.pop("inferences_dir", None)
        args.update(module=module, metadata="live", cone_camera=cone_camera)
        self.module = ProductionModuleAdapter(**args)
        self.hosts = []
        if extra_modules:
            from pf.rt.module_host import ModuleHost

            for extra in extra_modules:
                extra_args = dict(extra.get("module_args") or {})
                extra_args["cone_camera"] = cone_camera
                self.hosts.append(ModuleHost(extra["module"], extra_args))
        self.video_name = None
        self.manifest: dict = {}
        self._rows2: dict = {}
        self._images: dict = {}
        self._times = {"gm": [], "second_run_rows": [], "tracker": [], "module": [], "total": []}
        self._write_s = 0.0
        self._host_send_s = 0.0
        self._published = 0
        self._max_unpublished = 0
        self._blank = None
        self._gm_fh = self._trk_fh = None
        self.init_s: dict = {}

    def configure(self, manifest: dict) -> None:
        self.manifest = manifest
        self.video_name = os.path.basename(manifest["video"])
        self.module.configure(manifest)

    def start(self, fps: float) -> None:
        super().start(fps)
        os.environ.update({k: str(v) for k, v in (self.module.env or {}).items()})
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        t_hosts = time.perf_counter()
        for host in self.hosts:  # before anything changes the working directory
            host.start(self.manifest, fps)
        self.init_s["module_hosts"] = round(time.perf_counter() - t_hosts, 1)
        import torch  # noqa: F401

        from pf.gm.onnx_detector import YoloV8Onnx, YoloV8OnnxConfig
        from pf.gm.rows import ClassMap
        from pf.pipeline import GmStream
        from pf.pipeline.causal_rows import CausalSecondRun
        from pf.pipeline.gm_stream import Detectors
        from pf.tracker.stream import TrackerOptions, TrackerStream
        from scripts.gm_v2_run import load_str2id

        t0 = time.perf_counter()
        cm = ClassMap(load_str2id(self.str2id))

        def head(name):
            if name not in self.heads:
                return None
            weights, shape, thr = HEADS[name]
            return YoloV8Onnx(YoloV8OnnxConfig(
                weights=os.path.join(self.gm_weights_dir, weights), input_shape=shape, conf_thres=thr, iou_thres=0.7,
                provider=self.gm_provider, bgr_to_rgb=(self.gm_variant == "prod"),
                trt_cache_dir=os.path.join(ROOT, "out", "trt_cache")))

        self.detectors = Detectors(gm=head("gm"), chocks=head("chocks"), vehicle=head("vehicle"), parallel=True)
        self.gm = GmStream(cm, event_id=self.video_name or "live", fps=int(fps), detectors=self.detectors,
                           variant=self.gm_variant)
        self.causal = CausalSecondRun(self.gm.context, cm, refresh_every=self.refresh_every)
        self.tracker = TrackerStream(TrackerOptions(weights_dir=self.tracker_weights_dir, exact_fast=self.exact_fast,
                                                    cone_camera=self.cone_camera, classes=self.tracker_classes))
        self.init_s["gm_and_tracker"] = round(time.perf_counter() - t0, 1)
        if self.write_rows:
            os.makedirs(self.out_dir, exist_ok=True)
            self._gm_fh = io.open(os.path.join(self.out_dir, f"general_model{self.video_name}.ndjson"), "w",
                                  encoding="utf-8", newline="\n")
            self._trk_fh = io.open(os.path.join(self.out_dir, f"trackers{self.video_name}.ndjson"), "w",
                                   encoding="utf-8", newline="\n")
        t1 = time.perf_counter()
        self.module.start(fps)  # changes the working directory to the module checkout: every path above is absolute
        self.init_s["module"] = round(time.perf_counter() - t1, 1)
        np.random.seed(self.seed)  # right before the first frame, as the seeded batch tracker runs do

    def on_frame(self, frame: Frame) -> list:
        t0 = time.perf_counter()
        fid, image = frame.frame_id, frame.image
        if image is None:  # placeholder for a lost chunk
            if self._blank is None:
                self._blank = np.zeros((1080, 1920, 3), np.uint8)
            image = self._blank
        self.gm._ingest(fid, image)
        first_run = self.gm.raw_rows.pop(fid)
        t1 = time.perf_counter()
        rows2 = self.causal.rows(fid, first_run)
        t2 = time.perf_counter()
        published = self.tracker.update(fid, image, rows2)
        t3 = time.perf_counter()
        self._rows2[fid] = rows2
        if self.pixels:
            self._images[fid] = image
        self._max_unpublished = max(self._max_unpublished, len(self._rows2))
        outs = self._publish(published)
        for host in self.hosts:
            outs.extend(host.poll())
        t4 = time.perf_counter()
        for key, value in (("gm", t1 - t0), ("second_run_rows", t2 - t1), ("tracker", t3 - t2), ("module", t4 - t3),
                           ("total", t4 - t0)):
            self._times[key].append(value)
        return outs

    def _publish(self, published) -> list:
        from pf.gm.compat_writer import ndjson_line

        outs = []
        for fno, records in published:
            rows2 = self._rows2.pop(fno, [])
            image = self._images.pop(fno, None)
            self._published += 1
            if self.write_rows:
                tw = time.perf_counter()
                self._gm_fh.write(ndjson_line(fno, rows2))
                self._trk_fh.write(json.dumps({str(self._published): records}) + "\n")
                self._write_s += time.perf_counter() - tw
            meta = {"general_model": rows2, "trackers": records}
            th = time.perf_counter()
            for host in self.hosts:
                outs.extend(host.push(fno, meta))
            self._host_send_s += time.perf_counter() - th
            outs.extend(self.module.push(fno, image, meta))
        return outs

    def close(self) -> list:
        outs = self._publish(self.tracker.finish())
        outs.extend(self.module.close())
        for host in self.hosts:
            outs.extend(host.close())
        self.tracker.close()
        for fh in (self._gm_fh, self._trk_fh):
            if fh:
                fh.close()
        report = self.report()
        if self.out_dir:
            with io.open(os.path.join(self.out_dir, "pipeline_report.json"), "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=1, default=str)
        outs.append(Output("note", "pipeline_report", None, {
            "heads": report["heads"], "tracker_classes": report["tracker_classes"],
            "ms_per_frame_mean": {k: v.get("mean") for k, v in report["ms_per_frame"].items()},
            "module_hosts": report["module_hosts"]}))
        return outs

    def report(self) -> dict:
        import psutil

        mem = psutil.Process().memory_info()
        frames = len(self._times["total"])
        try:
            snap = self.gm.context.snapshot()
            context = {k: snap.get(k) for k in ("main_plane_track", "mode_plane_height", "frame_of_beginning",
                                                "main_front_wheel", "aircraft_type")}
        except Exception as e:  # the report must not fail the run
            context = {"error": f"{type(e).__name__}: {e}"}
        return {
            "module": self.module_name, "video": self.video_name, "heads": list(self.heads),
            "gm_variant": self.gm_variant, "gm_provider": self.gm_provider, "tracker_classes": list(self.tracker_classes),
            "exact_fast": self.exact_fast, "seed": self.seed, "pixels_to_module": self.pixels, "init_s": self.init_s,
            "frames": frames, "published_frames": self._published, "max_unpublished_frames": self._max_unpublished,
            "ms_per_frame": {k: _ms(v) for k, v in self._times.items()},
            "row_files_ms_per_frame": round(1000 * self._write_s / max(frames, 1), 3),
            "module_hosts": {h.module: {"per_frame": h.stats, "failed": h.failed} for h in self.hosts},
            "host_send_ms_per_frame": round(1000 * self._host_send_s / max(frames, 1), 3),
            "gm_heads": self.detectors.timings(), "tracker": self.tracker.report(), "causal_rows": vars(self.causal.stats),
            "gm_context_final": context,
            "process_memory_gb": {"private": round(getattr(mem, "private", 0) / 2**30, 2),
                                  "peak_working_set": round(getattr(mem, "peak_wset", 0) / 2**30, 2)},
        }
