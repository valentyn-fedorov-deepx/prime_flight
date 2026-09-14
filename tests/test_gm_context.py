"""Incremental per-video context: decisions must reproduce v1's end-of-video values and expose `decided_at`."""

from pf.gm.context import (
    AircraftTypeVoter,
    CameraVoter,
    EntityVoter,
    MainAircraftTracker,
    PartsLayout,
    VideoContextV2,
    merge_overlapping_planes,
)
from pf.gm.rows import ClassMap

CM = ClassMap(
    {
        "person": 0,
        "cone": 1,
        "airplane": 2,
        "beltloader": 3,
        "gse": 4,
        "pushback": 5,
        "airplane_tail": 6,
        "airplane_wing": 7,
        "airplane_engine": 8,
        "airplane_nose": 9,
        "front_door": 10,
        "back_door": 11,
        "front_wheel": 12,
        "back_wheel": 13,
        "trailer": 14,
        "fuel_truck": 15,
        "tow_bar": 16,
        "ladder": 17,
        "chock": 25,
        "obstacle": 29,
        "side_obstacle": 30,
        "vehicle": 31,
    }
)


def row(xyxy, cls, conf=0.9):
    return [*map(float, xyxy), conf, cls]


# ---------------------------------------------------------------- entity


def test_entity_decided_at_40_hits_every_8th_frame():
    v = EntityVoter()
    decided_at = None
    for f in range(1, 400):
        d = v.feed(f, [0] if f % 8 == 0 else [5])  # off-frames must be ignored
        if d:
            decided_at = f
    assert v.entity == "JetBlue" and decided_at == 320  # 40 hits × every 8th frame


def test_entity_disagreement_is_undefined():
    v = EntityVoter()
    for f in range(8, 8 * 41, 8):
        v.feed(f, [0 if f % 16 == 0 else 1])
    assert v.entity == "Undefined"


# ---------------------------------------------------------------- aircraft type


def jet_rows():
    # engine overlaps the tail (JET +1), engine above the wing (JET +1), tail left of nose; engine not at wing start (JET +1)
    return [
        row([100, 300, 300, 500], 6),
        row([1500, 300, 1700, 500], 9),
        row([200, 350, 400, 450], 8),
        row([600, 500, 1200, 700], 7),
    ]


def test_aircraft_type_answers_after_500_votes():
    v = AircraftTypeVoter()
    decided = None
    for f in range(1, 600):
        if v.feed(f, jet_rows(), CM):
            decided = f
    assert v.answer == "JET" and decided == 501  # count > 500 → answer on the 501st voting frame
    assert v.feed(700, jet_rows(), CM) == []  # frozen afterwards


def test_aircraft_type_without_engine_does_not_vote():
    v = AircraftTypeVoter()
    for f in range(1, 700):
        v.feed(f, [row([100, 300, 300, 500], 6)], CM)
    assert v.answer is None and v.votes == {}


# ---------------------------------------------------------------- camera


def test_camera_majority_and_confidence():
    c = CameraVoter()
    for i in range(10):
        c.feed(i + 1, i < 7)  # 7 cone, 3 wing
    assert c.majority() is True and abs(c.confidence() - 0.7) < 1e-9
    assert c.decide(10) == ["camera_type"] and c.camera_type_cone is True and c.decided_at == 10
    assert c.decide(11) == []


# ---------------------------------------------------------------- parts layout


def test_parts_layout_main_nose_after_30s_and_side_rois():
    """v1 quirk kept on purpose: the SMALLEST bucket sets the bar (`> limit`), so a part seen as one perfectly stable
    box never qualifies; real videos always have jitter buckets of count 1, which makes the bar max(1, 30·fps)."""
    layout = PartsLayout(fps=8)
    nose = [900, 400, 1000, 460]
    wing_left, wing_right = [1300, 300, 1800, 500], [100, 300, 700, 500]
    jitter = [row([50, 900, 120, 940], 9), row([50, 700, 400, 800], 7), row([1500, 700, 1850, 800], 7)]
    layout.update(1, jitter, CM)  # one-frame buckets (count 1) as in real videos
    decided_at = None
    for f in range(2, 301):
        d = layout.update(f, [row(nose, 9), row(wing_left, 7), row(wing_right, 7)], CM)
        if d:
            decided_at = f
    assert decided_at == 242  # stable bucket count > 30·8 = 240 first true on frame 242
    s = layout.snapshot()
    assert s["main_nose"] == tuple(nose)
    assert s["main_left_wing"] == wing_left and s["main_right_wing"] == wing_right
    assert s["left_side_obstacles_roi"] == [1300 + 0.8 * 500, 0, 1920, 1080]
    assert s["right_side_obstacles_roi"] == [0, 0, 100 + 0.2 * 600, 1080]


def test_single_stable_bucket_never_qualifies_as_in_v1():
    layout = PartsLayout(fps=8)
    for f in range(1, 400):
        layout.update(f, [row([900, 400, 1000, 460], 9)], CM)
    assert layout.snapshot()["main_nose"] is None


def test_parts_layout_without_parts_is_empty():
    s = PartsLayout().snapshot()
    assert s["main_front_wheel"] is None and s["left_side_obstacles_roi"] is False


# ---------------------------------------------------------------- main aircraft


def test_merge_drops_the_larger_overlapping_box():
    big, small = [0, 0, 1000, 700], [100, 100, 500, 500]
    assert merge_overlapping_planes([big, small]) == [small]
    assert merge_overlapping_planes([[0, 0, 100, 100], [500, 500, 900, 900]]) == [
        [0, 0, 100, 100],
        [500, 500, 900, 900],
    ]


def test_main_aircraft_longest_track_and_height_mode():
    t = MainAircraftTracker()
    for f in range(1, 11):
        t.update(f, [row([100, 50, 1700, 730], 2), row([10, 10, 30, 30], 0)], CM)  # height 680
    t.update(11, [row([100, 50, 1700, 735], 2)], CM)  # 685 → rounds to 680
    for f in range(20, 23):
        t.update(f, [row([1500, 800, 1900, 1000], 2)], CM)  # a second, short track
    assert t.first_seen_at == 1
    s = t.snapshot()
    assert s["main_plane_track"] == 1 and s["mode_plane_height"] == 680
    assert (s["frame_of_beginning"], s["frame_of_ending"]) == (1, 11)
    assert len(t.tracks) == 2


def test_main_aircraft_ignores_small_boxes():
    t = MainAircraftTracker()
    t.update(1, [row([100, 100, 400, 200], 2)], CM)  # height 100 < 150
    assert t.snapshot()["main_plane_track"] is None


# ---------------------------------------------------------------- aggregate


def test_video_context_collects_decisions_with_frames():
    ctx = VideoContextV2(CM)
    for f in range(1, 330):
        ctx.update(
            f, jet_rows() + [row([100, 50, 1700, 730], 2)], entity_class_ids=[0], is_cone=True, arrived=f > 5
        )
    snap = ctx.snapshot()
    assert snap["entity"] == "JetBlue" and snap["decided_at"]["entity"] == 320
    assert snap["decided_at"]["first_aircraft_seen"] == 1
    assert snap["camera_running_majority"] is True and snap["camera_type_cone"] is None  # not frozen yet
    assert snap["mode_plane_height"] == 680 and snap["frame_of_ending"] == 329
