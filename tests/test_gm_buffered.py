"""Buffered single-pass decisions (ADR-002, opt-in): the decision rule, the vote buffer, the aircraft-type replay, and the
default GmStream path, which must stay byte-identical when no observer is attached."""

import json

import numpy as np
import pytest

from pf.gm.buffered import (
    CameraRule,
    CameraVote,
    CameraVoteBuffer,
    decide_camera,
    replay_aircraft_type,
    votes_from_report,
)
from pf.gm.compat_writer import ndjson_line
from pf.gm.preprocessor import ImagePreprocessor, Mode
from pf.gm.rows import ClassMap
from pf.pipeline import GmStream

CM = ClassMap(
    {
        "person": 0,
        "airplane": 2,
        "beltloader": 3,
        "gse": 4,
        "pushback": 5,
        "airplane_tail": 6,
        "airplane_wing": 7,
        "airplane_engine": 8,
        "airplane_nose": 9,
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

MAIN = [100.0, 50.0, 1700.0, 730.0, 0.95, 2]  # the main aircraft, from frame 200 to the end
PASSING = [10.0, 740.0, 1900.0, 1070.0, 0.9, 2]  # another aircraft passing by on frames 20..119 (no overlap with MAIN)
PERSON = [10.0, 10.0, 40.0, 90.0, 0.8, 0]
WHEEL = [900.0, 700.0, 1000.0, 800.0, 0.9, 12]
BL = [100.0, 800.0, 400.0, 1000.0, 0.71, 3]


def cone_votes(frames_probs, main=True):
    return [CameraVote(f, p, main, main) for f, p in frames_probs]


# ---------------------------------------------------------------- decision rule


def test_fires_on_the_fiftieth_counted_vote():
    votes = cone_votes([(8 * i, 0.9) for i in range(1, 300)])
    d = decide_camera(votes, t_arr=400, end_frame=5000)
    counted = [v for v in votes if v.frame_id >= 400]
    assert d.rule == "share" and d.camera_type_cone is True and d.confidence_camera == 1.0
    assert d.votes_used == 50 and d.fired_on_vote_frame == counted[49].frame_id == d.decided_at
    assert d.votes_after_arrival == len(counted) and d.end_majority_cone is True


def test_votes_before_arrival_or_off_the_main_aircraft_do_not_count():
    before = cone_votes([(8 * i, 0.1) for i in range(1, 100)])  # wing votes before T_ARR = 800
    off_main = [CameraVote(800 + 8 * i, 0.1, True, False) for i in range(100)]  # another aircraft after T_ARR
    after = cone_votes([(804 + 8 * i, 0.99) for i in range(60)])
    d = decide_camera(before + off_main + after, t_arr=800, end_frame=9000)
    assert d.camera_type_cone is True and d.votes_used == 50 and d.confidence_camera == 1.0


def test_waits_until_the_share_reaches_the_threshold():
    probs = [0.2] * 6 + [0.8] * 64  # after k >= 50 votes the cone share is (k - 6) / k: reaches 0.9 at k = 60
    votes = cone_votes([(1000 + 8 * i, p) for i, p in enumerate(probs)])
    d = decide_camera(votes, t_arr=1000, end_frame=99999)
    assert d.rule == "share" and d.votes_used == 60 and d.cone_share == pytest.approx(0.9)
    assert d.confidence_camera == pytest.approx(0.9)


@pytest.mark.parametrize("cone_count,expected", [(45, True), (5, False)])
def test_exact_thresholds_fire(cone_count, expected):
    probs = [0.7] * cone_count + [0.3] * (50 - cone_count)
    d = decide_camera(cone_votes([(8 * (i + 1), p) for i, p in enumerate(probs)]), t_arr=1, end_frame=10**6)
    assert d.rule == "share" and d.votes_used == 50 and d.camera_type_cone is expected
    assert d.confidence_camera == pytest.approx(0.9)


def test_wing_decision_confidence_is_the_wing_share():
    probs = [0.3] * 48 + [0.7] * 2
    d = decide_camera(cone_votes([(16 * (i + 1), p) for i, p in enumerate(probs)]), t_arr=1, end_frame=10**6)
    assert d.camera_type_cone is False and d.confidence_camera == pytest.approx(0.96) and d.cone_share == pytest.approx(0.04)


def test_end_majority_when_the_rule_never_fires_and_a_tie_is_wing():
    d = decide_camera(cone_votes([(8 * (i + 1), 0.9 if i % 2 else 0.1) for i in range(80)]), t_arr=1, end_frame=777)
    assert d.rule == "end_majority" and d.decided_at == 777 and d.votes_used == 80
    assert d.camera_type_cone is False and d.confidence_camera == 0.5


def test_no_votes_and_no_arrival_like_v1():
    d = decide_camera([], t_arr=10, end_frame=100)
    assert (d.camera_type_cone, d.confidence_camera, d.rule, d.decided_at) == (None, 1.0, "no_votes", 100)
    d = decide_camera(cone_votes([(8, 0.9)]), t_arr=None, end_frame=100)
    assert (d.camera_type_cone, d.confidence_camera, d.rule) == (None, 1.0, "no_arrival")


def test_decision_waits_for_the_published_arrival_and_uses_all_stored_votes():
    votes = cone_votes([(1000 + 8 * i, 0.9) for i in range(200)])
    d = decide_camera(votes, t_arr=1000, t_arr_known_at=1600, end_frame=99999)
    assert d.decided_at == 1600 and d.votes_used == 76 and d.fired_on_vote_frame == 1600  # (1600 - 1000) / 8 + 1 votes


def test_state_at_publication_is_what_the_rule_sees_first():
    # 50 cone votes then 10 wing votes, all stored before T_ARR is published: at publication the share is 50 / 60 < 0.9,
    # so the rule does not fire on the 50th vote; afterwards cone votes lift the share to 0.9 at k = 100
    probs = [0.9] * 50 + [0.1] * 10 + [0.9] * 100
    votes = cone_votes([(8 * (i + 1), p) for i, p in enumerate(probs)])
    d = decide_camera(votes, t_arr=8, t_arr_known_at=480, end_frame=10**6)
    assert d.rule == "share" and d.votes_used == 100 and d.decided_at == 800
    assert decide_camera(votes, t_arr=8, end_frame=10**6).votes_used == 50  # published at once: fires on the 50th


def test_running_membership_is_the_causal_alternative():
    votes = [CameraVote(8 * i, 0.9, main_running=(i % 2 == 0), main_final=True) for i in range(1, 300)]
    final = decide_camera(votes, t_arr=8, end_frame=10**6)
    running = decide_camera(votes, t_arr=8, end_frame=10**6, membership="running")
    assert final.fired_on_vote_frame == 8 * 50 and running.fired_on_vote_frame == 8 * 100
    with pytest.raises(ValueError):
        decide_camera([CameraVote(8, 0.9, True)], t_arr=1, end_frame=10)  # not finalized
    with pytest.raises(ValueError):
        decide_camera(votes, t_arr=1, membership="other")


def test_custom_rule():
    votes = cone_votes([(8 * (i + 1), 0.9) for i in range(30)])
    assert decide_camera(votes, t_arr=1, end_frame=10**6, rule=CameraRule(min_votes=20)).votes_used == 20


def test_threshold_uses_float32_probability_semantics():
    assert CameraVote(8, 0.5, True).is_cone and not CameraVote(8, float(np.float32(0.49999997)), True).is_cone


# ---------------------------------------------------------------- the buffer inside GmStream


class FakeClassifier:
    def __init__(self):
        self.calls = []  # (image object, copy)

    def predict(self, image):
        self.calls.append(image)
        p = float(np.float32(image.mean() / 255.0))
        return p >= 0.5, p


def scene_rows(frame_id):
    rows = [PERSON, WHEEL]
    if 20 <= frame_id < 120:
        rows.append(PASSING)
    if frame_id >= 200:
        rows.append(MAIN)
    if frame_id >= 300:
        rows.append(BL)
    return rows


def frame_image(frame_id, h=24, w=32):
    rng = np.random.default_rng(frame_id)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def run_rows_stream(n_frames, observer=None, images=True):
    gs = GmStream(CM, "ev-buffered", rows_provider=lambda f, _img: scene_rows(f))
    if observer is not None:
        gs.frame_observer = observer
    for f in range(1, n_frames + 1):
        gs.process(f, frame_image(f) if images else None)
    return gs


def compat_text(gs, tmp_path, name):
    path = tmp_path / name
    gs.write_v1_compat(str(path))
    return path.read_bytes()


def test_default_path_is_byte_identical_with_and_without_the_observer(tmp_path):
    plain = run_rows_stream(700)
    buffer = CameraVoteBuffer(FakeClassifier(), noise_fn=lambda img: 0.0)
    observed = run_rows_stream(700, observer=buffer)
    assert compat_text(plain, tmp_path, "a.ndjson") == compat_text(observed, tmp_path, "b.ndjson")
    assert "".join(ndjson_line(f, r) for f, r in plain.iter_first_run()) == "".join(
        ndjson_line(f, r) for f, r in observed.iter_first_run()
    )
    assert plain.report() == observed.report()
    assert [vars(e) for e in plain.events] == [vars(e) for e in observed.events]
    assert buffer.votes, "the scene has aircraft frames, so the buffer must have voted"


def test_votes_every_eighth_frame_with_a_tracked_aircraft_and_marks_membership():
    buffer = CameraVoteBuffer(FakeClassifier(), noise_fn=lambda img: 0.0)
    gs = run_rows_stream(700, observer=buffer)
    history = gs.context.aircraft.snapshot()["history"]
    buffer.finalize(history)
    tracked = set()
    for frames in gs.context.aircraft.tracks.values():
        tracked.update(frames)
    expected = sorted(f for f in tracked if f % 8 == 0)
    assert [v.frame_id for v in buffer.votes] == expected
    passing = [v for v in buffer.votes if v.frame_id < 120]
    assert passing and all(v.main_running and not v.main_final for v in passing)  # the only aircraft then, not the main one
    assert all(v.main_final == (v.frame_id in history) for v in buffer.votes)
    # v1 bookkeeping: norfair returns the passing aircraft's initialised object with its stale box while it is alive, so it
    # keeps the longest history for a while after the main aircraft appears — the causal membership lags the final one
    assert any(v.main_final and not v.main_running for v in buffer.votes)
    assert all(v.main_final and v.main_running for v in buffer.votes if v.frame_id >= 400)
    rep = json.loads(json.dumps(buffer.as_report(aircraft=gs.context.aircraft, variant="prod")))
    assert votes_from_report(rep) == buffer.votes and rep["working_frame"] == "own_preprocessor"
    assert rep["first_aircraft_track_frame"] == gs.context.aircraft.first_track_at
    cost = buffer.cost_ms_per_frame(700)
    assert cost["classifier_calls"] == len(buffer.votes) and cost["frames"] == 700


def test_no_images_no_votes():
    buffer = CameraVoteBuffer(FakeClassifier(), noise_fn=lambda img: 0.0)
    run_rows_stream(300, observer=buffer, images=False)
    assert buffer.votes == [] and buffer.pre is None


class FakeDetectors:
    """Stands in for `Detectors`: records the image object each frame's rows were computed from."""

    def __init__(self):
        self.frame = 0
        self.images = {}

    def rows(self, image, cm):
        self.frame += 1
        self.images[self.frame] = image
        return [list(r) for r in scene_rows(self.frame)]


def test_detector_path_classifies_the_exact_detector_input():
    pytest.importorskip("cv2")
    from pf.gm.second_pass import preprocess_frame

    def make(observer):
        dets = FakeDetectors()
        gs = GmStream(CM, "ev-det", detectors=dets, preprocessor=ImagePreprocessor(noise_fn=lambda img: 1.0))
        if observer is not None:
            gs.frame_observer = observer
        raws = {}
        for f in range(1, 401):
            raws[f] = frame_image(f)
            gs.process(f, raws[f])
        return gs, dets, raws

    clf = FakeClassifier()
    buffer = CameraVoteBuffer(clf, noise_fn=lambda img: 0.0)  # the own preprocessor must stay unused on this path
    gs, dets, raws = make(buffer)
    plain, _, _ = make(None)
    assert buffer.votes and buffer.pre is None and buffer.saw_detector_input
    assert any(v.frame_id < 48 for v in buffer.votes) and any(v.frame_id >= 48 for v in buffer.votes)
    for vote, image in zip(buffer.votes, clf.calls):
        assert image is dets.images[vote.frame_id]  # the very array the detectors received on that frame
        mode = Mode.HEAVY if vote.frame_id >= 48 else Mode.CLEAR  # the first noise sample is taken on frame 48
        assert np.array_equal(image, preprocess_frame(raws[vote.frame_id], mode))
    assert gs.report() == plain.report()
    assert list(gs.iter_first_run()) == list(plain.iter_first_run())


def test_replay_path_blurs_only_voted_frames_with_the_mode_of_their_frame():
    pytest.importorskip("cv2")
    from pf.gm.second_pass import preprocess_frame

    clf = FakeClassifier()
    buffer = CameraVoteBuffer(clf, noise_fn=lambda img: 0.4)  # MIDDLE from frame 48 on
    run_rows_stream(400, observer=buffer)
    assert buffer.votes and buffer.own_blurred_votes == sum(1 for v in buffer.votes if v.frame_id >= 48)
    for vote, image in zip(buffer.votes, clf.calls):
        mode = Mode.MIDDLE if vote.frame_id >= 48 else Mode.CLEAR  # the first noise sample is taken on frame 48
        assert np.array_equal(image, preprocess_frame(frame_image(vote.frame_id), mode))


# ---------------------------------------------------------------- aircraft type with the real arrival

ENGINE = [800.0, 400.0, 900.0, 450.0, 0.8, 8]  # centre y 425, y2 450
WING = [600.0, 420.0, 1200.0, 520.0, 0.8, 7]  # centre y 470, y2 520 → engine above the wing: JET in both voters


def type_frames(n, main_from=1):
    box = [int(x) for x in MAIN[:4]]
    for f in range(1, n + 1):
        yield f, [ENGINE, WING], (box if f >= main_from else None)


def test_master_voter_counts_only_after_arrival_and_reports_on_the_next_frame():
    res = replay_aircraft_type(type_frames(700), CM, variant="entity_clip", t_arr=100)
    assert res["answer_reached_at"] == 600  # frames 100..600 = 501 votes > 500
    assert res["airplane_type"] == "JET" and res["decided_at"] == 601  # v1 copies the answer on the next arrived frame
    assert replay_aircraft_type(type_frames(700), CM, variant="entity_clip", t_arr=None)["airplane_type"] is None
    assert replay_aircraft_type(type_frames(600), CM, variant="entity_clip", t_arr=100)["airplane_type"] is None


def test_prod_voter_decides_at_departure():
    res = replay_aircraft_type(type_frames(900), CM, variant="prod", t_arr=100, t_dep=650)
    assert res["airplane_type"] == "JET" and res["decided_at"] == 650
    res = replay_aircraft_type(type_frames(900), CM, variant="prod", t_arr=100, t_dep=None)
    assert res["airplane_type"] == "JET" and res["decided_at"] == 900
