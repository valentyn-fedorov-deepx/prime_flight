"""The real-time branch end to end on a synthetic clip: transport, receiver, decode, adapter, outputs — no models.

What it asserts is the architecture, not a model: every frame arrives exactly once and in order (X2), a lost chunk becomes
placeholder frames without shifting a single frame id, per-frame ingest removes the chunk wait, and the runtime reports
the latency of each stage. It needs ffmpeg and about twenty seconds, so it runs on every push next to the unit tests.

    python scripts/ci_rt_smoke.py [--seconds 24] [--out out/ci/rt_smoke.json]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FPS = 8
GOP = 30  # 3.75 s at 8 fps, as the DXGAT cameras record


def make_clip(path: str, seconds: int) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"testsrc=size=320x240:rate={FPS}", "-t", str(seconds), "-c:v", "libx264",
                    "-g", str(GOP), "-keyint_min", str(GOP), "-sc_threshold", "0", "-pix_fmt", "yuv420p", path],
                   check=True)


def run_branch(folder: str, manifest: dict, *, loss: float = 0.0, ingest: str = "chunks", video: str | None = None):
    from pf.rt.adapters import make_adapter
    from pf.rt.cambox import LinkModel
    from pf.rt.runtime import RealtimeRun

    frame_sizes = None
    if ingest == "frames":
        from pf.rt.chunker import packet_sizes

        frame_sizes = packet_sizes(video)[:manifest["n_frames"]]
    run = RealtimeRun(folder, manifest, make_adapter("probe", delta=1.0), LinkModel(rtt_ms=5, loss=loss, seed=7),
                      speed=20.0, sample_s=0.05, ingest=ingest, video=video, frame_sizes=frame_sizes)
    return run, run.run()


def check(results: list, name: str, ok: bool, detail) -> bool:
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=int, default=24)
    ap.add_argument("--out", default=os.path.join("out", "ci", "rt_smoke.json"))
    a = ap.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ffmpeg/ffprobe not on PATH: the branch pins its decoder on both sides of a comparison (X4)")
        return 2

    from pf.rt.chunker import cut

    results: list = []
    expected = a.seconds * FPS
    with tempfile.TemporaryDirectory() as tmp:
        clip = os.path.join(tmp, "src.mp4")
        make_clip(clip, a.seconds)
        chunks = os.path.join(tmp, "chunks")
        manifest = cut(clip, chunks)
        check(results, "chunker cuts on keyframes", manifest["n_frames"] == expected,
              f"{manifest['n_chunks']} chunks, {manifest['n_frames']} frames of {expected}")

        run, report = run_branch(chunks, manifest)
        ids = [f["frame_id"] for f in run.frames]
        ok = check(results, "every frame once, in order (X2)", ids == list(range(1, expected + 1)),
                   f"{len(ids)} frames, first {ids[:3]}, last {ids[-3:]}")
        ok &= check(results, "decoder agrees with the manifest (X4)", not report["decode_mismatches"],
                    report["decode_mismatches"] or "no mismatch")
        ok &= check(results, "no runtime error", report["error"] is None, report["error"] or "none")
        ok &= check(results, "the branch keeps up on a clip this small", report["keeps_up"],
                    f"drift {report['latency_drift_s_per_recording_minute']} s per recording minute")
        ok &= check(results, "an adapter verdict is emitted", any(o["kind"] == "verdict" for o in run.outputs),
                    f"{len(run.outputs)} outputs")

        lossy, lossy_report = run_branch(chunks, manifest, loss=0.3)
        lossy_ids = [f["frame_id"] for f in lossy.frames]
        missing = [f["frame_id"] for f in lossy.frames if f["missing"]]
        ok &= check(results, "a lost chunk does not shift frame ids (X2)", lossy_ids == list(range(1, expected + 1)),
                    f"{len(missing)} placeholder frames, {lossy_report['receiver']['chunks_lost']} chunks lost")
        ok &= check(results, "placeholders are reported, not hidden", len(missing) == lossy_report["frames_missing"],
                    f"{lossy_report['frames_missing']} frames reported missing")

        per_frame, per_frame_report = run_branch(chunks, manifest, ingest="frames", video=clip)
        wait = (per_frame_report["latency_components_s"].get("wait_for_chunk_close_s") or {}).get("p50")
        ok &= check(results, "per-frame ingest removes the chunk wait", (wait or 0) < 0.01,
                    f"chunk wait p50 {wait} s, frame latency p50 "
                    f"{per_frame_report['frame_latency_s']['p50']} s")
        ok &= check(results, "per-frame ingest delivers the same frames",
                    [f["frame_id"] for f in per_frame.frames] == list(range(1, expected + 1)),
                    f"{len(per_frame.frames)} frames")

    summary = {"clip_seconds": a.seconds, "frames": expected, "checks": results,
               "failed": [r["check"] for r in results if not r["ok"]],
               "chunk_run": {k: report.get(k) for k in ("frame_latency_s", "module_ms_per_frame", "keeps_up")},
               "per_frame_run": {k: per_frame_report.get(k) for k in ("frame_latency_s", "keeps_up")}}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=str)
    print(f"\n{sum(1 for r in results if r['ok'])}/{len(results)} checks passed -> {a.out}")
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
