"""Tracker events for the stage detector (PF-Q1-06 / PF-Q1-17) — derived causally from published tracker records.

Input: the records the tracker publishes (v1 envelopes, from the v1-compat file or the v2 bus): the airplane's
`state_dict.arrival_frame` / `departure_frame`, a beltloader's `data.bl_type` ('front' | 'back' | 'undefined') and
`state_dict._status`. The derivation never touches the tracker loop, so it runs on production files as well — which is how
v1 and v2 event timings are compared.

Events (names from `pf.contract.EVENTS`):
  T_ARR       the first airplane record with `arrival_frame` set. `frame` = that value (the tracker rewrites arrival back to
              the first stopping frame), `decided_at` = the frame whose record carried it.
  T_DEP       the first airplane record with `departure_frame` set.
  BL_AT_DOOR  a free door ('front' / 'back') gets an occupant: a beltloader record shows that door. Another track id showing
              the same door while it is occupied is a re-identification of the occupant (the tracker re-keys objects when a
              loader is re-detected), recorded in `reidentifications`, not a new event.
  BL_LEAVE    the occupant's `bl_type` returns to 'undefined' — the tracker clears a door label only when the loader starts
              moving. An unobserved or lost occupant keeps the door.
PUSHBACK_ATTACHED is not derivable from tracker records (pushbacks are not tracked); it belongs to the stage detector on GM
rows.

Observed on the production tracker file of DjwtQRdZyt0sSk: T_ARR 3 669; beltloader 85 at the front door from frame 9 888 (the
start of beltloader-chocks' timeline), re-identified as 88 at 21 945.
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass, field

DOORS = ("front", "back")


@dataclass
class TrackerEvent:
    name: str
    frame: int
    decided_at: int
    attrs: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


class TrackerEventDeriver:
    def __init__(self):
        self.arrival_emitted = False
        self.departure_emitted = False
        self.occupant: dict = {}  # door -> tr_id
        self.events: list = []
        self.reidentifications: list = []

    def feed(self, frame_id: int, records) -> list:
        out = []
        for r in records or []:
            cls = r.get("cls_str")
            sd = r.get("state_dict") or {}
            if cls == "airplane":
                if not self.arrival_emitted and sd.get("arrival_frame") is not None:
                    self.arrival_emitted = True
                    out.append(TrackerEvent("T_ARR", int(sd["arrival_frame"]), frame_id, {"source": "tracker.airplane"}))
                if not self.departure_emitted and sd.get("departure_frame") is not None:
                    self.departure_emitted = True
                    out.append(TrackerEvent("T_DEP", int(sd["departure_frame"]), frame_id, {"source": "tracker.airplane"}))
            elif cls == "beltloader":
                tid = r.get("tr_id")
                bl_type = (r.get("data") or {}).get("bl_type")
                if bl_type in DOORS:
                    current = self.occupant.get(bl_type)
                    if current is None:
                        self.occupant[bl_type] = tid
                        out.append(TrackerEvent("BL_AT_DOOR", frame_id, frame_id,
                                                {"door": bl_type, "tr_id": tid, "status": sd.get("_status")}))
                    elif current != tid:
                        self.occupant[bl_type] = tid
                        self.reidentifications.append({"frame": frame_id, "door": bl_type, "from": current, "to": tid})
                else:
                    for door, occ in list(self.occupant.items()):
                        if occ == tid:
                            del self.occupant[door]
                            out.append(TrackerEvent("BL_LEAVE", frame_id, frame_id,
                                                    {"door": door, "tr_id": tid, "status": sd.get("_status")}))
        self.events.extend(out)
        return out


def iter_tracker_lines(path: str):
    """(frame_id, records) from a v1-compat tracker ndjson (`{"<n>": [...]}`) or a v2 bus file (`{"frame_id", "records"}`)."""
    with io.open(path, "rb") as fh:
        for line in fh:
            rec = json.loads(line)
            if "records" in rec and "frame_id" in rec:
                yield int(rec["frame_id"]), rec["records"]
            else:
                ((k, v),) = rec.items()
                yield int(k), v


def derive_events(path: str) -> TrackerEventDeriver:
    d = TrackerEventDeriver()
    for frame_id, records in iter_tracker_lines(path):
        d.feed(frame_id, records)
    return d
