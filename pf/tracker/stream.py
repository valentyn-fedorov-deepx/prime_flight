"""Tracker stream — the production tracker loop (`cv_trackers/tracker.py::detect` @bd43c3c) as a causal per-frame class.

`TrackerStream.update(frame_number, image_bgr, gm_rows)` consumes ONE decoded frame plus the GM rows of that frame
(second-run format `[x1, y1, x2, y2, conf, cls_id]`, the class-2 row carrying the height mode in the conf slot) and returns
the records that became FINAL at this frame. Records are v1 envelopes (`Track.to_json()`: tr_id, xyxy, cls_str, conf,
state_dict, data) so the v1-compat ndjson file is byte-compatible with production; the v2 bus strips the private
`_p0`/`_st` (`strip_private`).

Faithfulness (step 0 of PF-Q1-17): the per-object state machines are the vendored cv_common classes (`pf.tracker._v1`,
cv_common @2759daf), DeepSORT ×3 with the production configs, the same detection routing, obstacle rule, beltloader
typing, GSE re-initialisation, N_INIT publish delay and the retroactive `arrival_frame` rewrite through the airplane
buffer. What is deliberately NOT ported: `--save-video` drawing, per-frame `print`/`logging`, the `to_csv` log directory.

`TrackerOptions.exact_fast` switches on the output-identical performance paths (proven with seeded byte-level runs
against the production pin): `pf.tracker.fast_paths` (grey frames once per frame, vectorised in-box test, no stage-counter
print), `pf.tracker.fast_grouped_lk` (one optical-flow call per class grey pair and direction for beltloaders and GSE), no
full-frame copies of the tracked image, the bit-identical threaded noise estimate (`pf.tracker.fast_sigma`) and the three
DeepSORT updates in parallel threads. Default = production behaviour.
"""

from __future__ import annotations

import functools
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np

from pf.tracker._v1.bl_utils import get_bl_type
from pf.tracker._v1.common import (
    add_offset,
    bbox_area,
    bbox_rel,
    bboxes_iou,
    get_center,
    get_hw,
    get_relative_intersection,
)
from pf.tracker._v1.config import config as V1_CONFIG
from pf.tracker._v1.config import deep_sort_config
from pf.tracker._v1.track import Track
from pf.tracker._v1.tracked_object import FeatureTracker, ObjectSegmenter, Status
from pf.tracker._v1.transport import Airplane, Vehicle

IGNORE_DICT = {
    "gse": ["person", "cone"],
    "beltloader": ["person", "cone", "gse", "pushback", "trailer", "ladder"],
    "airplane": ["person", "cone", "gse", "pushback", "trailer", "beltloader", "ladder", "fuel_truck"],
}
YOLO_CLASS_MAPPING = {"beltloader": [0], "gse": [1]}
PRIVATE_STATE_KEYS = ("_p0", "_st")


@dataclass
class TrackerOptions:
    weights_dir: str = "weights"
    device: str = "cuda"
    cone_camera: bool = True
    plane_seg_weights: str = "yolo11s-seg_plane.pt"
    bl_gse_seg_weights: str = "yolo26s_seg_bl_gse_tr10_noalb.pt"
    # --- cost switches (production behaviour when False) -------------------------------------------
    exact_fast: bool = False  # output-identical performance paths (see module docstring)
    grouped_lk: bool = True  # within exact_fast: grouped optical flow for beltloaders/GSE
    fast_noise_gate: bool = False  # NOT exact: sigma on a half-resolution frame (needs calibration before use)
    # --- scope (production tracks all four) -------------------------------------------------------------
    # A real-time tracker keeps only the classes its modules read. Dropping a class skips its DeepSORT update, state
    # machines and segmentor; the airplane records are then NOT byte-identical to the full tracker (np.random draws
    # shift and the noise gate sees fewer tracked objects), so a scoped tracker is gated by module verdicts.
    classes: tuple = ("airplane", "beltloader", "gse", "person")


@dataclass
class StreamTimings:
    frames: int = 0
    deepsort_s: float = 0.0
    noise_s: float = 0.0
    airplane_s: float = 0.0
    beltloaders_s: float = 0.0
    gse_s: float = 0.0
    publish_s: float = 0.0
    total_s: float = 0.0

    def as_ms_per_frame(self) -> dict:
        n = max(self.frames, 1)
        return {k[:-2] + "_ms": round(1000 * v / n, 3) for k, v in vars(self).items() if k != "frames"}


def strip_private(record: dict) -> dict:
    """v2 bus record: the same envelope without the optical-flow point clouds (80–90 % of the bytes)."""
    sd = record.get("state_dict")
    if sd:
        record = dict(record)
        record["state_dict"] = {k: v for k, v in sd.items() if k not in PRIVATE_STATE_KEYS}
    return record


