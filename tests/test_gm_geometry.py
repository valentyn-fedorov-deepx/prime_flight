"""GM geometry: letterbox arithmetic must match v1 (`scripts/new_model.py:330-356`) and the report figures."""

from pf.gm.geometry import (
    bboxes_iou,
    correct_coords,
    count_bbox_frames,
    letterbox_geometry,
    overlay_ratio,
    relative_intersection,
)


def test_letterbox_1088_for_1080p():
    g = letterbox_geometry(1920, 1080, 1088, 1088)
    assert (g.new_w, g.new_h) == (1088, 640)  # int(1088 / 1.777) = 612 → ceil to 32 → 640
    assert (g.pad_x, g.pad_y) == (0, 224)
    assert g.padding == [0, 0, 224, 224]
    assert abs(g.padded_fraction - 0.4118) < 1e-3  # ≈41 % of the input is padding (gm_current.md §7)


def test_letterbox_1280_for_1080p():
    g = letterbox_geometry(1920, 1080, 1280, 1280)
    assert (g.new_w, g.new_h) == (1280, 736)  # int(1280 / 1.777) = 720 → 736
    assert (g.pad_x, g.pad_y) == (0, 272)
    assert abs(g.x_factor - 1.5) < 1e-9 and abs(g.y_factor - 1080 / 736) < 1e-9


def test_letterbox_portrait_uses_height():
    g = letterbox_geometry(1080, 1920, 1088, 1088)
    assert (g.new_w, g.new_h) == (640, 1088)
    assert (g.pad_x, g.pad_y) == (224, 0)


def test_correct_coords_clamps_like_v1():
    assert correct_coords([-5, -1, 2000, 1200]) == [0, 0, 1920, 1080]
    assert correct_coords([10, 20, 30, 40]) == [10, 20, 30, 40]
    assert correct_coords([0, 0, 1920, 1080]) == [0, 0, 1920, 1080]


def test_iou_uses_the_cv_common_plus_one_convention():
    a, b = [0, 0, 10, 10], [5, 0, 15, 10]
    # inclusive pixels: inter = 6*11 = 66, areas = 11*11 = 121 each → 66 / (242 - 66)
    assert abs(bboxes_iou(a, b) - 66 / 176) < 1e-9
    assert bboxes_iou(a, [20, 20, 30, 30]) == 0.0
    assert abs(bboxes_iou(a, a) - 1.0) < 1e-9


def test_relative_intersection_divides_by_main_area_plus_one():
    a, b = [0, 0, 10, 10], [5, 0, 15, 10]
    assert abs(relative_intersection(a, b) - 50 / 101) < 1e-9
    assert relative_intersection(a, [20, 20, 30, 30]) == 0
    assert relative_intersection([0, 0, 10, 10], [10, 0, 20, 10]) == 0.0   # touching: x1 == x2 → zero area, not early return


def test_center_and_hw_truncate_like_cv_common():
    from pf.gm.geometry import get_center, get_hw, is_overlap
    assert get_center([0.9, 0.9, 10.9, 20.9]) == (5, 10) and get_hw([0.9, 0.9, 10.9, 20.9]) == (20, 10)
    assert not is_overlap([0, 0, 10, 10], [10, 0, 20, 10])   # touching edges are not an overlap
    assert is_overlap([0, 0, 10, 10], [9, 0, 20, 10])


def test_overlay_ratio_is_relative_to_smaller_box():
    big, small = [0, 0, 100, 100], [10, 10, 20, 20]
    assert overlay_ratio(big, small) == 1.0
    assert overlay_ratio([0, 0, 10, 10], [20, 20, 30, 30]) == 0


def test_count_bbox_frames_buckets_by_iou():
    d = {}
    count_bbox_frames(d, [0, 0, 100, 100])
    count_bbox_frames(d, [1, 1, 101, 101])  # IoU ≈ 0.96 → same bucket
    count_bbox_frames(d, [500, 500, 600, 600])
    assert d[(0, 0, 100, 100)] == 2 and d[(500, 500, 600, 600)] == 1 and len(d) == 2
