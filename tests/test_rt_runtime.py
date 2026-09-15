import os
import shutil
import subprocess
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pf.rt.cambox import ChunkArrival, LinkModel, schedule  # noqa: E402
from pf.rt.receiver import ChunkReceiver  # noqa: E402


def arrival(index, frames=30):
    return ChunkArrival(index, f"c{index}.mp4", 1 + index * frames, frames, index * frames / 8, (index + 1) * frames / 8,
                        1000, 0.0, 0.0)


def test_receiver_releases_in_recording_order():
    r = ChunkReceiver(reorder_timeout_s=1.0)
    for i in (1, 0, 2):
        r.put(arrival(i))
    got = [r.next() for _ in range(3)]
    assert [g.arrival.index for g in got] == [0, 1, 2]
    assert [g.first_frame_id for g in got] == [1, 31, 61]


def test_receiver_waits_for_a_late_chunk_within_the_timeout():
    r = ChunkReceiver(reorder_timeout_s=0.5)
    r.put(arrival(1))
    threading.Timer(0.1, lambda: r.put(arrival(0))).start()
    assert r.next().arrival.index == 0
    assert r.next().arrival.index == 1
    assert r.stats.chunks_lost == 0


def test_receiver_declares_a_missing_chunk_lost_and_fills_its_frames():
    r = ChunkReceiver(reorder_timeout_s=0.1)
    r.put(arrival(0))
    r.put(arrival(2))
    assert r.next().arrival.index == 0
    t0 = time.monotonic()
    gap = r.next()
    assert time.monotonic() - t0 >= 0.09
    assert gap.arrival is None and gap.first_frame_id == 31 and gap.n_frames == 30 and gap.lost_indices == (1,)
    assert r.next().arrival.index == 2
    r.put(arrival(1))  # too late: its frames were already filled
    assert r.stats.late_dropped == 1 and r.stats.frames_filled == 30


def test_receiver_fills_trailing_frames_at_close():
    r = ChunkReceiver(reorder_timeout_s=5.0)
    r.put(arrival(0))
    assert r.next().arrival.index == 0
    r.close(total_frames=75)
    gap = r.next()
    assert gap.arrival is None and gap.first_frame_id == 31 and gap.n_frames == 45
    assert r.next() is None


def synthetic_chunks(tmp_path):
    from pf.rt.chunker import cut

    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=8",
                    "-t", "12", "-c:v", "libx264", "-g", "30", "-keyint_min", "30", "-sc_threshold", "0", "-pix_fmt",
                    "yuv420p", src], check=True)
    folder = str(tmp_path / "chunks")
    return folder, cut(src, folder)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_run_processes_every_frame_in_order_with_timings(tmp_path):
    from pf.rt.adapters import make_adapter
    from pf.rt.runtime import RealtimeRun

    folder, manifest = synthetic_chunks(tmp_path)
    run = RealtimeRun(folder, manifest, make_adapter("probe", delta=1.0), LinkModel(rtt_ms=10), speed=20.0,
                      out_dir=str(tmp_path / "run"), sample_s=0.05)
    report = run.run()
    assert report["error"] is None
    assert [f["frame_id"] for f in run.frames] == list(range(1, 97))
    assert report["frames"] == 96 and report["frames_missing"] == 0 and not report["decode_mismatches"]
    assert report["latency_components_s"]["wait_for_chunk_close_s"]["max"] <= 3.75 / 20 + 0.01
    assert any(o["kind"] == "verdict" for o in run.outputs)
    for name in ("outputs.ndjson", "frames.ndjson", "report.json"):
        assert os.path.exists(tmp_path / "run" / name)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_run_fills_a_lost_chunk_without_shifting_frame_ids(tmp_path):
    from pf.rt.adapters import make_adapter
    from pf.rt.runtime import RealtimeRun

    folder, manifest = synthetic_chunks(tmp_path)
    seed = next(s for s in range(200)
                if [a.index for a in schedule(manifest, LinkModel(loss=0.3, seed=s), 0.0) if a.lost] == [1])
    run = RealtimeRun(folder, manifest, make_adapter("probe"), LinkModel(rtt_ms=0, loss=0.3, seed=seed), speed=20.0,
                      reorder_timeout_s=0.05)
    report = run.run()
    assert [f["frame_id"] for f in run.frames] == list(range(1, 97))
    assert [f["frame_id"] for f in run.frames if f["missing"]] == list(range(31, 61))
    assert report["receiver"]["chunks_lost"] == 1 and report["frames_missing"] == 30
