"""Vendor the production tracker's dependencies into `pf/tracker/_v1/` (pinned copies, import paths rewritten).

Sources (read-only clones/worktrees under external/):
  cv_common         @ 2759daf (branch tracker_optimization — the revision whose `Vehicle.update_params` matches the
                    production tracker bd43c3c; the exact commit of the production image is an open question)
  cv_trackers_prod  @ bd43c3c (branch optimization): local_config.yaml, local_utils/bl_utils.py, deep_sort_pytorch/

What is copied verbatim: tracked_object.py, transport.py, track.py, bl_utils.py, deep_sort_pytorch (runtime subset),
global/local YAML configs; `common.py` is reduced to the helper functions the tracker path uses (AST-extracted, bodies
unchanged); drawing helpers (`plot_one_box`, norfair `Color`) are replaced by a tiny local module since they only serve
`--save-video`. Re-run after bumping a pin; the diff of `pf/tracker/_v1` must stay reviewable.

    python scripts/vendor_tracker_v1.py
"""

from __future__ import annotations

import ast
import io
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CVC = os.path.join(ROOT, "external", "cv_trackers_prod", "cv_common")  # cv_common @2759daf (archive)
TRK = os.path.join(ROOT, "external", "cv_trackers_prod")
DST = os.path.join(ROOT, "pf", "tracker", "_v1")

COMMON_FUNCS = [
    "get_distance", "check_bounding_box", "fix_incorrect_bbox", "bbox_area", "getLargestCC", "in_bbox",
    "bboxes_iou", "get_relative_intersection", "bbox_rel", "get_center", "get_hw", "is_overlap", "add_offset",
    "xyxy_to_det_arr",
]


def read(p: str) -> str:
    return io.open(p, encoding="utf-8").read().replace("\r\n", "\n")


def write(p: str, s: str) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


def extract_functions(src: str, names: list) -> str:
    tree = ast.parse(src)
    lines = src.split("\n")
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            start = node.lineno - 1
            if node.decorator_list:
                start = node.decorator_list[0].lineno - 1
            found[node.name] = "\n".join(lines[start : node.end_lineno])
    missing = [n for n in names if n not in found]
    if missing:
        raise SystemExit(f"functions not found in common.py: {missing}")
    return "\n\n\n".join(found[n] for n in names)


