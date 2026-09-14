"""Main-aircraft box stabilizer of the master-lineage GM (commits 13a4ddc … 8576299): `cv_common.detections.BboxStabilizer`.

`general_model/main.py` (master first pass) calls `stabilizer.update_bbox(obj.id, frame_id, xyxy, planes_tracking_meta_data)`
for every reported aircraft track on frames where the noise preprocessor is in HEAVY mode, before the history
bookkeeping. The class body is verbatim from cv_common (identical in ac5098d and 2759daf; GM 8576299 pins 71c6e242, not in
the archive — "Update cv_common for BboxStabilizer"). Quirks kept: the time-gap check compares a frame with itself and never
clears the window; the returned box is a list of floats.

`PlanesView` adapts `pf.gm.plane_tracker.NorfairPlaneTracker.planes` (id -> PlaneHistory, aliased on re-association) to the
`planes_dict[id][1][frame]` access the class uses.
"""

from __future__ import annotations

from collections import deque

import numpy as np


class BboxStabilizer:
    def __init__(self, window_size=16, time_gap=8):
        self.window_size = window_size
        self.time_gap = time_gap
        self.bbox_container = {}

    def update_bbox(self, plane_id, frame_id, xyxy, planes_dict):
        if plane_id not in self.bbox_container:
            self.bbox_container[plane_id] = deque(maxlen=self.window_size)

        self.bbox_container[plane_id].append((frame_id, xyxy))

        if (frame_id - self.bbox_container[plane_id][-1][0]) > self.time_gap:
            self.bbox_container[plane_id].clear()

        if len(self.bbox_container[plane_id]) == self.window_size:
            bboxes = [bbox for frame, bbox in self.bbox_container[plane_id]]
            running_mean = self.compute_running_mean(bboxes)

            bboxes = [planes_dict[plane_id][1][frame] for frame, bbox in self.bbox_container[plane_id] if frame in planes_dict[plane_id][1]] + [running_mean]

            # Compute the standard deviation of the center coordinates
            centers = np.array([[(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2] for bbox in bboxes])
            std_dev = np.std(centers, axis=0)

            # Compute the movement of the bounding box center
            last_frame = self.bbox_container[plane_id][-2][0]
            prev_center = np.array([(planes_dict[plane_id][1][last_frame][0] + planes_dict[plane_id][1][last_frame][2]) / 2,
                                    (planes_dict[plane_id][1][last_frame][1] + planes_dict[plane_id][1][last_frame][3]) / 2])
            current_center = np.array([(running_mean[0] + running_mean[2]) / 2, (running_mean[1] + running_mean[3]) / 2])
            movement = np.linalg.norm(current_center - prev_center)

            # Set thresholds for standard deviation and movement
            std_threshold_x = 10.0
            std_threshold_y = 10.0
            std_threshold = [std_threshold_x, std_threshold_y]
            movement_threshold = 1

            # Prevent movement if the object is stopped
            if np.all([t1 > t2 for t1, t2 in zip(std_dev, std_threshold)]) and movement > movement_threshold:
                prev_xyxy = planes_dict[plane_id][1][last_frame]
                running_mean = [(p[0] + p[1]) / 2.0 for p in zip(prev_xyxy, running_mean)]
            return running_mean

        return xyxy

    def compute_running_mean(self, bboxes):
        return [sum(coord) / len(bboxes) for coord in zip(*bboxes)]


class PlanesView:
    """`planes_dict[id]` -> `(None, {frame: xyxy})` over NorfairPlaneTracker.planes (histories stay aliased)."""

    def __init__(self, planes: dict):
        self.planes = planes

    def __getitem__(self, plane_id):
        return (None, self.planes[plane_id].frames)

    def __contains__(self, plane_id):
        return plane_id in self.planes
