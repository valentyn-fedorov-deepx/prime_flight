import json
import os
import shutil
import subprocess
import sys
import urllib.request

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pf.rt.cambox import LinkModel  # noqa: E402
from pf.rt.monitor import Monitor  # noqa: E402


def get(monitor: Monitor, path: str) -> bytes:
    with urllib.request.urlopen(monitor.url + path, timeout=5) as response:
        return response.read()


def free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_monitor_serves_the_page_and_the_state_it_was_given():
    monitor = Monitor(port=free_port()).start()
    try:
        monitor.update({"status": "keeping up", "frame_id": 42, "modules": [{"name": "m", "status": "running"}]})
        page = get(monitor, "").decode("utf-8")
        assert "<title>Real-time branch</title>" in page and "/frame.jpg" in page
        assert "https://" not in page and "//cdn" not in page  # the page is served locally, nothing is fetched
        state = json.loads(get(monitor, "state"))
        assert state["frame_id"] == 42 and state["modules"][0]["name"] == "m"
    finally:
        monitor.stop()


def test_monitor_draws_the_rows_and_records_the_modules_were_given():
    import cv2

    monitor = Monitor(port=free_port(), jpeg_width=480).start()
    try:
        assert get(monitor, "state") and monitor.frame_jpeg() is None  # no frame yet: the page keeps polling
        monitor.set_class_names({3: "person"})
        image = np.full((1080, 1920, 3), 30, np.uint8)
        monitor.set_frame(image, [[100.0, 100.0, 300.0, 400.0, 0.9, 3]],
                          [{"tr_id": 7, "xyxy": [500, 200, 900, 700], "cls_str": "airplane"}], frame_id=11)
        body = get(monitor, "frame.jpg")
        view = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
        assert view.shape == (270, 480, 3)
        assert view.std() > 1.0  # something was drawn on the flat frame
    finally:
        monitor.stop()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_a_run_feeds_the_page_while_it_runs(tmp_path):
    from pf.rt.adapters import make_adapter
    from pf.rt.chunker import cut
    from pf.rt.runtime import RealtimeRun

    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=8",
                    "-t", "12", "-c:v", "libx264", "-g", "30", "-keyint_min", "30", "-sc_threshold", "0", "-pix_fmt",
                    "yuv420p", src], check=True)
    folder = str(tmp_path / "chunks")
    manifest = cut(src, folder)
    monitor = Monitor(port=free_port()).start()
    try:
        RealtimeRun(folder, manifest, make_adapter("probe", delta=1.0), LinkModel(rtt_ms=10), speed=20.0,
                    out_dir=str(tmp_path / "run"), sample_s=0.05, monitor=monitor).run()
        state = json.loads(get(monitor, "state"))
        assert state["status"] == "finished" and state["frame_id"] == 96
        assert state["video_time"] == "00:12" and state["fps"] == 8.0
        assert state["latency_s"]["p50"] > 0 and set(state["components_s"]) >= {"link", "decode", "pipeline"}
        assert state["modules"][0]["name"] == "probe" and state["modules"][0]["status"] == "running"  # probe: no verdict
        assert get(monitor, "frame.jpg")  # the last decoded frame is still served after the run
    finally:
        monitor.stop()
