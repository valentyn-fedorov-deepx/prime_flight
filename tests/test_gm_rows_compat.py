"""First-run row assembly and the v1-compat second-run writer (quirks included)."""

import json

import numpy as np

from pf.gm.compat_writer import CompatContext, ndjson_line, second_run_rows
from pf.gm.rows import ClassMap, first_run_rows, forced_class_rows, gm_rows

# Minimal str2id for tests: ids confirmed by data/code where known (person 0, airplane 2, beltloader 3, gse 4,
# pushback 5, airplane_nose 9, chock 25, obstacle 29, side_obstacle 30, vehicle 31); the rest arbitrary.
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


def test_gm_rows_truncate_and_clamp():
    det = np.array([[-3.7, 10.9, 1925.2, 500.4, 0.91, 3.0]], dtype=np.float32)
    assert gm_rows(det, CM) == [[0.0, 10.0, 1920.0, 500.0, float(np.float32(0.91)), 3]]


def test_forced_class_rows_keep_raw_floats():
    det = np.array([[10.5, 20.25, 30.0, 40.0, 0.12, 0.0]], dtype=np.float32)
    rows = forced_class_rows(det, CM.id("chock"))
    assert rows == [[10.5, 20.25, 30.0, 40.0, float(np.float32(0.12)), 25]]


def test_first_run_order_gm_then_chocks_then_vehicles():
    rows = first_run_rows(
        np.array([[0, 0, 10, 10, 0.5, 0]]),
        np.array([[1, 1, 2, 2, 0.2, 0]]),
        np.array([[5, 5, 9, 9, 0.6, 0]]),
        CM,
    )
    assert [r[5] for r in rows] == [0, 25, 31]


def test_empty_detections_give_empty_rows():
    assert first_run_rows(None, np.zeros((0, 6)), [], CM) == []


# ---------------------------------------------------------------- second run


def ctx_with_gate():
    # main front wheel in the middle; left side ROI = x >= 1500
    return CompatContext(
        main_front_wheel=[900, 700, 1000, 800],
        left_side_obstacles_roi=[1500, 0, 1920, 1080],
        right_side_obstacles_roi=False,
        plane_history={7: [100, 50, 1700, 730]},
        mode_plane_height=680,
    )


def test_airplane_raw_rows_are_dropped_and_main_plane_row_appended_last():
    rows = [[100.0, 50.0, 1700.0, 730.0, 0.93, 2], [10.0, 10.0, 30.0, 30.0, 0.8, 0]]
    out = second_run_rows(rows, 7, ctx_with_gate(), CM)
    assert out == [[10.0, 10.0, 30.0, 30.0, 0.8, 0], [100.0, 50.0, 1700.0, 730.0, 680, 2]]
    assert isinstance(out[-1][4], int)  # height mode, not a confidence
    assert second_run_rows(rows, 8, ctx_with_gate(), CM) == [
        [10.0, 10.0, 30.0, 30.0, 0.8, 0]
    ]  # frame not in track


def test_obstacle_rows_use_the_stale_conf_and_side_roi():
    # beltloader left of the wheel and big → obstacle; gse fully inside the left ROI → side_obstacle
    rows = [[100.0, 600.0, 400.0, 800.0, 0.71, 3], [1600.0, 500.0, 1900.0, 900.0, 0.42, 4]]
    out = second_run_rows(rows, 1, ctx_with_gate(), CM)
    assert out[:2] == [[100.0, 600.0, 400.0, 800.0, 0.71, 3], [1600.0, 500.0, 1900.0, 900.0, 0.42, 4]]
    assert out[2] == [100.0, 600.0, 400.0, 800.0, 0.42, 29]  # conf = last row's conf (v1 stale variable)
    assert out[3] == [1600.0, 500.0, 1900.0, 900.0, 0.42, 30]


def test_small_or_inside_gate_transport_is_not_an_obstacle():
    rows = [
        [950.0, 720.0, 990.0, 790.0, 0.9, 3],  # inside wheel box: not left, not below → not in gate
        [100.0, 600.0, 150.0, 640.0, 0.9, 5],
    ]  # left of wheel but area 2000 < 7000
    out = second_run_rows(rows, 1, ctx_with_gate(), CM)
    assert [r[5] for r in out] == [3, 5]


def test_vehicle_overlapping_transport_is_deduplicated():
    rows = [
        [100.0, 600.0, 400.0, 800.0, 0.71, 3],  # beltloader
        [102.0, 601.0, 401.0, 802.0, 0.55, 31],  # same box as vehicle → IoU > 0.7 → dropped from transport
        [500.0, 900.0, 800.0, 1000.0, 0.66, 31],
    ]  # distinct vehicle → kept as 'vehicle' transport
    out = second_run_rows(rows, 1, ctx_with_gate(), CM)
    obstacles = [r for r in out if r[5] in (29, 30)]
    assert [r[:4] for r in obstacles] == [[100.0, 600.0, 400.0, 800.0], [500.0, 900.0, 800.0, 1000.0]]
    assert all(r[4] == 0.66 for r in obstacles)  # stale conf = last vehicle row's conf


def test_no_main_front_wheel_means_no_obstacle_rows():
    ctx = ctx_with_gate()
    ctx.main_front_wheel = None
    rows = [[100.0, 600.0, 400.0, 800.0, 0.71, 3]]
    assert [r[5] for r in second_run_rows(rows, 1, ctx, CM)] == [3]


def test_ndjson_line_matches_production_format():
    line = ndjson_line(7, [[255.0, 6.0, 1920.0, 1080.0, 0.8291015625, 14]])
    assert line == '{"7": [[255.0, 6.0, 1920.0, 1080.0, 0.8291015625, 14]]}\n'
    assert json.loads(line) == {"7": [[255.0, 6.0, 1920.0, 1080.0, 0.8291015625, 14]]}
    assert ndjson_line(1, []) == '{"1": []}\n'
