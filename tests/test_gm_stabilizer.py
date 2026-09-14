"""BboxStabilizer port (master-lineage GM, HEAVY-noise frames) and its use inside the norfair plane tracker."""

from pf.gm.plane_tracker import NorfairPlaneTracker, PlaneHistory
from pf.gm.stabilizer import BboxStabilizer, PlanesView


def test_returns_input_until_the_window_is_full_then_the_running_mean():
    st = BboxStabilizer(window_size=4)
    planes = {1: PlaneHistory({}, None)}
    boxes = [[0, 0, 100, 100], [2, 0, 102, 100], [4, 0, 104, 100], [6, 0, 106, 100]]
    out = []
    for f, b in enumerate(boxes, 1):
        r = st.update_bbox(1, f, b, PlanesView(planes))
        planes[1].frames[f] = r
        out.append(r)
    assert out[:3] == boxes[:3]
    assert out[3] == [3.0, 0.0, 103.0, 100.0]


def test_moving_box_with_spread_is_pulled_towards_the_previous_box():
    st = BboxStabilizer(window_size=3)
    planes = {7: PlaneHistory({}, None)}
    boxes = [[0, 0, 100, 100], [40, 40, 140, 140], [80, 80, 180, 180]]
    res = None
    for f, b in enumerate(boxes, 1):
        res = st.update_bbox(7, f, b, PlanesView(planes))
        planes[7].frames[f] = res
    mean = [40.0, 40.0, 140.0, 140.0]
    prev = planes[7].frames[2]
    assert res == [(p + m) / 2.0 for p, m in zip(prev, mean)]


def test_tracker_applies_the_stabilizer_only_on_heavy_frames(monkeypatch):
    tr = NorfairPlaneTracker(drop_tiny=False, stabilize_when_heavy=True)
    calls = []

    def fake_update(plane_id, frame_id, xyxy, planes_dict):
        calls.append(frame_id)
        return xyxy

    monkeypatch.setattr(tr.stabilizer, "update_bbox", fake_update)

    class CM:
        def id(self, name):
            return {"airplane": 2}[name]

    row = [100.0, 100.0, 900.0, 500.0, 0.9, 2]
    for f in range(1, 21):
        tr.update(f, [row], CM(), heavy=(f % 2 == 0))
    assert calls and all(f % 2 == 0 for f in calls)
    assert NorfairPlaneTracker().stabilizer is None