def check_obstacles(tracked_obj, xyxy, cfg=V1_CONFIG):
    """tracker.py::check_obstacles @bd43c3c — a GSE/trailer box covering a stopped beltloader in the door zone."""
    if (
        tracked_obj.status not in [Status.MOVING, Status.STOPPING]
        and get_relative_intersection(add_offset(xyxy, offset_x=0.1, offset_y=0.1), tracked_obj.xyxy) > 0.8
        and cfg["width"] * cfg["bl_range"][0] < get_center(tracked_obj.xyxy)[0] < cfg["width"] * cfg["bl_range"][1]
        and get_hw(tracked_obj.xyxy)[0] >= cfg["bl_min_height"]
    ):
        return False, xyxy
    return True, []


def replace_plane_arrival_frame(tracked_data, new_arrival_frame):
    if tracked_data and tracked_data[0].cls_str == "airplane":
        tracked_data[0].arrival_frame = new_arrival_frame
        tracked_data[0].state_dict["arrival_frame"] = new_arrival_frame


class NoiseGate:
    """Production: `skimage.estimate_sigma` on the full frame every `estimate_sigma_interval` seconds while any object is
    tracked; TV denoising (Chambolle, weight 5, 50 iterations) of the frame used for optical flow when sigma > 0.5.

    `exact_fast_sigma` uses the bit-identical threaded estimate; `copy_frames=False` returns the decoded frame itself
    instead of a copy when no denoising happens (nothing downstream writes to it)."""

    def __init__(self, fps: int, interval_s: int, fast: bool = False, device: str = "cuda",
                 exact_fast_sigma: bool = False, copy_frames: bool = True):
        self.delay = int(interval_s * fps)
        self.fast = fast
        self.device = device
        self.exact_fast_sigma = exact_fast_sigma
        self.copy_frames = copy_frames
        self.current_sigma = 0.0
        self.calls = 0
        self.denoised = 0

    def sigma(self, im0s: np.ndarray) -> float:
        self.calls += 1
        if self.fast:
            import cv2
            from skimage.restoration import estimate_sigma

            small = cv2.resize(im0s, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
            return float(estimate_sigma(small, average_sigmas=True, channel_axis=-1))
        if self.exact_fast_sigma:
            from pf.tracker.fast_sigma import estimate_sigma_rgb

            return estimate_sigma_rgb(im0s)
        from skimage.restoration import estimate_sigma

        return estimate_sigma(im0s, average_sigmas=True, channel_axis=-1)

    def image_to_track(self, frame_number: int, im0s: np.ndarray, any_object: bool) -> np.ndarray:
        if any_object:
            if (frame_number - 1) % self.delay == 0:
                self.current_sigma = self.sigma(im0s)
            if self.current_sigma > 0.5:
                self.denoised += 1
                return self.denoise(im0s)
        return im0s.copy() if self.copy_frames else im0s

    def denoise(self, im0s: np.ndarray) -> np.ndarray:
        try:
            import cupy as cp  # production (Linux, GPU)
            from cucim.skimage.restoration import denoise_tv_chambolle

            arr = cp.asarray(im0s.copy(), dtype=float)
            out = cp.asnumpy(denoise_tv_chambolle(arr, weight=5, eps=0.00005, max_num_iter=50, channel_axis=-1))
        except ImportError:  # torch port, bit-identical to scikit-image (scripts/win_shims/tv_chambolle_torch.py)
            import sys

            shims = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts", "win_shims"
            )
            if shims not in sys.path:
                sys.path.insert(0, shims)
            from tv_chambolle_torch import denoise_tv_chambolle

            out = denoise_tv_chambolle(
                im0s.astype(np.float64), weight=5, eps=0.00005, max_num_iter=50, channel_axis=-1, device=self.device
            )
        return out.astype(np.uint8)


