"""VENDORED verbatim from cv_common/tracked_object.py @2759daf (imports rewritten)."""
import numpy as np
import cv2
from ._draw import plot_one_box, Color
from .common import get_distance, check_bounding_box, bbox_area, getLargestCC, in_bbox, bboxes_iou, fix_incorrect_bbox
from enum import Enum, unique
from typing import Union


@unique
class Status(Enum):
    # moving statuses
    STOPPED = 'stopped'
    MOVING = 'moving'
    STOPPING = 'stopping'
    UNOBSERVED = 'unobserved'
    PROCEEDING = 'proceeding'


class ObjectState:
    def __init__(self, initial_status=Status.MOVING):
        self._status = initial_status
        self._color = Color.grey
        self._prev_status = None
        self._prev_color = None
        self._static_frames = 0
        self._moving_frames = 0
        self._is_stopped = False
        self._prev_stop_point = None
        self._stop_point = None
        self._stops_count = 0
        self._movement_anomaly = False
        self._normal_moving_frames = 0

    def set_unobserved(self):
        if self._status != Status.UNOBSERVED:
            self._prev_status = self._status
            self._prev_color = self._color
            self._status = Status.UNOBSERVED
            self._color = Color.black
            self._moving_frames = 0

    def set_observed(self):
        if self._status == Status.UNOBSERVED:
            self._status = self._prev_status
            self._color = self._prev_color
            self._prev_status = None
            self._prev_color = None

    def set_moving(self):
        if self._status is Status.PROCEEDING:
            # reset stops checking
            self._stops_count = 0
        self._status = Status.MOVING
        self._color = Color.grey
        self._is_stopped = False
        self._static_frames = 0
        self._moving_frames += 1
        if self._stop_point is not None:
            self._prev_stop_point = self._stop_point
            self._stop_point = None

    def set_stopping(self):
        self._status = Status.STOPPING
        self._color = Color.teal
        self._static_frames += 1
        self._is_stopped = False

    def set_stopped(self, center):
        self._status = Status.STOPPED
        self._color = Color.olive
        self._is_stopped = True
        self._moving_frames = 0
        self._stop_point = center

    def set_proceeding(self):
        self._status = Status.PROCEEDING
        self._color = Color.teal
        self._is_stopped = False
        if self._stop_point is not None:
            self._prev_stop_point = self._stop_point
            self._stop_point = None
        self._static_frames = 0

    @property
    def status(self):
        return self._status

    @property
    def is_stopped(self):
        return self._status == Status.STOPPED

    @property
    def stop_point(self):
        return self._stop_point


class FeatureTracker:
    _lk_params = dict(winSize=(20, 20),
                      maxLevel=5,
                      criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 16, 0.05))
    _max_num_keypoints = 250
    _OF_color = np.random.randint(0, 255, (_max_num_keypoints, 3))

    def __init__(self, init_dots_lifetime=8):
        self._p0 = None
        self._st = None
        self._of_dots_lifetime = 0
        self._init_dots_lifetime = init_dots_lifetime

    def find_new_features_OF(self, im0s, cur_gray, segmenter, predictor, xyxy, bboxes_to_remove=None, is_noised=False, frame_number=None, invoker=None, yolo_idx=None):
        alg  = cv2.FastFeatureDetector_create()

        mask_feat = segmenter.segment_object(im0s, predictor, xyxy, frame_number, invoker, yolo_idx)

        if bboxes_to_remove is not None:
            for xyxy in bboxes_to_remove:
                x1, y1, x2, y2 = map(int, xyxy)
                mask_feat[y1:y2, x1:x2] = 0

        if is_noised:
            cur_gray_processed = cv2.medianBlur(cv2.GaussianBlur(cur_gray, (5, 5), 0), 5)
            height, width = cur_gray_processed.shape[:2]
            top_height = int(height * 0.06)
            left_width = int(width * 0.36)
            cur_gray_processed[:top_height, :left_width] = 0
            keypoints = alg.detect(cur_gray_processed, mask=mask_feat)
        else:
            keypoints = alg.detect(cur_gray, mask=mask_feat)

        if len(keypoints) > self._max_num_keypoints:
            keypoints = np.random.choice(keypoints, self._max_num_keypoints)
            
        self._st = None
        self._of_dots_lifetime = self._init_dots_lifetime
        self._new_features = True

        return np.array([[kp.pt] for kp in keypoints], dtype=np.float32)

    def update_features(self, prev_gray, cur_gray, bboxes_to_remove=None):
        if bboxes_to_remove is not None:
            for xyxy in bboxes_to_remove:
                x1, y1, x2, y2 = map(int, xyxy)
                prev_gray[y1:y2, x1:x2] = 0
                cur_gray[y1:y2, x1:x2] = 0

        if self._p0 is None or len(self._p0) == 0:
            return None, None

        if self._new_features:
            p1, st, err = cv2.calcOpticalFlowPyrLK(cur_gray, prev_gray, self._p0, None, **self._lk_params)
        else:
            p1, st, err = cv2.calcOpticalFlowPyrLK(prev_gray, cur_gray, self._p0, None, **self._lk_params)  
        try:
            good_old = self._p0[st == 1]
            good_new = p1[st == 1]
        except (TypeError, IndexError) as e:
            print('Exc:', e)
            print(self._p0.shape)
            return None, None
        
        self._p0 = good_new.reshape(-1, 1, 2)
        if not self._new_features:
            self._st = st.reshape(-1)
        self._of_dots_lifetime -= 1
        self._new_features = False

        return good_old, good_new

    @property
    def p0(self):
        return self._p0


