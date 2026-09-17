"""The component table of the real-time branch: what each module declares, when its gate opens, what it is handed.

    python scripts/rt_components.py                      # the real-time module set
    python scripts/rt_components.py --all                # every module the static analysis knows
    python scripts/rt_components.py --measure zHxIAF2vUGxJ.mp4   # + the record size each component is given

Declarations come from `docs/analysis/module_consumption.json` (static analysis of the module code), gates from
`pf/rt/gating.json` (proposal). `--measure` pickles real rows from that event's batch files, the way the pipe sees them.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pickle
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pf.rt.component import CONSUMPTION, ComponentSpec  # noqa: E402

RT_MODULES = [  # group A of docs/analysis/rt_module_selection.md
    "beltloader-chocks", "bl_rear_cone", "3-stop-brake-check",
    "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked",
    "pushback-pathway-confirmed-clear-of-obstacles",
    "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready",
    "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed",
    "cones-placed-in-proper-positions-and-timely", "chocks-and-cones-available-and-staged-for-arrival",
    "crew-present-10-minutes-prior-to-aircraft-arrival", "all-cargo-bin-doors-opened-and-verified",
]


def records_of(video: str, frames: int, skip: int):
    from scripts.testset import orchestrate as o

    paths = o.paths(video)
    for key in ("gm_compat", "trk_compat"):
        if not os.path.exists(paths[key]):
            raise SystemExit(f"no batch file {paths[key]}: run the test set for {video} first")
    metas = []
    with io.open(paths["gm_compat"], encoding="utf-8") as gm, io.open(paths["trk_compat"], encoding="utf-8") as trk:
        for i, (row_line, track_line) in enumerate(zip(gm, trk)):
            if i < skip:
                continue
            if len(metas) >= frames:
                break
            metas.append({"general_model": next(iter(json.loads(row_line).values()), []),
                          "trackers": next(iter(json.loads(track_line).values()), [])})
    return metas


def kb(metas) -> float:
    return statistics.mean(len(pickle.dumps(m, protocol=pickle.HIGHEST_PROTOCOL)) for m in metas) / 1024


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="every analysed module, not only the real-time set")
    ap.add_argument("--measure", default=None, help="event to measure the handed record on (e.g. zHxIAF2vUGxJ.mp4)")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--skip", type=int, default=11000, help="start at this frame (the middle of the turnaround)")
    ap.add_argument("--json", action="store_true", help="the table as JSON")
    a = ap.parse_args()

    modules = RT_MODULES
    if a.all:
        modules = sorted(json.load(io.open(CONSUMPTION, encoding="utf-8"))["modules"])

    metas = class_id_of = full = None
    if a.measure:
        from pf.gm.rows import ClassMap
        from scripts.gm_v2_run import load_str2id

        cm = ClassMap(load_str2id(os.path.join(ROOT, "external", "cv_common", "global_config.yaml")))
        class_id_of = cm.str2id.get
        metas = records_of(a.measure, a.frames, a.skip)
        full = kb(metas)
        print(f"{a.measure}: {len(metas)} frames from frame {a.skip}, whole record {full:.1f} KB per frame "
              f"({statistics.mean(len(m['general_model']) for m in metas):.1f} rows, "
              f"{statistics.mean(len(m['trackers']) for m in metas):.1f} records)\n")

    table = []
    for module in modules:
        spec = ComponentSpec.for_module(module)
        row = {**spec.as_dict(), "optical_flow_state": spec.reads_optical_flow_state()}
        if metas is not None:
            sub = spec.subscription(class_id_of)
            row["given_kb"] = round(kb([sub.filter(m) for m in metas]), 2)
            row["share_of_record"] = round(row["given_kb"] / full, 3)
        table.append(row)

    if a.json:
        print(json.dumps(table, indent=1))
        return 0
    header = f"{'component':46s} {'pixels':7s} {'gate':34s} {'gm classes':11s} {'tracks':28s}"
    print(header + ("  given" if metas is not None else ""))
    print("-" * (len(header) + (7 if metas is not None else 0)))
    for row in table:
        gate = f"{row['gate']['open_on'][:16]:17s}->{row['gate']['close_on'][:14]:15s}"
        given = f"  {row['given_kb']:5.2f} KB ({100 * row['share_of_record']:.0f} %)" if metas is not None else ""
        print(f"{row['module'][:44]:46s} {'yes' if row['pixels'] else 'no':7s} {gate} "
              f"{len(row['gm_classes']):<11d} {','.join(row['tracker_classes'])[:28]:28s}{given}")
    if not any(r["declared"] for r in table):
        print("\nnothing declared: docs/analysis/module_consumption.json has no entry for these modules")
    print("\ngate: proposal in pf/rt/gating.json, applied only when a stage-event source is wired (PF-Q1-03)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
