import os
import shutil
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pf.rt.cambox import CameraBoxSim, LinkModel, schedule  # noqa: E402


def manifest(n_chunks=3, frames=30, fps=8.0, size=1_875_000):
    chunks = [{"index": i, "path": f"chunk_{i:05d}.mp4", "first_frame_id": 1 + i * frames, "n_frames": frames,
               "t_start": i * frames / fps, "t_end": (i + 1) * frames / fps, "bytes": size} for i in range(n_chunks)]
    return {"fps": fps, "chunks": chunks}


def test_chunk_arrives_after_it_closes_plus_link_time():
    arrivals = schedule(manifest(), LinkModel(bandwidth_mbps=1000, rtt_ms=10), t0=100.0)
    first = arrivals[0]
    # 1.875 MB over 1 Gbit/s = 15 ms, plus 10 ms RTT, after the chunk closes at 3.75 s
    assert first.transfer_s == pytest.approx(0.025)
    assert first.due == pytest.approx(100.0 + 3.75 + 0.025)
    assert [a.index for a in arrivals] == [0, 1, 2]


def test_speed_compresses_all_durations():
    a = schedule(manifest(), LinkModel(rtt_ms=10), t0=0.0, speed=10.0)[1]
    assert a.due == pytest.approx((7.5 + a.transfer_s) / 10.0)


def test_slow_link_and_loss():
    arrivals = schedule(manifest(n_chunks=50), LinkModel(bandwidth_mbps=4, rtt_ms=0, loss=0.5, seed=1), t0=0.0)
    assert arrivals[0].transfer_s == pytest.approx(3.75)  # 15 Mbit over 4 Mbit/s
    lost = [a for a in arrivals if a.lost]
    assert lost and all(a.path is None for a in lost)
    assert all(a.path for a in arrivals if not a.lost)


def test_jitter_can_reorder_but_delivery_is_time_ordered():
    arrivals = schedule(manifest(n_chunks=200, frames=1), LinkModel(rtt_ms=0, jitter_ms=2000, seed=3), t0=0.0)
    dues = [a.due for a in arrivals]
    assert dues == sorted(dues)
    assert [a.index for a in arrivals] != sorted(a.index for a in arrivals)


def test_simulator_delivers_on_the_wall_clock():
    got = []
    sim = CameraBoxSim(manifest(n_chunks=4), LinkModel(rtt_ms=10), speed=50.0)
    sim.start(got.append)
    assert sim.done.wait(5.0)
    assert [a.index for a in got] == [0, 1, 2, 3]
    assert all(a.arrived >= a.due - 0.002 for a in got)
    assert sim.capture_time(31) == pytest.approx(sim.t0 + 30 / 8.0 / 50.0)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_chunker_cuts_at_keyframes_with_identical_pixels(tmp_path):
    from pf.rt.chunker import cut, verify_pixels

    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=8",
                    "-t", "12", "-c:v", "libx264", "-g", "30", "-keyint_min", "30", "-sc_threshold", "0", "-bf", "2",
                    "-pix_fmt", "yuv420p", src], check=True)
    m = cut(src, str(tmp_path / "chunks"), gops_per_chunk=1)
    assert m["n_frames"] == 96
    assert [c["n_frames"] for c in m["chunks"]] == [30, 30, 30, 6]
    assert all(c["starts_on_keyframe"] for c in m["chunks"])
    assert [c["first_frame_id"] for c in m["chunks"]] == [1, 31, 61, 91]
    check = verify_pixels(str(tmp_path / "chunks"))
    assert check["frames_compared"] == 96 and check["frames_identical"] == 96
    with pytest.raises(FileExistsError):
        cut(src, str(tmp_path / "chunks"))
    two = cut(src, str(tmp_path / "chunks2"), gops_per_chunk=2)
    assert [c["n_frames"] for c in two["chunks"]] == [60, 36]
