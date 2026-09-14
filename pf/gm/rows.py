"""Row assembly: detector outputs → the 6-element rows modules consume (`[x1, y1, x2, y2, conf, class_id]`).

First-run semantics of `general_model/main.py:541-592` are reproduced exactly:
  * GM detector rows: coordinates truncated with `int()`, clamped with `correct_coords`, stored as floats;
  * chocks detector rows: raw float coordinates from the model, class forced to `str2id['chock']`;
  * vehicle detector rows: raw float coordinates, class forced to `str2id['vehicle']`.
The second-run (v1-compat) pass truncates and clamps every row again (see `pf.gm.compat_writer`).
"""

from __future__ import annotations

from dataclasses import dataclass

from pf.gm.geometry import correct_coords

# Classes GM synthesizes itself (not produced by any detector head); ids come from cv_common/global_config.yaml str2id.
SYNTHETIC_CLASSES = ("chock", "vehicle", "obstacle", "side_obstacle")

# Transport classes that take part in the obstacle / side-obstacle logic (`main.py:789-790`).
TRANSPORT_CLASSES = ("beltloader", "gse", "pushback", "tow_bar", "fuel_truck", "trailer", "ladder")

# Classes whose boxes are removed from optical-flow tracking of the aircraft (`main.py:575-577, 780`).
PLANE_TRACKING_REMOVE_CLASSES = ("person", "trailer", "fuel_truck", "gse")


@dataclass(frozen=True)
class ClassMap:
    """`str2id` from cv_common/global_config.yaml, frozen as data so the id mapping is versioned with the code."""

    str2id: dict

    def __post_init__(self):
        object.__setattr__(self, "id2str", {v: k for k, v in self.str2id.items()})

    def id(self, name: str) -> int:
        return self.str2id[name]

    def name(self, class_id: int):
        return self.id2str.get(int(class_id))

    def ids(self, names) -> list:
        return [self.str2id[n] for n in names if n in self.str2id]


def gm_rows(det, cm: ClassMap) -> list:
    """GM detector output (N, 6 float) → first-run rows, exact port of `main.py:542-551` (row part only)."""
    rows = []
    if det is None or len(det) == 0:
        return rows
    for *xyxy, conf, cls_id in det:
        xyxy = list(map(int, xyxy))
        xyxy = correct_coords(xyxy)
        rows.append([*list(map(float, xyxy)), float(conf), int(cls_id)])
    return rows


def forced_class_rows(det, class_id: int) -> list:
    """Chocks / vehicle detector output → rows with a forced class id, exact port of `main.py:583-592`."""
    rows = []
    if det is None or len(det) == 0:
        return rows
    for *xyxy, conf, _cls in det:
        rows.append([*list(map(float, xyxy)), float(conf), int(class_id)])
    return rows


def first_run_rows(gm_det, chocks_det, vehicle_det, cm: ClassMap) -> list:
    """Row order of the first-run file: GM rows, then chock rows, then vehicle rows."""
    return (
        gm_rows(gm_det, cm)
        + forced_class_rows(chocks_det, cm.id("chock"))
        + forced_class_rows(vehicle_det, cm.id("vehicle"))
    )
