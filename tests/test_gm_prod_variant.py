"""Production-only GM logic (commit a0157a4): noise preprocessor, tiny-plane filter, per-frame aircraft-type vote."""

import numpy as np

from pf.gm.context_prod import AircraftTypeVoterProd, drop_tiny_planes, evaluate_plane_type, save_plane_type_frame_data
from pf.gm.preprocessor import ImagePreprocessor, Mode
from pf.gm.rows import ClassMap

CM = ClassMap({"person": 0, "airplane": 2, "airplane_wing": 6, "airplane_engine": 7, "airplane_tail": 8})


def row(xyxy, cls, conf=0.9):
    return [*map(float, xyxy), conf, cls]


# ---------------------------------------------------------------- preprocessor


def test_preprocessor_estimates_every_48th_frame_and_stays_clear_for_low_noise():
    calls = []
    pre = ImagePreprocessor(noise_fn=lambda f: calls.append(len(calls)) or 0.28)
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    for f in range(1, 145):
        pre.update(f, frame)
    assert calls == [0, 1, 2] and pre.samples == 3 and pre.mode is Mode.CLEAR
    assert pre.get_preprocessed() is frame and pre.decided_at is None
    assert abs(pre.mean_noise - 0.28) < 1e-12 and pre.get_noise_std() < 1e-9


def test_preprocessor_switches_to_median_blur_when_noisy():
    pre = ImagePreprocessor(noise_fn=lambda f: 0.4)
    frame = (np.arange(25 * 3, dtype=np.uint8).reshape(5, 5, 3)) % 255
    pre.update(48, frame)
    assert pre.mode is Mode.MIDDLE and pre.decided_at == 48 and not pre.is_heavy()
    out = pre.get_preprocessed()
    assert out.shape == frame.shape and out is not frame          # median blur applied
    pre2 = ImagePreprocessor(noise_fn=lambda f: 0.9)
    pre2.update(48, frame)
    assert pre2.mode is Mode.HEAVY and pre2.is_heavy()
    assert pre2.snapshot()["video_type_by_noise"] == "HEAVY"


def test_preprocessor_running_mean_uses_welford():
    vals = iter([0.2, 0.4, 0.6])
    pre = ImagePreprocessor(noise_fn=lambda f: next(vals))
    for f in (48, 96, 144):
        pre.update(f, np.zeros((2, 2, 3), np.uint8))
    assert abs(pre.mean_noise - 0.4) < 1e-12 and abs(pre.get_noise_std() - 0.2) < 1e-12
    assert pre.mode is Mode.MIDDLE                                # 0.4 < 0.45


# ---------------------------------------------------------------- tiny planes


def test_tiny_planes_are_dropped_by_frame_fraction():
    big, small = [0, 0, 1000, 700], [0, 0, 400, 300]                # 0.34 vs 0.058 of 1920×1080
    assert drop_tiny_planes([big, small]) == [big]


# ---------------------------------------------------------------- aircraft type (production rule)


def plane_rows(engine_y2, wing_y2, plane=(100, 50, 1700, 730)):
    return [row(plane, 2), row([600, 300, 1200, wing_y2], 6), row([700, 350, 900, engine_y2], 7)]


def test_frame_vote_engine_above_wing_is_jet_and_parts_must_lie_in_the_plane():
    c = {"airplane": 0, "jet": 0, "frames_evaluated": 0, "consecutive_plane_det": 0}
    save_plane_type_frame_data(plane_rows(engine_y2=400, wing_y2=500), (100, 50, 1700, 730), c, CM)
    assert c["jet"] == 1 and c["frames_evaluated"] == 1
    save_plane_type_frame_data(plane_rows(engine_y2=600, wing_y2=500), (100, 50, 1700, 730), c, CM)
    assert c["airplane"] == 1 and c["frames_evaluated"] == 2
    # parts outside the aircraft box (< 50 % inside) do not vote
    save_plane_type_frame_data(plane_rows(engine_y2=400, wing_y2=500), (1800, 900, 1900, 1000), c, CM)
    assert c["frames_evaluated"] == 2
    assert evaluate_plane_type(c, True) == "AIRCRAFT"                # tie → AIRCRAFT (airplane < jet is False)
    assert evaluate_plane_type({"airplane": 0, "jet": 0, "frames_evaluated": 0}, False) is None


def test_voter_decides_at_departure_or_finalize_and_resets_on_passing_plane():
    v = AircraftTypeVoterProd(fps=8)
    plane = (100, 50, 1700, 730)
    # a plane passes by before arrival: votes, then disappears for > 10 s → counters reset
    for f in range(1, 21):
        v.feed(f, plane_rows(400, 500), CM, plane_available=True, main_plane_xyxy=plane, arrived=False, departured=False)
    assert v.counters["jet"] == 20 and v.plane_passing_by
    for f in range(21, 21 + 81):
        v.feed(f, [], CM, plane_available=False, main_plane_xyxy=plane, arrived=False, departured=False)
    assert v.counters["jet"] == 0 and not v.plane_passing_by
    # the real aircraft: engine below wing → AIRCRAFT, decided on the departure frame
    decided = None
    for f in range(200, 400):
        d = v.feed(f, plane_rows(600, 500), CM, plane_available=True, main_plane_xyxy=plane, arrived=f > 210,
                   departured=f == 399)
        if d:
            decided = f
    assert v.answer == "AIRCRAFT" and decided == 399 and v.plane_was_detected
    v2 = AircraftTypeVoterProd()
    v2.feed(1, plane_rows(400, 500), CM, plane_available=True, main_plane_xyxy=plane, arrived=True, departured=False)
    assert v2.finalize(500) == ["aircraft_type"] and v2.answer == "JET" and v2.decided_at == 500
