"""Vendor the production tracker's dependencies into `pf/tracker/_v1/` (pinned copies, import paths rewritten).

Sources (read-only clones/worktrees under external/):
  cv_common         @ 2759daf (branch tracker_optimization — the revision whose `Vehicle.update_params` matches the
                    production tracker bd43c3c; the exact commit of the production image is an open question)
  cv_trackers_prod  @ bd43c3c (branch optimization): local_config.yaml, local_utils/bl_utils.py, deep_sort_pytorch/

What is copied verbatim: tracked_object.py, transport.py, track.py, bl_utils.py, deep_sort_pytorch (runtime subset),
global/local YAML configs. `common.py` is reduced to the helper functions the tracker path uses: each function body is
verbatim, together with the transitive closure of what it references in the source module (other functions, top-level
constants, and the import statements — including imports nested in module-level try/if blocks — that bind the names it
uses). A name that cannot be resolved aborts the run unless it is listed in `extra_imports` for that file (reported on
stdout). The first version of this script copied bodies without their imports and `get_distance` lost
`from math import sqrt` — caught by the seeded parity run.

The output is built in a temporary directory and swapped in only when everything succeeded, so a failed run never leaves a
half-generated package behind.

    python scripts/vendor_tracker_v1.py
"""

from __future__ import annotations

import ast
import builtins
import io
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CVC = os.path.join(ROOT, "external", "cv_trackers_prod", "cv_common")  # cv_common @2759daf (archive)
TRK = os.path.join(ROOT, "external", "cv_trackers_prod")
DST = os.path.join(ROOT, "pf", "tracker", "_v1")
TMP = DST + "_tmp"

COMMON_FUNCS = [
    "get_distance", "check_bounding_box", "fix_incorrect_bbox", "bbox_area", "getLargestCC", "in_bbox",
    "bboxes_iou", "get_relative_intersection", "bbox_rel", "get_center", "get_hw", "is_overlap", "add_offset",
]
BUILTIN_NAMES = set(dir(builtins))


def read(p: str) -> str:
    return io.open(p, encoding="utf-8").read().replace("\r\n", "\n")


def write(p: str, s: str) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


def _bound_names(node: ast.AST) -> set:
    """Names bound anywhere inside `node` (assignments, loop/with/except targets, nested defs, args, local imports)."""
    bound = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            bound.add(n.id)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not node:
            bound.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
    return bound


def _free_names(node: ast.AST) -> set:
    used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return used - _bound_names(node) - BUILTIN_NAMES


def _module_level_statements(body: list):
    """Module-level statements, descending into top-level try/if blocks (not into functions or classes)."""
    for n in body:
        yield n
        if isinstance(n, ast.Try):
            for block in (n.body, n.orelse, n.finalbody, *[h.body for h in n.handlers]):
                yield from _module_level_statements(block)
        elif isinstance(n, ast.If):
            yield from _module_level_statements(n.body)
            yield from _module_level_statements(n.orelse)


def extract_with_dependencies(src: str, names: list, what: str, extra_imports: dict | None = None) -> tuple:
    """Return (imports_text, definitions_text) for `names` plus everything they need from the same module."""
    extra_imports = extra_imports or {}
    tree = ast.parse(src)
    lines = src.split("\n")

    def text(n):
        start = (n.decorator_list[0].lineno if getattr(n, "decorator_list", None) else n.lineno) - 1
        return textwrap_dedent("\n".join(lines[start : n.end_lineno]))

    functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    constants = {}
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    constants[t.id] = n
    imports = []
    for n in _module_level_statements(tree.body):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            imports.append(({(a.asname or a.name).split(".")[0] for a in n.names}, n))

    chosen, chosen_imports, added, queue = {}, [], [], list(names)
    while queue:
        name = queue.pop(0)
        if name in chosen:
            continue
        if name in functions:
            node = functions[name]
        elif name in constants:
            node = constants[name]
        else:
            raise SystemExit(f"{what}: '{name}' is not a top-level function/class/constant")
        chosen[name] = node
        free = _free_names(node.value) if isinstance(node, ast.Assign) else _free_names(node)
        for f in sorted(free):
            if f in functions or f in constants:
                queue.append(f)
                continue
            providers = [imp for bound, imp in imports if f in bound]
            if providers:
                for imp in providers:
                    if imp not in chosen_imports:
                        chosen_imports.append(imp)
            elif f in extra_imports:
                if extra_imports[f] not in added:
                    added.append(extra_imports[f])
            else:
                raise SystemExit(f"{what}: unresolved name '{f}' used by '{name}'")
    if added:
        print(f"{what}: names not bound in the source module, import added by the vendoring script: {added}")
    imports_text = "\n".join([text(n) for n in sorted(chosen_imports, key=lambda n: n.lineno)] + added)
    defs_text = "\n\n\n".join(text(n) for n in sorted(chosen.values(), key=lambda n: n.lineno))
    return imports_text, defs_text


