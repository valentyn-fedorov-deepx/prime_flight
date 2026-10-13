"""Module pose interfaces served by one shared ONNX SimCC model (pose unification), module code unchanged.

The pose modules reach a pose network through three interfaces:

  mmpose    `from mmpose.apis import inference_topdown, init_model`: hand-signals, steering, lead-marshaller, wing-walkers
            (HRNet-W48 256x192) and pin-verification (SimCC ResNet-50 384x288), both with flip test. They read
            `pred_instances.keypoints[0]` (17, 2) / `keypoint_scores[0]` (17,); pin-verification also `gt_instances.bboxes`
            and `merge_data_samples`; steering and pin-verification build a visualizer from `model.cfg.visualizer` and
            `model.dataset_meta`.
  movenet   `from onnx_thunder_inference import PoseEstimation`: fod-walk (MoveNet SinglePose Thunder on the person crop,
            letterboxed to 256x256); only `is_backside` is called, which compares the shoulders' x.
  rtmpose   `from onnx_model_utils import build_session, generate_keypoints`: gse-chocks (the same RTMPose-l file, run on
            the cut-out crop, which leaves the 1.25 padding black, and on BGR); keypoints relative to the crop.

`install()` patches every interface the module folder offers. Call it before the module is imported (the names are bound
at import). The mmpose functions return real `PoseDataSample` / `InstanceData` objects carrying the fields mmpose 1.3.1
fills, so `merge_data_samples` and the visualizers keep working. `init_model` reads the module's config only (for `cfg`
and `dataset_meta`); no module pose weights are loaded. MoveNet's output is given in MoveNet's own frame (y, x in the
letterboxed 256x256 input, truncated to integers as `predict` does). gse-chocks gets crop-relative keypoints, as before.

`install_timing()` is the control: the modules' own models, unchanged, with the same call / box / time counters.
"""

from __future__ import annotations

import importlib.util
import os
import time

import numpy as np

from pf.pose.topdown_onnx import PoseTimings, SimccTopdown


