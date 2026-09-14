"""Exact tracker fast paths: identical in-box booleans, grey-frame sharing semantics, guarded method rebuilds."""

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
pytest.importorskip("skimage")
pytest.importorskip("yaml")

from pf.tracker import fast_paths  # noqa: E402
from pf.tracker._v1 import tracked_object as to_mod  # noqa: E402
from pf.tracker._v1.common import in_bbox  # noqa: E402


def test_in_bbox_vec_matches_python_loop_including_edges():
    rng = np.random.default_rng(3)
    pts = rng.uniform(-5, 1925, size=(4000, 2)).astype(np.float32)
    edges = np.array([[100, 50], [300, 50], [100, 200], [300, 200], [99.99999, 50], [300.00003, 200], [np.nan, 60]],
                     dtype=np.float32)
    pts = np.concatenate([pts, edges])
    for bbox in [(100, 50, 300, 200), (np.int64(100), np.int64(50), np.int64(300), np.int64(200)), (0, 0, 1919, 1079)]:
        ref = np.array([in_bbox(p, bbox) for p in pts], dtype=bool)
        got = fast_paths.in_bbox_vec(pts, bbox)
        assert got.dtype == bool and np.array_equal(ref, got)


def _frames():
    rng = np.random.default_rng(5)
    prev = rng.integers(0, 256, size=(60, 80, 3), dtype=np.uint8)
    cur = rng.integers(0, 256, size=(60, 80, 3), dtype=np.uint8)
    return prev, cur


def test_frame_grays_convert_once_and_carry_current_to_next_frame():
    prev, cur = _frames()
    g1 = fast_paths.FrameGrays(prev, cur)
    assert np.array_equal(g1.prev_gray, cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY))
    assert np.array_equal(g1.cur_gray, cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY))
    _ = g1.cur_gray, g1.prev_gray
    assert g1.conversions == 2
    nxt = np.flip(cur, axis=0).copy()
    g2 = fast_paths.FrameGrays(cur, nxt, carry=g1)
    assert g2.prev_gray is g1.cur_gray and g2.conversions == 0


def test_masked_pairs_are_private_shared_per_box_list_and_never_touch_unmasked():
    prev, cur = _frames()
    g = fast_paths.FrameGrays(prev, cur)
    unmasked_prev, unmasked_cur = g.prev_gray.copy(), g.cur_gray.copy()
    assert g.for_optical_flow([]) == (g.prev_gray, g.cur_gray) or g.for_optical_flow([])[0] is g.prev_gray
    p1, c1 = g.for_optical_flow([(10.7, 5, 30, 20)])
    p2, c2 = g.for_optical_flow([(10, 5, 30.2, 20)])  # same integer boxes → same pair
    assert p1 is p2 and c1 is c2 and p1 is not g.prev_gray
    p1[5:20, 10:30] = 0  # what FeatureTracker.update_features does
    p3, _ = g.for_optical_flow([(0, 0, 5, 5)])
    assert p3 is not p1 and np.array_equal(p3, unmasked_prev)
    assert np.array_equal(g.prev_gray, unmasked_prev) and np.array_equal(g.cur_gray, unmasked_cur)


def test_enable_rebuilds_methods_and_disable_restores():
    orig_moving = to_mod.TrackedObject.__dict__["_update_moving_status"]
    orig_analyze = to_mod.MovementAnalyzer.__dict__["analyze_movement"]
    try:
        fast_paths.enable()
        assert fast_paths.enabled()
        assert to_mod.TrackedObject.__dict__["_update_moving_status"] is not orig_moving
        assert to_mod.MovementAnalyzer.__dict__["analyze_movement"] is not orig_analyze
        names = to_mod.TrackedObject.__dict__["_update_moving_status"].__code__.co_names
        assert "_TrackedObject__feature_tracker" in names  # private-name mangling preserved
    finally:
        fast_paths.disable()
    assert to_mod.TrackedObject.__dict__["_update_moving_status"] is orig_moving
    assert to_mod.MovementAnalyzer.__dict__["analyze_movement"] is orig_analyze
    assert not fast_paths.enabled()


def test_rebuild_refuses_when_the_pinned_source_does_not_match():
    with pytest.raises(RuntimeError):
        fast_paths.rebuild_method(to_mod, "MovementAnalyzer", "analyze_movement", [("this line is not there", "x")])
