"""Parity: batch feeding vs chunked feeding, and old-vs-new GM ndjson comparison mechanics.

Lesson built into these tests (from the stand): the first full parity run showed 22 791 frames vs 22 800 and it
was a FALSE ALARM — ffmpeg vs OpenCV on non-monotonic DTS, not batch vs stream. The decoder must be pinned on
both sides of any comparison (X4); these tests use deterministic synthetic frames so only the feeding mechanics
are under test.
"""

import json

from pf.contract import make_frame
from pf.eval import as_chunks, compare_gm_ndjson, diff_streams, digest
from pf.receiver import stream_from_chunks


def synth_frames(n=600, seed=7):
    rng = seed
    frames = []
    for i in range(1, n + 1):
        rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
        k = rng % 4
        dets = [[10 + k, 20 + k, 90 + k, 120 + k, 0.9, k] for _ in range(k)]
        tracks = (
            [{"state_dict": {"_class_name": "airplane", "_obj_id": 1, "_xyxy": [10, 20, 900, 700]}}]
            if k
            else []
        )
        frames.append(make_frame(i, dets, tracks))
    return frames


def test_chunked_feeding_yields_the_same_stream():
    frames = synth_frames()
    out = list(stream_from_chunks("ev", as_chunks(frames, 60)))
    assert digest(out) == digest(frames)


def test_chunk_size_does_not_matter():
    frames = synth_frames()
    base = digest(frames)
    for size in (7, 30, 60, 137, 600):
        out = list(stream_from_chunks("ev", as_chunks(frames, size)))
        assert digest(out) == base, "chunk size %d changed the stream" % size


def test_frame_count_is_preserved():
    frames = synth_frames(n=600)
    assert len(list(stream_from_chunks("ev", as_chunks(frames, 60)))) == 600


def test_lost_chunk_breaks_parity_visibly():
    frames = synth_frames()
    out = list(stream_from_chunks("ev", as_chunks(frames, 60), drop={3}))
    assert len(out) == len(frames)
    assert digest(out) != digest(frames)


def test_lost_chunk_is_localised_exactly():
    frames = synth_frames()
    out = list(stream_from_chunks("ev", as_chunks(frames, 60), drop={3}))
    diff = diff_streams(frames, out)
    assert diff
    assert all(180 <= i <= 239 for i in diff), [i for i in diff if not 180 <= i <= 239]


# --------------------------------------------------------------------------
# GM ndjson comparison (production format: {"<frame_no>": [[x1,y1,x2,y2,conf,cls], ...]})
# --------------------------------------------------------------------------


def _write_ndjson(path, frames):
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps({str(frame["frame_id"]): frame["general_model"]}) + "\n" for frame in frames)


def test_identical_gm_files_have_full_parity(tmp_path):
    frames = synth_frames(n=200)
    a, b = tmp_path / "a.ndjson", tmp_path / "b.ndjson"
    _write_ndjson(a, frames)
    _write_ndjson(b, frames)
    res = compare_gm_ndjson(str(a), str(b))
    assert res.frames_compared == 200 and res.frame_parity == 1.0
    assert res.dets_a == res.dets_b == res.dets_matched


def test_gm_diff_is_counted_and_located(tmp_path):
    frames = synth_frames(n=200)
    changed = [dict(f) for f in frames]
    # perturb frame 50: shift one box by 5 px and drop a detection in frame 120
    changed[49] = make_frame(
        50, [[d[0] + 5, d[1], d[2], d[3], d[4], d[5]] for d in frames[49]["general_model"]], []
    )
    changed[119] = make_frame(120, frames[119]["general_model"][1:], [])
    a, b = tmp_path / "a.ndjson", tmp_path / "b.ndjson"
    _write_ndjson(a, frames)
    _write_ndjson(b, changed)
    res = compare_gm_ndjson(str(a), str(b))
    assert res.frames_compared == 200
    assert res.frames_equal == 200 - sum(1 for i in (49, 119) if frames[i]["general_model"])
    assert [d[0] for d in res.first_diffs] == [i + 1 for i in (49, 119) if frames[i]["general_model"]]


def test_gm_frames_are_matched_by_key_not_position(tmp_path):
    """A missing frame in one file must not shift the comparison of all later frames (X2)."""
    frames = synth_frames(n=100)
    a, b = tmp_path / "a.ndjson", tmp_path / "b.ndjson"
    _write_ndjson(a, frames)
    _write_ndjson(b, [f for f in frames if f["frame_id"] != 10])
    res = compare_gm_ndjson(str(a), str(b))
    assert res.frames_only_in_a == 1 and res.frames_only_in_b == 0
    assert res.frames_compared == 99 and res.frames_equal == 99
