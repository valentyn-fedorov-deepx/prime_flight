"""Production main-aircraft tracking: norfair 0.2.0 semantics + v1 history bookkeeping."""

from pf.gm.plane_tracker import NorfairPlaneTracker, iou_distance, merge_overlapping_planes, xyxy_to_det_arr
from pf.gm.rows import ClassMap

CM = ClassMap({"person": 0, "airplane": 2})


def row(xyxy, cls=2, conf=0.9):
    return [*map(float, xyxy), conf, cls]


def big_plane(dx=0):
    # 1200×680 px box: 0.39 of the frame → survives the 10 % tiny-plane filter and the 150 px height rule
    return [100 + dx, 50, 1300 + dx, 730]


def test_track_is_reported_after_the_initialization_delay():
    t = NorfairPlaneTracker()
    first = None
    for f in range(1, 40):
        d = t.update(f, [row(big_plane(f))], CM)
        if "first_aircraft_track" in d:
            first = f
    # norfair 0.2.0: hit_counter starts at 11, +1 net per frame, reported when > 10 + 8 → 9th frame with the detection
    assert t.first_seen_at == 1 and first == 9
    snap = t.snapshot()
    assert snap["main_plane_track"] == 1 and snap["frame_of_beginning"] == 9 and snap["frame_of_ending"] == 39
    assert snap["mode_plane_height"] == 680 and len(snap["history"]) == 31


def test_no_candidates_means_no_tracker_step_and_small_boxes_are_ignored():
    t = NorfairPlaneTracker()
    assert t.update(1, [row([0, 0, 300, 200])], CM) == []  # 0.03 of the frame → dropped (production filter)
    assert t.update(2, [row([0, 0, 900, 100])], CM) == []  # height 100 < 150
    assert t.first_seen_at is None and t.snapshot()["main_plane_track"] is None
    t_master = NorfairPlaneTracker(drop_tiny=False)
    assert t_master.update(1, [row([0, 0, 900, 160])], CM) == ["first_aircraft_seen"]  # only the height rule


def test_new_norfair_id_after_a_gap_is_reassociated_and_shares_history():
    """v1 steps the norfair tracker only on frames WITH candidates, so a pure absence never ages an object; the object
    ages while another aircraft is visible. When the original returns, norfair gives it a new id and v1 aliases the
    new id to the old history (overlay > 0.5 with the last known box)."""
    t = NorfairPlaneTracker()
    left, right = big_plane(), [1000, 100, 1900, 700]
    for f in range(1, 30):
        t.update(f, [row(left)], CM)
    for f in range(30, 61):  # only another aircraft → the left object decays
        t.update(f, [row(right)], CM)
    for f in range(61, 100):
        t.update(f, [], CM)  # no candidates → no tracker step
    ids_before = set(t.planes)
    for f in range(100, 130):
        t.update(f, [row(big_plane(dx=5))], CM)  # the original returns at the same place
    assert len(t.planes) == 3 and set(t.planes) > ids_before
    hist = {k: v for k, v in t.planes.items()}
    new_id = max(t.planes)
    assert hist[new_id] is hist[1]  # same PlaneHistory object (v1 alias semantics)
    snap = t.snapshot()
    assert snap["main_plane_track"] in (1, new_id)
    assert snap["frame_of_beginning"] == 9 and snap["frame_of_ending"] == 129
    assert 29 in snap["history"] and 100 not in snap["history"] and 108 in snap["history"]


def test_distinct_planes_get_distinct_histories():
    t = NorfairPlaneTracker()
    left, right = [0, 100, 900, 700], [1000, 100, 1900, 700]  # both ≥ 10 % of the frame, no overlap
    for f in range(1, 30):
        t.update(f, [row(left), row(right)], CM)
    assert len(t.planes) == 2 and len({id(h) for h in t.planes.values()}) == 2
    assert t.snapshot()["main_plane_track"] in t.planes


def test_iou_distance_and_merge():
    class Obj:
        estimate = xyxy_to_det_arr([0, 0, 100, 100])

    from pf.gm._norfair020 import Detection

    assert abs(iou_distance(Detection(xyxy_to_det_arr([0, 0, 100, 100])), Obj())) < 1e-12
    assert merge_overlapping_planes([[0, 0, 1000, 700], [100, 100, 500, 500]]) == [[100, 100, 500, 500]]
