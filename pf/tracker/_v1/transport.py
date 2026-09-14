"""VENDORED verbatim from cv_common/transport.py @2759daf (imports rewritten; config from .config)."""
from .tracked_object import TrackedObject, Status
from .common import get_relative_intersection
from .config import config
from ._draw import Color
import numpy as np



class Airplane(TrackedObject):
    """Class for Plane representation.
    
        The class is inherited from the TrackedObject class,
        with properties and methods that are often used to describe 
        airplane behaviour and determine the stage of the full-turn
        processing.

        Key params:
            - _moving_counter - tracks the number of frames with moving status.
            - _stopped_counter - tracks the number of frames with stopped status.
            - have_pre_arrival_stage - defines if there were a pre-arrival 
                stage on the video by Airplane movement behaviour.
            - have_arrival_stage - defines if there was arrival 
                stage on the video by Airplane movement behaviour.
        
        Key methods:
            - _update_stage_status - Function to update counters for Airplane statuses.
                Also, they used to determine stages of the full-turn.
            - _update_segm_points - Generates the list of 10 points from the center
                of the most suitable airplane nose bbox.
            - update_inner_state, update_params - default TrackedObject behaiviour,
                but with the additional call of the _update_stage_status.
        
        Key properties:
            - arrived, departured - returns bool if the Plane has arrived or
                departured respectively.
    """
    _departure_thresh = 10 * config['fps']
    _movement_before_arrival = 3 * config['fps']
    _arrival_thresh = 4 * config['fps']
    _minimal_pre_arrival_time = 60 * config['fps']

    def __init__(self, obj_id=None, class_name='Airplane', xyxy=None, tracking_params=None, height_mode=None):
        if tracking_params is None:
            tracking_params = {}
        tracking_params['model_type'] = 'yolo_seg'
        super(Airplane, self).__init__(obj_id=obj_id, class_name=class_name, xyxy=xyxy, **tracking_params)
        
        self._moving_counter = 0
        self._stopped_counter = 0

        self.have_pre_arrival_stage = False
        self.have_arrival_stage = False
        self.arrival_frame = None
        self.departure_frame = None

        self._height_mode = height_mode
    
    def _update_segm_points(self, nose_list):
        """Generates the list of 10 points from the center
          of the most suitable airplane nose bbox."""
        if not len(nose_list):
            self._segm_points = None
            return

        # select the most appropriate airplane nose out of the list
        nose = max(nose_list, key=lambda xyxy: get_relative_intersection(self.xyxy, xyxy))
        
        if get_relative_intersection(self.xyxy, nose) <= 0.5:
            self._segm_points = None

        else:
            # get the central part of it for the segmentation
            x1, y1, x2, y2 = nose
            w, h = x2 - x1, y2 - y1
            y1, y2 = y1 + int(self._from_y * h), y1 + int(self._to_y * h)
            x1, x2 = x1 + int(self._from_x * w), x1 + int(self._to_x * w)
            
            # select 10 random points and update segm_points
            self._segm_points = [(np.random.randint(x1, x2), np.random.randint(y1, y2)) for _ in range(10)]

    def _update_stage_status(self, frame_id):
        '''
        Function to update counters for Airplane statuses.
        Also, they used to determine stages of the full-turn.
        '''
        # arrival stage
        if self.arrival_frame is None:
            self._moving_counter += 1 if self._status == Status.MOVING else 0
            self._stopped_counter = self._stopped_counter + 1 if self._status == Status.STOPPED else 0
            if self._stopped_counter > self._arrival_thresh and self.arrival_frame is None and \
                (self._height_mode is None or (self.xyxy[3] - self.xyxy[1] > 0.95 * self._height_mode)):
                self.arrival_frame = frame_id
                self._moving_counter = 0

                self.have_pre_arrival_stage = self.arrival_frame >= self._minimal_pre_arrival_time
            
            if self.normal_moving_frames > self._movement_before_arrival:
                self.have_arrival_stage = True
                
        # departure determining
        else:
            self._moving_counter = min(self._moving_counter + 1, self._departure_thresh) \
                if self._status == Status.MOVING else max(self._moving_counter - 10, 0)

            if self.departure_frame is None and self._moving_counter==self._departure_thresh:
                self.departure_frame = frame_id
        
        print(f"Stopped counter: {self._stopped_counter} \nMoving counter: {self._moving_counter}")

    def update_inner_state(self, state_dict: dict):
        self.from_state_dict(state_dict)
    
    def update_params(self, xyxy, prev_im0s, im0s, frame_id, predictor, nose_list, bboxes_to_remove=None, is_noised=False, invoker=None):
        self._update_segm_points(nose_list)
        super().update_params(xyxy, prev_im0s, im0s, predictor, bboxes_to_remove, is_noised=is_noised, frame_number=frame_id, invoker=self)
        self._update_stage_status(frame_id)
        
    def to_state_dict(self) -> dict:
        state_dict = super().to_state_dict()
        
        state_dict['_moving_counter'] = self._moving_counter
        state_dict['_stopped_counter'] = self._stopped_counter

        state_dict['have_pre_arrival_stage'] = self.have_pre_arrival_stage
        state_dict['have_arrival_stage'] = self.have_arrival_stage
        state_dict['arrival_frame'] = self.arrival_frame
        state_dict['departure_frame'] = self.departure_frame

        state_dict['_height_mode'] = self._height_mode
        return state_dict

    def from_state_dict(self, state_dict: dict):
        state_dict = state_dict.copy()
        
        self._moving_counter = state_dict.pop('_moving_counter', None)
        self._stopped_counter = state_dict.pop('_stopped_counter', None)

        self.have_pre_arrival_stage = state_dict.pop('have_pre_arrival_stage', None)
        self.have_arrival_stage = state_dict.pop('have_arrival_stage', None)
        self.arrival_frame = state_dict.pop('arrival_frame', None)
        self.departure_frame = state_dict.pop('departure_frame', None)

        self._height_mode = state_dict.pop('_height_mode', None)

        super().from_state_dict(state_dict)
        
        return self
    
    @property
    def departured(self):
        return True if self.departure_frame is not None else False
    
    @property
    def arrived(self):
        return self.arrival_frame is not None
    

