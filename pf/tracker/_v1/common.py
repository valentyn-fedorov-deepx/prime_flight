"""Helper functions of cv_common/common.py @2759daf used by the tracker path — bodies verbatim (AST-extracted by
scripts/vendor_tracker_v1.py). Do not edit by hand.
"""

import numpy as np
from skimage.measure import label


def get_distance(point1, point2) -> float:
    """ Get Euclidean distance between dot1, dot2
    :param point1: (x1, y1)
    :param point2: (x2, y2)
    :return: Euclidean distance
    """
    try:
        x1, y1 = map(int, point1)
        x2, y2 = map(int, point2)
        return sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
    except (ValueError, TypeError):
        logging.exception('Exception during the call get_distance({}, {})'.format(point1, point2))
        return -1


def check_bounding_box(bbox, shape=None) -> bool:
    """Checks whether the entire bounding box is on the image plane and has non-zero area.

    Args:
        bbox (tuple): Tuple of (x1, y1, x2, y2) representing the bounding box coordinates.
        shape (tuple, optional): Tuple of (height, width) representing the shape of the image. Defaults to None.

    Returns:
        bool: True if the bounding box is on the image plane and has non-zero area, False otherwise.
    """
    if bbox_area(bbox) == 0:
        return False

    x1, y1, x2, y2 = bbox
    if any(map(lambda x: x < 0, bbox)):
        return False

    if x1 > x2 or y1 > y2:
        return False

    if shape:
        h, w = shape
        if x1 > w or x2 > w or y1 > h or y2 > h:
            return False

    return True


def fix_incorrect_bbox(bbox, shape) -> list:
    """
    Fixes the bounding box by ensuring that the coordinates are non-negative, ordered correctly, and within the image boundaries.
    Args:
        bbox (list): List of [x1, y1, x2, y2] representing the bounding box coordinates.
        shape (tuple): Tuple of (height, width) representing the shape of the image.
    Returns:
        list: A list of [x1, y1, x2, y2] representing the corrected bounding box coordinates.
    """
    x1, y1, x2, y2 = bbox
    x1, y1, x2, y2 = abs(x1), abs(y1), abs(x2), abs(y2)
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    h, w = shape
    x1, x2 = max(0, min(w, x1)), max(0, min(w, x2))
    y1, y2 = max(0, min(h, y1)), max(0, min(h, y2))
    return [x1, y1, x2, y2]


def bbox_area(bbox, is_xyxy=True) -> float:
    """ Get area of bounding box
    :param bbox: bounding box
    :param is_xyxy: if True - then bbox is in xyxy format, else - in xywh
    :return: area of bounding box
    """
    if is_xyxy:
        return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])  # (x2 - x1) * (y2 - y1)
    else:
        return bbox[2] * bbox[3]  # w * h


def getLargestCC(mask):
    """
    Selects the biggest connected component from the mask.

    Args:
        mask (numpy.ndarray): Binary mask.

    Returns:
        numpy.ndarray: Binary mask with only the largest connected component.
    """
    
    labels = label(mask)
    if labels.max() == 0:
        return np.zeros_like(mask)
    else:
        largestCC = labels == np.argmax(np.bincount(labels.flat)[1:])+1
        return np.array(largestCC, dtype=np.uint8)


def in_bbox(point, bbox) -> bool:
    """ Check if point is inside bbox
    :param point: represented as (c1, c2)
    :param bbox: represented as (x1, y1, x2, y2)
    :return: True of point inside, else - False
    """
    c1, c2 = point
    x1, y1, x2, y2 = bbox
    return x1 <= c1 <= x2 and y1 <= c2 <= y2


def bboxes_iou(xyxy1, xyxy2) -> float:
    """
    Calculate IoU for two bounding boxes
    :param xyxy1: array-like, contains (x1, y1, x2, y2)
    :param xyxy2: array-like, contains (x1, y1, x2, y2)
    :return: float, IoU(xyxy1, xyxy2)
    """
    x1_d, y1_d, x2_d, y2_d = xyxy1
    x1_e, y1_e, x2_e, y2_e = xyxy2

    # determine the coordinates of the intersection rectangle
    x_left = max(x1_d, x1_e)
    y_top = max(y1_d, y1_e)
    x_right = min(x2_d, x2_e)
    y_bottom = min(y2_d, y2_e)

    intersection_area = max(0, x_right - x_left + 1) * max(0, y_bottom - y_top + 1)

    bb1_area = (max(0, x2_d - x1_d) + 1) * (max(0, y2_d - y1_d) + 1)
    bb2_area = (max(0, x2_e - x1_e) + 1) * (max(0, y2_e - y1_e) + 1)

    # compute the intersection over union by taking the intersection
    # area and dividing it by the sum of prediction + ground-truth
    # areas - the intersection area
    iou = intersection_area / float(bb1_area + bb2_area - intersection_area)

    assert 0 <= iou <= 1, f'expected value in range [0, 1], got {iou}'  # double-check ourselves

    return iou


