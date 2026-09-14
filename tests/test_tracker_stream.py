"""Tracker stream helpers (CPU only): v2 bus stripping, retroactive arrival_frame rewrite, noise-gate schedule."""

import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("skimage")
pytest.importorskip("yaml")

from pf.tracker._v1.track import Track  # noqa: E402
from pf.tracker.stream import (  # noqa: E402
    PRIVATE_STATE_KEYS,
    NoiseGate,
    replace_plane_arrival_frame,
    strip_private,
)


def test_strip_private_removes_optical_flow_points_without_mutating():
    rec = {
        "tr_id": 3,
        "cls_str": "gse",
        "state_dict": {"_p0": [[[1.0, 2.0]]], "_st": [1], "_status": "stopped"},
        "data": None,
    }
    out = strip_private(rec)
    assert "_p0" not in out["state_dict"] and "_st" not in out["state_dict"]
    assert out["state_dict"]["_status"] == "stopped"
    assert "_p0" in rec["state_dict"]  # the v1-compat writer still needs the original
    assert set(PRIVATE_STATE_KEYS) == {"_p0", "_st"}


def test_strip_private_person_record_without_state():
    rec = {"tr_id": 7, "cls_str": "person", "state_dict": {}, "data": None}
    assert strip_private(rec) == rec


def test_replace_plane_arrival_frame_rewrites_airplane_record_and_envelope():
    t = Track(tr_id=1, xyxy=(0, 0, 10, 10), cls_str="airplane", state_dict={"arrival_frame": None})
    replace_plane_arrival_frame([t], 3465)
    assert t.state_dict["arrival_frame"] == 3465
    # v1 quirk kept on purpose: the envelope gains a top-level `arrival_frame` (a tolerated extra of the contract)
    assert t.to_json()["arrival_frame"] == 3465


def test_replace_plane_arrival_frame_ignores_non_airplane_and_empty():
    t = Track(tr_id=5, cls_str="beltloader", state_dict={"arrival_frame": None})
    replace_plane_arrival_frame([t], 10)
    assert t.state_dict["arrival_frame"] is None and "arrival_frame" not in t.to_json()
    replace_plane_arrival_frame([], 10)


def test_noise_gate_schedule_every_interval_while_objects_present():
    gate = NoiseGate(fps=8, interval_s=2)
    calls = []
    gate.sigma = lambda img: calls.append(1) or 0.1
    img = np.zeros((4, 4, 3), dtype=np.uint8)
    for f in range(1, 41):
        out = gate.image_to_track(f, img, any_object=True)
        assert out is not img and np.array_equal(out, img)
    assert len(calls) == 3  # frames 1, 17, 33
    assert gate.denoised == 0


def test_noise_gate_no_objects_no_estimate_and_sigma_persists():
    gate = NoiseGate(fps=8, interval_s=2)
    seen = []
    gate.sigma = lambda img: seen.append(1) or 0.7
    gate.denoise = lambda img: np.full_like(img, 9)
    img = np.zeros((2, 2, 3), dtype=np.uint8)
    assert np.array_equal(gate.image_to_track(1, img, any_object=False), img)
    assert seen == []
    assert gate.image_to_track(17, img, any_object=True)[0, 0, 0] == 9  # estimated at 17 → 0.7 → denoise
    assert gate.image_to_track(18, img, any_object=True)[0, 0, 0] == 9  # cached sigma keeps denoising
    assert gate.image_to_track(19, img, any_object=False)[0, 0, 0] == 0  # no objects → plain copy
    assert len(seen) == 1 and gate.denoised == 2
