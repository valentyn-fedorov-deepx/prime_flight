"""Pure-Python geometry helpers used by the General Model port.

Exact ports of `general_model/main.py` (correct_coords, get_overlay_ratio, count_bbox_frames) and of the
`cv_common/common.py` helpers at pin ac5098d (bbox_area, bboxes_iou, get_hw, get_center, get_relative_intersection,
is_overlap). The cv_common helpers carry conventions that matter for parity and are kept verbatim:
  * `bboxes_iou` uses the +1 pixel convention (inclusive coordinates) — `common.py:204-232`;
  * `get_hw` / `get_center` truncate with `int()` and `get_center` uses integer division — `common.py:101-111`;
  * `get_relative_intersection(target, main)` = intersection / (area(main) + 1), 0 when boxes do not touch — `common.py:235-250`;
  * `is_overlap` treats touching edges as NOT overlapping (`>=`) — `common.py:113-134`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FRAME_W, FRAME_H = 1920, 1080


def correct_coords(xyxy, img_height: int = FRAME_H, img_width: int = FRAME_W) -> list:
    """Exact port of `general_model/main.py:153-168`: clamp a box into the frame."""
    new_xyxy = [i for i in xyxy]
    new_xyxy[0] = xyxy[0] if xyxy[0] > 0 else 0
    new_xyxy[1] = xyxy[1] if xyxy[1] > 0 else 0
    new_xyxy[2] = xyxy[2] if xyxy[2] < img_width else img_width
    new_xyxy[3] = xyxy[3] if xyxy[3] < img_height else img_height
    new_xyxy = [i if i >= 0 else 0 for i in new_xyxy]
    return new_xyxy


def bbox_area(bbox, is_xyxy: bool = True) -> float:
    """`cv_common/common.py:74-84`."""
    if is_xyxy:
        return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    return bbox[2] * bbox[3]


def get_hw(bbox):
    """`cv_common/common.py:107-110`: (height, width) after int truncation."""
    x1, y1, x2, y2 = map(int, bbox)
    return y2 - y1, x2 - x1


def get_center(bbox):
    """`cv_common/common.py:101-104`: integer centre."""
    x1, y1, x2, y2 = map(int, bbox)
    return (x1 + x2) // 2, (y1 + y2) // 2


def bboxes_iou(xyxy1, xyxy2) -> float:
    """`cv_common/common.py:204-232`: IoU with the +1 (inclusive pixel) convention."""
    x1_d, y1_d, x2_d, y2_d = xyxy1
    x1_e, y1_e, x2_e, y2_e = xyxy2
    x_left = max(x1_d, x1_e)
    y_top = max(y1_d, y1_e)
    x_right = min(x2_d, x2_e)
    y_bottom = min(y2_d, y2_e)
    intersection_area = max(0, x_right - x_left + 1) * max(0, y_bottom - y_top + 1)
    bb1_area = (max(0, x2_d - x1_d) + 1) * (max(0, y2_d - y1_d) + 1)
    bb2_area = (max(0, x2_e - x1_e) + 1) * (max(0, y2_e - y1_e) + 1)
    return intersection_area / float(bb1_area + bb2_area - intersection_area)


def relative_intersection(target_bbox, main_bbox) -> float:
    """`cv_common/common.py:235-250` (`get_relative_intersection`): intersection / (area(main) + 1)."""
    x1 = max(target_bbox[0], main_bbox[0])
    x2 = min(target_bbox[2], main_bbox[2])
    y1 = max(target_bbox[1], main_bbox[1])
    y2 = min(target_bbox[3], main_bbox[3])
    if x1 > x2 or y1 > y2:
        return 0
    intersection_area = (x2 - x1) * (y2 - y1)
    return intersection_area / (bbox_area(main_bbox) + 1)


def is_overlap(box1, box2, is_xyxy: bool = True) -> bool:
    """`cv_common/common.py:113-134`: touching edges do not count as overlap."""
    if is_xyxy:
        b1_x1, b1_y1, b1_x2, b1_y2 = box1[0], box1[1], box1[2], box1[3]
        b2_x1, b2_y1, b2_x2, b2_y2 = box2[0], box2[1], box2[2], box2[3]
    else:
        b1_x1, b1_x2 = box1[0] - box1[2] / 2, box1[0] + box1[2] / 2
        b1_y1, b1_y2 = box1[1] - box1[3] / 2, box1[1] + box1[3] / 2
        b2_x1, b2_x2 = box2[0] - box2[2] / 2, box2[0] + box2[2] / 2
        b2_y1, b2_y2 = box2[1] - box2[3] / 2, box2[1] + box2[3] / 2
    if b1_x1 >= b2_x2 or b2_x1 >= b1_x2:
        return False
    if b1_y1 >= b2_y2 or b2_y1 >= b1_y2:
        return False
    return True


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
