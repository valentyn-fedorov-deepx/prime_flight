import os
import sys
import textwrap

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

READS_LENGTH = """
def detect(source, output_path, device, video_worker=None, weights_dir='', write_video=False, cone_camera=True,
           json_logger=None):
    dataset = video_worker.load_source(source)
    metadata = video_worker.load_metadata()
    seen = []
    for frame_number, _meta in enumerate(metadata, 1):
        length = dataset.nframes
        if frame_number in (5, 20):
            seen.append((frame_number, length))
        if frame_number == length:
            seen.append(('last frame', frame_number))
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


def fake_module(root) -> str:
    folder = os.path.join(str(root), "reads_length")
    for rel, text in {"main.py": READS_LENGTH, **FAKE_FILES}.items():
        path = os.path.join(folder, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
    return folder


def run(tmp_path, **kwargs):
    from pf.rt.prod_module import ProductionModuleAdapter

    adapter = ProductionModuleAdapter("reads_length", module_dir=fake_module(tmp_path), metadata="live", device="cpu",
                                      work_dir=str(tmp_path / "work"), **kwargs)
    adapter.configure({"video": "src.mp4", "n_frames": 20})
    adapter.start(8.0)
    outs = []
    for fid in range(1, 21):
        outs += adapter.push(fid, np.zeros((16, 16, 3), np.uint8), {"general_model": [], "trackers": []})
    outs += adapter.close()
    return {o.name: o.payload for o in outs}


def test_the_session_length_is_unknown_until_the_last_frame(tmp_path):
    out = run(tmp_path)
    # frame 5: a value no frame number reaches; frame 20: the real length, so the module sees its last frame
    assert out["reads_length"]["report"] == [str([(5, 1_000_000_000), (20, 20), ("last frame", 20)])]
    audit = out["real_time_audit"]
    assert audit["session_length"] == "marker" and audit["session_length_known_at_close"] is True
    reads = audit["non_causal_reads"]
    assert reads["dataset.nframes before the end-of-session marker"]["count"] == 19
    assert reads["dataset.nframes"]["count"] == 1  # only the last frame, when the recording had closed


def test_manifest_mode_keeps_the_old_behaviour(tmp_path):
    out = run(tmp_path, session_length="manifest")
    assert out["reads_length"]["report"] == [str([(5, 20), (20, 20), ("last frame", 20)])]
    assert "dataset.nframes before the end-of-session marker" not in out["real_time_audit"]["non_causal_reads"]
