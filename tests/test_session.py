"""Session tests: chunks must be invisible to a module. Central question: what happens when a chunk is lost."""

import pytest

from pf.contract import ContractError, make_frame
from pf.receiver import Session, stream_from_chunks


def chunk(start, n=60):
    return [make_frame(start + i, [], []) for i in range(n)]


def test_intact_stream_passes_unchanged():
    sess = Session("ev-1")
    out = sess.feed_chunk(chunk(1)) + sess.feed_chunk(chunk(61))
    assert [f["frame_id"] for f in out] == list(range(1, 121))
    assert sess.stats.frames_filled == 0


def test_chunk_boundary_is_invisible_in_numbering():
    ids = [f["frame_id"] for f in stream_from_chunks("ev", [chunk(1), chunk(61)])]
    assert ids == list(range(1, 121))


def test_lost_chunk_is_filled_with_placeholders():
    """Correct receiver behaviour: content is lost, numbering stays intact."""
    frames = list(stream_from_chunks("ev", [chunk(1), chunk(61), chunk(121)], drop={1}))
    assert [f["frame_id"] for f in frames] == list(range(1, 181))
    lost = [f for f in frames if 61 <= f["frame_id"] <= 120]
    assert all(f["general_model"] == [] and f["trackers"] == [] for f in lost)


def test_without_fill_the_numbering_drifts():
    """'As-is' behaviour: frames simply vanish; position in stream != absolute id by exactly one chunk."""
    frames = list(stream_from_chunks("ev", [chunk(1), chunk(61), chunk(121)], drop={1}, fill_gaps=False))
    assert len(frames) == 120
    assert frames[-1]["frame_id"] - len(frames) == 60


def test_unordered_stream_is_rejected():
    sess = Session("ev")
    sess.feed_chunk(chunk(1))
    with pytest.raises(ContractError, match="not ordered"):
        sess.feed_chunk(chunk(1))


def test_hole_inside_a_chunk_is_closed_too():
    sess = Session("ev")
    partial = [make_frame(1, [], []), make_frame(5, [], [])]  # 2, 3, 4 never arrived
    out = sess.feed_chunk(partial)
    assert [f["frame_id"] for f in out] == [1, 2, 3, 4, 5]
    assert sess.stats.frames_filled == 3


def test_loss_statistics():
    frames = list(stream_from_chunks("ev", [chunk(1), chunk(61)], drop={0}))
    assert len(frames) == 120
    assert sum(1 for f in frames if not f["general_model"] and f["frame_id"] <= 60) == 60


def test_closed_session_rejects_input():
    sess = Session("ev")
    sess.close()
    with pytest.raises(RuntimeError, match="closed"):
        sess.feed_chunk(chunk(1))


def test_stage_fields_survive_the_receiver():
    """Stage/events/anchors stamped upstream must reach modules untouched."""
    fr = make_frame(1, [], [], stage="PRE_ARRIVAL", events=[], anchors={})
    out = Session("ev").feed_chunk([fr])
    assert out[0]["stage"] == "PRE_ARRIVAL" and out[0]["events"] == [] and out[0]["anchors"] == {}
