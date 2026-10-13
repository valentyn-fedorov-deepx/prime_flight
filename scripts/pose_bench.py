"""Pose models side by side on the same person boxes: keypoint agreement with HRNet-W48 and time per call.

The pose modules' own models (HRNet-W48 COCO 256x192 and SimCC ResNet-50 384x288, both through mmpose 1.3.1 with flip
test, as configured) and the shared candidates (RTMPose-l body7 ONNX, DWPose-l body part) get the same frames and the same
person track boxes (a v2 tracker file), one call per frame with all boxes of that frame, the way the modules call.

Agreement with HRNet-W48 (the model of four of the five modules): per-keypoint distance divided by the box height,
PCK at 5 % and 10 % of the box height, for all 17 keypoints and for the arm keypoints (shoulders, elbows, wrists) that the
hand-signal checks read, on the keypoints HRNet itself scores >= 0.3. Scores side by side (the scales differ: heatmap peak
vs SimCC maximum). Timing after a warm-up, the models one after another on the same frames.

Geometry check: the runner's crops against mmpose's own test pipeline (GetBBoxCenterScale + TopdownAffine of the
RTMPose-l config) on the same boxes, max absolute pixel difference (0 expected).

    python scripts/pose_bench.py --video out/testset/videos/zHxIAF2vUGxJ.mp4 \
        --tracks out/testset/v2_inf/zHxIAF2vUGxJ.mp4/trackerszHxIAF2vUGxJ.mp4.ndjson --frames 120 --out out/pose/bench.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "out", "envs", "mmpose1"))  # the overlay the pose modules run with
sys.path.append(ROOT)
os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")  # the module checkpoints, as in scripts/testset/profiles.ENV

import cv2  # noqa: E402
import numpy as np  # noqa: E402

MIM = os.path.join(ROOT, "out", "envs", "mmpose1", "mmpose", ".mim", "configs", "body_2d_keypoint")
TORCH_MODELS = {
    "hrnet_w48": (os.path.join(ROOT, "external", "hand-signals", "td-hm_hrnet-w48_8xb32-210e_coco-256x192.py"),
                  os.path.join(ROOT, "external", "hand-signals", "weights",
                               "td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth")),
    "simcc_r50": (os.path.join(MIM, "simcc", "coco", "simcc_res50_8xb32-140e_coco-384x288.py"),
                  os.path.join(ROOT, "external", "pin-verification", "weights",
                               "simcc_res50_8xb32-140e_coco-384x288-45c3ba34_20220913.pth")),
}
ONNX_MODELS = {  # label -> (model, kwargs)
    "rtmpose_l": ("rtmpose-l", {}),
    "rtmpose_l_bgr": ("rtmpose-l", {"to_rgb": False}),
    "rtmpose_l_flip": ("rtmpose-l", {"flip_test": True}),
    "dwpose_l_body": ("dwpose-l", {}),
}
ARM = [5, 6, 7, 8, 9, 10]


def person_frames(tracks: str, min_h: int) -> dict:
    out = {}
    with io.open(tracks, encoding="utf-8") as fh:
        for line in fh:
            ((key, recs),) = json.loads(line).items()
            boxes = [r["xyxy"] for r in recs if r.get("cls_str") == "person" and r["xyxy"][3] - r["xyxy"][1] >= min_h]
            if boxes:
                out[int(key)] = boxes
    return out


def read_frames(video: str, wanted: list) -> dict:
    cap = cv2.VideoCapture(video)
    frames, n, want = {}, 0, set(wanted)
    last = max(wanted)
    while n < last:
        ok = cap.grab()
        if not ok:
            break
        n += 1  # frame numbers start at 1, as in the ndjson keys and get_im0s
        if n in want:
            ok, img = cap.retrieve()
            if ok:
                frames[n] = img
    cap.release()
    return frames


def clamp(boxes, w=1920, h=1080):
    b = np.asarray(boxes, dtype=np.int64)
    b[:, [0, 2]] = b[:, [0, 2]].clip(0, w - 1)
    b[:, [1, 3]] = b[:, [1, 3]].clip(0, h - 1)
    return b


def geometry_check(frames: dict, boxes: dict, runner) -> dict:
    from mmengine.config import Config
    from mmengine.dataset import Compose

    from mmpose.utils import register_all_modules

    register_all_modules()
    cfg = Config.fromfile(os.path.join(MIM, "rtmpose", "body8", "rtmpose-l_8xb256-420e_body8-256x192.py"))
    pipeline = Compose(cfg.test_dataloader.dataset.pipeline)
    worst, n = 0, 0
    for fid in list(frames)[:10]:
        img = frames[fid]
        ours, _, _ = runner.crops(img, boxes[fid])
        for i, bbox in enumerate(boxes[fid]):
            data = pipeline(dict(img=img, bbox=np.asarray(bbox)[None], bbox_score=np.ones(1, dtype=np.float32)))
            theirs = data["inputs"].numpy().transpose(1, 2, 0)  # uint8 HWC BGR, before the data preprocessor
            worst = max(worst, int(np.abs(theirs.astype(np.int16) - ours[i].astype(np.int16)).max()))
            n += 1
    return {"boxes": n, "max_abs_pixel_diff": worst}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--tracks", required=True, help="tracker ndjson with person track boxes")
    ap.add_argument("--frames", type=int, default=120, help="frames sampled evenly from the frames with persons")
    ap.add_argument("--min-h", type=int, default=48, help="smallest person box height, px")
    ap.add_argument("--models", default="hrnet_w48,simcc_r50,rtmpose_l,rtmpose_l_bgr,rtmpose_l_flip,dwpose_l_body")
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import torch

    from pf.pose.topdown_onnx import SimccTopdown

    persons = person_frames(a.tracks, a.min_h)
    keys = sorted(persons)
    pick = [keys[int(i)] for i in np.linspace(0, len(keys) - 1, min(a.frames, len(keys)))]
    t0 = time.time()
    frames = read_frames(a.video, pick)
    boxes = {f: clamp(persons[f]) for f in frames}
    print(f"{len(frames)} frames, {sum(len(b) for b in boxes.values())} boxes, decoded in {time.time() - t0:.1f} s", flush=True)

    results, timing, info = {}, {}, {}
    for label in [m for m in a.models.split(",") if m]:
        if label in TORCH_MODELS:
            from mmpose.apis import inference_topdown, init_model

            config, ckpt = TORCH_MODELS[label]
            model = init_model(config, ckpt, device="cuda:0")
            flip = bool(model.cfg.model.get("test_cfg", {}).get("flip_test", False))
            info[label] = {"config": os.path.relpath(config, ROOT), "checkpoint": os.path.relpath(ckpt, ROOT), "flip_test": flip,
                           "params_m": round(sum(p.numel() for p in model.parameters()) / 1e6, 2)}

            def call(img, b, model=model):
                res = inference_topdown(model, img, b, bbox_format="xyxy")
                return (np.stack([r.pred_instances.keypoints[0] for r in res]),
                        np.stack([r.pred_instances.keypoint_scores[0] for r in res]))
        else:
            name, kw = ONNX_MODELS[label]
            runner = SimccTopdown(name, **kw)

            def call(img, b, runner=runner):
                k, s, _, _ = runner(img, b)
                return k, s
            info[label] = runner.describe()
            if label == "rtmpose_l":
                info["geometry_check_vs_mmpose_pipeline"] = geometry_check(frames, boxes, runner)
        fids = list(frames)
        for f in fids[:a.warmup]:
            call(frames[f], boxes[f])
        per_call, kps, scs = [], {}, {}
        for f in fids:
            torch.cuda.synchronize()
            t = time.perf_counter()
            k, s = call(frames[f], boxes[f])
            per_call.append(time.perf_counter() - t)
            kps[f], scs[f] = k, s
        if label in TORCH_MODELS:
            del model
            torch.cuda.empty_cache()
        results[label] = (kps, scs)
        nb = sum(len(boxes[f]) for f in fids)
        timing[label] = {"calls": len(fids), "boxes": nb, "ms_per_call_mean": round(1000 * float(np.mean(per_call)), 2),
                         "ms_per_call_median": round(1000 * float(np.median(per_call)), 2),
                         "ms_per_box": round(1000 * float(np.sum(per_call)) / nb, 2)}
        print(label, timing[label], flush=True)

    agreement = {}
    if "hrnet_w48" in results:
        rk, rs = results["hrnet_w48"]
        for label, (kps, scs) in results.items():
            errs, errs_arm, s_ref, s_m = [], [], [], []
            for f in frames:
                h = (boxes[f][:, 3] - boxes[f][:, 1]).astype(np.float64)[:, None]
                d = np.linalg.norm(kps[f] - rk[f], axis=-1) / h  # (N, 17)
                vis = rs[f] >= 0.3
                errs.append(d[vis])
                errs_arm.append(d[:, ARM][vis[:, ARM]])
                s_ref.append(rs[f].ravel())
                s_m.append(scs[f].ravel())
            e, ea = np.concatenate(errs), np.concatenate(errs_arm)
            sr, sm = np.concatenate(s_ref), np.concatenate(s_m)
            agreement[label] = {
                "keypoints_compared": int(e.size),
                "median_err_of_box_h": round(float(np.median(e)), 4),
                "pck_5": round(float((e < 0.05).mean()), 4), "pck_10": round(float((e < 0.10).mean()), 4),
                "arm_median_err_of_box_h": round(float(np.median(ea)), 4),
                "arm_pck_5": round(float((ea < 0.05).mean()), 4), "arm_pck_10": round(float((ea < 0.10).mean()), 4),
                "score_median": round(float(np.median(sm)), 4), "score_p10": round(float(np.percentile(sm, 10)), 4),
                "score_corr_with_hrnet": round(float(np.corrcoef(sr, sm)[0, 1]), 4),
                "share_score_ge_0_3": round(float((sm >= 0.3).mean()), 4),
            }
            print(label, agreement[label], flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"video": os.path.basename(a.video), "frames": len(frames), "boxes": sum(len(b) for b in boxes.values()),
                   "min_h": a.min_h, "gpu": torch.cuda.get_device_name(0), "models": info, "timing": timing,
                   "agreement_with_hrnet_w48": agreement}, fh, indent=1)
    print("written", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
