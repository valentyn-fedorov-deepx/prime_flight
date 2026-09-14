"""Contract tests. Each one corresponds to a real production problem, not a hypothetical one.
Ported from the gat-streaming stand and extended with the stage-detector fields."""

import pytest

from pf.contract import (
    ContractError,
    check_class_leakage,
    empty_frame,
    make_frame,
    strip_class_leakage,
    validate_frame,
)


def test_canonical_frame_passes():
    validate_frame(make_frame(1, [], []))


def test_missing_field():
    frame = make_frame(1, [], [])
    del frame["frame_id"]
    with pytest.raises(ContractError, match="frame_id"):
        validate_frame(frame)


def test_foreign_schema_version_is_rejected():
    """The whole point of schema_version: incompatible input is visible immediately, not by a module crash."""
    frame = make_frame(1, [], [], schema_version="0.9")
    with pytest.raises(ContractError, match="schema version"):
        validate_frame(frame)


def test_zero_frame_id_is_rejected():
    with pytest.raises(ContractError, match="frame_id"):
        validate_frame(make_frame(0, [], []))


def test_placeholder_is_valid():
    frame = empty_frame(42)
    validate_frame(frame)
    assert frame["frame_id"] == 42
    assert frame["general_model"] == [] and frame["trackers"] == []


def test_frame_without_stage_fields_stays_minimal():
    """Frames produced without a stage detector must stay byte-identical to the stand's schema 1.0."""
    assert set(make_frame(1, [], []).keys()) == {"schema_version", "frame_id", "general_model", "trackers"}


# --------------------------------------------------------------------------
# Stage detector fields
# --------------------------------------------------------------------------


def test_stage_fields_pass_when_valid():
    frame = make_frame(
        100, [], [], stage="DOWNLOAD_UPLOAD", events=["BL_AT_DOOR"], anchors={"T_ARR": 40, "BL_AT_DOOR": 100}
    )
    validate_frame(frame)


def test_unknown_stage_is_rejected():
    with pytest.raises(ContractError, match="unknown stage"):
        validate_frame(make_frame(1, [], [], stage="LUNCH"))


def test_unknown_event_is_rejected():
    with pytest.raises(ContractError, match="unknown events"):
        validate_frame(make_frame(1, [], [], events=["ALIENS"]))


def test_anchor_in_the_future_is_not_causal():
    """An anchor can only point to the past: the stage detector is causal by construction."""
    with pytest.raises(ContractError, match="future"):
        validate_frame(make_frame(10, [], [], anchors={"T_ARR": 11}))


# --------------------------------------------------------------------------
# Class-field leakage — reproduction of the real bug
# --------------------------------------------------------------------------


def _airplane(with_leak):
    state = {"_class_name": "airplane", "_obj_id": 1, "arrival_frame": 10}
    if with_leak:
        state["_bl_type_bbox"] = None
        state["_bl_type_frames"] = {"front": 0, "back": 0}
    return {"state_dict": state}


def _beltloader():
    return {
        "state_dict": {
            "_class_name": "beltloader",
            "_obj_id": 2,
            "_bl_type_bbox": None,
            "_bl_type_frames": {"front": 3, "back": 1},
        }
    }


def test_clean_tracks_have_no_violations():
    assert check_class_leakage([_airplane(False), _beltloader()]) == []


def test_leak_into_airplane_is_caught():
    """Exactly the case that broke the module on 3 of 8 videos: 40 keys instead of 38."""
    assert check_class_leakage([_airplane(True)]) == [("airplane", ["_bl_type_bbox", "_bl_type_frames"])]


def test_beltloader_may_own_these_fields():
    assert check_class_leakage([_beltloader()]) == []


def test_hygiene_removes_exactly_the_foreign_keys():
    tracks = [_airplane(True), _beltloader()]
    assert strip_class_leakage(tracks) == 2
    assert check_class_leakage(tracks) == []
    assert tracks[1]["state_dict"]["_bl_type_frames"] == {"front": 3, "back": 1}
    assert tracks[0]["state_dict"]["arrival_frame"] == 10


def test_hygiene_is_idempotent():
    tracks = [_airplane(True)]
    strip_class_leakage(tracks)
    assert strip_class_leakage(tracks) == 0
