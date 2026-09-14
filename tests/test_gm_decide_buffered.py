"""`scripts/gm_decide_buffered.py` helpers: when T_ARR becomes known downstream, the lockstep row reader, report names."""

import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_script():
    spec = importlib.util.spec_from_file_location("gm_decide_buffered", os.path.join(ROOT, "scripts", "gm_decide_buffered.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def airplane(arrival, stopped, moving):
    return {"tr_id": 1, "cls_str": "airplane", "xyxy": [0, 0, 10, 10], "conf": 0.0,
            "state_dict": {"arrival_frame": arrival, "departure_frame": None, "_stopped_counter": stopped,
                           "_moving_counter": moving}}


def tracker_frames():
    """Frames 1..80: moving until 19, stopping from 20; the tracker decides arrival on frame 60 (stop counter 33, moving
    counter reset) and rewrites the buffered records back to 20, so every published record from 20 on carries 20."""
    out = []
    for f in range(1, 81):
        if f < 20:
            recs = [airplane(None, 0, f)]
        elif f < 60:
            recs = [airplane(20, max(0, f - 27), 19)]  # rewritten: arrival set, counter still below the threshold
        else:
            recs = [airplane(20, 33, 0)]
        out.append((f, recs))
    return out


@pytest.mark.parametrize("fmt", ["bus", "compat"])
def test_arrival_is_known_when_the_deciding_record_leaves_the_publish_buffer(tmp_path, fmt):
    pytest.importorskip("yaml")
    mod = load_script()
    path = tmp_path / f"trackers.{fmt}.ndjson"
    with open(path, "w", encoding="utf-8") as fh:
        for f, recs in tracker_frames():
            line = {"frame_id": f, "records": recs} if fmt == "bus" else {str(f): recs}
            fh.write(json.dumps(line) + "\n")
    events = mod.tracker_events(str(path))
    assert events["T_ARR"] == {"frame": 20, "decided_at": 20}
    pub = mod.tracker_arrival_publication(str(path), 20, fps=8)
    n_init = mod.workers_n_init()
    assert pub == {"tracker_decided_frame": 60, "published_at": 60 + n_init - 1, "publish_delay_frames": n_init - 1}


def test_publication_unknown_without_a_deciding_record(tmp_path):
    pytest.importorskip("yaml")
    mod = load_script()
    path = tmp_path / "trackers.ndjson"
    with open(path, "w", encoding="utf-8") as fh:
        for f, recs in tracker_frames()[:50]:
            fh.write(json.dumps({"frame_id": f, "records": recs}) + "\n")
    assert mod.tracker_arrival_publication(str(path), 20, fps=8)["published_at"] is None


def test_rows_are_read_in_lockstep_with_the_main_aircraft_box(tmp_path):
    mod = load_script()
    first, second = tmp_path / "first.ndjson", tmp_path / "second.ndjson"
    with open(first, "w", encoding="utf-8") as f1, open(second, "w", encoding="utf-8") as f2:
        for f in range(1, 4):
            f1.write(json.dumps({str(f): [[1.0, 2.0, 3.0, 4.0, 0.9, 8]]}) + "\n")
            rows2 = [[1.0, 2.0, 3.0, 4.0, 0.9, 8]] + ([[10.0, 20.0, 300.0, 400.0, 670, 2]] if f == 2 else [])
            f2.write(json.dumps({str(f): rows2}) + "\n")
    got = list(mod.iter_rows_with_main(str(first), str(second), airplane_id=2))
    assert [(f, box) for f, _rows, box in got] == [(1, None), (2, [10, 20, 300, 400]), (3, None)]
    with open(second, "w", encoding="utf-8") as f2:
        f2.write(json.dumps({"7": []}) + "\n")
    with pytest.raises(SystemExit):
        list(mod.iter_rows_with_main(str(first), str(second), airplane_id=2))


def test_video_name_from_report_prefixes():
    mod = load_script()
    for name in ("gm_v2_reportAB12.mp4.json", "gm_v2_replayAB12.mp4.json", "gm_buffered_votesAB12.mp4.json"):
        assert mod.video_name_from_report(os.path.join("x", name)) == "AB12.mp4"
