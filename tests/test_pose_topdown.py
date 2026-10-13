"""Shared pose runner: crop geometry and SimCC decoding must be mmpose 1.x's (`pf.pose.topdown_onnx`)."""

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from pf.pose.topdown_onnx import bbox_xyxy2cs, fix_aspect_ratio, simcc_maximum, warp_matrix  # noqa: E402


def test_center_scale_with_padding():
    c, s = bbox_xyxy2cs(np.array([[100, 200, 160, 400]]), padding=1.25)
    assert c.tolist() == [[130.0, 300.0]]
    assert s.tolist() == [[75.0, 250.0]]


def test_aspect_ratio_widens_the_short_side():
    tall = fix_aspect_ratio(np.array([[75.0, 250.0]]), 192 / 256)  # too narrow for 0.75 -> width from height
    assert tall.tolist() == [[187.5, 250.0]]
    wide = fix_aspect_ratio(np.array([[300.0, 100.0]]), 192 / 256)  # too wide -> height from width
    assert wide.tolist() == [[300.0, 400.0]]


def test_warp_maps_the_box_centre_to_the_input_centre():
    center, scale = np.array([130.0, 300.0]), np.array([187.5, 250.0])
    m = warp_matrix(center, scale, (192, 256))
    x, y = m @ np.array([130.0, 300.0, 1.0])
    assert abs(x - 96) < 1e-4 and abs(y - 128) < 1e-4
    x, y = m @ np.array([130.0 - 187.5 / 2, 300.0, 1.0])  # left edge of the scaled box -> x = 0
    assert abs(x) < 1e-4 and abs(y - 128) < 1e-4


def test_warp_matches_mmpose_when_installed():
    transforms = pytest.importorskip("mmpose.structures.bbox.transforms")
    center, scale = np.array([811.5, 640.25]), np.array([317.5, 423.3])
    theirs = transforms.get_warp_matrix(center, scale, 0.0, output_size=(192, 256))
    assert np.allclose(warp_matrix(center, scale, (192, 256)), theirs)


def test_simcc_maximum_takes_the_smaller_peak_and_marks_nonpositive():
    sx = np.zeros((1, 2, 8), np.float32)
    sy = np.zeros((1, 2, 6), np.float32)
    sx[0, 0, 5], sy[0, 0, 2] = 0.9, 0.4   # keypoint 0: x at 5, y at 2, score min(0.9, 0.4)
    sx[0, 1, 1], sy[0, 1, 3] = -0.2, 0.7  # keypoint 1: x peak <= 0 -> location -1
    sx[0, 1, :] -= 1.0
    locs, vals = simcc_maximum(sx, sy)
    assert locs[0, 0].tolist() == [5.0, 2.0] and abs(vals[0, 0] - 0.4) < 1e-6
    assert locs[0, 1].tolist() == [-1.0, -1.0] and vals[0, 1] <= 0