def main() -> int:
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    os.makedirs(DST)

    # --- common.py (helpers only) -------------------------------------------------------------------
    common_src = read(os.path.join(CVC, "common.py"))
    funcs = extract_functions(common_src, COMMON_FUNCS)
    write(
        os.path.join(DST, "common.py"),
        '"""Helper functions of cv_common/common.py @2759daf used by the tracker path — bodies verbatim (AST-extracted by\n'
        'scripts/vendor_tracker_v1.py). Do not edit by hand.\n"""\n\n'
        "import numpy as np\nfrom skimage.measure import label\n\n\n" + funcs + "\n",
    )

    # --- drawing stand-ins ----------------------------------------------------------------------------
    plots_src = read(os.path.join(CVC, "utils", "plots.py"))
    plot_one_box = extract_functions(plots_src, ["plot_one_box"])
    write(
        os.path.join(DST, "_draw.py"),
        '"""Drawing helpers for the vendored tracker classes (only used with save_video): `plot_one_box` verbatim from\n'
        'cv_common/utils/plots.py @2759daf; `Color` replaces `norfair.Color` (BGR tuples) so norfair is not a dependency.\n"""\n\n'
        "import random\n\nimport cv2\n\n\nclass Color:\n    grey = (128, 128, 128)\n    black = (0, 0, 0)\n"
        "    teal = (128, 128, 0)\n    olive = (0, 128, 128)\n    red = (0, 0, 255)\n    green = (0, 255, 0)\n"
        "    blue = (255, 0, 0)\n    white = (255, 255, 255)\n\n\n" + plot_one_box + "\n",
    )

    # --- tracked_object.py / transport.py / track.py / bl_utils.py -----------------------------------
    to = read(os.path.join(CVC, "tracked_object.py"))
    to = to.replace("from utils.plots import plot_one_box\n", "from ._draw import plot_one_box, Color\n")
    to = to.replace("from norfair import Color\n", "")
    to = re.sub(r"^from common import ", "from .common import ", to, flags=re.M)
    assert "from .common import" in to and "from ._draw import" in to
    write(os.path.join(DST, "tracked_object.py"), '"""VENDORED verbatim from cv_common/tracked_object.py @2759daf (imports rewritten).""" \n' + to)

    tr = read(os.path.join(CVC, "transport.py"))
    tr = tr.replace("from cv_common.tracked_object import TrackedObject, Status\n", "from .tracked_object import TrackedObject, Status\n")
    tr = tr.replace("from cv_common.common import parse_config, get_relative_intersection\n", "from .common import get_relative_intersection\nfrom .config import config\n")
    tr = tr.replace("from norfair import Color\n", "from ._draw import Color\n")
    tr = re.sub(r"^config = parse_config\(\)\n", "", tr, flags=re.M)
    assert "parse_config" not in tr
    write(os.path.join(DST, "transport.py"), '"""VENDORED verbatim from cv_common/transport.py @2759daf (imports rewritten; config from .config).""" \n' + tr)

    write(os.path.join(DST, "track.py"), '"""VENDORED verbatim from cv_common/track.py @2759daf.""" \n' + read(os.path.join(CVC, "track.py")))

    bl = read(os.path.join(TRK, "local_utils", "bl_utils.py"))
    bl = bl.replace("from cv_common.common import (bboxes_iou, bbox_area, is_overlap)", "from .common import bboxes_iou, bbox_area, is_overlap")
    assert "from .common import" in bl
    write(os.path.join(DST, "bl_utils.py"), '"""VENDORED verbatim from cv_trackers/local_utils/bl_utils.py @bd43c3c (import rewritten).""" \n' + bl)

    # --- configs ----------------------------------------------------------------------------------------
    os.makedirs(os.path.join(DST, "config"), exist_ok=True)
    shutil.copy(os.path.join(CVC, "global_config.yaml"), os.path.join(DST, "config", "global_config.yaml"))
    shutil.copy(os.path.join(TRK, "local_config.yaml"), os.path.join(DST, "config", "local_config.yaml"))
    shutil.copy(os.path.join(TRK, "deep_sort_pytorch", "configs", "deep_sort.yaml"), os.path.join(DST, "config", "deep_sort.yaml"))
    write(
        os.path.join(DST, "config.py"),
        '"""Configuration of the vendored tracker: cv_common global_config.yaml @2759daf updated by the production tracker\'s\n'
        'local_config.yaml @bd43c3c — the same merge as `cv_common.common.parse_config` (top-level keys of the local file\n'
        'replace the global ones), loaded from the vendored copies instead of the current working directory.\n"""\n\n'
        "import os\n\nimport yaml\n\n_HERE = os.path.dirname(os.path.abspath(__file__))\n\n\n"
        "def load_config() -> dict:\n"
        "    with open(os.path.join(_HERE, 'config', 'global_config.yaml'), encoding='utf-8') as fh:\n"
        "        cfg = yaml.load(fh, Loader=yaml.FullLoader)\n"
        "    with open(os.path.join(_HERE, 'config', 'local_config.yaml'), encoding='utf-8') as fh:\n"
        "        cfg.update(yaml.load(fh, Loader=yaml.FullLoader))\n"
        "    return cfg\n\n\n"
        "def deep_sort_config():\n"
        "    from .deep_sort_pytorch.utils.parser import get_config\n\n"
        "    cfg = get_config()\n"
        "    cfg.merge_from_file(os.path.join(_HERE, 'config', 'deep_sort.yaml'))\n"
        "    return cfg\n\n\nconfig = load_config()\n",
    )

    # --- deep_sort_pytorch runtime subset ------------------------------------------------------------
    src = os.path.join(TRK, "deep_sort_pytorch")
    dst = os.path.join(DST, "deep_sort_pytorch")
    keep = [
        "__init__.py", "LICENSE",
        "deep_sort/__init__.py", "deep_sort/deep_sort.py",
        "deep_sort/deep/__init__.py", "deep_sort/deep/feature_extractor.py", "deep_sort/deep/model.py",
        "deep_sort/sort/__init__.py", "deep_sort/sort/detection.py", "deep_sort/sort/iou_matching.py",
        "deep_sort/sort/kalman_filter.py", "deep_sort/sort/linear_assignment.py", "deep_sort/sort/nn_matching.py",
        "deep_sort/sort/preprocessing.py", "deep_sort/sort/track.py", "deep_sort/sort/tracker.py",
        "utils/__init__.py", "utils/parser.py",
    ]
    for rel in keep:
        s, d = os.path.join(src, rel), os.path.join(dst, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy(s, d)
    # deep_sort/__init__.py imports "from .deep_sort import DeepSort" (relative) — nothing to rewrite.

    write(
        os.path.join(DST, "__init__.py"),
        '"""Pinned, import-rewritten copies of the production tracker\'s dependencies (see VENDORED.md). Generated by\n'
        'scripts/vendor_tracker_v1.py — edit the generator or the pins, not these files, except for the marked\n'
        'performance patches listed in VENDORED.md.\n"""\n',
    )
    write(
        os.path.join(DST, "VENDORED.md"),
        "# Vendored tracker dependencies\n\n"
        "| file | source | revision | change |\n|---|---|---|---|\n"
        "| `tracked_object.py` | cv_common/tracked_object.py | 2759daf (tracker_optimization) | imports rewritten |\n"
        "| `transport.py` | cv_common/transport.py | 2759daf | imports rewritten, `config` from `.config` |\n"
        "| `track.py` | cv_common/track.py | 2759daf | none |\n"
        "| `common.py` | cv_common/common.py | 2759daf | helper functions only (AST-extracted, bodies verbatim) |\n"
        "| `_draw.py` | cv_common/utils/plots.py + norfair.Color | 2759daf | `plot_one_box` verbatim; `Color` stub |\n"
        "| `bl_utils.py` | cv_trackers/local_utils/bl_utils.py | bd43c3c (optimization) | import rewritten |\n"
        "| `config/global_config.yaml` | cv_common/global_config.yaml | 2759daf | none |\n"
        "| `config/local_config.yaml` | cv_trackers/local_config.yaml | bd43c3c | none |\n"
        "| `config/deep_sort.yaml` | cv_trackers/deep_sort_pytorch/configs/deep_sort.yaml | bd43c3c | none |\n"
        "| `deep_sort_pytorch/` | cv_trackers/deep_sort_pytorch (runtime subset: deep_sort/, utils/parser.py) | bd43c3c | none (MIT, LICENSE kept) |\n\n"
        "Performance patches applied on top (each one must keep the outputs identical and is listed here):\n\n"
        "- (none yet)\n",
    )
    print("vendored into", DST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