class ObjectSegmenter:
    Classwise_buffer_mask = {}
    
    def __init__(self, segm_points=None, model_type='mobile_sam'):
        self._mask = None
        self._segm_points = segm_points
        self._model_type = model_type

    def segment_object(self, image, predictor, xyxy, frame_number=None, invoker=None, yolo_idx=None):
        input_box = np.array(xyxy, dtype=np.int64)
        if self._model_type == 'mobile_sam':
            point_coords = np.array(self._segm_points) if self._segm_points is not None else None
            point_labels = np.ones(len(point_coords)) if point_coords is not None else None

            predictor.set_image(image)

            masks, scores, _ = predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                box=input_box[None, :],
                multimask_output=True,
            )

            mask = np.array(masks[np.argmax(scores), :, :], dtype=np.uint8)
            self._mask = getLargestCC(mask)
        elif self._model_type == 'yolo_seg':
            # Prevent redundant inference by caching results per invoker class and frame number
            key = invoker.__class__.__name__
            # print(f"Current key: {key}")
            conf = 0.01 if key == 'Vehicle' else 0.1
            if frame_number is not None and invoker is not None and hasattr(invoker, '__class__'):
                if key not in ObjectSegmenter.Classwise_buffer_mask:
                    ObjectSegmenter.Classwise_buffer_mask[key] = [None, None]
                if ObjectSegmenter.Classwise_buffer_mask[key][0] == frame_number:
                    results = ObjectSegmenter.Classwise_buffer_mask[key][1]
                else:
                    results = predictor(image, classes=yolo_idx, conf=conf)
                    ObjectSegmenter.Classwise_buffer_mask[key][1] = results
                    ObjectSegmenter.Classwise_buffer_mask[key][0] = frame_number
            else:
                results = predictor(image, classes=yolo_idx, conf=conf)
            
            # Find the mask whose bounding box has the highest IoU with input_box
            best_iou = -1
            best_mask = None
            if results[0].boxes is not None and results[0].masks is not None:
                for i, box in enumerate(results[0].boxes.xyxy.cpu().numpy()):
                    if (iou := bboxes_iou(input_box, box)) > best_iou:
                        best_iou = iou
                        best_mask = results[0].masks.data[i].cpu().numpy().astype(np.uint8)
            mask = best_mask if best_mask is not None else np.zeros(image.shape[:2], dtype=np.uint8)
            if mask.shape != image.shape[:2]:
                # Ultralytics masks may come back at the network stride size; resize to the frame resolution.
                mask = cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
            x1, y1, x2, y2 = input_box.astype(int)
            h, w = image.shape[:2]
            x1 = max(0, min(w, x1))
            x2 = max(0, min(w, x2))
            y1 = max(0, min(h, y1))
            y2 = max(0, min(h, y2))
            full_mask = np.zeros_like(mask, dtype=np.uint8)
            full_mask[y1:y2, x1:x2] = mask[y1:y2, x1:x2]
            self._mask = full_mask
        else:
            raise NotImplementedError(f"Model type '{self._model_type}' is not implemented for segmentation.")
        return self._mask

    @property
    def mask(self):
        return self._mask


