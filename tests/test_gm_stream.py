"""Chunk-wise GM driver: contract frames out, gaps filled, decisions stamped with frames, legacy artefact at close."""

import json

from pf.contract import validate_frame
from pf.eval import compare_gm_ndjson
from pf.gm.compat_writer import ndjson_line, second_run_rows
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

PLANE = [100.0, 50.0, 1700.0, 730.0, 0.95, 2]
PERSON = [10.0, 10.0, 40.0, 90.0, 0.8, 0]
WHEEL = [900.0, 700.0, 1000.0, 800.0, 0.9, 12]
BL = [100.0, 600.0, 400.0, 800.0, 0.71, 3]


def rows_provider(frame_id, _image):
    rows = [PERSON, WHEEL]
    if frame_id % 500 == 1:  # jitter buckets so v1's "smallest bucket" rule does not block the layout
        rows.append([50.0, 900.0, 120.0, 940.0, 0.5, 12])
    if frame_id >= 10:
        rows.append(PLANE)
    if frame_id >= 300:
        rows.append(BL)
    return rows


def make_stream():
    return GmStream(CM, "ev-1", rows_provider=rows_provider)


def test_contract_frames_are_valid_and_contiguous():
    gs = make_stream()
    out = []
    for f in range(1, 121):
        out += gs.process(f)
    assert [fr["frame_id"] for fr in out] == list(range(1, 121))
    for fr in out:
        validate_frame(fr)
    assert out[9]["general_model"][-1] == PLANE and out[1]["general_model"] == [PERSON, WHEEL]
    assert len(out[0]["general_model"]) == 3  # frame 1 carries the jitter bucket row


def test_lost_chunk_is_filled_and_reported():
    gs = make_stream()
    out = gs.process_chunk((f, None) for f in range(1, 61))
    out += gs.process_chunk((f, None) for f in range(121, 181))  # frames 61..120 never arrived
    assert [fr["frame_id"] for fr in out] == list(range(1, 181))
    assert all(fr["general_model"] == [] for fr in out if 61 <= fr["frame_id"] <= 120)
    rep = gs.report()
    assert rep["session"] == {"frames_in": 120, "frames_filled": 60, "chunks_in": 2}


def test_decisions_carry_frame_ids_and_close_freezes_camera():
    gs = make_stream()
    for f in range(1, 400):
        gs.process(f, entity_class_ids=[0], is_cone=(f % 3 != 0), arrived=f > 20)
    names = {e.name: e.frame_id for e in gs.events}
    assert names["first_aircraft_seen"] == 10
    assert names["entity"] == 320
    assert names["parts_layout"] == 241  # front-wheel bucket > 30·8 frames
    assert "camera_type" not in names
    snap = gs.close()
    assert (
        snap["camera_type_cone"] is True
        and gs.events[-1].name == "camera_type"
        and gs.events[-1].frame_id == 399
    )
    assert snap["mode_plane_height"] == 680 and snap["frame_of_beginning"] == 10


def test_v1_compat_file_matches_direct_second_run(tmp_path):
    gs = make_stream()
    for f in range(1, 400):
        gs.process(f, arrived=f > 20)
    path = tmp_path / "general_modelEV.mp4-second_run.ndjson"
    n = gs.write_v1_compat(str(path))
    assert n == 399
    ctx = gs.compat_context()
    assert ctx.main_front_wheel == (900, 700, 1000, 800) and ctx.mode_plane_height == 680
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    assert lines[0] == ndjson_line(1, second_run_rows(rows_provider(1, None), 1, ctx, CM))
    rec = json.loads(lines[349])  # frame 350: BL left of the wheel → obstacle row, plane last
    rows = rec["350"]
    assert rows[-1] == [100.0, 50.0, 1700.0, 730.0, 680, 2]
    assert [r[5] for r in rows] == [0, 12, 3, 29, 2]
    assert not any(r[5] == 2 and r[4] != 680 for r in rows)  # no raw airplane rows survive
    # the file compares equal to itself through the parity tool (sanity of the format)
    res = compare_gm_ndjson(str(path), str(path))
    assert res.frame_parity == 1.0 and res.frames_compared == 399


def test_stream_requires_a_source():
    try:
        GmStream(CM, "ev")
    except ValueError as e:
        assert "rows_provider" in str(e)
    else:
        raise AssertionError("expected ValueError")
