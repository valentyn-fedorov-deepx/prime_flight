"""Input hygiene for tracker records: class-field leakage between tracked-object classes.

Real bug (gat-streaming stand, 3 of 8 production videos): in a newer tracker version the beltloader-only fields
``_bl_type_bbox`` / ``_bl_type_frames`` moved up the class hierarchy and started being written into the airplane
state (40 keys instead of 38). ``aircraft-chocks`` restores only the airplane from ``state_dict``; its class does
not know those fields and ``cv_common/tracked_object.py`` raises ``ValueError``.

``check_class_leakage`` catches it before deployment; ``strip_class_leakage`` cures existing data by the same
mechanism the production code already uses for stale fields (``state_dict.pop('_recent_bboxes', None)``).
This is not a logic change: no module reads ``bl_type`` for the airplane.
"""

from __future__ import annotations

# Fields the ``Vehicle`` class may write into its own state and which must NOT appear in the airplane state.
VEHICLE_ONLY_KEYS = frozenset({"_bl_type_bbox", "_bl_type_frames"})

# Classes for which the vehicle-only keys are legitimate.
VEHICLE_CLASSES = frozenset({"beltloader", "gse", "vehicle", "pushback"})


def _state_of(obj):
    if not isinstance(obj, dict):
        return None
    state = obj.get("state_dict")
    return state if isinstance(state, dict) else None


def check_class_leakage(tracks) -> list:
    """Return violations as ``[(class_name, [leaked keys])]``; empty list means clean."""
    bad = []
    for obj in tracks or []:
        state = _state_of(obj)
        if state is None:
            continue
        cls = state.get("_class_name")
        if cls is None or cls in VEHICLE_CLASSES:
            continue
        leaked = VEHICLE_ONLY_KEYS & state.keys()
        if leaked:
            bad.append((cls, sorted(leaked)))
    return bad


def strip_class_leakage(tracks) -> int:
    """Remove foreign fields from non-vehicle states in place. Returns the number of removed keys."""
    fixed = 0
    for obj in tracks or []:
        state = _state_of(obj)
        if state is None:
            continue
        cls = state.get("_class_name")
        if cls is None or cls in VEHICLE_CLASSES:
            continue
        for key in VEHICLE_ONLY_KEYS:
            if key in state:
                del state[key]
                fixed += 1
    return fixed