class MovementAnalyzer:
    def __init__(self, static_points_thres=0.5, stopping_time_thres=3*8, moving_time_thres=8, proceeding_time_thres=2*8,
                 display_proceeding_time_thres=5, real_height=7, min_points_number=2, movement_anomaly_thres_x=50, movement_anomaly_thres_y=50):
        self._static_points_thres = static_points_thres
        self._stopping_time_thres = stopping_time_thres
        self._moving_time_thres = moving_time_thres
        self._proceeding_time_thres = proceeding_time_thres
        self._display_proceeding_time_thres = display_proceeding_time_thres
        self._real_height = real_height
        self._min_points_number = min_points_number
        self._movement_anomaly_thres_x = movement_anomaly_thres_x
        self._movement_anomaly_thres_y = movement_anomaly_thres_y

    def analyze_movement(self, prev_gray, cur_gray, good_old, good_new, state, xyxy, feature_tracker):
        if len(good_new) > 0:
            in_bbox_mask = np.array([in_bbox(point, xyxy) for point in good_new], dtype=bool)
            old_inliers = good_old[in_bbox_mask]
            new_inliers = good_new[in_bbox_mask]

            vectors = new_inliers - old_inliers
            median = np.median(vectors, axis=0)
            std_dev = np.std(vectors, axis=0)
            std_mask = np.abs(vectors - median) < 1 * std_dev
            std_mask = std_mask[:, 0] & std_mask[:, 1]
            old_inliers = old_inliers[std_mask]
            new_inliers = new_inliers[std_mask]
        else:
            old_inliers = good_old
            new_inliers = good_new
        
        if len(new_inliers) < self._min_points_number:
            return state
        
        tol = 0.002 * (xyxy[3] - xyxy[1]) / self._real_height
        tol = max(tol, 0.1)

        stopped_dots = np.count_nonzero(np.all(np.isclose(old_inliers, new_inliers, atol=tol), axis=1))
        stopping_flag = stopped_dots > self._static_points_thres * new_inliers.shape[0]
        
        # stopped_dots = np.count_nonzero(np.all(np.isclose(good_old, good_new, atol=0.1), axis=1))
        # stopping_flag = stopped_dots > self._static_points_thres * good_new.shape[0]
        
        x1, y1, x2, y2 = xyxy
        center = (x1 + x2) // 2, (y1 + y2) // 2
        _dist_between_stops = int((x2 - x1) * 0.05)

        if state.status in [Status.MOVING, Status.STOPPING]:
            if state.status == Status.MOVING:
                if state.stop_point is not None:
                    state._prev_stop_point = state.stop_point
                    state._stop_point = None
            
            if stopping_flag:
                state.set_stopping()
                state._moving_frames = 0
                if state.stop_point is None and (state._prev_stop_point is None or
                                                 get_distance(state._prev_stop_point, center) >
                                                 _dist_between_stops):
                    state._stop_point = center
                    state._stops_count += 1
                
                if state._static_frames >= self._stopping_time_thres:
                    state.set_stopped(center)
            else:
                if state.status == Status.STOPPING and state._moving_frames >= self._moving_time_thres:
                    state.set_moving()
                elif state.status == Status.STOPPING:
                    state.set_stopping()
                    state._moving_frames += 1
                else:
                    state.set_moving()
        elif state.status in [Status.STOPPED, Status.PROCEEDING]:
            if not stopping_flag:
                if state._moving_frames >= self._proceeding_time_thres:
                    state.set_moving()
                else:
                    state._moving_frames += 1
                    if state._moving_frames > self._display_proceeding_time_thres:
                        state.set_proceeding()
            else:
                if state._static_frames < self._stopping_time_thres:
                    state._static_frames += 1
                state.set_stopped(center)
        
        # check for abnormal fast movement
        if state.status in [Status.MOVING, Status.PROCEEDING]:
            mean_diff_x = np.mean(new_inliers[:, 0] - old_inliers[:, 0])
            mean_diff_y = np.mean(new_inliers[:, 1] - old_inliers[:, 1])
            state._movement_anomaly = (abs(mean_diff_x) > self._movement_anomaly_thres_x
                                        or abs(mean_diff_y) > self._movement_anomaly_thres_y)
        else:
            state._movement_anomaly = False
            
        if state.status in [Status.MOVING, Status.PROCEEDING] and not state._movement_anomaly:
            state._normal_moving_frames += 1
        else:
            state._normal_moving_frames = 0
        
        return state