def textwrap_dedent(s: str) -> str:
    import textwrap

    return textwrap.dedent(s)


def main() -> int:
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)

    # --- common.py (helpers + their dependency closure) --------------------------------------------------
    imports_text, defs_text = extract_with_dependencies(read(os.path.join(CVC, "common.py")), COMMON_FUNCS, "common.py")
    write(
        os.path.join(TMP, "common.py"),
        '"""Helper functions of cv_common/common.py @2759daf used by the tracker path, with the imports/constants they\n'
        "reference — bodies verbatim (AST-extracted by scripts/vendor_tracker_v1.py). Do not edit by hand.\n"
        '"""\n\n' + imports_text + "\n\n\n" + defs_text + "\n",
    )

    # --- drawing helpers ------------------------------------------------------------------------------
    # plot_one_box draws a random colour when none is given; the source module does not bind `random` at module level,
    # so the import is added explicitly (drawing is only used with save_video, never on the tracking path).
    p_imports, p_defs = extract_with_dependencies(
        read(os.path.join(CVC, "utils", "plots.py")), ["plot_one_box"], "plots.py", extra_imports={"random": "import random"}
    )
    write(
        os.path.join(TMP, "_draw.py"),
        '"""Drawing helpers for the vendored tracker classes (only used with save_video): `plot_one_box` verbatim from\n'
        "cv_common/utils/plots.py @2759daf with its imports; `Color` replaces `norfair.Color` (same BGR values) so norfair\n"
        'is not a dependency.\n"""\n\n' + p_imports + "\n\n\nclass Color:\n    grey = (128, 128, 128)\n    black = (0, 0, 0)\n"
        "    teal = (128, 128, 0)\n    olive = (0, 128, 128)\n\n\n" + p_defs + "\n",
    )

    # --- tracked_object.py / transport.py / track.py / bl_utils.py -----------------------------------
    to = read(os.path.join(CVC, "tracked_object.py"))
    to = to.replace("from utils.plots import plot_one_box\n", "from ._draw import plot_one_box, Color\n")
    to = to.replace("from norfair import Color\n", "")
    to = re.sub(r"^from common import ", "from .common import ", to, flags=re.M)
    assert "from .common import" in to and "from ._draw import" in to
    write(os.path.join(TMP, "tracked_object.py"), '"""VENDORED verbatim from cv_common/tracked_object.py @2759daf (imports rewritten)."""\n' + to)

    tr = read(os.path.join(CVC, "transport.py"))
    tr = tr.replace("from cv_common.tracked_object import TrackedObject, Status\n", "from .tracked_object import TrackedObject, Status\n")
    tr = tr.replace(
        "from cv_common.common import parse_config, get_relative_intersection\n",
        "from .common import get_relative_intersection\nfrom .config import config\n",
    )
    tr = tr.replace("from norfair import Color\n", "from ._draw import Color\n")
    tr = re.sub(r"^config = parse_config\(\)\n", "", tr, flags=re.M)
    assert "parse_config" not in tr
    write(os.path.join(TMP, "transport.py"), '"""VENDORED verbatim from cv_common/transport.py @2759daf (imports rewritten; config from .config)."""\n' + tr)

    write(os.path.join(TMP, "track.py"), '"""VENDORED verbatim from cv_common/track.py @2759daf."""\n' + read(os.path.join(CVC, "track.py")))

    bl = read(os.path.join(TRK, "local_utils", "bl_utils.py"))
    bl = bl.replace("from cv_common.common import (bboxes_iou, bbox_area, is_overlap)", "from .common import bboxes_iou, bbox_area, is_overlap")
    assert "from .common import" in bl
    write(os.path.join(TMP, "bl_utils.py"), '"""VENDORED verbatim from cv_trackers/local_utils/bl_utils.py @bd43c3c (import rewritten)."""\n' + bl)

    # --- configs ----------------------------------------------------------------------------------------
    os.makedirs(os.path.join(TMP, "config"), exist_ok=True)
    shutil.copy(os.path.join(CVC, "global_config.yaml"), os.path.join(TMP, "config", "global_config.yaml"))
    shutil.copy(os.path.join(TRK, "local_config.yaml"), os.path.join(TMP, "config", "local_config.yaml"))
    shutil.copy(os.path.join(TRK, "deep_sort_pytorch", "configs", "deep_sort.yaml"), os.path.join(TMP, "config", "deep_sort.yaml"))
    write(
        os.path.join(TMP, "config.py"),
        '"""Configuration of the vendored tracker: cv_common global_config.yaml @2759daf updated by the production tracker\'s\n'
        "local_config.yaml @bd43c3c — the same merge as `cv_common.common.parse_config` (top-level keys of the local file\n"
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
    dst = os.path.join(TMP, "deep_sort_pytorch")
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

    write(
        os.path.join(TMP, "__init__.py"),
        '"""Pinned, import-rewritten copies of the production tracker\'s dependencies (see VENDORED.md). Generated by\n'
        "scripts/vendor_tracker_v1.py — edit the generator or the pins, not these files. Performance changes live outside\n"
        '(pf/tracker/fast_*.py) and are switched on explicitly.\n"""\n',
    )
    write(
        os.path.join(TMP, "VENDORED.md"),
        "# Vendored tracker dependencies\n\n"
        "| file | source | revision | change |\n|---|---|---|---|\n"
        "| `tracked_object.py` | cv_common/tracked_object.py | 2759daf (tracker_optimization) | imports rewritten |\n"
        "| `transport.py` | cv_common/transport.py | 2759daf | imports rewritten, `config` from `.config` |\n"
        "| `track.py` | cv_common/track.py | 2759daf | none |\n"
        "| `common.py` | cv_common/common.py | 2759daf | helper functions + their dependency closure (AST-extracted, bodies verbatim) |\n"
        "| `_draw.py` | cv_common/utils/plots.py + norfair.Color | 2759daf | `plot_one_box` + imports verbatim (`import random` added: not bound in the source module); `Color` constants |\n"
        "| `bl_utils.py` | cv_trackers/local_utils/bl_utils.py | bd43c3c (optimization) | import rewritten |\n"
        "| `config/global_config.yaml` | cv_common/global_config.yaml | 2759daf | none |\n"
        "| `config/local_config.yaml` | cv_trackers/local_config.yaml | bd43c3c | none |\n"
        "| `config/deep_sort.yaml` | cv_trackers/deep_sort_pytorch/configs/deep_sort.yaml | bd43c3c | none |\n"
        "| `deep_sort_pytorch/` | cv_trackers/deep_sort_pytorch (runtime subset: deep_sort/, utils/parser.py) | bd43c3c | none (MIT, LICENSE kept) |\n\n"
        "Nothing in this directory is hand-edited. Performance changes are separate modules (`pf/tracker/fast_*.py`) enabled\n"
        "through `TrackerOptions`, each proven output-identical with seeded runs against the production pin.\n",
    )

    if os.path.isdir(DST):
        shutil.rmtree(DST)
    os.rename(TMP, DST)
    print("vendored into", DST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
