"""Vendored core of norfair 0.2.0 (Tracker / TrackedObject / Detection) — the version pinned by the production GM
(`no_deps_req.txt` @ a0157a4: `norfair==0.2.0`). Vendored verbatim (whitespace/imports aside) because the installed
norfair 2.x has a different API and different Kalman defaults, and the main-aircraft track ids / frame ranges (class-2
rows of the second-run file) depend on these exact semantics.

Copyright (c) 2020, Tryolabs — BSD-3-Clause license (see the norfair 0.2.0 distribution). Changes: `rich.print` → print,
`exit()` → ValueError, type hints unchanged.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np


def validate_points(points: np.ndarray) -> np.ndarray:
    if points.shape == (2,):
        points = points[np.newaxis, ...]
    elif len(points.shape) == 1:
        raise ValueError(f"detection points must be (N, 2) or (2,), got {points.shape}")
    else:
        if points.shape[1] != 2 or len(points.shape) > 2:
            raise ValueError(f"detection points must be (N, 2), got {points.shape}")
    return points


class Detection:
    def __init__(self, points: np.ndarray, scores=None, data=None):
        self.points = points
        self.scores = scores
        self.data = data


class Tracker:
    def __init__(
        self,
        distance_function: Callable[[Detection, TrackedObject], float],
        distance_threshold: float,
        hit_inertia_min: int = 10,
        hit_inertia_max: int = 25,
        initialization_delay: int | None = None,
        detection_threshold: float = 0,
        point_transience: int = 4,
    ):
        self.tracked_objects: Sequence[TrackedObject] = []
        self.distance_function = distance_function
        self.hit_inertia_min = hit_inertia_min
        self.hit_inertia_max = hit_inertia_max
        if initialization_delay is None:
            self.initialization_delay = int((self.hit_inertia_max - self.hit_inertia_min) / 2)
        elif initialization_delay < 0 or initialization_delay > self.hit_inertia_max - self.hit_inertia_min:
            raise ValueError(
                "Argument 'initialization_delay' for 'Tracker' class should be an int between 0 and "
                f"(hit_inertia_max - hit_inertia_min = {hit_inertia_max - hit_inertia_min}). "
                f"The selected value is {initialization_delay}."
            )
        else:
            self.initialization_delay = initialization_delay
        self.distance_threshold = distance_threshold
        self.detection_threshold = detection_threshold
        self.point_transience = point_transience
        TrackedObject.count = 0

    def update(self, detections: list[Detection] | None = None, period: int = 1):
        self.period = period
        self.tracked_objects = [o for o in self.tracked_objects if o.has_inertia]
        for obj in self.tracked_objects:
            obj.tracker_step()
        unmatched_detections = self.update_objects_in_place(
            [o for o in self.tracked_objects if not o.is_initializing], detections
        )
        unmatched_detections = self.update_objects_in_place(
            [o for o in self.tracked_objects if o.is_initializing], unmatched_detections
        )
        for detection in unmatched_detections:
            self.tracked_objects.append(self._new_object(detection))
        return [p for p in self.tracked_objects if not p.is_initializing]

    def _new_object(self, detection: Detection) -> TrackedObject:
        return TrackedObject(
            detection,
            self.hit_inertia_min,
            self.hit_inertia_max,
            self.initialization_delay,
            self.detection_threshold,
            self.period,
            self.point_transience,
        )

    def update_objects_in_place(self, objects: Sequence[TrackedObject], detections: list[Detection] | None):
        if detections is not None and len(detections) > 0:
            distance_matrix = np.ones((len(detections), len(objects)), dtype=np.float32)
            distance_matrix *= self.distance_threshold + 1
            for d, detection in enumerate(detections):
                for o, obj in enumerate(objects):
                    distance = self.distance_function(detection, obj)
                    if distance > self.distance_threshold:
                        distance_matrix[d, o] = self.distance_threshold + 1
                    else:
                        distance_matrix[d, o] = distance
            if np.isnan(distance_matrix).any():
                raise ValueError("Received nan values from distance function")
            if np.isinf(distance_matrix).any():
                raise ValueError("Received inf values from distance function")
            if distance_matrix.any():
                for i, minimum in enumerate(distance_matrix.min(axis=0)):
                    objects[i].current_min_distance = minimum if minimum < self.distance_threshold else None
            matched_det_indices, matched_obj_indices = self.match_dets_and_objs(distance_matrix)
            if len(matched_det_indices) > 0:
                unmatched_detections = [d for i, d in enumerate(detections) if i not in matched_det_indices]
                for match_det_idx, match_obj_idx in zip(matched_det_indices, matched_obj_indices):
                    match_distance = distance_matrix[match_det_idx, match_obj_idx]
                    matched_detection = detections[match_det_idx]
                    matched_object = objects[match_obj_idx]
                    if match_distance < self.distance_threshold:
                        matched_object.hit(matched_detection, period=self.period)
                        matched_object.last_distance = match_distance
                    else:
                        unmatched_detections.append(matched_detection)
            else:
                unmatched_detections = detections
        else:
            unmatched_detections = []
        return unmatched_detections

    def match_dets_and_objs(self, distance_matrix: np.ndarray):
        distance_matrix = distance_matrix.copy()
        if distance_matrix.size > 0:
            det_idxs = []
            obj_idxs = []
            current_min = distance_matrix.min()
            while current_min < self.distance_threshold:
                flattened_arg_min = distance_matrix.argmin()
                det_idx = flattened_arg_min // distance_matrix.shape[1]
                obj_idx = flattened_arg_min % distance_matrix.shape[1]
                det_idxs.append(det_idx)
                obj_idxs.append(obj_idx)
                distance_matrix[det_idx, :] = self.distance_threshold + 1
                distance_matrix[:, obj_idx] = self.distance_threshold + 1
                current_min = distance_matrix.min()
            return det_idxs, obj_idxs
        return [], []


class TrackedObject:
    count = 0
    initializing_count = 0

    def __init__(
        self,
        initial_detection: Detection,
        hit_inertia_min: int,
        hit_inertia_max: int,
        initialization_delay: int,
        detection_threshold: float,
        period: int,
        point_transience: int,
    ):
        self.num_points = validate_points(initial_detection.points).shape[0]
        self.hit_inertia_min: int = hit_inertia_min
        self.hit_inertia_max: int = hit_inertia_max
        self.initialization_delay = initialization_delay
        self.point_hit_inertia_min: int = math.floor(hit_inertia_min / point_transience)
        self.point_hit_inertia_max: int = math.ceil(hit_inertia_max / point_transience)
        if (self.point_hit_inertia_max - self.point_hit_inertia_min) < period:
            self.point_hit_inertia_max = self.point_hit_inertia_min + period
        self.detection_threshold: float = detection_threshold
        self.initial_period: int = period
        self.hit_counter: int = hit_inertia_min + period
        self.point_hit_counter: np.ndarray = np.ones(self.num_points) * self.point_hit_inertia_min
        self.last_distance: float | None = None
        self.current_min_distance: float | None = None
        self.last_detection: Detection = initial_detection
        self.age: int = 0
        self.is_initializing_flag: bool = True
        self.id: int | None = None
        self.initializing_id: int = TrackedObject.initializing_count
        TrackedObject.initializing_count += 1
        self.setup_filter(initial_detection.points)
        self.detected_at_least_once_points = np.array([False] * self.num_points)

    def setup_filter(self, initial_detection: np.ndarray):
        from filterpy.kalman import KalmanFilter  # lazy

        initial_detection = validate_points(initial_detection)
        dim_x = 2 * 2 * self.num_points
        dim_z = 2 * self.num_points
        self.dim_z = dim_z
        self.filter = KalmanFilter(dim_x=dim_x, dim_z=dim_z)
        self.filter.F = np.eye(dim_x)
        dt = 1
        for p in range(dim_z):
            self.filter.F[p, p + dim_z] = dt
        self.filter.H = np.eye(dim_z, dim_x)
        self.filter.R *= 4.0
        self.filter.Q[dim_z:, dim_z:] /= 10
        self.filter.x[:dim_z] = np.expand_dims(initial_detection.flatten(), 0).T
        self.filter.P[dim_z:, dim_z:] *= 10.0

    def tracker_step(self):
        self.hit_counter -= 1
        self.point_hit_counter -= 1
        self.age += 1
        self.filter.predict()

    @property
    def is_initializing(self):
        if self.is_initializing_flag and self.hit_counter > self.hit_inertia_min + self.initialization_delay:
            self.is_initializing_flag = False
            TrackedObject.count += 1
            self.id = TrackedObject.count
        return self.is_initializing_flag

    @property
    def has_inertia(self):
        return self.hit_counter >= self.hit_inertia_min

    @property
    def estimate(self):
        return self.filter.x.T.flatten()[: self.dim_z].reshape(-1, 2)

    @property
    def live_points(self):
        return self.point_hit_counter > self.point_hit_inertia_min

    def hit(self, detection: Detection, period: int = 1):
        points = validate_points(detection.points)
        self.last_detection = detection
        if self.hit_counter < self.hit_inertia_max:
            self.hit_counter += 2 * period
        if detection.scores is not None:
            assert len(detection.scores.shape) == 1
            points_over_threshold_mask = detection.scores > self.detection_threshold
            matched_sensors_mask = np.array([[m, m] for m in points_over_threshold_mask]).flatten()
            H_pos = np.diag(matched_sensors_mask).astype(float)
            self.point_hit_counter[points_over_threshold_mask] += 2 * period
        else:
            points_over_threshold_mask = np.array([True] * self.num_points)
            H_pos = np.identity(points.size)
            self.point_hit_counter += 2 * period
        self.point_hit_counter[self.point_hit_counter >= self.point_hit_inertia_max] = (
            self.point_hit_inertia_max
        )
        self.point_hit_counter[self.point_hit_counter < 0] = 0
        H_vel = np.zeros(H_pos.shape)
        H = np.hstack([H_pos, H_vel])
        self.filter.update(np.expand_dims(points.flatten(), 0).T, None, H)
        detected_at_least_once_mask = np.array([[m, m] for m in self.detected_at_least_once_points]).flatten()
        self.filter.x[self.dim_z :][np.logical_not(detected_at_least_once_mask)] = 0
        self.detected_at_least_once_points = np.logical_or(
            self.detected_at_least_once_points, points_over_threshold_mask
        )