class ParameterManager:
    def __init__(self, params):
        self._stopping_time_thres = params.get('stopping_time_thres', 3 * 8)
        self._static_points_thres = params.get('static_points_thres', 0.5)
        self._proceeding_time_thres = params.get('proceeding_time_thres', 2 * 8)
        self._display_proceeding_time_thres = params.get('display_proceeding_time_thres', 5)
        self._moving_time_thres = params.get('moving_time_thres', 8)
        self._init_dots_lifetime = params.get('init_dots_lifetime', 8)
        self._from_x = params.get('from_x', 0.2)
        self._to_x = params.get('to_x', 0.9)
        self._from_y = params.get('from_y', 0.25)
        self._to_y = params.get('to_y', 0.7)

    def prepare_coordinates(self, xyxy):
        x1, y1, x2, y2 = xyxy
        w, h = x2 - x1, y2 - y1
        y1, y2 = y1 + int(self._from_y * h), y1 + int(self._to_y * h)
        x1, x2 = x1 + int(self._from_x * w), x1 + int(self._to_x * w)

        return [x1, y1, x2, y2]


class BoxesQueue:
    def __init__(self, xyxy, fps=8):
        self._recent_bboxes = [xyxy]
        self._recent_bboxes_time = 10 * fps
        
    def update_recent_bboxes(self, xyxy):
        if len(self._recent_bboxes) >= self._recent_bboxes_time:
            self._recent_bboxes.pop(0)
        self._recent_bboxes.append(xyxy)

    @property
    def recent_biggest_bbox(self):
        return max(self._recent_bboxes, key=bbox_area)


