"""Pure-Python geometry helpers used by the General Model port.

Ported from `general_model/main.py` (correct_coords, get_overlay_ratio, count_bbox_frames) and re-implemented for the
`cv_common.common` helpers that are pinned but not available on disk (bbox_area, bboxes_iou, get_hw, get_center,
get_relative_intersection, is_overlap). Where the cv_common implementation could not be verified, the docstring says
ASSUMPTION; parity runs against v1 output will confirm or refute them (tracked in docs/analysis/gm_current.md §11).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FRAME_W, FRAME_H = 1920, 1080


def correct_coords(xyxy, img_height: int = FRAME_H, img_width: int = FRAME_W) -> list:
    """Exact port of `general_model/main.py:153-168`: clamp a box into the frame."""
    new_xyxy = [i for i in xyxy]
    new_xyxy[0] = max(0, xyxy[0])
    new_xyxy[1] = max(0, xyxy[1])
    new_xyxy[2] = min(img_width, xyxy[2])
    new_xyxy[3] = min(img_height, xyxy[3])
    new_xyxy = [max(i, 0) for i in new_xyxy]
    return new_xyxy


def bbox_area(box) -> float:
    """ASSUMPTION (cv_common.common.bbox_area): (x2 - x1) * (y2 - y1), no clamping."""
    return (box[2] - box[0]) * (box[3] - box[1])


def get_hw(box):
    """ASSUMPTION (cv_common.common.get_hw): returns (height, width)."""
    return box[3] - box[1], box[2] - box[0]


def get_center(box):
    """ASSUMPTION (cv_common.common.get_center): (cx, cy)."""
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def intersection_area(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    if x1 >= x2 or y1 >= y2:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def bboxes_iou(a, b) -> float:
    """ASSUMPTION (cv_common.common.bboxes_iou): standard IoU on xyxy boxes."""
    inter = intersection_area(a, b)
    if inter <= 0:
        return 0.0
    union = bbox_area(a) + bbox_area(b) - inter
    return inter / union if union > 0 else 0.0


def relative_intersection(a, b) -> float:
    """ASSUMPTION (cv_common.common.get_relative_intersection): intersection area / area of the SECOND box.

    Used as `get_relative_intersection(side_roi, transport) > 0.7` (fraction of the transport inside the ROI) and as
    the association key `get_relative_intersection(new_xyxy, plane.xyxy)`.
    """
    area_b = bbox_area(b)
    if area_b <= 0:
        return 0.0
    return intersection_area(a, b) / area_b


def is_overlap(a, b) -> bool:
    """ASSUMPTION (cv_common.common.is_overlap): boxes share a positive-area intersection."""
    return intersection_area(a, b) > 0


def overlay_ratio(target_bbox, main_bbox) -> float:
    """Exact port of `general_model/main.py:251-273`: intersection / area of the smaller box."""
    x1 = max(target_bbox[0], main_bbox[0])
    x2 = min(target_bbox[2], main_bbox[2])
    y1 = max(target_bbox[1], main_bbox[1])
    y2 = min(target_bbox[3], main_bbox[3])
    if x1 > x2 or y1 > y2:
        return 0
    inter = (x2 - x1) * (y2 - y1)
    area_target = (target_bbox[2] - target_bbox[0]) * (target_bbox[3] - target_bbox[1])
    area_main = (main_bbox[2] - main_bbox[0]) * (main_bbox[3] - main_bbox[1])
    min_area = min(area_target, area_main)
    return inter / min_area


def count_bbox_frames(bboxes_dict: dict, xyxy) -> dict:
    """Exact port of `general_model/main.py:199-207`: bucket boxes by IoU > 0.8 and count frames per bucket."""
    if bboxes_dict:
        for bbox in bboxes_dict:
            if bboxes_iou(xyxy, bbox) > 0.8:
                bboxes_dict[tuple(bbox)] += 1
                return bboxes_dict
    bboxes_dict[tuple(xyxy)] = 1
    return bboxes_dict


@dataclass(frozen=True)
class Letterbox:
    """Static letterbox geometry of `YOLOv8_onnx.predict` (`scripts/new_model.py:330-356`), computed once per source size."""

    img_w: int
    img_h: int
    input_w: int
    input_h: int
    new_w: int
    new_h: int
    pad_x: int
    pad_y: int

    @property
    def x_factor(self) -> float:
        return self.img_w / self.new_w

    @property
    def y_factor(self) -> float:
        return self.img_h / self.new_h

    @property
    def padding(self) -> list:
        """torch.nn.functional.pad order: (left, right, top, bottom)."""
        return [max(0, self.pad_x), max(0, self.pad_x), max(0, self.pad_y), max(0, self.pad_y)]

    @property
    def padded_fraction(self) -> float:
        """Share of the model input that is padding (compute wasted on 114-grey)."""
        return 1.0 - (self.new_w * self.new_h) / (self.input_w * self.input_h)


def letterbox_geometry(img_w: int, img_h: int, input_w: int = 1088, input_h: int = 1088) -> Letterbox:
    """Same arithmetic as v1: bigger side → model side, other side keeps aspect, both rounded UP to multiples of 32."""
    aspect = img_w / img_h
    if aspect > 1:
        new_w = input_w
        new_h = int(new_w / aspect)
    else:
        new_h = input_h
        new_w = int(new_h * aspect)
    new_w = math.ceil(new_w / 32) * 32
    new_h = math.ceil(new_h / 32) * 32
    pad_x = (input_w - new_w) // 2
    pad_y = (input_h - new_h) // 2
    return Letterbox(img_w, img_h, input_w, input_h, new_w, new_h, pad_x, pad_y)
