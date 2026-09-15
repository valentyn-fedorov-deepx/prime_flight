import json
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pf.rt.cambox import LinkModel  # noqa: E402

FAKE_MAIN = """
import numpy as np

def detect(source, output_path, device, video_worker=None, weights_dir='', write_video=False, cone_camera=True,
           json_logger=None, stop_after=None, read_total=False):
    dataset = video_worker.load_source(source)
    metadata = video_worker.load_metadata()
    total = dataset.nframes if read_total else None
    means, persons = [], 0
    for frame_number, meta in enumerate(metadata, 1):
        persons += len(meta['general_model'])
        if frame_number % 2 == 0:
            means.append(float(dataset.get_im0s(frame_number)[::8, ::8].mean()))
        if stop_after and frame_number >= stop_after:
            return 'Fail', [f'stopped at {frame_number}'], [], {'means': len(means)}
    return 'Pass', [f'{len(means)} frames read, {persons} rows, total {total}'], []
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


@pytest.fixture
def fake_module(tmp_path):
    root = tmp_path / "fake_module"
    for rel, text in {"main.py": FAKE_MAIN, **FAKE_FILES}.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    cwd, path = os.getcwd(), list(sys.path)
    yield str(root)
    os.chdir(cwd)
    sys.path[:] = path
    for name in [n for n in sys.modules if n == "main" or n.split(".")[0] in ("cv_common", "db_worker")]:
        del sys.modules[name]


def chunks(tmp_path):
    from pf.rt.chunker import cut

    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=8",
                    "-t", "12", "-c:v", "libx264", "-g", "30", "-keyint_min", "30", "-sc_threshold", "0", "-pix_fmt",
                    "yuv420p", src], check=True)
    folder = str(tmp_path / "chunks")
    manifest = cut(src, folder)
    inf = tmp_path / "inf"
    inf.mkdir()
    with open(inf / "general_modelsrc.mp4.ndjson", "w") as gm, open(inf / "trackerssrc.mp4.ndjson", "w") as trk:
        for i in range(1, 97):
            gm.write(json.dumps({str(i): [[0, 0, 10, 10, 0.9, 0]]}) + "\n")
            trk.write(json.dumps({str(i): []}) + "\n")
    return folder, manifest, str(inf)


def run(tmp_path, fake_module, **kw):
    from pf.rt.prod_module import ProductionModuleAdapter
    from pf.rt.runtime import RealtimeRun

    folder, manifest, inf = chunks(tmp_path)
    folder = os.path.abspath(folder)
    adapter = ProductionModuleAdapter("fake", module_dir=fake_module, inferences_dir=inf, device="cpu",
                                      work_dir=str(tmp_path / "work"), **kw.pop("adapter", {}))
    adapter.configure(manifest)
    r = RealtimeRun(folder, manifest, adapter, LinkModel(rtt_ms=0), speed=40.0, out_dir=str(tmp_path / "run"), **kw)
    return r, r.run()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_production_module_runs_on_live_frames_and_reports_at_close(tmp_path, fake_module):
    r, report = run(tmp_path, fake_module)
    verdict = next(o for o in r.outputs if o["kind"] == "verdict")
    assert verdict["payload"]["status"] == "Pass"
    assert verdict["payload"]["report"] == ["48 frames read, 96 rows, total None"]
    assert verdict["payload"]["session_closed"] is True
    audit = next(o for o in r.outputs if o["name"] == "real_time_audit")
    assert audit["payload"]["non_causal_reads"] == {}
    assert report["frames"] == 96 and report["error"] is None


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_early_decision_is_emitted_before_the_session_ends_and_total_reads_are_audited(tmp_path, fake_module):
    # stop_after / read_total reach detect() through a wrapper main.py
    with open(os.path.join(fake_module, "main.py"), "a") as fh:
        fh.write("\n_detect = detect\n"
                 "def detect(**kw):\n"
                 "    return _detect(stop_after=40, read_total=True, **kw)\n")
    r, report = run(tmp_path, fake_module)
    verdict = next(o for o in r.outputs if o["kind"] == "verdict")
    assert verdict["payload"]["status"] == "Fail"
    assert verdict["payload"]["decided_after_frame"] == 40
    assert verdict["payload"]["session_closed"] is False  # decided while frames were still arriving
    audit = next(o for o in r.outputs if o["name"] == "real_time_audit")
    assert audit["payload"]["non_causal_reads"]["dataset.nframes"]["count"] == 1
    assert report["frames"] == 96
