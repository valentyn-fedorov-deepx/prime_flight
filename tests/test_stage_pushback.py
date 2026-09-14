"""PUSHBACK_ATTACHED: causal nose rule (gating, > 5 s counter) and the offline replication of both production branches."""

import pytest

pytest.importorskip("skimage")

from pf.stage.pushback import PushbackAttachedCausal, production_pushback_attached_frame  # noqa: E402

S2I = {"pushback": 5, "airplane_nose": 9}
AIR = (600, 200, 1600, 700)  # aircraft box: h = 500


def records(arrival=None, departure=None):
    return [{"tr_id": 1, "cls_str": "airplane", "xyxy": list(AIR),
             "state_dict": {"_xyxy": list(AIR), "arrival_frame": arrival, "departure_frame": departure}}]


NOSE = [500.0, 400.0, 620.0, 460.0, 0.8, 9]
PB_HIT = [560.0, 520.0, 760.0, 800.0, 0.9, 5]      # x1 560 < nose.x2 620 + w//2 100; y2 800 - 700 = 100 < 150
PB_FAR = [1700.0, 520.0, 1900.0, 800.0, 0.9, 5]    # x1 1700 > 620 + 100


def gm_frames(n, arrival_at, hit_from, pb=PB_HIT):
    out = []
    for f in range(1, n + 1):
        rows = [NOSE, pb] if f >= hit_from else [NOSE, PB_FAR]
        out.append((f, rows, records(arrival=arrival_at)))
    return out


def test_causal_fires_on_the_41st_hit_after_arrival():
    frames = gm_frames(200, arrival_at=50, hit_from=10)
    det = PushbackAttachedCausal(S2I, fps=8)
    fired = [det.feed(f, rows, recs) for f, rows, recs in frames]
    hits = [f for f in fired if f is not None]
    assert det.stop_frame == 50
    assert hits == [90]  # hits count from the stop frame 50 on: 50..90 is 41 hits
    assert det.frame == 90


def test_causal_never_fires_before_arrival_or_without_nose():
    det = PushbackAttachedCausal(S2I, fps=8)
    for f in range(1, 300):
        det.feed(f, [PB_HIT], records(arrival=None))
    assert det.frame is None and det.stop_frame == 0


def test_production_replication_nose_branch_equals_causal_without_departure():
    frames = gm_frames(200, arrival_at=50, hit_from=10)
    res = production_pushback_attached_frame(
        lambda: ((f, rows) for f, rows, _ in frames), lambda: ((f, recs) for f, _, recs in frames), n_frames=210, str2id=S2I
    )
    assert res["rule"] == "nose" and res["frame"] == 90 and res["stop_frame"] == 50


def test_production_replication_median_branch_counts_up_and_down():
    n = 3000
    frames = []
    for f in range(1, n + 1):
        departure = 2900 if f >= 2900 else None
        rows = [NOSE, PB_HIT] if 1000 <= f < 2900 else []
        frames.append((f, rows, records(arrival=100, departure=departure)))
    res = production_pushback_attached_frame(
        lambda: ((f, rows) for f, rows, _ in frames), lambda: ((f, recs) for f, _, recs in frames), n_frames=n, str2id=S2I
    )
    assert res["rule"] == "median"
    assert res["median_pushback"] == [560.0, 520.0, 760.0, 800.0]
    assert res["frame"] == 1040  # IoU with the median is 1.0 from frame 1000: 41 hits → 1040
