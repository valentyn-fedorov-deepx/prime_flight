import os
import sys
import textwrap

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAKE_MAIN = """
def detect(source, output_path, device, video_worker=None, weights_dir='', write_video=False, cone_camera=True,
           json_logger=None):
    metadata = video_worker.load_metadata()
    rows = frames = 0
    for frame_number, meta in enumerate(metadata, 1):
        rows += len(meta['general_model'])
        frames = frame_number
        if STOP_AT and frame_number >= STOP_AT:
            return 'Fail', [f'{NAME}: stopped at {frame_number}'], []
    return 'Pass', [f'{NAME}: {frames} frames, {rows} rows'], []
"""

PIXEL_MAIN = """
def detect(source, output_path, device, video_worker=None, weights_dir='', write_video=False, cone_camera=True,
           json_logger=None):
    dataset = video_worker.load_source(source)
    metadata = video_worker.load_metadata()
    seen = []
    for frame_number, _meta in enumerate(metadata, 1):
        seen.append(int(dataset.get_im0s(frame_number)[0, 0, 0]))
    return 'Pass', [str(seen)], []
"""

FAKE_FILES = {
    "cv_common/__init__.py": "",
    "cv_common/common.py": "def parse_config():\n    return {'status2id': {}, 'str2id': {}}\n",
    "cv_common/log_utils.py": "class JsonLogger:\n    def __init__(self, *a):\n        pass\n",
    "cv_common/utils/__init__.py": "",
    "cv_common/utils/datasets.py": "def letterbox(img, size, stride=64, auto=True):\n    return (img,)\n",
    "db_worker/__init__.py": "",
    "db_worker/ML_worker.py": textwrap.dedent("""
        cv_config = {'img_size': 640}
        class VideoWorker:
            def __init__(self, model_name, load_tracks, source, testing, auto_download_inference, inferences_dir):
                self.source = source
                self.number_of_frames = 0
    """),
}


def write_module(root, name: str, main_text: str) -> str:
    folder = os.path.join(str(root), name)
    for rel, text in {"main.py": main_text, **FAKE_FILES}.items():
        path = os.path.join(folder, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
    return folder


def fake_module(root, name: str, stop_at: int = 0) -> str:
    return write_module(root, name, f"NAME = {name!r}\nSTOP_AT = {stop_at}\n" + FAKE_MAIN)


def test_two_modules_in_their_own_processes_get_the_same_frames(tmp_path):
    # Each fake module has its own `main` / `cv_common` / `db_worker` — impossible in one process, fine in hosts.
    from pf.rt.module_host import ModuleHost

    hosts = [ModuleHost(name, {"module_dir": fake_module(tmp_path, name, stop), "device": "cpu",
                               "work_dir": str(tmp_path / f"work_{name}")})
             for name, stop in (("fake_a", 0), ("fake_b", 30))]
    for h in hosts:
        h.start({"video": "src.mp4", "n_frames": 48}, 8.0)
    outs = []
    for fid in range(1, 49):
        for h in hosts:
            outs += h.push(fid, {"general_model": [[0, 0, 10, 10, 0.9, 0]] * 3, "trackers": []})
    for h in hosts:
        outs += h.close()
    verdicts = {o.name: o.payload for o in outs if o.kind == "verdict"}
    assert verdicts["fake_a"]["status"] == "Pass" and verdicts["fake_a"]["report"] == ["fake_a: 48 frames, 144 rows"]
    assert verdicts["fake_b"]["status"] == "Fail" and verdicts["fake_b"]["decided_after_frame"] == 30
    assert verdicts["fake_b"]["session_closed"] is False  # decided while frames were still being pushed
    assert all(h.failed is None and h.stats["frames"] >= 30 for h in hosts)


def test_a_hosted_module_reads_pixels_from_the_shared_ring(tmp_path):
    from pf.rt.module_host import ModuleHost, SharedFrameRing

    ring = SharedFrameRing(shape=(8, 8, 3), slots=4)  # deliberately smaller than the run: the ring wraps every 4 frames
    host = ModuleHost("pix", {"module_dir": write_module(tmp_path, "pix", PIXEL_MAIN), "device": "cpu",
                              "work_dir": str(tmp_path / "work_pix")}, pixels=True)
    try:
        host.start({"video": "src.mp4", "n_frames": 10}, 8.0, ring.spec)
        outs = []
        for fid in range(1, 11):
            slot = ring.write(fid, np.full((8, 8, 3), fid, np.uint8), [host])
            outs += host.push(fid, {"general_model": [], "trackers": []}, slot)
        outs += host.close()
    finally:
        ring.close()
    verdict = next(o for o in outs if o.kind == "verdict")
    assert verdict.payload["report"] == [str(list(range(1, 11)))]  # every frame arrived intact despite the wrap
    assert host.failed is None


def test_a_module_that_fails_to_start_is_reported_not_hung(tmp_path):
    import pytest

    from pf.rt.module_host import ModuleHost

    host = ModuleHost("missing", {"module_dir": str(tmp_path / "does_not_exist"), "device": "cpu",
                                  "work_dir": str(tmp_path / "work")})
    with pytest.raises(RuntimeError):
        host.start({"video": "src.mp4", "n_frames": 10}, 8.0, timeout_s=120)
