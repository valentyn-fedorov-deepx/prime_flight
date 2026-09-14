"""Tracker parity on consumed fields: identity by (cls_str, _obj_id), frames by key, _p0/_st by length only."""

import json

from pf.eval.tracker_parity import (
    CONSUMED_STATE_FIELDS,
    TrackerParity,
    compare_tracker_frames,
    compare_tracker_ndjson,
)


def airplane(obj_id=1, tr_id=7, status="stopped", arrival=None, p0=None, extra=None):
    sd = {
        "_class_name": "airplane",
        "_obj_id": obj_id,
        "_status": status,
        "_xyxy": [100, 50, 1700, 730],
        "arrival_frame": arrival,
        "departure_frame": None,
        "have_arrival_stage": arrival is not None,
        "have_pre_arrival_stage": False,
        "_p0": p0 if p0 is not None else [[1.0, 2.0]] * 5,
        "_st": [1] * 5,
        "_of_dots_lifetime": 10,
        "_init_dots_lifetime": 10,
        "_is_stopped": status == "stopped",
        "_stops_count": 1,
    }
    if extra:
        sd.update(extra)
    return {
        "tr_id": tr_id,
        "xyxy": [100, 50, 1700, 730],
        "cls_str": "airplane",
        "conf": 0.0,
        "state_dict": sd,
        "data": None,
    }


def beltloader(obj_id=2, tr_id=9, bl_type="front"):
    sd = {
        "_class_name": "beltloader",
        "_obj_id": obj_id,
        "_status": "moving",
        "_xyxy": [1, 2, 3, 4],
        "_bl_type_bbox": None,
        "_bl_type_frames": {"front": 3, "back": 1},
        "_p0": [],
        "_st": [],
    }
    return {
        "tr_id": tr_id,
        "xyxy": [1, 2, 3, 4],
        "cls_str": "beltloader",
        "conf": 0.0,
        "state_dict": sd,
        "data": {"bl_type": bl_type},
    }


def test_identical_frames_are_equal():
    res = TrackerParity()
    assert compare_tracker_frames([airplane(), beltloader()], [airplane(), beltloader()], 1, res)
    assert res.objects_matched == 2 and res.field_mismatches == {}


def test_tr_id_and_private_flow_payload_do_not_matter_but_consumed_fields_do():
    res = TrackerParity()
    # different tr_id, different _p0 values of the same length → still equal on what modules consume
    b = airplane(tr_id=99, p0=[[9.0, 9.0]] * 5)
    assert compare_tracker_frames([airplane()], [b], 1, res, envelope=("xyxy", "cls_str"))
    # a different arrival_frame is a consumed-field mismatch
    res2 = TrackerParity()
    assert not compare_tracker_frames([airplane(arrival=[100])], [airplane(arrival=[101])], 5, res2)
    assert res2.field_mismatches == {"arrival_frame": 1}
    assert res2.first_diffs[0][:3] == (5, ("airplane", 1), "arrival_frame")


def test_p0_length_change_and_key_set_change_are_reported():
    res = TrackerParity()
    b = airplane(p0=[[1.0, 2.0]] * 3, extra={"_height_mode": 680})
    assert not compare_tracker_frames([airplane()], [b], 2, res)
    assert res.field_mismatches == {"len(_p0)": 1, "state_dict.keys": 1}


def test_bl_type_and_missing_objects():
    res = TrackerParity()
    assert not compare_tracker_frames(
        [airplane(), beltloader(bl_type="front")], [beltloader(bl_type="back")], 3, res
    )
    assert res.objects_only_in_a == 1 and res.field_mismatches == {"<object>": 1, "data.bl_type": 1}


def _write(path, frames):
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps({str(k): objs}) + "\n" for k, objs in frames)


def test_ndjson_comparison_matches_frames_by_key(tmp_path):
    a, b = tmp_path / "a.ndjson", tmp_path / "b.ndjson"
    _write(a, [(1, []), (2, [airplane()]), (3, [airplane(status="moving")]), (4, [airplane()])])
    _write(
        b, [(1, []), (3, [airplane(status="moving")]), (4, [airplane(status="stopping")])]
    )  # frame 2 missing
    res = compare_tracker_ndjson(str(a), str(b))
    s = res.summary()
    assert s["frames_only_in_a"] == 1 and s["frames_compared"] == 3 and s["frames_equal"] == 2
    assert s["field_mismatches"] == {"_status": 1, "_is_stopped": 1}
    assert s["unique_identities_a"] == 1 and set(CONSUMED_STATE_FIELDS) >= {"_status", "_is_stopped"}