class TrackedObject:
    def __init__(self, obj_id: int = None, class_name: str = None, xyxy: Union[list, tuple] = None, **tracking_params):
        self.__obj_id = obj_id
        self.__class_name = class_name
        self.__xyxy = xyxy
        self.__previous_xyxy = xyxy
        self.__init_xyxy = xyxy
        self.__state = ObjectState()
        self.__feature_tracker = FeatureTracker(tracking_params.get('init_dots_lifetime', 8))
        self.__segmenter = ObjectSegmenter(model_type = tracking_params.get('model_type', 'mobile_sam'))
        self.__bboxes_queue = BoxesQueue(xyxy)
        self.__movement_analyzer = MovementAnalyzer(
            static_points_thres=tracking_params.get('static_points_thres', 0.5),
            stopping_time_thres=tracking_params.get('stopping_time_thres', 3*8),
            moving_time_thres=tracking_params.get('moving_time_thres', 8),
            proceeding_time_thres=tracking_params.get('proceeding_time_thres', 2*8),
            display_proceeding_time_thres=tracking_params.get('display_proceeding_time_thres', 5),
            real_height=tracking_params.get('real_height', 7),
            min_points_number=tracking_params.get('min_points_number', 2),
            movement_anomaly_thres_x=tracking_params.get('movement_anomaly_thres_x', 50),
            movement_anomaly_thres_y=tracking_params.get('movement_anomaly_thres_y', 5)
        )
        self.__param_manager = ParameterManager(tracking_params)

    def _find_new_features_OF(self, im0s, cur_gray, predictor, bboxes_to_remove=None, is_noised=False, frame_number=None, invoker=None, yolo_idx=None):
        """Initialize new keypoints to track the status changes."""
        return self.__feature_tracker.find_new_features_OF(im0s, cur_gray, self.__segmenter, predictor, self.xyxy, bboxes_to_remove, is_noised, frame_number, invoker, yolo_idx)

    def _segment_object(self, image, predictor):
        """Apply MobileSAM model to the image by given bbox and coordinates."""
        return self.__segmenter.segment_object(image, predictor, self.xyxy)

    def _update_moving_status(self, prev_im0s, im0s, predictor, bboxes_to_remove=None, is_noised=False, frame_number=None, invoker=None, yolo_idx=None):
        """Calculates the object shift between two consecutive frames and
            assigns appropriate status to the movement nature."""
        if not self.__state._is_stopped:
            prev_gray = cv2.cvtColor(prev_im0s, cv2.COLOR_BGR2GRAY)
            cur_gray = cv2.cvtColor(im0s, cv2.COLOR_BGR2GRAY)

            area_shift = bbox_area(self.xyxy) / bbox_area(self.__previous_xyxy)
            if area_shift > 1.5 or area_shift < 0.66:
                return

            if self.__feature_tracker.p0 is None or self.__feature_tracker._of_dots_lifetime == 0 or len(self.__feature_tracker.p0) == 0:
                self.__feature_tracker._p0 = self._find_new_features_OF(im0s, cur_gray, predictor, bboxes_to_remove=bboxes_to_remove, is_noised=is_noised, frame_number=frame_number, invoker=invoker, yolo_idx=yolo_idx)

            good_old, good_new = self.__feature_tracker.update_features(prev_gray, cur_gray, bboxes_to_remove)
            if good_old is None or good_new is None:
                return

            self.__state = self.__movement_analyzer.analyze_movement(prev_gray, cur_gray, good_old, good_new, self.__state, self.xyxy, self.__feature_tracker)

    def update_params(self, xyxy, prev_im0s, im0s, predictor, bboxes_to_remove=None, is_noised=False, frame_number=None, invoker=None, yolo_idx=None):
        """Checks the correctness of the inserted bounding box and
            updates the moving status of the object."""
        if self.__state.status != Status.UNOBSERVED:
            if xyxy and not check_bounding_box(xyxy, prev_im0s.shape[:2]):
                xyxy = fix_incorrect_bbox(xyxy, prev_im0s.shape[:2])
                if not check_bounding_box(xyxy, prev_im0s.shape[:2]):
                    raise ValueError(f'Trying to set incorrect bounding box: {xyxy}')
            self.__previous_xyxy = self.xyxy
            self.xyxy = xyxy
            self.__bboxes_queue.update_recent_bboxes(self.xyxy)
            self.__state._is_stopped = None
            self._update_moving_status(prev_im0s, im0s, predictor, bboxes_to_remove, is_noised=is_noised, frame_number=frame_number, invoker=invoker, yolo_idx=yolo_idx)


    # ==================================== Setters ==================================== #
    def set_unobserved(self):
        self.__state.set_unobserved()

    def set_observed(self):
        self.__state.set_observed()

    # =================================== Properties ================================== #
    @property
    def status(self):
        return self.__state.status

    @property
    def is_stopped(self):
        return self.__state.is_stopped

    @property
    def stop_point(self):
        return self.__state.stop_point

    @property
    def center(self):
        x1, y1, x2, y2 = self.xyxy
        return (x1 + x2) // 2, (y1 + y2) // 2

    @property
    def _xyxy(self):
        return self.__xyxy

    @_xyxy.setter
    def _xyxy(self, xyxy):
            self.__xyxy = xyxy

    @property
    def xyxy(self):
        return self.__xyxy

    @xyxy.setter
    def xyxy(self, xyxy):
        if not xyxy:
            self.__xyxy = xyxy
        elif check_bounding_box(xyxy):
            self.__xyxy = xyxy
        else:
            raise ValueError(f'Trying to set incorrect bounding box: {xyxy}')
        
    @property
    def init_xyxy(self):
        return self.__init_xyxy

    @ property
    def recent_biggest_bbox(self):
        return self.__bboxes_queue.recent_biggest_bbox
    
    @property
    def class_name(self):
        return self.__class_name

    @property
    def obj_id(self):
        return self.__obj_id
    
    @property
    def _obj_id(self):
        return self.__obj_id
    
    @_obj_id.setter
    def _obj_id(self, obj_id):
        self.__obj_id = obj_id

    @property
    def _dist_between_stops(self) -> int:
        x1, y1, x2, y2 = self.xyxy
        return int((x2 - x1) * 0.05)

    @property
    def _static_frames(self):
        return self.__state._static_frames
    
    @property
    def _moving_frames(self):
        return self.__state._moving_frames
    
    @property
    def _p0(self):
        return self.__feature_tracker._p0
    
    @property
    def _st(self):
        return self.__feature_tracker._st

    @property
    def normal_moving_frames(self):
        return self.__state._normal_moving_frames
    

    # ==================================== Plotting =================================== #
    def draw_bbox(self, img_to_draw, label=None, color=None, line_thickness=2):
        draw_label = label if label else str(self)
        if self.__state.status == Status.STOPPING and not label:
            draw_label += ' [Stop {}]'.format(self.__state._stops_count)
        draw_color = color if color else self.__state._color
        plot_one_box(self.xyxy, img_to_draw, label=draw_label,
                    color=draw_color, line_thickness=line_thickness)

    def draw_OF_points(self, img_to_draw):
        if self.__feature_tracker.p0 is not None and len(self.__feature_tracker.p0):
            x, y, _, _ = self.xyxy 
            for i, pt in enumerate(self.__feature_tracker.p0):
                a, b = map(int, pt.ravel())
                cv2.circle(img_to_draw, (a, b), 3, FeatureTracker._OF_color[i].tolist(), -1)
        
    def draw_obj_mask(self, img_to_draw, color=None):
        if self.__segmenter.mask is not None:
            if color is None:
                color = (0, 255, 0)
            height, width, _ = img_to_draw.shape
            color_image = np.full((height, width, 3), color, dtype=np.uint8)
            fg = cv2.bitwise_or(color_image, color_image, mask=self.__segmenter.mask)
            mask = cv2.bitwise_not(self.__segmenter.mask)
            bk = cv2.bitwise_or(img_to_draw, img_to_draw, mask=mask)
            img_to_draw = cv2.bitwise_or(fg, bk)
        return img_to_draw

    # ================================= Magic methods ================================= #
    def __str__(self):
        return '{}[{}]: {}'.format(self.__class_name.capitalize(), self.__obj_id, self.__state.status)

    def __repr__(self):
        return '{}[{}]: {}'.format(self.__class_name.capitalize(), self.__obj_id, self.__state.status)

    # ============================== Save / load object =============================== #
    def to_state_dict(self) -> dict:
        """Save the inner values into dictionary format that could be used to store in JSON."""
        state_dict = {}
        
        state_dict['to_numpy'] = []
        state_dict['to_status'] = ['_status']

        # Save the TrackedObject instance attributes
        state_dict['_obj_id'] = self.__obj_id
        state_dict['_class_name'] = self.__class_name
        state_dict['_xyxy'] = self.__xyxy
        state_dict['_previous_xyxy'] = self.__previous_xyxy
        state_dict['_init_xyxy'] = self.__init_xyxy

        # Save the ObjectState instance attributes
        state_dict['_status'] = self.__state._status.value
        state_dict['_color'] = self.__state._color
        if self.__state._prev_status:
            state_dict['to_status'].append('_prev_status')
            state_dict['_prev_status'] = self.__state._prev_status.value
        else:
            state_dict['_prev_status'] = None
        state_dict['_prev_color'] = self.__state._prev_color
        state_dict['_static_frames'] = self.__state._static_frames
        state_dict['_moving_frames'] = self.__state._moving_frames
        state_dict['_is_stopped'] = self.__state._is_stopped
        state_dict['_prev_stop_point'] = self.__state._prev_stop_point
        state_dict['_stop_point'] = self.__state._stop_point
        state_dict['_stops_count'] = self.__state._stops_count

        # Save the FeatureTracker instance attributes
        if self.__feature_tracker._p0 is not None:
            state_dict['_p0'] = self.__feature_tracker._p0.tolist()
            state_dict['to_numpy'].append('_p0')
        else:
            state_dict['_p0'] = None 
            
        if self.__feature_tracker._st is not None:
            state_dict['_st'] = self.__feature_tracker._st.tolist()
            state_dict['to_numpy'].append('_st')
        else:
            state_dict['_st'] = None
            
        state_dict['_of_dots_lifetime'] = self.__feature_tracker._of_dots_lifetime
        state_dict['_init_dots_lifetime'] = self.__feature_tracker._init_dots_lifetime

        # Save the ObjectSegmenter instance attributes
        state_dict['_mask'] = None  # Exclude the mask to avoid storing it in the state dictionary
        state_dict['_segm_points'] = self.__segmenter._segm_points

        # Save the MovementAnalyzer instance attributes
        state_dict['_static_points_thres'] = self.__movement_analyzer._static_points_thres
        state_dict['_stopping_time_thres'] = self.__movement_analyzer._stopping_time_thres
        state_dict['_moving_time_thres'] = self.__movement_analyzer._moving_time_thres
        state_dict['_proceeding_time_thres'] = self.__movement_analyzer._proceeding_time_thres
        state_dict['_display_proceeding_time_thres'] = self.__movement_analyzer._display_proceeding_time_thres

        # Save the ParameterManager instance attributes
        state_dict['_from_x'] = self.__param_manager._from_x
        state_dict['_to_x'] = self.__param_manager._to_x
        state_dict['_from_y'] = self.__param_manager._from_y
        state_dict['_to_y'] = self.__param_manager._to_y

        return state_dict


    def from_state_dict(self, state_dict: dict):
        state_dict = state_dict.copy()

        """Update the inner values from the dictionary format that could be used to store in JSON."""
        for key in state_dict.get('to_numpy', []):
            state_dict[key] = np.array(state_dict[key])
        if 'to_numpy' in state_dict:
            state_dict.pop('to_numpy')

        for key in state_dict.get('to_status', []):
            state_dict[key] = Status(state_dict[key])
        if 'to_status' in state_dict:
            state_dict.pop('to_status')

        # Assign arguments to the ObjectState instance
        self.__state._status = state_dict.pop('_status', None)
        self.__state._color = state_dict.pop('_color', None)
        self.__state._prev_status = state_dict.pop('_prev_status', None)
        self.__state._prev_color = state_dict.pop('_prev_color', None)
        self.__state._static_frames = state_dict.pop('_static_frames', None)
        self.__state._moving_frames = state_dict.pop('_moving_frames', None)
        self.__state._is_stopped = state_dict.pop('_is_stopped', None)
        self.__state._prev_stop_point = state_dict.pop('_prev_stop_point', None)
        self.__state._stop_point = state_dict.pop('_stop_point', None)
        self.__state._stops_count = state_dict.pop('_stops_count', None)

        # Assign arguments to the FeatureTracker instance
        self.__feature_tracker._p0 = state_dict.pop('_p0', None)
        if self.__feature_tracker._p0 is not None:
            self.__feature_tracker._p0 = np.array(self.__feature_tracker._p0, dtype=np.float32)
        self.__feature_tracker._st = state_dict.pop('_st', None)
        if self.__feature_tracker._st is not None:
            self.__feature_tracker._st = np.array(self.__feature_tracker._st, dtype=bool)
        self.__feature_tracker._of_dots_lifetime = state_dict.pop('_of_dots_lifetime', None)
        self.__feature_tracker._init_dots_lifetime = state_dict.pop('_init_dots_lifetime', None)

        # Assign arguments to the ObjectSegmenter instance
        self.__segmenter._mask = state_dict.pop('_mask', None)
        self.__segmenter._segm_points = state_dict.pop('_segm_points', None)

        # Assign arguments to the MovementAnalyzer instance
        self.__movement_analyzer._static_points_thres = state_dict.pop('_static_points_thres', None)
        self.__movement_analyzer._stopping_time_thres = state_dict.pop('_stopping_time_thres', None)
        self.__movement_analyzer._moving_time_thres = state_dict.pop('_moving_time_thres', None)
        self.__movement_analyzer._proceeding_time_thres = state_dict.pop('_proceeding_time_thres', None)
        self.__movement_analyzer._display_proceeding_time_thres = state_dict.pop('_display_proceeding_time_thres', None)

        # Assign arguments to the ParameterManager instance
        self.__param_manager._from_x = state_dict.pop('_from_x', None)
        self.__param_manager._to_x = state_dict.pop('_to_x', None)
        self.__param_manager._from_y = state_dict.pop('_from_y', None)
        self.__param_manager._to_y = state_dict.pop('_to_y', None)

        # Update the TrackedObject instance with the remaining arguments
        self.__dict__.update({
            '_TrackedObject__obj_id': state_dict.pop('_obj_id', None),
            '_TrackedObject__class_name': state_dict.pop('_class_name', None),
            '_TrackedObject__xyxy': state_dict.pop('_xyxy', None),
            '_TrackedObject__previous_xyxy': state_dict.pop('_previous_xyxy', None),
            '_TrackedObject__init_xyxy': state_dict.pop('_init_xyxy', None)
        })

        state_dict.pop('_recent_bboxes', None)
        state_dict.pop('_recent_bboxes_time', None)
        state_dict.pop('arrival_frame', None)

        # Raise an exception if the state_dict is not empty after updating
        if state_dict:
            raise ValueError(f"Unexpected keys in state_dict: {list(state_dict.keys())}")

        return self


    # ============================ backward compatibility ============================
    @property
    def _from_x(self):
        return self.__param_manager._from_x

    @_from_x.setter
    def _from_x(self, value):
        self.__param_manager._from_x = value

    @property
    def _to_x(self):
        return self.__param_manager._to_x

    @_to_x.setter
    def _to_x(self, value):
        self.__param_manager._to_x = value

    @property
    def _from_y(self):
        return self.__param_manager._from_y

    @_from_y.setter
    def _from_y(self, value):
        self.__param_manager._from_y = value

    @property
    def _to_y(self):
        return self.__param_manager._to_y

    @_to_y.setter
    def _to_y(self, value):
        self.__param_manager._to_y = value

    @property
    def _stopping_time_thres(self):
        return self.__movement_analyzer._stopping_time_thres

    @_stopping_time_thres.setter
    def _stopping_time_thres(self, value):
        self.__movement_analyzer._stopping_time_thres = value

    @property
    def _static_points_thres(self):
        return self.__movement_analyzer._static_points_thres

    @_static_points_thres.setter
    def _static_points_thres(self, value):
        self.__movement_analyzer._static_points_thres = value

    @property
    def _proceeding_time_thres(self):
        return self.__movement_analyzer._proceeding_time_thres

    @_proceeding_time_thres.setter
    def _proceeding_time_thres(self, value):
        self.__movement_analyzer._proceeding_time_thres = value

    @property
    def _display_proceeding_time_thres(self):
        return self.__movement_analyzer._display_proceeding_time_thres

    @_display_proceeding_time_thres.setter
    def _display_proceeding_time_thres(self, value):
        self.__movement_analyzer._display_proceeding_time_thres = value

    @property
    def _moving_time_thres(self):
        return self.__movement_analyzer._moving_time_thres

    @_moving_time_thres.setter
    def _moving_time_thres(self, value):
        self.__movement_analyzer._moving_time_thres = value

    @property
    def _init_dots_lifetime(self):
        return self.__feature_tracker._init_dots_lifetime

    @_init_dots_lifetime.setter
    def _init_dots_lifetime(self, value):
        self.__feature_tracker._init_dots_lifetime = value

    @property
    def _p0(self):
        return self.__feature_tracker._p0

    @_p0.setter
    def _p0(self, value):
        self.__feature_tracker._p0 = value

    @property
    def _of_dots_lifetime(self):
        return self.__feature_tracker._of_dots_lifetime

    @_of_dots_lifetime.setter
    def _of_dots_lifetime(self, value):
        self.__feature_tracker._of_dots_lifetime = value

    @property
    def _status(self):
        return self.status

    @_status.setter
    def _status(self, value):
        self.__state._status = value   

    @property
    def _segm_points(self):
        return self.__segmenter._segm_points

    @_segm_points.setter
    def _segm_points(self, value):
        self.__segmenter._segm_points = value

    @property
    def stops_count(self):
        return self.__state._stops_count
    
    @property
    def _stops_count(self):
        return self.__state._stops_count


if __name__ == '__main__':
    params = dict(
    stopping_time_thres=58,
    moving_time_thres=28,
    from_x=0.1,
    to_x=0.9,
    from_y=0.5,
    to_y=0.9,
    )
    print(TrackedObject(0, 'Obj', (0, 0, 15, 15), **params))