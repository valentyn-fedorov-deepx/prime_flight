"""Streaming pipeline v0 (PF-Q1-04 foundation): GM v2 + Tracker v2 on chunks as they arrive, events on the fly.

    chunk (60 frames = 7.5 s) ─► GM heads ─► first-run rows ─► VideoContextV2 ─► causal second-run rows (pf.pipeline.causal_rows)
                                                                                         │
                                  Tracker v2 (exact fast paths) ◄───────────────────────┘
                                         │ records published after the N_INIT delay
                                         ├─► events: T_ARR / T_DEP / BL_AT_DOOR / BL_LEAVE (pf.tracker.events)
                                         ├─► PUSHBACK_ATTACHED (pf.stage.pushback, causal nose rule)
                                         └─► v2 bus frames (pf.contract: schema 1.0 + events + anchors)

Outputs in --out-dir:
  bus<video>.ndjson                           one contract frame per published frame (tracker records without `_p0/_st`)
  general_model<video>.ndjson                 streaming second-run rows (what the modules would read on the fly)
  trackers<video>.ndjson                      v1-compat tracker file from the streaming rows
  batch/general_model<video>.ndjson           the end-of-video second-run file from the same first-run rows (for L1)
  stream_report<video>.json                   timings, latency, events, anchors, streaming-vs-batch GM rows

    python scripts/stream_pipeline.py --video G:/gat_stages/atlc5_videos/DjwtQRdZyt0sSk.mp4 --out-dir out/stream_Djwt \
        [--max-frames 6000] [--realtime]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

HEADS = {
    "gm": ("GM_yolov8m_best_augmentation_march2024.onnx", (1088, 1088), 0.35),
    "chocks": ("chocks_v4.3_200ep_yolov8.onnx", (1280, 1280), 0.10),
    "vehicle": ("VM_yolov8m_last_september2023.onnx", (1088, 1088), 0.40),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--gm-weights-dir", default=os.path.join(ROOT, "external", "general_model_prod", "weights"))
    ap.add_argument("--tracker-weights-dir", default=os.path.join(ROOT, "external", "cv_trackers_prod", "weights"))
    ap.add_argument("--str2id", default=os.path.join(ROOT, "external", "cv_common", "global_config.yaml"))
    ap.add_argument("--chunk-frames", type=int, default=60)
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cone-camera", action="store_true")
    ap.add_argument("--realtime", action="store_true", help="release chunks at video pace and measure latency against it")
    ap.add_argument("--out-dir", default="out/stream")
    a = ap.parse_args()

    import cv2
    import torch

    from pf.contract import make_frame
    from pf.eval.parity import compare_gm_ndjson_tolerant
    from pf.gm.compat_writer import ndjson_line
    from pf.gm.onnx_detector import YoloV8Onnx, YoloV8OnnxConfig
    from pf.gm.rows import ClassMap
    from pf.pipeline import GmStream
    from pf.pipeline.causal_rows import CausalSecondRun
    from pf.pipeline.gm_stream import Detectors
    from pf.stage.pushback import PushbackAttachedCausal
    from pf.tracker._v1.config import config as tracker_config
    from pf.tracker.events import TrackerEventDeriver
    from pf.tracker.stream import TrackerOptions, TrackerStream, strip_private
    from scripts.gm_v2_run import load_str2id

    name = os.path.basename(a.video)
    os.makedirs(os.path.join(a.out_dir, "batch"), exist_ok=True)
    cm = ClassMap(load_str2id(a.str2id))

    t_init = time.perf_counter()
    heads = {
        n: YoloV8Onnx(YoloV8OnnxConfig(weights=os.path.join(a.gm_weights_dir, f), input_shape=shape, conf_thres=thr, iou_thres=0.7))
        for n, (f, shape, thr) in HEADS.items()
    }
    detectors = Detectors(gm=heads["gm"], chocks=heads["chocks"], vehicle=heads["vehicle"], parallel=True)
    stream = GmStream(cm, event_id=name, fps=a.fps, detectors=detectors)
    causal = CausalSecondRun(stream.context, cm, refresh_every=a.chunk_frames)
    tracker = TrackerStream(TrackerOptions(weights_dir=a.tracker_weights_dir, exact_fast=True, cone_camera=a.cone_camera))
    events = TrackerEventDeriver()
    pushback = PushbackAttachedCausal(tracker_config["str2id"], fps=a.fps)
    init_s = time.perf_counter() - t_init

    bus_fh = io.open(os.path.join(a.out_dir, f"bus{name}.ndjson"), "w", encoding="utf-8", newline="\n")
    gm_fh = io.open(os.path.join(a.out_dir, f"general_model{name}.ndjson"), "w", encoding="utf-8", newline="\n")
    trk_fh = io.open(os.path.join(a.out_dir, f"trackers{name}.ndjson"), "w", encoding="utf-8", newline="\n")
    rows2_by_frame: dict = {}
    anchors: dict = {}
    counter = 1
    publish_lag = []
    event_log = []
    chunk_log = []
    t_gm = t_rows = t_trk = t_pub = 0.0

    def publish(items, current_frame):
        nonlocal counter, t_pub
        tp = time.perf_counter()
        for fno, records in items:
            fired = [e for e in events.feed(fno, records)]
            pb = pushback.feed(fno, rows2_by_frame.get(fno), records)
            names = [e.name for e in fired]
            if pb is not None:
                names.append("PUSHBACK_ATTACHED")
                fired_pb = {"name": "PUSHBACK_ATTACHED", "frame": pb, "decided_at": fno, "attrs": {"rule": "nose"}}
                event_log.append({**fired_pb, "published_at_frame": current_frame})
                anchors.setdefault("PUSHBACK_ATTACHED", pb)
            for e in fired:
                event_log.append({**e.as_dict(), "published_at_frame": current_frame})
                if e.name == "BL_LEAVE":
                    anchors["BL_LEAVE"] = e.frame
                else:
                    anchors.setdefault(e.name, e.frame)
            frame = make_frame(fno, rows2_by_frame.get(fno, []), [strip_private(r) for r in records],
                               events=names or None, anchors=dict(anchors) if anchors else None)
            bus_fh.write(json.dumps(frame) + "\n")
            trk_fh.write(json.dumps({str(counter): records}) + "\n")
            counter += 1
            publish_lag.append(current_frame - fno)
            rows2_by_frame.pop(fno, None)
        t_pub += time.perf_counter() - tp

    cap = cv2.VideoCapture(a.video)
    np.random.seed(a.seed)
    frame_id = 0
    chunk_index = 0
    t_start = time.perf_counter()
    done = False
    while not done:
        chunk = []
        while len(chunk) < a.chunk_frames:
            if a.max_frames is not None and frame_id >= a.max_frames:
                done = True
                break
            ok, img = cap.read()
            if not ok:
                done = True
                break
            frame_id += 1
            chunk.append((frame_id, img))
        if not chunk:
            break
        arrival = t_start + (chunk[-1][0] / a.fps if a.realtime else 0.0)
        if a.realtime:
            now = time.perf_counter()
            if arrival > now:
                time.sleep(arrival - now)
        t_chunk = time.perf_counter()
        contract_frames = []
        for fid, img in chunk:
            t0 = time.perf_counter()
            contract_frames.append(stream._ingest(fid, img))
            t1 = time.perf_counter()
            rows2 = causal.rows(fid, stream.raw_rows[fid])
            rows2_by_frame[fid] = rows2
            gm_fh.write(ndjson_line(fid, rows2))
            t2 = time.perf_counter()
            items = tracker.update(fid, img, rows2)
            t3 = time.perf_counter()
            publish(items, fid)
            t_gm += t1 - t0
            t_rows += t2 - t1
            t_trk += t3 - t2
        stream.session.feed_chunk(contract_frames)
        chunk_done = time.perf_counter()
        chunk_log.append({"chunk": chunk_index, "last_frame": chunk[-1][0], "processing_s": round(chunk_done - t_chunk, 3),
                          "latency_s": round(chunk_done - arrival, 3) if a.realtime else None})
        chunk_index += 1
    publish(tracker.finish(), frame_id)
    torch.cuda.synchronize()
    total = time.perf_counter() - t_start
    cap.release()
    tracker.close()
    for fh in (bus_fh, gm_fh, trk_fh):
        fh.close()

    batch_path = os.path.join(a.out_dir, "batch", f"general_model{name}.ndjson")
    stream.write_v1_compat(batch_path)
    streaming_path = os.path.join(a.out_dir, f"general_model{name}.ndjson")
    gm_rows_cmp = compare_gm_ndjson_tolerant(batch_path, streaming_path).summary()
    gm_rows_cmp.pop("first_diffs", None)
    per_class = {}
    for cname, classes in (("class2_main_aircraft", (cm.id("airplane"),)), ("obstacle_rows", (cm.id("obstacle"), cm.id("side_obstacle")))):
        ignore = tuple(sorted(set(range(40)) - set(classes)))
        s = compare_gm_ndjson_tolerant(batch_path, streaming_path, ignore_classes=ignore).summary()
        s.pop("first_diffs", None)
        per_class[cname] = s

    n = max(frame_id, 1)
    lag = np.array(publish_lag) if publish_lag else np.zeros(1)
    report = {
        "video": name,
        "frames": frame_id,
        "chunks": chunk_index,
        "chunk_frames": a.chunk_frames,
        "realtime_paced": a.realtime,
        "init_s": round(init_s, 1),
        "total_s": round(total, 1),
        "ms_per_frame": {
            "total": round(1000 * total / n, 2),
            "gm_heads_and_context": round(1000 * t_gm / n, 2),
            "causal_rows": round(1000 * t_rows / n, 2),
            "tracker": round(1000 * t_trk / n, 2),
            "events_and_bus": round(1000 * t_pub / n, 2),
        },
        "realtime_factor": round((n / a.fps) / max(total, 1e-9), 3),
        "publish_lag_frames": {"p50": float(np.percentile(lag, 50)), "p99": float(np.percentile(lag, 99)), "max": int(lag.max())},
        "chunk_latency_s": ({"p50": float(np.percentile([c["latency_s"] for c in chunk_log], 50)),
                             "max": float(max(c["latency_s"] for c in chunk_log))} if a.realtime and chunk_log else None),
        "events": event_log,
        "anchors": anchors,
        "causal_rows": vars(causal.stats),
        "gm_context_final": {k: stream.context.snapshot().get(k) for k in ("main_plane_track", "mode_plane_height", "frame_of_beginning", "main_front_wheel")},
        "streaming_vs_batch_gm_rows": {"all_classes": gm_rows_cmp, **per_class},
        "gm_timings": detectors.timings(),
        "tracker": tracker.report(),
    }
    with io.open(os.path.join(a.out_dir, f"stream_report{name}.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    print(json.dumps({k: report[k] for k in ("frames", "chunks", "ms_per_frame", "realtime_factor", "publish_lag_frames", "anchors", "causal_rows")}, indent=1, default=str))
    s = report["streaming_vs_batch_gm_rows"]
    print("streaming vs batch GM rows:", json.dumps({k: {kk: v.get(kk) for kk in ("pair_recall", "frame_parity_tolerant", "dets_a", "dets_b")} for k, v in s.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
