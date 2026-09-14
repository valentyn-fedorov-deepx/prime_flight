"""Tracker events for the stage detector: arrival/departure once, door occupancy per door with re-identification."""

import json

from pf.tracker.events import TrackerEventDeriver, derive_events


def air(arr=None, dep=None):
    return {"tr_id": 1, "cls_str": "airplane", "state_dict": {"arrival_frame": arr, "departure_frame": dep}, "data": None}


def bl(tid, bl_type, status):
    return {"tr_id": tid, "cls_str": "beltloader", "state_dict": {"_status": status}, "data": {"bl_type": bl_type}}


SEQUENCE = [
    (1, [air(), bl(5, "undefined", "stopped")]),
    (2, [air(arr=1), bl(5, "undefined", "stopped")]),        # retroactive arrival
    (3, [air(arr=1), bl(5, "front", "stopped")]),            # at the front door
    (4, [air(arr=1), bl(5, "front", "unobserved")]),         # unobserved keeps the door
    (5, [air(arr=1), bl(7, "front", "stopped")]),            # re-keyed occupant
    (6, [air(arr=1), bl(5, "undefined", "moving")]),         # the old id is not the occupant any more
    (7, [air(arr=1), bl(7, "undefined", "moving")]),         # leave
    (8, [air(arr=1, dep=8), bl(9, "back", "stopped")]),      # departure + back door
]


def _run():
    d = TrackerEventDeriver()
    for f, recs in SEQUENCE:
        d.feed(f, recs)
    return d


def test_events_and_frames():
    d = _run()
    got = [(e.name, e.frame, e.decided_at, e.attrs.get("door"), e.attrs.get("tr_id")) for e in d.events]
    assert got == [
        ("T_ARR", 1, 2, None, None),
        ("BL_AT_DOOR", 3, 3, "front", 5),
        ("BL_LEAVE", 7, 7, "front", 7),
        ("T_DEP", 8, 8, None, None),
        ("BL_AT_DOOR", 8, 8, "back", 9),
    ]
    assert d.reidentifications == [{"frame": 5, "door": "front", "from": 5, "to": 7}]
    assert d.occupant == {"back": 9}


def test_both_file_formats(tmp_path):
    compat = tmp_path / "compat.ndjson"
    bus = tmp_path / "bus.ndjson"
    compat.write_text("".join(json.dumps({str(f): recs}) + "\n" for f, recs in SEQUENCE), encoding="utf-8")
    bus.write_text("".join(json.dumps({"frame_id": f, "records": recs}) + "\n" for f, recs in SEQUENCE), encoding="utf-8")
    a = [e.as_dict() for e in derive_events(str(compat)).events]
    b = [e.as_dict() for e in derive_events(str(bus)).events]
    assert a == b and len(a) == 5
