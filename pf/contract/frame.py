"""Frame contract: the record that travels on the bus from GM + tracker (+ stage detector) to modules.

Ported from the gat-streaming stand (G:/gat-streaming/streaming/contract.py) and extended with the
stage-detector fields from docs/02_target_architecture.md §2:

    {
      "schema_version": "1.0",
      "frame_id": 1234,              # absolute, 1-based, NOT the position in the stream (X2)
      "general_model": [...],        # detections: [x1, y1, x2, y2, conf, class_id] (observed prod format)
      "trackers": [...],             # tracked objects with "state_dict"
      "stage": "DOWNLOAD_UPLOAD",    # optional, from the stage detector
      "events": ["BL_AT_DOOR"],      # optional, transitions fired on this frame_id
      "anchors": {"T_ARR": 4812}     # optional, absolute frame ids of past events
    }

Two production problems this contract exists for (both measured on real data):
1. schema drift without a version: 15–16 incompatible tracker inference versions per video in the bucket,
   distinguishable only by loading them and seeing which module crashes  -> ``schema_version`` (X3);
2. frame numbering by stream position: modules use ``enumerate(metadata, 1)``; one lost 7.5 s chunk shifts every
   ``frame_number == aircraft.departure_frame`` comparison by 60 frames -> mandatory absolute ``frame_id`` (X2).

The optional stage fields are only emitted when present, so frames produced without a stage detector stay
byte-identical to the stand's schema 1.0 frames.
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0"

REQUIRED_FRAME_KEYS = frozenset({"schema_version", "frame_id", "general_model", "trackers"})
OPTIONAL_FRAME_KEYS = frozenset({"stage", "events", "anchors"})

# Stage detector vocabulary (docs/02_target_architecture.md §5). Names are frozen here; a change is an ADR.
STAGES = ("PRE_ARRIVAL", "ARRIVAL_POST", "DOWNLOAD_UPLOAD", "PRE_DEPARTURE", "DEPARTURE")
EVENTS = ("T_ARR", "BL_AT_DOOR", "BL_LEAVE", "PUSHBACK_ATTACHED", "T_DEP")


class ContractError(ValueError):
    """Contract violation. Failing here beats silently producing the wrong verdict."""


def make_frame(
    frame_id: int,
    detections,
    tracks,
    *,
    stage: str | None = None,
    events=None,
    anchors=None,
    schema_version: str = SCHEMA_VERSION,
) -> dict:
    """Build a frame record in canonical form. Optional stage fields are added only when given."""
    frame = {
        "schema_version": schema_version,
        "frame_id": int(frame_id),
        "general_model": detections if detections is not None else [],
        "trackers": tracks if tracks is not None else [],
    }
    if stage is not None:
        frame["stage"] = stage
    if events is not None:
        frame["events"] = list(events)
    if anchors is not None:
        frame["anchors"] = dict(anchors)
    return frame


def empty_frame(frame_id: int, schema_version: str = SCHEMA_VERSION) -> dict:
    """Placeholder for a lost frame — keeps the numbering continuous (X2)."""
    return make_frame(frame_id, [], [], schema_version=schema_version)


def validate_frame(frame: dict, *, strict_version: bool = True) -> dict:
    """Validate one record. Returns it unchanged so it can be chained inside a stream."""
    if not isinstance(frame, dict):
        raise ContractError(f"frame record must be a dict, got {type(frame).__name__}")

    missing = REQUIRED_FRAME_KEYS - frame.keys()
    if missing:
        raise ContractError("missing fields: {}".format(", ".join(sorted(missing))))

    if strict_version and frame["schema_version"] != SCHEMA_VERSION:
        raise ContractError(
            "schema version {!r}, expected {!r}".format(frame["schema_version"], SCHEMA_VERSION)
        )

    fid = frame["frame_id"]
    if isinstance(fid, bool) or not isinstance(fid, int) or fid < 1:
        raise ContractError(f"frame_id must be an int >= 1, got {fid!r}")

    for key in ("general_model", "trackers"):
        if not isinstance(frame[key], list):
            raise ContractError(f"{key} must be a list, got {type(frame[key]).__name__}")

    if "stage" in frame and frame["stage"] not in STAGES:
        raise ContractError("unknown stage {!r} (allowed: {})".format(frame["stage"], ", ".join(STAGES)))
    if "events" in frame:
        if not isinstance(frame["events"], list):
            raise ContractError("events must be a list")
        unknown = [e for e in frame["events"] if e not in EVENTS]
        if unknown:
            raise ContractError("unknown events {!r} (allowed: {})".format(unknown, ", ".join(EVENTS)))
    if "anchors" in frame:
        anchors = frame["anchors"]
        if not isinstance(anchors, dict):
            raise ContractError("anchors must be a dict event -> frame_id")
        for name, value in anchors.items():
            if name not in EVENTS:
                raise ContractError(f"unknown anchor {name!r}")
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ContractError(f"anchor {name} must be an int frame_id >= 1, got {value!r}")
            if value > fid:
                raise ContractError(
                    "anchor %s=%d lies in the future of frame %d (not causal)" % (name, value, fid)
                )
    return frame
