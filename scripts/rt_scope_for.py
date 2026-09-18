"""What GM heads and tracked classes a set of real-time modules needs, and the run command for them.

Rules (from `docs/analysis/module_consumption.json` and the second-run row logic):
  * a module that reads the `chock` class needs the chocks head; `vehicle` needs the vehicle head; everything else the GM head;
  * `obstacle` / `side_obstacle` rows are synthesised from the transport boxes and the de-duplicated vehicle boxes, so a module
    that reads them needs the vehicle head to get the same rows as batch;
  * tracked classes are the ones the modules read from the tracker records.

    python scripts/rt_scope_for.py --modules pushback-pathway-confirmed-clear-of-obstacles,3-stop-brake-check
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.testset import profiles  # noqa: E402

HEAD_OF_CLASS = {"chock": "chocks", "vehicle": "vehicle", "obstacle": "vehicle", "side_obstacle": "vehicle"}
ALL_TRACKER_CLASSES = ("airplane", "beltloader", "gse", "person")


def scope(modules: list) -> dict:
    mods = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "module_consumption.json"), encoding="utf-8"))["modules"]
    per_module, heads, tracked = {}, {"gm"}, set()
    for name in modules:
        entry = mods.get(name)
        if entry is None:
            raise SystemExit(f"{name}: not in module_consumption.json")
        from pf.rt.component import ComponentSpec  # the declaration plus what was found against the running checkout

        spec = ComponentSpec.for_module(name)
        gm_classes = sorted(spec.gm_classes)
        module_heads = sorted({HEAD_OF_CLASS[c] for c in gm_classes if c in HEAD_OF_CLASS} | {"gm"})
        classes = sorted(spec.tracker_classes)
        per_module[name] = {"gm_classes": gm_classes, "heads": module_heads, "tracker_classes": classes,
                            "private_tracker_fields": sorted(entry["tracker"].get("private_fields", [])),
                            "passes": entry.get("passes"), "pixels": not profiles.profile(name).get("pixel_free")}
        heads |= set(module_heads)
        tracked |= set(classes)
    return {"modules": per_module,
            "heads": [h for h in ("gm", "chocks", "vehicle") if h in heads],
            "tracker_classes": [c for c in ALL_TRACKER_CLASSES if c in tracked],
            "tracker_classes_dropped": [c for c in ALL_TRACKER_CLASSES if c not in tracked]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modules", required=True, help="comma list; the first one runs in the pipeline process")
    ap.add_argument("--video", default="zHxIAF2vUGxJ.mp4")
    ap.add_argument("--tag", default="rt_scope")
    a = ap.parse_args()

    modules = [m for m in a.modules.split(",") if m]
    result = scope(modules)
    for name, info in result["modules"].items():
        print(f"{name}\n  heads {info['heads']} · tracker {info['tracker_classes']} · passes {info['passes']}"
              f" · pixels {info['pixels']}")
    print(f"\nunion: heads {result['heads']} · tracker classes {result['tracker_classes']}"
          f" · not needed: {result['tracker_classes_dropped'] or 'none'}")
    extra = ",".join(modules[1:])
    print("\nrun:\npython scripts/rt_pipeline_run.py --video {} --module {}{} --tag {} --speed 1 --no-write-rows "
          "--heads {} --tracker-classes {}".format(
              a.video, modules[0], f" --extra-modules {extra}" if extra else "", a.tag, ",".join(result["heads"]),
              ",".join(result["tracker_classes"])))
    print("\nnote: dropping a tracked class is not exact (the random draws and the noise gate shift) — gate it on verdicts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
