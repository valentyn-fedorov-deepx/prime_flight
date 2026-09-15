"""Run the real-time branch simulation on a chunked video and write outputs, per-frame timings and a report.

    python -m pf.rt.chunker  --video out/testset/videos/zHxIAF2vUGxJ.mp4 --out out/rt/chunks/zHxIAF2vUGxJ
    python -m pf.rt.simulate --chunks out/rt/chunks/zHxIAF2vUGxJ --adapter probe --max-seconds 300 --out out/rt/runs/probe_300s

Outputs in --out: outputs.ndjson (written the moment each output is emitted), frames.ndjson (per-frame stage times relative
to the capture of frame 1), report.json (latency percentiles and components, drift, backlog samples, receiver stats).
"""

from __future__ import annotations

import argparse
import json

from pf.rt.adapters import ADAPTERS, make_adapter
from pf.rt.cambox import LinkModel
from pf.rt.chunker import load_manifest
from pf.rt.runtime import RealtimeRun, subset_manifest

BRIEF = ("adapter", "frames", "frames_missing", "video_seconds", "wall_seconds", "frame_latency_s",
         "latency_components_s", "latency_drift_s_per_recording_minute", "module_ms_per_frame", "module_realtime_factor",
         "keeps_up", "max_frame_queue", "max_receiver_pending_chunks", "outputs", "output_latency_s", "decode_mismatches",
         "error")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", required=True, help="folder written by pf.rt.chunker")
    ap.add_argument("--adapter", default="probe", choices=sorted(ADAPTERS))
    ap.add_argument("--adapter-args", default="{}", help="JSON object of adapter keyword arguments")
    ap.add_argument("--speed", type=float, default=1.0, help="1 = real time; >1 compresses the wall clock (smoke tests)")
    ap.add_argument("--max-seconds", type=float, default=None, help="only the chunks closing within this recording time")
    ap.add_argument("--bandwidth-mbps", type=float, default=1000.0)
    ap.add_argument("--rtt-ms", type=float, default=10.0)
    ap.add_argument("--jitter-ms", type=float, default=0.0)
    ap.add_argument("--loss", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--frame-queue", type=int, default=64)
    ap.add_argument("--reorder-timeout-s", type=float, default=2.0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    manifest = subset_manifest(load_manifest(a.chunks), a.max_seconds)
    adapter = make_adapter(a.adapter, **json.loads(a.adapter_args))
    link = LinkModel(a.bandwidth_mbps, a.rtt_ms, a.jitter_ms, a.loss, a.seed)
    report = RealtimeRun(a.chunks, manifest, adapter, link, a.speed, a.frame_queue, a.reorder_timeout_s, a.out).run()
    print(json.dumps({k: report.get(k) for k in BRIEF}, indent=1, default=str))
    return 0 if not report.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
