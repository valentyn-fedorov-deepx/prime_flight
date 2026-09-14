"""Run GM v2 on a video (or a chunk list) and write the artefacts needed for parity and speed baselines.

Outputs in --out-dir:
  general_model<video>.ndjson              first-run rows (raw, as v1 pass 1 writes them)
  general_model<video>-second_run.ndjson   v1-compat second-run file (what the tracker and the 27 modules read)
  gm_v2_report<video>.json                 decisions with decided_at frames, session stats, per-component ms/frame

Parity against a production file:
  python scripts/gm_v2_run.py --video G:/gat_stages/atlc5_videos/<ID>.mp4 --weights-dir <dir> --str2id <json> \
      --out-dir out/ --compare G:/gat_stages/atlc5_inferences/general_model<ID>.mp4.ndjson

Requirements: opencv-python, numpy, torch, torchvision, onnxruntime-gpu (only for real inference). The decoder is
OpenCV on purpose (X4: ffmpeg drops frames on non-monotonic DTS; production reads with cv2 as well).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pf.eval.parity import compare_gm_ndjson  # noqa: E402
from pf.gm.compat_writer import ndjson_line  # noqa: E402
from pf.gm.onnx_detector import YoloV8Onnx, YoloV8OnnxConfig  # noqa: E402
from pf.gm.rows import ClassMap  # noqa: E402
from pf.pipeline import Detectors, GmStream  # noqa: E402


def load_str2id(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        if path.endswith((".yaml", ".yml")):
            import yaml  # lazy

            cfg = yaml.safe_load(fh)
            return cfg["str2id"] if "str2id" in cfg else cfg
        data = json.load(fh)
        return data["str2id"] if "str2id" in data else data


def frames_from_video(path: str, max_frames: int | None = None):
    import cv2  # lazy

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise SystemExit(f"cannot open video: {path}")
    frame_id = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        frame_id += 1
        yield frame_id, img
        if max_frames and frame_id >= max_frames:
            break
    cap.release()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--weights-dir", required=True, help="folder with the three ONNX files (DVC pull of general_model)")
    ap.add_argument("--gm-weights", default="GM_yolov8m_best_augmentation_march2024.onnx")
    ap.add_argument("--chocks-weights", default="chocks_v4.3_200ep_yolov8.onnx")
    ap.add_argument("--vehicle-weights", default="vehicle.onnx")
    ap.add_argument("--str2id", required=True, help="json/yaml with the cv_common str2id mapping")
    ap.add_argument("--conf-thres", type=float, default=0.35)
    ap.add_argument("--chock-conf-thres", type=float, default=0.10, help="v1 config value unknown; 0.10 observed in data")
    ap.add_argument("--vehicle-conf-thres", type=float, default=0.40, help="v1 config value unknown; 0.40 observed")
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--compare", default=None, help="production second-run ndjson to compare the compat file against")
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()

    cm = ClassMap(load_str2id(a.str2id))
    wd = a.weights_dir
    mk = lambda w, shape, thr: YoloV8Onnx(YoloV8OnnxConfig(  # noqa: E731
        weights=os.path.join(wd, w), input_shape=shape, conf_thres=thr, iou_thres=0.7, device_type=a.device))
    dets = Detectors(gm=mk(a.gm_weights, (1088, 1088), a.conf_thres),
                     chocks=mk(a.chocks_weights, (1280, 1280), a.chock_conf_thres),
                     vehicle=mk(a.vehicle_weights, (1088, 1088), a.vehicle_conf_thres))

    video_name = os.path.basename(a.video)
    os.makedirs(a.out_dir, exist_ok=True)
    first_run_path = os.path.join(a.out_dir, f"general_model{video_name}.ndjson")
    compat_path = os.path.join(a.out_dir, f"general_model{video_name}-second_run.ndjson")
    report_path = os.path.join(a.out_dir, f"gm_v2_report{video_name}.json")

    stream = GmStream(cm, event_id=video_name, fps=a.fps, detectors=dets)
    t_decode = 0.0
    t_total0 = time.perf_counter()
    n = 0
    with open(first_run_path, "w", encoding="utf-8", newline="\n") as fh:
        t_prev = time.perf_counter()
        for frame_id, img in frames_from_video(a.video, a.max_frames):
            t_dec = time.perf_counter()
            t_decode += t_dec - t_prev
            stream.process(frame_id, img)
            fh.write(ndjson_line(frame_id, stream.raw_rows[frame_id]))
            n += 1
            t_prev = time.perf_counter()
    total = time.perf_counter() - t_total0
    stream.write_v1_compat(compat_path)

    report = stream.report()
    report["timings_ms_per_frame"] = {
        "decode": round(1000 * t_decode / max(n, 1), 3),
        "gm": dets.gm.timings.as_ms_per_frame(),
        "chocks": dets.chocks.timings.as_ms_per_frame(),
        "vehicle": dets.vehicle.timings.as_ms_per_frame(),
        "end_to_end": round(1000 * total / max(n, 1), 3),
        "realtime_factor_at_fps": round((n / a.fps) / total, 3) if total else None,
    }
    report["letterbox"] = {k: vars(getattr(dets, k).geometry) for k in ("gm", "chocks", "vehicle")
                           if getattr(dets, k).geometry}
    report["events"] = [vars(e) for e in stream.events]
    if a.compare:
        report["parity_vs_production"] = compare_gm_ndjson(a.compare, compat_path).summary()
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    print(json.dumps({k: report[k] for k in ("number_of_frames", "timings_ms_per_frame", "decided_at")}, indent=1))
    if a.compare:
        print("parity:", json.dumps(report["parity_vs_production"], indent=1)[:800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