def _offered(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class PoseModelProxy:
    """What `init_model` returns: the module's config and dataset meta; the network is the shared ONNX model."""

    def __init__(self, cfg, dataset_meta, runner: SimccTopdown):
        self.cfg = cfg
        self.dataset_meta = dataset_meta
        self.runner = runner

    def eval(self):
        return self

    def to(self, *args, **kwargs):
        return self


def _config_and_meta(config):
    from mmengine.config import Config

    from mmpose.apis.inference import dataset_meta_from_config
    from mmpose.datasets.datasets.utils import parse_pose_metainfo
    from mmpose.utils import register_all_modules

    register_all_modules()  # what init_model's init_default_scope('mmpose') gives the visualizer registry
    if isinstance(config, Config):
        cfg = config
    else:
        try:
            cfg = Config.fromfile(str(config))
        except Exception:  # the config is only read for cfg.visualizer
            cfg = Config(dict(visualizer=dict(type="PoseLocalVisualizer", vis_backends=[dict(type="LocalVisBackend")],
                                              name="visualizer")))
    meta = None
    try:
        meta = dataset_meta_from_config(cfg, dataset_mode="train")
    except Exception:
        meta = None
    if meta is None:
        meta = parse_pose_metainfo(dict(from_file="configs/_base_/datasets/coco.py"))
    return cfg, meta


def _patch_mmpose(runner: SimccTopdown, record: dict) -> None:
    import mmpose.apis as apis
    from mmengine.structures import InstanceData

    from mmpose.structures import PoseDataSample
    from mmpose.structures.bbox import bbox_xywh2xyxy

    def init_model(config, checkpoint=None, device="cuda:0", cfg_options=None):
        record["init_model_calls"].append({"interface": "mmpose", "config": str(config),
                                           "checkpoint_not_loaded": str(checkpoint), "device": str(device)})
        cfg, meta = _config_and_meta(config)
        return PoseModelProxy(cfg, meta, runner)

    def inference_topdown(model, img, bboxes=None, bbox_format="xyxy"):
        if isinstance(img, str):
            import cv2

            img = cv2.imread(img)
        if bboxes is None or len(bboxes) == 0:
            h, w = img.shape[:2]
            bboxes = np.array([[0, 0, w, h]], dtype=np.float32)
        else:
            if isinstance(bboxes, list):
                bboxes = np.array(bboxes)
            assert bbox_format in {"xyxy", "xywh"}, f'Invalid bbox_format "{bbox_format}".'
            if bbox_format == "xywh":
                bboxes = bbox_xywh2xyxy(bboxes)
        kpts, scores, centers, scales = model.runner(img, bboxes)
        meta = model.dataset_meta or {}
        results = []
        for i, bbox in enumerate(bboxes):
            gt = InstanceData()
            gt.bboxes = bbox[None]
            gt.bbox_scores = np.ones(1, dtype=np.float32)
            pred = InstanceData()
            pred.keypoints = kpts[i:i + 1]
            pred.keypoint_scores = scores[i:i + 1]
            pred.keypoints_visible = scores[i:i + 1]
            pred.bboxes = gt.bboxes
            pred.bbox_scores = gt.bbox_scores
            ds = PoseDataSample(metainfo=dict(
                img_shape=img.shape[:2], ori_shape=img.shape[:2], input_size=model.runner.input_size,
                input_center=centers[i].astype(np.float32), input_scale=scales[i].astype(np.float32),
                flip_indices=meta.get("flip_indices"), dataset_name=meta.get("dataset_name")))
            ds.gt_instances = gt
            ds.pred_instances = pred
            results.append(ds)
        return results

    apis.init_model = init_model
    apis.inference_topdown = inference_topdown
    try:  # also the defining module, for code that imports from mmpose.apis.inference
        import mmpose.apis.inference as inference_mod

        inference_mod.init_model = init_model
        inference_mod.inference_topdown = inference_topdown
    except Exception:
        pass
    record["patched"].append("mmpose")


def movenet_letterbox(w: int, h: int, input_w: int = 256, input_h: int = 256) -> tuple[int, int, int, int]:
    """fod-walk `PoseEstimation.preprocess_image`: (tw, th, tx1, ty1) of the long-side resize, centred zero padding."""
    r_w, r_h = input_w / w, input_h / h
    if r_h > r_w:
        tw, th = input_w, int(r_w * h)
        return tw, th, 0, int((input_h - th) / 2)
    tw, th = int(r_h * w), input_h
    return tw, th, int((input_w - tw) / 2), 0


def _patch_movenet(runner: SimccTopdown, record: dict) -> None:
    import onnx_thunder_inference as m  # module folder (sys.path[0])

    original = m.PoseEstimation

    class SharedPoseEstimation(original):
        """MoveNet's interface; keypoints from the shared model in MoveNet's output frame: (y, x) of the letterboxed
        256x256 input, truncated to integers, then the score."""

        def __init__(self, weights_dir, model_name):
            record["init_model_calls"].append({"interface": "movenet",
                                               "model_not_loaded": os.path.join(str(weights_dir), str(model_name))})
            self.input_w = self.input_h = 256  # MoveNet SinglePose Thunder input [1, 256, 256, 3]

        def predict(self, bgr_image, image_path=None):
            h, w = bgr_image.shape[:2]
            kpts, scores, _, _ = runner(bgr_image, np.array([[0, 0, w, h]], dtype=np.float32))
            tw, th, tx1, ty1 = movenet_letterbox(w, h, self.input_w, self.input_h)
            out = np.zeros((17, 3), dtype=np.float32)
            out[:, 0] = (kpts[0, :, 1] * th / h + ty1).astype(np.int32)
            out[:, 1] = (kpts[0, :, 0] * tw / w + tx1).astype(np.int32)
            out[:, 2] = scores[0]
            return out

    m.PoseEstimation = SharedPoseEstimation
    record["patched"].append("movenet")


def _patch_rtmpose_utils(runner: SimccTopdown, record: dict) -> None:
    import onnx_model_utils as m  # module folder (sys.path[0])

    def build_session(onnx_file, device="cuda"):
        record["init_model_calls"].append({"interface": "rtmpose_utils", "model_not_loaded": str(onnx_file),
                                           "device": str(device)})
        return runner

    def generate_keypoints(img, bbox, session):
        x1, y1, x2, y2 = bbox
        kpts, scores, _, _ = runner(img, np.array([[x1, y1, x2, y2]], dtype=np.float32))
        return kpts[0] - np.array([x1, y1], dtype=np.float32), scores[0]  # crop-relative, as the original returns

    m.build_session = build_session
    m.generate_keypoints = generate_keypoints
    record["patched"].append("rtmpose_utils")


def install(model: str = "rtmpose-l", device: str = "cuda", **runner_kwargs) -> dict:
    """Serve every pose interface the module offers from one SimccTopdown. Returns a live record (see `finish`)."""
    runner = SimccTopdown(model, device=device, **runner_kwargs)
    record = {"mode": "override", **runner.describe(), "patched": [], "init_model_calls": [], "timings": runner.timings}
    if _offered("mmpose"):
        _patch_mmpose(runner, record)
    if _offered("onnx_thunder_inference"):
        _patch_movenet(runner, record)
    if _offered("onnx_model_utils"):
        _patch_rtmpose_utils(runner, record)
    return record


def install_timing() -> dict:
    """The modules' own pose models with call / box / wall-time counters (the control for `install`)."""
    timings = PoseTimings()
    record = {"mode": "timing", "patched": [], "init_model_calls": [], "timings": timings}

    def count(n: int, dt: float) -> None:
        timings.calls += 1
        timings.boxes += n
        timings.run_s += dt
        timings.batch_sizes[n] = timings.batch_sizes.get(n, 0) + 1

    if _offered("mmpose"):
        import mmpose.apis as apis

        original_topdown, original_init = apis.inference_topdown, apis.init_model

        def init_model(config, checkpoint=None, device="cuda:0", cfg_options=None):
            record["init_model_calls"].append({"interface": "mmpose", "config": str(config),
                                               "checkpoint": str(checkpoint), "device": str(device)})
            return original_init(config, checkpoint, device=device, cfg_options=cfg_options)

        def inference_topdown(model, img, bboxes=None, bbox_format="xyxy"):
            t0 = time.perf_counter()
            out = original_topdown(model, img, bboxes, bbox_format)  # numpy results: the GPU work is finished here
            count(len(out), time.perf_counter() - t0)
            return out

        apis.init_model = init_model
        apis.inference_topdown = inference_topdown
        record["patched"].append("mmpose")
    if _offered("onnx_thunder_inference"):
        import onnx_thunder_inference as m

        original_predict = m.PoseEstimation.predict

        def predict(self, bgr_image, image_path=None):
            t0 = time.perf_counter()
            out = original_predict(self, bgr_image, image_path)
            count(1, time.perf_counter() - t0)
            return out

        m.PoseEstimation.predict = predict
        record["patched"].append("movenet")
    if _offered("onnx_model_utils"):
        import onnx_model_utils as m

        original_generate = m.generate_keypoints

        def generate_keypoints(img, bbox, session):
            t0 = time.perf_counter()
            out = original_generate(img, bbox, session)
            count(1, time.perf_counter() - t0)
            return out

        m.generate_keypoints = generate_keypoints
        record["patched"].append("rtmpose_utils")
    return record


def finish(record: dict) -> dict:
    """The record as JSON (timings flattened)."""
    out = dict(record)
    out["timings"] = record["timings"].as_dict()
    return out
