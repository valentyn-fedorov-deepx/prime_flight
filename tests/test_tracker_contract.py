"""Tracker v1-compat contract: exact key sets per class, envelope rules, tolerated extras."""

from pf.tracker.contract import (
    AIRPLANE_KEYS,
    BASE_KEYS,
    VEHICLE_KEYS,
    check_record,
    check_state_dict,
    expected_keys,
    make_record,
)


def state_for(cls):
    return {k: None for k in expected_keys(cls)} | {"_class_name": cls, "_status": "stopped", "_obj_id": 1}


def test_key_counts_match_the_observed_production_schema():
    assert len(BASE_KEYS) == 32 and len(AIRPLANE_KEYS) == 7 and len(VEHICLE_KEYS) == 2
    assert len(expected_keys("airplane")) == 39
    assert len(expected_keys("beltloader")) == 34 and len(expected_keys("gse")) == 34
    assert expected_keys("person") == ()
    assert len(set(BASE_KEYS)) == 32  # no duplicates


def test_exact_state_passes_and_deviations_are_named():
    assert check_state_dict("airplane", state_for("airplane")).ok
    leaked = state_for("airplane") | {"_bl_type_bbox": None}
    res = check_state_dict("airplane", leaked)
    assert [(v.kind, v.detail) for v in res.violations] == [("unknown", "_bl_type_bbox")]
    missing = state_for("beltloader")
    del missing["_bl_type_frames"]
    assert [(v.kind, v.detail) for v in check_state_dict("beltloader", missing).violations] == [
        ("missing", "_bl_type_frames")
    ]
    bad_status = state_for("gse") | {"_status": "parked"}
    assert check_state_dict("gse", bad_status).violations[0].kind == "status"


def test_tolerated_extras_do_not_raise_in_v1():
    st = state_for("airplane") | {"_recent_bboxes": [], "_recent_bboxes_time": []}
    assert check_state_dict("airplane", st).ok
    assert not check_state_dict("airplane", st, allow_tolerated_extras=False).ok


def test_envelope_rules():
    rec = make_record(7, [1.9, 2, 3, 4], "beltloader", state_for("beltloader"), bl_type="front")
    assert rec["xyxy"] == [1, 2, 3, 4] and rec["conf"] == 0.0 and rec["data"] == {"bl_type": "front"}
    assert check_record(rec).ok
    plane = make_record(1, [0, 0, 10, 10], "airplane", state_for("airplane"))
    assert plane["data"] is None and check_record(plane).ok
    person = make_record(3, [0, 0, 1, 1], "person", {})
    assert check_record(person).ok
    gse = make_record(4, [0, 0, 5, 5], "gse", state_for("gse"))
    assert gse["data"] is None and check_record(gse).ok  # gse records carry data: null in production
    bad = dict(plane, conf=0.9, data={"bl_type": "front"})
    kinds = [v.kind for v in check_record(bad).violations]
    assert kinds.count("envelope") == 2
    assert check_record({"tr_id": 1}).violations[0].detail.startswith("missing envelope keys")