class Vehicle(TrackedObject):
    """Class for Vehicles representation.
    
        The class is inherited from the TrackeObject class to 
        represent the Vehicle behaiviour. 

        Key difference:
            - each class objected is initialized with the Stopped 
                Status to suit the assumption that all transport 
                is static once it appears on the frame.

    """
    def __init__(self, obj_id, class_name, xyxy, tracking_params=None):
        if tracking_params is None:
            tracking_params = {}
        tracking_params['model_type'] = 'yolo_seg'
        super(Vehicle, self).__init__(obj_id, class_name, xyxy, **tracking_params)
        self._status = Status.STOPPED
        self._color = Color.olive
        
        # parameters for the beltloader type definition
        self._bl_type_frames = {'front': 0, 'back': 0}
        self._bl_type_bbox = None
    
    @property
    def bl_type_frames(self):
        return self._bl_type_frames
    
    @bl_type_frames.setter
    def bl_type_frames(self, bl_type_frames):
        self._bl_type_frames = bl_type_frames

    @property
    def bl_type_bbox(self):
        return self._bl_type_bbox
    
    @bl_type_bbox.setter
    def bl_type_bbox(self, bl_type_bbox):
        self._bl_type_bbox = bl_type_bbox
    
    def update_params(self, xyxy, prev_im0s, im0s, frame_id, predictor, bboxes_to_remove=None, is_noised=False, yolo_idx=None):
        super().update_params(xyxy, prev_im0s, im0s, predictor, bboxes_to_remove, is_noised=is_noised, frame_number=frame_id, invoker=self, yolo_idx=yolo_idx)
    
    def to_state_dict(self) -> dict:
        state_dict = super().to_state_dict()
        
        state_dict['_bl_type_bbox'] = self._bl_type_bbox
        state_dict['_bl_type_frames'] = self._bl_type_frames
        
        return state_dict

    def from_state_dict(self, state_dict: dict):
        state_dict = state_dict.copy()

        self._bl_type_bbox = state_dict.pop('_bl_type_bbox', None)
        self._bl_type_frames = state_dict.pop('_bl_type_frames', None)

        super().from_state_dict(state_dict)
        
        return self