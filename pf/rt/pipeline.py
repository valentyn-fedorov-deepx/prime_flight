"""GM v2 + Tracker v2 inside the real-time branch: decoded frames in, production modules fed with rows produced live.

    decoded frame ─► GM heads ─► first-run rows ─► VideoContextV2 ─► causal second-run rows (pf.pipeline.causal_rows)
                                                                          │
                          Tracker v2 (one per event, scoped classes) ◄────┘  records final after the N_INIT delay (1 s)
                                  │ (frame_id, records), in frame order
                                  ├─► primary production module in this process (pf.rt.prod_module, metadata="live")
                                  └─► extra modules, one process each (pf.rt.module_host), pixels through a shared ring

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
                 pixels: bool = True, out_dir: str | None = None, write_rows: bool = True, extra_modules=None,
                 monitor=None, filter_rows: bool = False, alerts_file: bool = True, gating: bool = False):
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
        self.filter_rows = bool(filter_rows)
        self.gating = bool(gating)  # stage gating needs an event source: PF-Q1-03
        self.alerts_file = bool(alerts_file)
        self.bus = None
        self.extra_modules = list(extra_modules or [])
        self.hosts = []
        if any(bool(extra.get("pixels")) for extra in self.extra_modules):
            self.pixels = True  # the pipeline keeps the frames a hosted module still needs
        self.ring = None
        self.monitor = monitor  # the live page sees the published frame: the rows and records the modules were given
        self.feeds_monitor_frames = monitor is not None
        self.video_name = None
        self.manifest: dict = {}
        self._rows2: dict = {}
        self._images: dict = {}
        self._mon_images: dict = {}
        self._last_published = (0, 0, 0)  # frame id, rows, records
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

    def _build_hosts(self, cm) -> None:
        """One component per extra module: its declared subscription, its gate, outputs on the shared bus."""
        from pf.rt.component import ComponentSpec
        from pf.rt.module_host import ModuleHost

        for extra in self.extra_modules:
            extra_args = dict(extra.get("module_args") or {})
            extra_args["cone_camera"] = self.cone_camera
            spec = ComponentSpec.for_module(extra["module"], pixels=bool(extra.get("pixels")))
            self.hosts.append(ModuleHost(extra["module"], extra_args, pixels=bool(extra.get("pixels")), spec=spec,
                                         subscription=spec.subscription(lambda name: cm.str2id.get(name)),
                                         bus=self.bus, filter_rows=self.filter_rows, gating=self.gating))

    def start(self, fps: float) -> None:
        super().start(fps)
        os.environ.update({k: str(v) for k, v in (self.module.env or {}).items()})
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from pf.gm.onnx_detector import YoloV8Onnx, YoloV8OnnxConfig
        from pf.gm.rows import ClassMap
        from pf.pipeline import GmStream
        from pf.pipeline.causal_rows import CausalSecondRun
        from pf.pipeline.gm_stream import Detectors
        from pf.rt.component import ComponentSpec, OutputBus, ndjson_sink
        from pf.tracker.stream import TrackerOptions, TrackerStream
        from scripts.gm_v2_run import load_str2id

        cm = ClassMap(load_str2id(self.str2id))  # the class map the components declare their rows in
        sinks = []
        if self.alerts_file and self.out_dir:
            os.makedirs(self.out_dir, exist_ok=True)
            sinks.append(ndjson_sink(os.path.join(self.out_dir, "component_outputs.ndjson")))
        self.bus = OutputBus(sinks=sinks)
        t_hosts = time.perf_counter()
        self._build_hosts(cm)
        frame_spec = None
        if any(h.pixels for h in self.hosts):
            from pf.rt.module_host import SharedFrameRing

            self.ring = SharedFrameRing()
            frame_spec = self.ring.spec
        for host in self.hosts:  # before anything changes the working directory
            host.start(self.manifest, fps, frame_spec)
        self.init_s["module_hosts"] = round(time.perf_counter() - t_hosts, 1)
        import torch  # noqa: F401

        t0 = time.perf_counter()

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
        if self.monitor is not None:
            self.monitor.set_class_names(cm.id2str)
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
        elif self.monitor is not None:
            self._mon_images[fid] = image  # a reference, freed when the frame is published
        self._max_unpublished = max(self._max_unpublished, len(self._rows2))
        outs = self._publish(published)
        if self.bus is not None:  # whatever the components produced since the last frame, already stamped and delivered
            outs.extend(self.bus.drain())
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
            # A module in batch reads these records from the tracker file, i.e. after a JSON round trip: lists, never
            # tuples. Handing over the tracker's own objects crashed three modules that edit a box in place ("'tuple'
            # object does not support item assignment"), so the live hand-off goes through the same trip.
            encoded = json.dumps(records)
            records = json.loads(encoded)
            if self.write_rows:
                tw = time.perf_counter()
                self._gm_fh.write(ndjson_line(fno, rows2))
                self._trk_fh.write('{"%d": %s}\n' % (self._published, encoded))
                self._write_s += time.perf_counter() - tw
            meta = {"general_model": rows2, "trackers": records}
            th = time.perf_counter()
            slot = self.ring.write(fno, image, [h for h in self.hosts if h.pixels]) if self.ring is not None else None
            for host in self.hosts:
                outs.extend(host.push(fno, meta, slot))
            self._host_send_s += time.perf_counter() - th
            outs.extend(self.module.push(fno, image, meta))
            if self.monitor is not None:
                self._last_published = (fno, len(rows2), len(records))
                view = image if image is not None else self._mon_images.get(fno)
                for stale in [k for k in self._mon_images if k <= fno]:
                    del self._mon_images[stale]
                self.monitor.set_frame(view, rows2, records, fno)
        return outs

    # ------------------------------------------------------------------ live view

    def module_names(self) -> list:
        return [self.module_name, *[h.module for h in self.hosts]]

    def live_state(self) -> dict:
        """What the page shows about the branch itself; recent means, not the whole run."""
        window = 50
        ms = {k: (round(1000.0 * sum(v[-window:]) / len(v[-window:]), 2) if v else None) for k, v in self._times.items()}
        fno, rows, records = self._last_published
        return {
            "components_ms": ms,
            "gm": {"heads": list(self.heads), "rows": rows, "variant": self.gm_variant, "provider": self.gm_provider},
            "tracker": {"classes": list(self.tracker_classes), "records": records,
                        "publish_lag_frames": len(self._rows2), "published_frame": fno},
            "queues": {"unpublished": len(self._rows2)},
            "components": [{"module": h.module, "gate": h.gate.as_dict(), "frames_sent": h.frames_sent,
                            "frames_skipped": h.frames_skipped, "pixels": h.pixels,
                            "rows_dropped": h.rows_dropped, "failed": h.failed} for h in self.hosts],
            "bus": self.bus.report() if self.bus is not None else {},
        }

    def close(self) -> list:
        outs = self._publish(self.tracker.finish())
        outs.extend(self.module.close())
        for host in self.hosts:
            outs.extend(host.close())
        if self.bus is not None:
            outs.extend(self.bus.drain())  # a component that answered while it was closing
            for sink in self.bus.sinks:
                if hasattr(sink, "close"):
                    sink.close()
        if self.ring is not None:
            self.ring.close()
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
            "module_hosts": {h.module: h.report() for h in self.hosts},
            "output_bus": self.bus.report() if self.bus is not None else {},
            "host_send_ms_per_frame": round(1000 * self._host_send_s / max(frames, 1), 3),
            "gm_heads": self.detectors.timings(), "tracker": self.tracker.report(), "causal_rows": vars(self.causal.stats),
            "gm_context_final": context,
            "process_memory_gb": {"private": round(getattr(mem, "private", 0) / 2**30, 2),
                                  "peak_working_set": round(getattr(mem, "peak_wset", 0) / 2**30, 2)},
        }
