"""Drawing helpers for the vendored tracker classes (only used with save_video): `plot_one_box` verbatim from
cv_common/utils/plots.py @2759daf; `Color` replaces `norfair.Color` (BGR tuples) so norfair is not a dependency.
"""

import random

import cv2


class Color:
    grey = (128, 128, 128)
    black = (0, 0, 0)
    teal = (128, 128, 0)
    olive = (0, 128, 128)
    red = (0, 0, 255)
    green = (0, 255, 0)
    blue = (255, 0, 0)
    white = (255, 255, 255)


def plot_one_box(x, img, color=None, label=None, line_thickness=None):
    # Plots one bounding box on image img
    tl = line_thickness or max(round(0.001 * (img.shape[0] + img.shape[1]) / 2), 1)  # line/font thickness
    color = color or [random.randint(0, 255) for _ in range(3)]
    c1, c2 = (int(x[0]), int(x[1])), (int(x[2]), int(x[3]))
    cv2.rectangle(img, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)
    if label:
        tf = 1  # font thickness
        font_scale = tl / 4
        t_size = cv2.getTextSize(label, 0, fontScale=font_scale, thickness=tf)[0]
        c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3
        cv2.rectangle(img, c1, c2, color, -1, cv2.LINE_AA)  # filled
        cv2.putText(img, label, (c1[0], c1[1] - 2), 0, font_scale, [225, 255, 255], thickness=tf, lineType=cv2.LINE_AA)