class TrackerStream:
    def __init__(self, options: TrackerOptions | None = None, cfg: dict | None = None):
        import torch  # lazy

        self.opt = options or TrackerOptions()
        self.cfg = cfg or V1_CONFIG
        self.ds_cfg = deep_sort_config()
        use_cuda = self.opt.device != "cpu"
        from pf.tracker._v1.deep_sort_pytorch.deep_sort import DeepSort

        t = self.ds_cfg.DEEPSORT_TRANSPORT
        w = self.ds_cfg.DEEPSORT_WORKER
        wanted = set(self.opt.classes)
        self.bl_tracker = None if "beltloader" not in wanted else DeepSort(
            max_dist=t.MAX_DIST, min_confidence=t.MIN_CONFIDENCE, nms_max_overlap=t.NMS_MAX_OVERLAP,
            max_iou_distance=t.MAX_IOU_DISTANCE, max_age=t.MAX_AGE, n_init=t.N_INIT, nn_budget=t.NN_BUDGET,
            use_cuda=use_cuda, resnet=True,
        )
        self.gse_tracker = None if "gse" not in wanted else DeepSort(
            max_dist=t.MAX_DIST, min_confidence=t.MIN_CONFIDENCE, nms_max_overlap=t.NMS_MAX_OVERLAP,
            max_iou_distance=t.MAX_IOU_DISTANCE, max_age=t.MAX_AGE, n_init=t.N_INIT, nn_budget=t.NN_BUDGET,
            use_cuda=use_cuda, resnet=True, metric_type=t.METRIC_TYPE,
        )
        self.workers_tracker = None if "person" not in wanted else DeepSort(
            os.path.join(self.opt.weights_dir, self.cfg["deepsort_weights"]),
            max_dist=w.MAX_DIST, min_confidence=w.MIN_CONFIDENCE, nms_max_overlap=w.NMS_MAX_OVERLAP,
            max_iou_distance=w.MAX_IOU_DISTANCE, max_age=w.MAX_AGE, n_init=w.N_INIT, nn_budget=w.NN_BUDGET,
            use_cuda=use_cuda, metric_type=w.METRIC_TYPE,
        )
        self.n_init_delay = int(w.N_INIT)

        import logging

        from ultralytics import YOLO
        from ultralytics.utils import LOGGER

        LOGGER.setLevel(logging.WARNING)
        device = "cpu" if self.opt.device == "cpu" else "cuda:0"
        self.plane_segmentor = YOLO(os.path.join(self.opt.weights_dir, self.opt.plane_seg_weights)).to(device)
        self.bl_gse_segmentor = (YOLO(os.path.join(self.opt.weights_dir, self.opt.bl_gse_seg_weights)).to(device)
                                 if wanted & {"beltloader", "gse"} else None)
        ObjectSegmenter.Classwise_buffer_mask = {}  # class-level cache in cv_common: reset per stream

        self.fast = None
        self.grouped = None
        self.grouped_stats: dict = {}
        self._pool = None
        if self.opt.exact_fast:
            from pf.tracker import fast_paths

            fast_paths.enable()
            fast_paths.end_stream()
            self.fast = fast_paths
            self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="pf-deepsort")
            if self.opt.grouped_lk:
                from pf.tracker import fast_grouped_lk

                fast_grouped_lk.check_pinned_source()
                self.grouped = fast_grouped_lk

        self.noise = NoiseGate(
            self.cfg["fps"], self.cfg["estimate_sigma_interval"], fast=self.opt.fast_noise_gate, device=device,
            exact_fast_sigma=self.opt.exact_fast, copy_frames=not self.opt.exact_fast,
        )
        self.str2id = self.cfg["str2id"]
        self.ignore_ids = {cls_name: [self.str2id[c] for c in classes] for cls_name, classes in IGNORE_DICT.items()}
        self.tracking = self.cfg["tracking"]
        self.torch = torch

        # --- state of detect() ---------------------------------------------------------------------
        self.bl_labels_dict = {"front": None, "back": None}
        self.bl_obj_dict: dict = {}
        self.bl_to_init: dict = {}
        self.gse_obj_dict: dict = {}
        self.main_airplane = None
        self.prev_img_to_track = None
        self.airplane_height_mode = None
        self.tracked_data_buffer: list = []
        self.airplane_data_buffer: list = []
        self.accumulate_airplane_data = False
        self.real_arrival_frame = None
        self.confirmed_workers_ids: list = []
        self.timings = StreamTimings()
        self.frames_seen = 0

    # ------------------------------------------------------------------------------------------------
    def _deepsort_updates(self, im0s, bl_xywh, bl_confs, w_xywh, w_confs, g_xywh, g_confs):
        """The three DeepSORT updates of tracker.py in production order (BL, workers + tentative, GSE)."""
        torch = self.torch
        xywhs_beltloaders = torch.Tensor(bl_xywh)
        confss_beltloaders = torch.Tensor(bl_confs)
        xywhs_workers = torch.Tensor(w_xywh)
        confss_workers = torch.Tensor(w_confs)
        xywhs_gse = torch.Tensor(g_xywh)
        confss_gse = torch.Tensor(g_confs)

        def beltloaders():
            if self.bl_tracker is None:
                return []
            if bl_xywh is not None and len(bl_xywh):
                return self.bl_tracker.update(xywhs_beltloaders, confss_beltloaders, im0s)
            self.bl_tracker.increment_ages()
            return []

        def workers():
            if self.workers_tracker is None:
                return [], []
            if w_xywh is not None and len(w_xywh):
                out = self.workers_tracker.update(xywhs_workers, confss_workers, im0s)
                return out, self.workers_tracker.get_tentative_tracks()
            self.workers_tracker.increment_ages()
            return [], []

        def gse():
            if self.gse_tracker is None:
                return []
            if g_xywh is not None and len(g_xywh):
                return self.gse_tracker.update(xywhs_gse, confss_gse, im0s)
            self.gse_tracker.increment_ages()
            return []

        if self._pool is None:
            outputs_beltloaders = beltloaders()
            outputs_workers, outputs_workers_tentative = workers()
            outputs_gse = gse()
        else:  # independent trackers → the same results in any interleaving
            f_bl, f_w, f_g = self._pool.submit(beltloaders), self._pool.submit(workers), self._pool.submit(gse)
            outputs_beltloaders = f_bl.result()
            outputs_workers, outputs_workers_tentative = f_w.result()
            outputs_gse = f_g.result()
        return outputs_beltloaders, outputs_workers, outputs_workers_tentative, outputs_gse

    # ---- beltloader loop pieces (shared by the sequential and the grouped variants) --------------------
    def _bl_record(self, tracked_obj, beltloader_id, tracked_data):
        if self.bl_labels_dict["front"] == beltloader_id:
            bl_type = "front"
        elif self.bl_labels_dict["back"] == beltloader_id:
            bl_type = "back"
        else:
            bl_type = "undefined"
        tracked_data.append(
            Track(beltloader_id, tracked_obj.xyxy, "beltloader", state_dict=tracked_obj.to_state_dict(),
                  data={"bl_type": bl_type})
        )

    def _bl_after_update_existing(self, tracked_obj, beltloader_id, observed, beltloader_type, biggest_doors_xyxy,
                                  engines_det, back_wheels_det, tracked_data):
        if tracked_obj.is_stopped and observed:
            bl_type = get_bl_type(tracked_obj, beltloader_type, self.opt.cone_camera, biggest_doors_xyxy,
                                  engines_det, back_wheels_det, fps=self.cfg["fps"])
            if bl_type != "undefined":
                self.bl_labels_dict[bl_type] = beltloader_id
        elif tracked_obj.status == Status.MOVING:
            for bl_type in self.bl_labels_dict.keys():
                if self.bl_labels_dict[bl_type] == beltloader_id:
                    self.bl_labels_dict[bl_type] = None
        self._bl_record(tracked_obj, beltloader_id, tracked_data)

    def _bl_type_new(self, tracked_obj, beltloader_id, observed, beltloader_type, biggest_doors_xyxy,
                     engines_det, back_wheels_det):
        if tracked_obj.is_stopped and observed:
            bl_type = get_bl_type(tracked_obj, beltloader_type, self.opt.cone_camera, biggest_doors_xyxy,
                                  engines_det, back_wheels_det, fps=self.cfg["fps"])
            if bl_type != "undefined":
                self.bl_labels_dict[bl_type] = beltloader_id

    def _beltloaders_grouped(self, outputs_beltloaders, det, frame_number, img_to_track, bboxes_to_ignore,
                             beltloader_type, biggest_doors_xyxy, engines_det, back_wheels_det, tracked_data):
        """The beltloader loop with grouped optical flow (pf.tracker.fast_grouped_lk.Batch) — same order of effects."""
        cfg, s2i = self.cfg, self.str2id
        gse_trailer_ids = [s2i["gse"], s2i["trailer"]]
        batch = self.grouped.Batch(FeatureTracker._lk_params, self.grouped_stats)
        for *bl_xyxy, beltloader_id in outputs_beltloaders:
            beltloader_id = int(beltloader_id)
            bl_xyxy = tuple(map(int, bl_xyxy))
            if beltloader_id in self.bl_obj_dict:
                tracked_obj = self.bl_obj_dict[beltloader_id]
                observed = True
                for *xyxy, conf, cls_id in det:
                    if cls_id in gse_trailer_ids and observed:
                        observed, _obstacle = check_obstacles(tracked_obj, xyxy, cfg)
                if not observed:
                    tracked_obj.set_unobserved()
                    batch.then(functools.partial(self._bl_record, tracked_obj, beltloader_id, tracked_data))
                else:
                    tracked_obj.set_observed()
                    batch.update(tracked_obj, bl_xyxy, self.prev_img_to_track, img_to_track, frame_number,
                                 self.bl_gse_segmentor, bboxes_to_ignore["beltloader"], YOLO_CLASS_MAPPING["beltloader"])
                    batch.then(functools.partial(self._bl_after_update_existing, tracked_obj, beltloader_id, observed,
                                                 beltloader_type, biggest_doors_xyxy, engines_det, back_wheels_det,
                                                 tracked_data))
            elif beltloader_id in self.bl_to_init:
                tracked_obj = self.bl_to_init.pop(beltloader_id)
                observed = True
                for *xyxy, conf, cls_id in det:
                    if cls_id in gse_trailer_ids and observed:
                        observed, _obstacle = check_obstacles(tracked_obj, xyxy, cfg)
                if observed:
                    tracked_obj.set_observed()
                    batch.update(tracked_obj, bl_xyxy, self.prev_img_to_track, img_to_track, frame_number,
                                 self.bl_gse_segmentor, bboxes_to_ignore["beltloader"], YOLO_CLASS_MAPPING["beltloader"])
                    re_initialized = False
                    for bl_id in reversed(list(self.bl_obj_dict.keys())):
                        if get_relative_intersection(tracked_obj.xyxy, self.bl_obj_dict[bl_id].recent_biggest_bbox) > 0.3:
                            self.bl_obj_dict[beltloader_id] = self.bl_obj_dict.pop(bl_id)
                            re_initialized = True
                            break
                    if not re_initialized:
                        batch.then(functools.partial(self._bl_type_new, tracked_obj, beltloader_id, observed,
                                                     beltloader_type, biggest_doors_xyxy, engines_det, back_wheels_det))
                        self.bl_obj_dict[beltloader_id] = tracked_obj
            else:
                self.bl_to_init[beltloader_id] = Vehicle(
                    obj_id=beltloader_id, class_name="beltloader", xyxy=bl_xyxy,
                    tracking_params=self.tracking["beltloader"]["tracked_object"],
                )
        batch.flush()

    def _gse_record(self, obj, gse_id, tracked_data):
        tracked_data.append(Track(gse_id, obj.xyxy, "gse", state_dict=obj.to_state_dict()))

    def _gse_grouped(self, outputs_gse, frame_number, img_to_track, bboxes_to_ignore, tracked_data):
        """The GSE loop with grouped optical flow — same order of effects."""
        cfg = self.cfg
        batch = self.grouped.Batch(FeatureTracker._lk_params, self.grouped_stats)
        for *gse_xyxy, gse_id in outputs_gse:
            gse_id = int(gse_id)
            gse_xyxy = tuple(map(int, gse_xyxy))
            if gse_id not in self.gse_obj_dict:
                re_init_id = None
                closest_objects = [(bboxes_iou(gse_xyxy, gse_obj.xyxy), gid) for gid, gse_obj in self.gse_obj_dict.items()]
                if len(closest_objects) > 0:
                    max_iou, closest_id = sorted(closest_objects, reverse=True)[0]
                    if max_iou > cfg["gse_iou_reinit_thresh"]:
                        re_init_id = closest_id
                if re_init_id is not None:
                    self.gse_obj_dict[gse_id] = self.gse_obj_dict.pop(re_init_id)
                else:
                    self.gse_obj_dict[gse_id] = Vehicle(
                        obj_id=gse_id, class_name="gse", xyxy=gse_xyxy,
                        tracking_params=self.tracking["gse"]["tracked_object"],
                    )
            else:
                batch.update(self.gse_obj_dict[gse_id], gse_xyxy, self.prev_img_to_track, img_to_track, frame_number,
                             self.bl_gse_segmentor, bboxes_to_ignore["gse"], YOLO_CLASS_MAPPING["gse"])
            batch.then(functools.partial(self._gse_record, self.gse_obj_dict[gse_id], gse_id, tracked_data))
        batch.flush()

    def update(self, frame_number: int, im0s: np.ndarray, det) -> list:
        """One frame → list of (frame_id, [record dicts]) that became final. `det`: GM rows of this frame (list)."""
        t_start = time.perf_counter()
        cfg, s2i = self.cfg, self.str2id
        bboxes_to_ignore = {c: list() for c in IGNORE_DICT}
        bbox_xywh_beltloaders, confs_beltloaders = [], []
        bbox_xywh_workers, confs_workers = [], []
        bbox_xywh_gse, confs_gse = [], []
        airplane_det, nose_list = [], []
        tracked_data, tracked_data_tentative = [], []
        front_door_det, back_door_det = [], []
        front_door_xyxy, back_door_xyxy = [], []
        engines_det, back_wheels_det = [], []
        beltloader_type = {"front": None, "back": None}
        if det is None:
            det = []

        if det is not None and len(det):
            for *xyxy, conf, cls_id in det:
                xyxy = tuple(map(int, xyxy))
                cls_id = int(cls_id)
                conf = float(conf)
                for cls_name, ignore_ids in self.ignore_ids.items():
                    if cls_id in ignore_ids:
                        bboxes_to_ignore[cls_name].append(xyxy)
                if cls_id == s2i["airplane_nose"]:
                    nose_list.append(xyxy)
                if cls_id == s2i["beltloader"]:
                    bl_h, bl_w = get_hw(xyxy)
                    if min(bl_h, bl_w) / max(bl_h, bl_w) >= 0.9:
                        continue  # small square detection
                    x_c, y_c, bbox_w, bbox_h = bbox_rel(*xyxy)
                    bbox_xywh_beltloaders.append([x_c, y_c, bbox_w, bbox_h])
                    confs_beltloaders.append([float(conf)])
                elif cls_id == s2i["gse"]:
                    x_c, y_c, bbox_w, bbox_h = bbox_rel(*xyxy)
                    bbox_xywh_gse.append([x_c, y_c, bbox_w, bbox_h])
                    confs_gse.append([float(conf)])
                elif cls_id == s2i["person"]:
                    x_c, y_c, bbox_w, bbox_h = bbox_rel(*xyxy)
                    bbox_xywh_workers.append([x_c, y_c, bbox_w, bbox_h])
                    confs_workers.append([float(conf)])
                elif cls_id in [s2i["front_door"]]:
                    front_door_det.append(xyxy)
                elif cls_id in [s2i["back_door"]]:
                    back_door_det.append(xyxy)
                if cls_id == s2i["airplane"]:
                    self.airplane_height_mode = conf
                    airplane_det.append(xyxy)
                if cls_id == s2i["airplane_engine"]:
                    engines_det.append(xyxy)
                if cls_id == s2i["back_wheel"]:
                    back_wheels_det.append(xyxy)

        # ------------------------- DeepSORT updates -------------------------
        t0 = time.perf_counter()
        if bbox_xywh_beltloaders:
            combined = list(zip(bbox_xywh_beltloaders, confs_beltloaders))
            combined.sort(key=lambda x: x[0][2] * x[0][3], reverse=True)
            bbox_xywh_beltloaders, confs_beltloaders = zip(*combined)
        outputs_beltloaders, outputs_workers, outputs_workers_tentative, outputs_gse = self._deepsort_updates(
            im0s, bbox_xywh_beltloaders, confs_beltloaders, bbox_xywh_workers, confs_workers, bbox_xywh_gse, confs_gse
        )
        t1 = time.perf_counter()
        self.timings.deepsort_s += t1 - t0

        # ------------------------- noise gate -------------------------
        any_object = bool(len(airplane_det) or len(outputs_gse) or len(outputs_workers) or len(outputs_beltloaders))
        img_to_track = self.noise.image_to_track(frame_number, im0s, any_object)
        if self.fast is not None:
            self.fast.begin_frame(self.prev_img_to_track, img_to_track)
        t2 = time.perf_counter()
        self.timings.noise_s += t2 - t1

        # ------------------------- main airplane -------------------------
        if len(airplane_det) > 0:
            airplane_xyxy = max(airplane_det, key=lambda x: abs(x[2] - x[0]) * abs(x[3] - x[1]))
            if self.main_airplane is None:
                self.main_airplane = Airplane(
                    obj_id=1, class_name="airplane", xyxy=airplane_xyxy,
                    tracking_params=self.tracking["airplane"]["tracked_object"], height_mode=self.airplane_height_mode,
                )
            else:
                self.main_airplane.update_params(
                    airplane_xyxy, self.prev_img_to_track, img_to_track, frame_number, self.plane_segmentor,
                    nose_list, bboxes_to_ignore["airplane"],
                )
            if self.main_airplane.arrival_frame is None and self.main_airplane.status in [Status.STOPPING, Status.STOPPED]:
                self.accumulate_airplane_data = True
            else:
                self.accumulate_airplane_data = False
            tracked_data.append(
                Track(tr_id=self.main_airplane.obj_id, xyxy=self.main_airplane.xyxy, cls_str="airplane",
                      state_dict=self.main_airplane.to_state_dict())
            )
        t3 = time.perf_counter()
        self.timings.airplane_s += t3 - t2

        # ------------------------- biggest doors -------------------------
        for biggest_door_xyxy, door_detections in [(front_door_xyxy, front_door_det), (back_door_xyxy, back_door_det)]:
            if door_detections:
                for coordinate in sorted(door_detections, key=lambda x: bbox_area(x), reverse=True)[0]:
                    biggest_door_xyxy.append(coordinate)
        biggest_doors_xyxy = {"front": front_door_xyxy, "back": back_door_xyxy}

        # ------------------------- beltloaders -------------------------
        if self.bl_tracker is None:
            pass
        elif self.grouped is not None:
            self._beltloaders_grouped(outputs_beltloaders, det, frame_number, img_to_track, bboxes_to_ignore,
                                      beltloader_type, biggest_doors_xyxy, engines_det, back_wheels_det, tracked_data)
        else:
            gse_trailer_ids = [s2i["gse"], s2i["trailer"]]
            for *bl_xyxy, beltloader_id in outputs_beltloaders:
                beltloader_id = int(beltloader_id)
                bl_xyxy = tuple(map(int, bl_xyxy))
                if beltloader_id in self.bl_obj_dict:
                    tracked_obj = self.bl_obj_dict[beltloader_id]
                    observed = True
                    for *xyxy, conf, cls_id in det:
                        if cls_id in gse_trailer_ids and observed:
                            observed, _obstacle = check_obstacles(tracked_obj, xyxy, cfg)
                    if not observed:
                        tracked_obj.set_unobserved()
                    else:
                        tracked_obj.set_observed()
                        tracked_obj.update_params(
                            bl_xyxy, self.prev_img_to_track, img_to_track, frame_number, self.bl_gse_segmentor,
                            bboxes_to_remove=bboxes_to_ignore["beltloader"], yolo_idx=YOLO_CLASS_MAPPING["beltloader"],
                        )
                        if tracked_obj.is_stopped and observed:
                            bl_type = get_bl_type(tracked_obj, beltloader_type, self.opt.cone_camera, biggest_doors_xyxy,
                                                  engines_det, back_wheels_det, fps=cfg["fps"])
                            if bl_type != "undefined":
                                self.bl_labels_dict[bl_type] = beltloader_id
                        elif tracked_obj.status == Status.MOVING:
                            for bl_type in self.bl_labels_dict.keys():
                                if self.bl_labels_dict[bl_type] == beltloader_id:
                                    self.bl_labels_dict[bl_type] = None
                    self._bl_record(tracked_obj, beltloader_id, tracked_data)
                elif beltloader_id in self.bl_to_init:
                    tracked_obj = self.bl_to_init.pop(beltloader_id)
                    observed = True
                    for *xyxy, conf, cls_id in det:
                        if cls_id in gse_trailer_ids and observed:
                            observed, _obstacle = check_obstacles(tracked_obj, xyxy, cfg)
                    if observed:
                        tracked_obj.set_observed()
                        tracked_obj.update_params(
                            bl_xyxy, self.prev_img_to_track, img_to_track, frame_number, self.bl_gse_segmentor,
                            bboxes_to_remove=bboxes_to_ignore["beltloader"], yolo_idx=YOLO_CLASS_MAPPING["beltloader"],
                        )
                        re_initialized = False
                        for bl_id in reversed(list(self.bl_obj_dict.keys())):
                            if get_relative_intersection(tracked_obj.xyxy, self.bl_obj_dict[bl_id].recent_biggest_bbox) > 0.3:
                                self.bl_obj_dict[beltloader_id] = self.bl_obj_dict.pop(bl_id)
                                re_initialized = True
                                break
                        if not re_initialized:
                            if tracked_obj.is_stopped and observed:
                                bl_type = get_bl_type(tracked_obj, beltloader_type, self.opt.cone_camera,
                                                      biggest_doors_xyxy, engines_det, back_wheels_det, fps=cfg["fps"])
                                if bl_type != "undefined":
                                    self.bl_labels_dict[bl_type] = beltloader_id
                            self.bl_obj_dict[beltloader_id] = tracked_obj
                else:
                    self.bl_to_init[beltloader_id] = Vehicle(
                        obj_id=beltloader_id, class_name="beltloader", xyxy=bl_xyxy,
                        tracking_params=self.tracking["beltloader"]["tracked_object"],
                    )
        t4 = time.perf_counter()
        self.timings.beltloaders_s += t4 - t3

        # ------------------------- workers -------------------------
        for *w_xyxy, worker_id in outputs_workers:
            worker_id = int(worker_id)
            w_xyxy = tuple(map(int, w_xyxy))
            if worker_id not in self.confirmed_workers_ids:
                for _, _, _, confirmed_tracks, tentative_tracks in self.tracked_data_buffer:
                    for tentative_track in tentative_tracks:
                        if tentative_track.cls_str == "person" and tentative_track.tr_id == worker_id:
                            confirmed_tracks.append(tentative_track)
            self.confirmed_workers_ids.append(worker_id)
            tracked_data.append(Track(worker_id, w_xyxy, "person"))
        for *w_xyxy, worker_id in outputs_workers_tentative:
            worker_id = int(worker_id)
            w_xyxy = tuple(map(int, w_xyxy))
            tracked_data_tentative.append(Track(worker_id, w_xyxy, "person"))

        # ------------------------- GSE -------------------------
        if self.gse_tracker is None:
            pass
        elif self.grouped is not None:
            self._gse_grouped(outputs_gse, frame_number, img_to_track, bboxes_to_ignore, tracked_data)
        else:
            for *gse_xyxy, gse_id in outputs_gse:
                gse_id = int(gse_id)
                gse_xyxy = tuple(map(int, gse_xyxy))
                if gse_id not in self.gse_obj_dict:
                    re_init_id = None
                    closest_objects = [(bboxes_iou(gse_xyxy, gse_obj.xyxy), gid) for gid, gse_obj in self.gse_obj_dict.items()]
                    if len(closest_objects) > 0:
                        max_iou, closest_id = sorted(closest_objects, reverse=True)[0]
                        if max_iou > cfg["gse_iou_reinit_thresh"]:
                            re_init_id = closest_id
                    if re_init_id is not None:
                        self.gse_obj_dict[gse_id] = self.gse_obj_dict.pop(re_init_id)
                    else:
                        self.gse_obj_dict[gse_id] = Vehicle(
                            obj_id=gse_id, class_name="gse", xyxy=gse_xyxy,
                            tracking_params=self.tracking["gse"]["tracked_object"],
                        )
                else:
                    self.gse_obj_dict[gse_id].update_params(
                        gse_xyxy, self.prev_img_to_track, img_to_track, frame_number, self.bl_gse_segmentor,
                        bboxes_to_remove=bboxes_to_ignore["gse"], yolo_idx=YOLO_CLASS_MAPPING["gse"],
                    )
                self._gse_record(self.gse_obj_dict[gse_id], gse_id, tracked_data)
        t5 = time.perf_counter()
        self.timings.gse_s += t5 - t4

        # ------------------------- buffers / publish -------------------------
        out = []
        arrival_frame = self.main_airplane.arrival_frame if self.main_airplane is not None else None
        self.tracked_data_buffer.append(
            (frame_number, arrival_frame, self.accumulate_airplane_data, tracked_data, tracked_data_tentative)
        )
        if len(self.tracked_data_buffer) >= self.n_init_delay:
            fno, arrival_frame, accumulate_airplane, tracked_data, _ = self.tracked_data_buffer.pop(0)
            if accumulate_airplane:
                self.airplane_data_buffer.append((tracked_data, fno))
            else:
                if self.airplane_data_buffer:
                    if arrival_frame and not self.real_arrival_frame:
                        self.real_arrival_frame = self.airplane_data_buffer[0][1]
                        self.main_airplane.arrival_frame = self.real_arrival_frame
                        for _, _, _, res_tracked_data, _ in self.tracked_data_buffer:
                            replace_plane_arrival_frame(res_tracked_data, self.real_arrival_frame)
                        replace_plane_arrival_frame(tracked_data, self.real_arrival_frame)
                        for stored_tracked_data, _sfn in self.airplane_data_buffer:
                            replace_plane_arrival_frame(stored_tracked_data, self.real_arrival_frame)
                    for stored_tracked_data, stored_frame_number in self.airplane_data_buffer:
                        out.append((stored_frame_number, [tr.to_json() for tr in stored_tracked_data]))
                    self.airplane_data_buffer.clear()
                out.append((fno, [tr.to_json() for tr in tracked_data]))
        self.prev_img_to_track = img_to_track if self.fast is not None else img_to_track.copy()
        t6 = time.perf_counter()
        self.timings.publish_s += t6 - t5
        self.timings.frames += 1
        self.timings.total_s += t6 - t_start
        self.frames_seen += 1
        return out

    def finish(self) -> list:
        """Flush the publish buffers at the end of the video (same order as production)."""
        out = []
        for fno, _, _, tracked_data, _ in self.tracked_data_buffer:
            out.append((fno, [tr.to_json() for tr in tracked_data]))
        for tracked_data, fno in self.airplane_data_buffer:
            out.append((fno, [tr.to_json() for tr in tracked_data]))
        self.tracked_data_buffer.clear()
        self.airplane_data_buffer.clear()
        return out

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None
        if self.fast is not None:
            self.fast.end_stream()

    def report(self) -> dict:
        return {
            "frames": self.frames_seen,
            "exact_fast": self.opt.exact_fast,
            "classes": list(self.opt.classes),
            "grouped_lk": self.grouped is not None,
            "grouped_lk_stats": dict(self.grouped_stats),
            "timings_ms_per_frame": self.timings.as_ms_per_frame(),
            "noise_gate": {"sigma_calls": self.noise.calls, "denoised_frames": self.noise.denoised,
                           "last_sigma": round(float(self.noise.current_sigma), 4)},
            "identities": {
                "beltloaders": sorted(self.bl_obj_dict), "gse": sorted(self.gse_obj_dict),
                "workers": len(set(self.confirmed_workers_ids)),
                "airplane_arrival_frame": self.main_airplane.arrival_frame if self.main_airplane else None,
            },
        }
