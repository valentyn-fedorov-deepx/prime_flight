"""Run GM v2 on a video (or a chunk list) and write the artefacts needed for parity and speed baselines.

Outputs in --out-dir:
  general_model<video>.ndjson              first-run rows (raw, as v1 pass 1 writes them)
  general_model<video>-second_run.ndjson   v1-compat second-run file (what the tracker and the 27 modules read)
  gm_v2_report<video>.json                 decisions with decided_at frames, session stats, per-component ms/frame

Opt-in `--buffered-decisions` (ADR-002): the cone/wing classifier runs on every 8th frame with a tracked aircraft inside this
single pass (on the detector input, no second decode) and the report gains `buffered_votes` and
`buffered_decisions_cost_ms_per_frame`; `scripts/gm_decide_buffered.py` decides camera_type / frame_stopped / airplane_type
from them once Tracker v2 has run. The first-run and second-run files are the same with and without the flag.

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

from pf.eval.parity import compare_gm_ndjson, compare_gm_ndjson_tolerant
from pf.gm.compat_writer import ndjson_line
from pf.gm.onnx_detector import YoloV8Onnx, YoloV8OnnxConfig
from pf.gm.rows import ClassMap
from pf.pipeline import Detectors, GmStream


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
    ap.add_argument(
        "--weights-dir", required=True, help="folder with the three ONNX files (DVC pull of general_model)"
    )
    ap.add_argument("--gm-weights", default="GM_yolov8m_best_augmentation_march2024.onnx")
    ap.add_argument("--chocks-weights", default="chocks_v4.3_200ep_yolov8.onnx")
    ap.add_argument("--vehicle-weights", default="VM_yolov8m_last_september2023.onnx")
    ap.add_argument(
        "--str2id",
        default=os.path.join(ROOT, "external", "cv_common", "global_config.yaml"),
        help="json/yaml with the cv_common str2id mapping (default: external/cv_common/global_config.yaml)",
    )
    ap.add_argument("--conf-thres", type=float, default=0.35)
    ap.add_argument(
        "--chock-conf-thres", type=float, default=0.10, help="cv_common global_config chock_conf_thres"
    )
    ap.add_argument(
        "--vehicle-conf-thres", type=float, default=0.40, help="cv_common global_config vehicle_conf_thres"
    )
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--out-dir", default="out")
    ap.add_argument(
        "--compare", default=None, help="production second-run ndjson to compare the compat file against"
    )
    ap.add_argument("--device", default="cuda")
    ap.add_argument(
        "--parallel-heads", action="store_true", help="run the three heads concurrently (same rows)"
    )
    ap.add_argument("--provider", default="cuda", choices=["cuda", "tensorrt"])
    ap.add_argument(
        "--variant",
        default="prod",
        choices=["prod", "entity_clip", "master"],
        help="GM behaviour to reproduce: prod = a0157a4 (RGB input), entity_clip = 8576299 (BGR input), master = 13a4ddc",
    )
    ap.add_argument(
        "--compare-ignore-classes",
        default="",
        help="comma-separated class ids to ignore in --compare (e.g. 2,29,30 for a partial run)",
    )
    ap.add_argument(
        "--buffered-decisions",
        action="store_true",
        help="ADR-002 opt-in: camera classifier on every 8th frame with a tracked aircraft during this pass; adds "
        "buffered_votes and buffered_decisions_cost_ms_per_frame to the report (rows unchanged)",
    )
    ap.add_argument(
        "--camera-weights-dir",
        default=None,
        help="folder with camera_cls_effnet_b0_october_v1.8.1.pt for --buffered-decisions (default: --weights-dir)",
    )
    ap.add_argument(
        "--camera-transform",
        default="numpy",
        choices=["numpy", "torchvision"],
        help="classifier input for --buffered-decisions: numpy (bit-identical to v1's torchvision transform, one CPU "
        "thread) or torchvision (v1's code path)",
    )
    a = ap.parse_args()

    cm = ClassMap(load_str2id(a.str2id))
    wd = a.weights_dir
    mk = lambda w, shape, thr: YoloV8Onnx(
        YoloV8OnnxConfig(
            weights=os.path.join(wd, w),
            input_shape=shape,
            conf_thres=thr,
            iou_thres=0.7,
            device_type=a.device,
            provider=a.provider,
            bgr_to_rgb=(a.variant == "prod"),
        )
    )
    dets = Detectors(
        gm=mk(a.gm_weights, (1088, 1088), a.conf_thres),
        chocks=mk(a.chocks_weights, (1280, 1280), a.chock_conf_thres),
        vehicle=mk(a.vehicle_weights, (1088, 1088), a.vehicle_conf_thres),
        parallel=a.parallel_heads,
    )

    video_name = os.path.basename(a.video)
    os.makedirs(a.out_dir, exist_ok=True)
    first_run_path = os.path.join(a.out_dir, f"general_model{video_name}.ndjson")
    compat_path = os.path.join(a.out_dir, f"general_model{video_name}-second_run.ndjson")
    report_path = os.path.join(a.out_dir, f"gm_v2_report{video_name}.json")

    stream = GmStream(cm, event_id=video_name, fps=a.fps, detectors=dets, variant=a.variant)
    buffer, buffer_init_s = None, 0.0
    if a.buffered_decisions:
        from pf.gm.buffered import CameraVoteBuffer
        from pf.gm.camera import CameraClassifier

        t_buffer = time.perf_counter()
        buffer = CameraVoteBuffer(
            CameraClassifier(a.camera_weights_dir or wd, device=a.device, transform=a.camera_transform)
        )
        buffer_init_s = time.perf_counter() - t_buffer
        stream.frame_observer = buffer
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
    report["letterbox"] = {
        k: vars(getattr(dets, k).geometry) for k in ("gm", "chocks", "vehicle") if getattr(dets, k).geometry
    }
    report["timings_ms_per_frame"]["runner"] = dets.timings()
    report["events"] = [vars(e) for e in stream.events]
    if buffer is not None:
        buffer.finalize(stream.context.aircraft.snapshot().get("history"))
        report["buffered_votes"] = buffer.as_report(aircraft=stream.context.aircraft, variant=a.variant)
        report["buffered_decisions_cost_ms_per_frame"] = buffer.cost_ms_per_frame(n, init_s=buffer_init_s)
    if a.compare:
        ignore = [int(x) for x in a.compare_ignore_classes.split(",") if x.strip()]
        report["parity_vs_production"] = compare_gm_ndjson(
            a.compare, compat_path, ignore_classes=ignore, only_common_frames=bool(a.max_frames)
        ).summary()
        report["parity_vs_production"]["ignore_classes"] = ignore
        report["parity_vs_production_tolerant"] = compare_gm_ndjson_tolerant(
            a.compare, compat_path, ignore_classes=ignore, only_common_frames=bool(a.max_frames)
        ).summary()
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    print(
        json.dumps(
            {k: report[k] for k in ("number_of_frames", "timings_ms_per_frame", "decided_at")}, indent=1
        )
    )
    if buffer is not None:
        print("buffered decisions:", json.dumps(report["buffered_decisions_cost_ms_per_frame"]))
    if a.compare:
        print("parity (exact):", json.dumps(report["parity_vs_production"], indent=1)[:600])
        print("parity (tolerant):", json.dumps(report["parity_vs_production_tolerant"], indent=1)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
