"""VENDORED verbatim from cv_trackers/local_utils/bl_utils.py @bd43c3c (import rewritten).""" 
from .common import bboxes_iou, bbox_area, is_overlap


def get_bl_type(bl_tracked_obj=None, beltloader_type={}, cone_camera=True, doors={'front': None, 'back': None}, engines=None, back_wheels=None, fps=8) -> str:
    """ Function to determine whether beltloader is near the airplane
        (if so, near front or back doors?), or somewhere away.
        Should be called, when beltloader is STOPPED.
    Args:
        :param bl_tracked_obj: tracked beltloader
        :param beltloader_type: dict with beltloader types that are already classified
        :param doors: dict with the biggest front and back doors
        :param engines: engines bboxes
        :param back_wheels: back wheels bboxes
    Returns:
        :return: str, beltloader type, one of "undefined", "front" or "back"
    """

    def check_door(bl_tracked_obj, cone_camera, doors={'front': None, 'back': None}):
        """ ----- First check -----
        Check if beltloader is near the front doors (bl_xyxy[2] > 0.6 * door width)
        or back doors (bl and back door are must be intersected)

        Args:
            :param bl_tracked_obj: tracked beltloader
            :param doors: dict with the biggest front and back doors
            :param cone_camera: bool, True if cone, False if wing 
        Returns:   
            :return: str, beltloader type, one of "undefined", "front" or "back"
        """
        bl_xyxy = bl_tracked_obj.xyxy
        bl_type_bbox = bl_tracked_obj.bl_type_bbox
        front_type_frames, back_type_frames = bl_tracked_obj.bl_type_frames['front'], bl_tracked_obj.bl_type_frames['back']
        front_door_xyxy, back_door_xyxy = doors['front'], doors['back']
        
        # check if beltloader is near the front doors
        if front_door_xyxy and is_overlap(bl_xyxy, front_door_xyxy):
            if bl_xyxy[2] > front_door_xyxy[0] + (front_door_xyxy[2] - front_door_xyxy[0]) * 0.6 or \
                    bl_xyxy[0] < front_door_xyxy[2] - (front_door_xyxy[2] - front_door_xyxy[0]) * 0.6:
                # there is a beltloader that defined as front already
                if beltloader_type['front'] is not None:
                    # check if beltloader is the same (if there are 2 detects of the same beltloader)
                    if bboxes_iou(bl_xyxy, beltloader_type['front']) > 0.8:
                        front_type_frames += 1
                    # if not, check if beltloader can be defined as back
                else:
                    front_type_frames += 1

        # if front door is closed check if beltloader is stopped at the same place
        elif bl_type_bbox and bboxes_iou(bl_xyxy, bl_type_bbox) > 0.8:
            front_type_frames += 1
        else:
            # skip beltloader counter if it is not near the front doors
            front_type_frames = 0

        bl_tracked_obj.bl_type_frames['front'] = front_type_frames

        if front_type_frames >= 1 * fps and back_type_frames == 0:
            return 'front'

        # check if beltloader is near the back doors
        if back_door_xyxy and is_overlap(bl_xyxy, back_door_xyxy):
            # there is a beltloader that defined as back already
            if beltloader_type['back'] is not None:
                # check if beltloader is the same (if there are 2 detects of the same beltloader)
                if bboxes_iou(bl_xyxy, beltloader_type['back']) > 0.8:
                    back_type_frames += 1
            else:
                back_type_frames += 1

        # if back door is closed check if beltloader is stopped at the same place
        elif bl_type_bbox and bboxes_iou(bl_xyxy, bl_type_bbox) > 0.8:
            back_type_frames += 1
        else:
            # skip beltloader counter if it is not near the back doors
            back_type_frames = 0

        bl_tracked_obj.bl_type_frames['back'] = back_type_frames
        
        if back_type_frames >= 1 * fps and (front_type_frames == 0 or not cone_camera):
            return 'back'

        return 'undefined'
    

    def check_wing_extra(bl_tracked_obj, back_wheels=None, engines=None):
        """ ----- Extra wing check -----
        Check if beltloader is behind the wheel and the engine, and its right side (and door) is obscured by engine

        Args:
            :param bl_tracked_obj: tracked beltloader
            :param back_wheels: back wheels bboxes
            :param engines: engines bboxes
        Returns:
            :return: str, beltloader type, one of "undefined", "front" or "back"
        """
        
        front_type_frames, back_type_frames = bl_tracked_obj.bl_type_frames['front'], bl_tracked_obj.bl_type_frames['back']

        if engines and back_wheels:
            biggest_engine = max(engines, key=lambda engine: bbox_area(engine))
            closest_back_wheel = min(back_wheels, key=lambda wheel: wheel[0])

            # check if beltloader is behind the wheel and the engine, and its right side (and door) is obscured by engine
            if (bl_tracked_obj.xyxy[3] < closest_back_wheel[3] and is_overlap(bl_tracked_obj.xyxy, biggest_engine)
                and bl_tracked_obj.xyxy[0] < biggest_engine[0] < bl_tracked_obj.xyxy[2]):
                back_type_frames += 1

        bl_tracked_obj.bl_type_frames['back'] = back_type_frames

        if back_type_frames >= 1 * fps:
            return 'back'
        
        return 'undefined'
    

    bl_type = 'undefined'

    # ignore if there is no beltloader bbox
    bl_xyxy = bl_tracked_obj.xyxy
    if bl_xyxy is None:
        return bl_type

    # excecute checks in order of priority
    bl_type = check_door(bl_tracked_obj, cone_camera, doors)
    if bl_type == 'undefined' and not cone_camera:
        bl_type = check_wing_extra(bl_tracked_obj, back_wheels, engines)

    # if beltloader type is defined, save it and its bbox
    if bl_type in beltloader_type.keys():
        beltloader_type[bl_type] = bl_xyxy
        bl_tracked_obj.bl_type_bbox = bl_xyxy

    return bl_type