def get_relative_intersection(target_bbox, main_bbox):
    """
    Helper function to get relative intersection areas fraction.
    :param target_bbox: i.e. Airplane
    :param main_bbox: i.e. Beltloader
    :return: 'intersection area' / 'area of main bbox'
    """
    x1 = max(target_bbox[0], main_bbox[0])
    x2 = min(target_bbox[2], main_bbox[2])
    y1 = max(target_bbox[1], main_bbox[1])
    y2 = min(target_bbox[3], main_bbox[3])
    if x1 > x2 or y1 > y2:
        return 0
    intersection_area = (x2 - x1) * (y2 - y1)
    relative_fraction = intersection_area / (bbox_area(main_bbox) + 1)
    return relative_fraction


def bbox_rel(*xyxy):
    """Calculates the relative bounding box from absolute pixel values for DeepSORT.

    Args:
        *xyxy: A tuple of four float values representing the absolute pixel values of the bounding box.

    Returns:
        A tuple of four float values representing the relative bounding box coordinates (x_center, y_center, width, height).
    """
    bbox_left = min([float(xyxy[0]), float(xyxy[2])])
    bbox_top = min([float(xyxy[1]), float(xyxy[3])])
    bbox_w = abs(float(xyxy[0]) - float(xyxy[2]))
    bbox_h = abs(float(xyxy[1]) - float(xyxy[3]))
    x_c = (bbox_left + bbox_w / 2)
    y_c = (bbox_top + bbox_h / 2)
    w = bbox_w
    h = bbox_h
    return x_c, y_c, w, h


def get_center(bbox) -> 'tuple[int, int]':
    ''' Get center of bounding box'''
    x1, y1, x2, y2 = map(int, bbox)
    return (x1 + x2) // 2, (y1 + y2) // 2


def get_hw(bbox) -> 'tuple[int, int]':
    """ Get height and width of bounding box """
    x1, y1, x2, y2 = map(int, bbox)
    return y2 - y1, x2 - x1


def is_overlap(box1, box2, is_xyxy=True) -> bool:
    """ Check if two bboxes is overlapping """
    # Get the coordinates of bounding boxes
    if is_xyxy:  # x1, y1, x2, y2 = box1
        b1_x1, b1_y1, b1_x2, b1_y2 = box1[0], box1[1], box1[2], box1[3]
        b2_x1, b2_y1, b2_x2, b2_y2 = box2[0], box2[1], box2[2], box2[3]
    else:  # transform from xywh to xyxy
        b1_x1, b1_x2 = box1[0] - box1[2] / 2, box1[0] + box1[2] / 2
        b1_y1, b1_y2 = box1[1] - box1[3] / 2, box1[1] + box1[3] / 2
        b2_x1, b2_x2 = box2[0] - box2[2] / 2, box2[0] + box2[2] / 2
        b2_y1, b2_y2 = box2[1] - box2[3] / 2, box2[1] + box2[3] / 2

    # If one rectangle is on left side of other
    if b1_x1 >= b2_x2 or b2_x1 >= b1_x2:
        return False

    # If one rectangle is above other
    if b1_y1 >= b2_y2 or b2_y1 >= b1_y2:
        return False

    return True


def add_offset(bbox, offset_x, offset_y, img_width=1920, img_height=1080) -> 'tuple[int, ...]':
    """ Adds offset to bbox with respect to img size
    :param bbox: represented as (x1, y1, x2, y2)
    :param offset_x: if int - treated as absolute value, if float in range (0, 1) - as relative value
    :param offset_y: if int - treated as absolute value, if float in range (0, 1) - as relative value
    :param img_width: maximum width of the img
    :param img_height: maximum height of the img
    :return: tuple, bbox in xyxy format
    """

    x1, y1, x2, y2 = map(int, bbox)
    w, h = x2 - x1, y2 - y1
    if type(offset_x) is float and 0 <= offset_x <= 1:
        # treat as percentage
        x1 = max(int(x1 - offset_x * w), 0)
        x2 = min(int(x2 + offset_x * w), img_width)
    elif type(offset_x) is int and 0 <= offset_x < img_width:
        x1 = max(int(x1 - offset_x), 0)
        x2 = min(int(x2 + offset_x), img_width)
    else:
        raise TypeError('Incorrect offset_x value, got {}'.format(offset_x))

    if type(offset_y) is float and 0 < offset_y < 1:
        # treat as percentage
        y1 = max(int(y1 - offset_y * h), 0)
        y2 = min(int(y2 + offset_y * h), img_height)
    elif type(offset_y) is int and 0 <= offset_y < img_height:
        y1 = max(int(y1 - offset_y), 0)
        y2 = min(int(y2 + offset_y), img_height)
    else:
        raise TypeError('Incorrect offset_y value, got {}'.format(offset_y))

    return x1, y1, x2, y2


def xyxy_to_det_arr(xyxy) -> np.ndarray:
    """
    Helper function to convert detection bounding box into Detection format for norfair
    :param xyxy: array-like, contains (x1, y1, x2, y2)
    :return: np.ndarray, array([[x1, y1], [x2, y2]])
    """
    x1, y1, x2, y2 = xyxy
    return np.array([[x1, y1], [x2, y2]])
