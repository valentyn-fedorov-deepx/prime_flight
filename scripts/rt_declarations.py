"""Correct the declared inputs of every module against the checkout that actually runs.

`docs/analysis/module_consumption.json` was written from the default branch of each module. The test set — like
production — runs several modules from other branches (`not_observed_logic`, `obstruction_plane_track`, `bl_approach` …),
and those read more classes: the subscription pass over the 69 events changed 75 verdicts, every one of them a module that
no longer saw the classes its obstruction logic looks at. This scan reads the checkout named in `scripts/testset/profiles`
and adds every class name the code quotes. It over-approximates on purpose — a class too many costs a few rows, a class too
few silently changes a verdict.

    python scripts/rt_declarations.py            # writes pf/rt/declarations.json and prints what was added
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.gm_v2_run import load_str2id  # noqa: E402
from scripts.testset import profiles  # noqa: E402

TRACKED = ("airplane", "beltloader", "gse", "person")
SKIP_DIRS = ("cv_common", "db_worker", ".git", "weights", "__pycache__", "output", "mmpose", "mmdet", "mmcv")
OUT = os.path.join(ROOT, "pf", "rt", "declarations.json")

# Tracked classes cannot be found by scanning: modules pick records through helpers that take the class list as an
# argument (`collect_tracks(tracks, classes=[...])`), and the same names are GM classes too. A tracked class too many is
# also the expensive mistake (the tracker costs 2.5-28 ms per frame depending on its classes), so these are added only on
# evidence: a verdict that changed when the class was withheld.
VERIFIED_TRACKED = {
    "all-cargo-bin-doors-opened-and-verified": {
        "classes": ["beltloader"],
        "evidence": "withholding beltloader records turned 63 of 68 test-set verdicts (Pass 'a beltloader approached the "
                    "doors' -> Fail 'No beltloaders approached'); branch bl_approach reads them through a helper",
    },
}


def quoted_names(folder: str, names: set) -> tuple:
    """(class names quoted anywhere in the module's code, tracked classes compared with a record's `cls_str`)."""
    found, tracked = set(), set()
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith((".py", ".yaml", ".yml")):
                continue
            text = io.open(os.path.join(root, name), encoding="utf-8", errors="replace").read()
            found |= {n for n in names if re.search(r"['\"]" + re.escape(n) + r"['\"]", text)}
            for line in text.splitlines():  # a tracked class is read where a record's class is tested
                if "cls_str" in line or "class_name" in line:
                    tracked |= {n for n in TRACKED if re.search(r"['\"]" + n + r"['\"]", line)}
    return found, tracked


def main() -> int:
    names = set(load_str2id(os.path.join(ROOT, "external", "cv_common", "global_config.yaml")))
    declared = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "module_consumption.json"), encoding="utf-8"))["modules"]
    out = {"_meta": {
        "what": "Classes each module reads in the checkout that actually runs, beyond docs/analysis/module_consumption.json.",
        "how": "scripts/rt_declarations.py: every class name quoted in the module's own code (not in its vendored "
               "cv_common / db_worker); a deliberate over-approximation.",
        "why": "the static analysis covered the default branches; the test set and production run other branches for several "
               "modules, and a scoped GM built from the old declaration changed 75 of 680 verdicts."}}
    for module in sorted(declared):
        try:
            prof = profiles.profile(module)
        except Exception:
            continue
        folder = os.path.join(ROOT, prof.get("module_dir") or os.path.join("external", module))
        if not os.path.isdir(folder):
            continue
        used, tracked_used = quoted_names(folder, names)
        gm = declared[module].get("gm") or {}
        gm_declared = set(gm.get("class_names") or []) | set(gm.get("class_names_cosmetic") or [])
        trk_declared = set((declared[module].get("tracker") or {}).get("classes") or [])
        gm_extra = sorted(used - gm_declared)
        verified = VERIFIED_TRACKED.get(module) or {}
        trk_extra = sorted(set(verified.get("classes") or []) - trk_declared)
        trk_candidates = sorted(tracked_used - trk_declared - set(trk_extra))
        if gm_extra or trk_extra:
            out[module] = {"checkout": os.path.relpath(folder, ROOT).replace("\\", "/"),
                           "gm_classes_extra": gm_extra, "tracker_classes_extra": trk_extra,
                           "tracker_classes_evidence": verified.get("evidence"),
                           "tracker_classes_unverified_candidates": trk_candidates}
            print(f"{module[:52]:54s} +gm {gm_extra}  +tracked {trk_extra}")
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    print(f"\n{len(out) - 1} modules corrected -> {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
