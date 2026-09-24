"""Which modules could run on a small model of their own, and what that model has to detect.

The question this answers is a dataset question: if the shared General Model is the blocker, which checks can be taken
forward with a detector of two or three classes plus the models the module already carries, and what exactly has to be
labelled for each. Built from what the modules actually read:

  * `docs/analysis/module_consumption.json` - per module: the GM classes it reads, which of them are only drawn, the tracker
    classes and private fields, the models it loads itself, the passes;
  * `pf/rt/declarations.json` - the corrections found by running the checkouts the test set uses.

Each class a module reads is put in one of four groups, so the size of the dataset it would need is visible:

  * **check** - the objects the rule is about (people, cones, chocks, doors, the vest, the wand, the belt loader when the
    rule is about it): these have to be in a dataset;
  * **aircraft** - the aircraft and its parts: needed for geometry (distances to the wheel, the nose, the wing) and, through
    the tracker, for the stage anchors; the stage detector (PF-Q1-03) is meant to own the second use;
  * **traffic** - other vehicles and ground equipment, mostly read to answer "is something in the way" or "has the ramp
    cleared";
  * **derived** - not detections at all: `obstacle` / `side_obstacle` are synthesised from the transport and vehicle boxes in
    the second-run rows, `roi` and `safety_zone` are drawn regions.

    python scripts/module_dataset_needs.py
"""

from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

AIRCRAFT = {"airplane", "airplane_nose", "airplane_tail", "airplane_wing", "airplane_engine", "front_wheel", "back_wheel",
            "tow_bar"}
DERIVED = {"obstacle", "side_obstacle", "roi", "safety_zone"}
TRAFFIC = {"gse", "fuel_truck", "trailer", "vehicle", "pushback", "ladder", "air_conditioning", "beltloader"}
CHECK = {"person", "safety_vest", "wand", "cone", "engine_cone", "wing_cone", "tail_cone", "beltloader_cone", "chock",
         "front_door", "back_door"}
# modules whose rule is about a vehicle: for them that vehicle belongs to the check, not to the traffic around it
CHECK_VEHICLE = {
    "handrails-on-gse-being-used": {"beltloader"}, "safety-handrails-fully-extended": {"beltloader"},
    "gse-chocks": {"gse", "beltloader"}, "beltloader-chocks": {"beltloader"}, "bl_rear_cone": {"beltloader"},
    "3-stop-brake-check": {"beltloader"}, "hand-signals": {"beltloader"}, "all-cargo-bin-doors-opened-and-verified": {"beltloader"},
    "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed": {"air_conditioning"},
    "seat-belts-used-on-all-gse-equipped-with-seat-belts": {"gse", "beltloader", "fuel_truck"},
    "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked": {"gse", "beltloader"},
    "pushback-pathway-confirmed-clear-of-obstacles": {"pushback"},
    "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready": {"pushback"},
    "pin-verification": {"pushback"}, "aircraft-chocks": {"pushback"},
}
SHORT = {"safety-vests-secured-to-body": "safety-vests", "steering-by-pass-pin-installed-or-steering-otherwise-bypassed": "steering",
         "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready": "pushback-wing-walkers",
         "pushback-pathway-confirmed-clear-of-obstacles": "pushback-pathway",
         "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked": "cones-removed",
         "chocks-and-cones-available-and-staged-for-arrival": "chocks-and-cones-staged",
         "crew-present-10-minutes-prior-to-aircraft-arrival": "crew-present",
         "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed": "conditioned-air",
         "all-cargo-bin-doors-opened-and-verified": "cargo-doors",
         "wing-walkers-in-proper-position-and-using-approved-wands": "wing-walkers-wands",
         "lead-marshaller-and-wing-walkers-in-position": "lead-marshaller",
         "cones-placed-in-proper-positions-and-timely": "cones-placed", "pre-arrival-safety-huddle": "huddle",
         "post-arrival-aircraft-walk-around-inspection-completed-accurately": "walk-around post-arrival",
         "pre-departure-walk-around-completed": "walk-around pre-departure",
         "seat-belts-used-on-all-gse-equipped-with-seat-belts": "seat-belts (out of scope)",
         "safety-zone-confirmed-clear": "safety-zone", "handrails-on-gse-being-used": "handrails-on-gse",
         "safety-handrails-fully-extended": "safety-handrails", "fod-walk-completed": "fod-walk",
         "beltloader-chocks": "beltloader-chocks", "aircraft-chocks": "aircraft-chocks", "hand-signals": "hand-signals",
         "3-stop-brake-check": "3-stop", "pin-verification": "pin-verification", "bl_rear_cone": "bl_rear_cone"}


def model_names(own: list) -> list:
    out = []
    for m in own or []:
        name = m.split("(")[0].strip().rstrip(",")
        if name.lower() not in ("none", "no weights", ""):
            out.append(name)
    return out


def main() -> int:
    from pf.rt.component import ComponentSpec

    cons = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "module_consumption.json"), encoding="utf-8"))["modules"]
    rt = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"), encoding="utf-8"))
    ready = {r["module"]: r["runs_in_real_time_as_is"] for r in rt["modules"]}
    rows = []
    for name, c in cons.items():
        spec = ComponentSpec.for_module(name)
        cosmetic = set(c["gm"].get("class_names_cosmetic") or [])
        decision = sorted(set(spec.gm_classes) - cosmetic)
        check_vehicles = CHECK_VEHICLE.get(name, set())
        buckets = {"check": [], "aircraft": [], "traffic": [], "derived": []}
        for cls in decision:
            if cls in CHECK or cls in check_vehicles:
                buckets["check"].append(cls)
            elif cls in AIRCRAFT:
                buckets["aircraft"].append(cls)
            elif cls in DERIVED:
                buckets["derived"].append(cls)
            elif cls in TRAFFIC:
                buckets["traffic"].append(cls)
            else:
                buckets["check"].append(cls)
        rows.append({
            "module": name, "short": SHORT.get(name, name), "runs_in_real_time_as_is": ready.get(name),
            "pixels": bool(c["pixels"].get("reads_frames")), "passes": c.get("passes"),
            "own_models": model_names(c["pixels"].get("own_models")),
            "classes_for_the_check": buckets["check"], "aircraft_classes": buckets["aircraft"],
            "traffic_classes": buckets["traffic"], "derived_rows": buckets["derived"],
            "drawn_only": sorted(cosmetic), "tracker_classes": sorted(spec.tracker_classes),
            "recomputes_the_stage_itself": bool([x for x in (c["tracker"].get("events_recomputed_locally") or [])
                                                 if x and not x.lower().startswith("none")]),
            "reads_optical_flow_state": bool(c["tracker"].get("private_fields")),
        })
    rows.sort(key=lambda r: (len(r["classes_for_the_check"]) + len(r["aircraft_classes"]), len(r["traffic_classes"])))

    def cell(items):
        return ", ".join(items) if items else "—"

    L = ["# What a module would need from a model of its own", "",
         "Generated by `scripts/module_dataset_needs.py` from `docs/analysis/module_consumption.json` (static analysis of the "
         "module code) and `pf/rt/declarations.json` (corrections found by running the checkouts the test set uses); the "
         "grouping of the classes is a reading of that analysis, not a measurement — the ablation at the end is how to confirm "
         "it per module. Do not edit by hand.", "",
         "**for the check** = the objects the rule is about, the ones a dataset has to carry. **aircraft** = the aircraft and "
         "its parts: geometry plus, through the tracker, the stage anchors (the stage detector, PF-Q1-03, is meant to own the "
         "second use). **traffic** = other ground equipment, mostly read to answer \"is something in the way\". **derived** = not "
         "detections: `obstacle` / `side_obstacle` are synthesised from the transport and vehicle boxes, `roi` and `safety_zone` "
         "are drawn regions. Classes the module only draws are left out of all four.", "",
         "| module | its own models | for the check | aircraft | traffic | derived | tracker | pixels | passes |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['short']} | {cell(r['own_models']) if r['own_models'] else '—'} | **{cell(r['classes_for_the_check'])}** | "
                 f"{cell(r['aircraft_classes'])} | {cell(r['traffic_classes'])} | {cell(r['derived_rows'])} | "
                 f"{cell(r['tracker_classes'])} | {'yes' if r['pixels'] else 'no'} | {r['passes']} |")

    stage_users = [r["short"] for r in rows if r["recomputes_the_stage_itself"]]
    free = [r for r in rows if not r["aircraft_classes"] and not r["traffic_classes"]]
    small = [r for r in rows if r not in free and len(r["classes_for_the_check"]) + len(r["aircraft_classes"]) <= 4]
    L += ["", "## Where a small model would be enough", "",
          "**Nothing from the aircraft or the traffic around it** — a detector of the check's own classes plus the models the "
          "module already carries:", ""]
    for r in free:
        L.append(f"- **{r['short']}**: detect {cell(r['classes_for_the_check'])}; own models: {cell(r['own_models'])}; "
                 f"tracked: {cell(r['tracker_classes'])}. Real time: {r['runs_in_real_time_as_is']}.")
    L += ["", "**Four classes or fewer, including the aircraft parts it measures against**:", ""]
    for r in small:
        L.append(f"- **{r['short']}**: detect {cell(r['classes_for_the_check'])} + {cell(r['aircraft_classes'])}; "
                 f"own models: {cell(r['own_models'])}; tracked: {cell(r['tracker_classes'])}"
                 + ("; it also derives the stage itself from the tracker's optical-flow fields" if r["recomputes_the_stage_itself"] and r["reads_optical_flow_state"] else "")
                 + ".")

    # which of the models a module carries were trained on our data (a dataset to keep) and which are stock COCO weights
    OURS = ("swin-t", "efficientnet", "effnet", "yolov8", "tsai", "scaler", "handrail", "vest", "difference", "hair")
    STOCK = ("hrnet", "simcc", "movenet", "dwpose", "rtmpose", "mmpose", "mobile_sam", "norfair", "mixvisiontransformer")
    ours, stock = {}, {}
    for r in rows:
        for m in r["own_models"]:
            low = m.lower()
            if any(k in low for k in STOCK) and not any(k in low for k in OURS):
                stock.setdefault(m.split(",")[0], []).append(r["short"])
            elif any(k in low for k in OURS):
                ours.setdefault(m.split(",")[0], []).append(r["short"])
            else:
                ours.setdefault(m.split(",")[0] + " (unclear, check the weights)", []).append(r["short"])
    L += ["", "## The models the modules already carry", "",
          "A pose model is not a dataset problem: the ones in use are stock COCO weights. The classifiers are ours and each "
          "has a crop dataset behind it.", "",
          "| trained on our data | used by |", "|---|---|"]
    for m, mods in sorted(ours.items()):
        L.append(f"| {m} | {', '.join(sorted(set(mods)))} |")
    L += ["", "| stock weights, no dataset needed | used by |", "|---|---|"]
    for m, mods in sorted(stock.items()):
        L.append(f"| {m} | {', '.join(sorted(set(mods)))} |")

    L += ["", "**What a small model does not solve.** A short class list is not the same as independence: "
          f"{len(stage_users)} of {len(rows)} modules also work out the stage themselves from the aircraft track (T_arr, T_dep, "
          "pushback attached, belt loader at the door), and most of them read the synthesised `obstacle` / `side_obstacle` rows "
          "to decide \"the view was blocked, not observed\". Taking a check off the General Model therefore needs three things, "
          "not one: its own detector, the stage anchors from the stage detector (PF-Q1-03), and a decision about what plays the "
          "part of the obstruction rows.", ""]

    groups = {}
    for r in rows:
        for cls in r["classes_for_the_check"]:
            groups.setdefault(cls, []).append(r["short"])
    L += ["", "## One dataset, several checks", "",
          "How many checks each class unblocks (the class as the check's own object, not as scenery):", "",
          "| class to label | checks that need it |", "|---|---|"]
    for cls, mods in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        L.append(f"| **{cls}** ({len(mods)}) | {', '.join(sorted(mods))} |")

    L += ["", "## How to confirm a class list before collecting for it", "",
          "The branch can already hand a module only the rows of the classes it declares (`scripts/run_module.py "
          "--subscription`, `pf/rt/component.py`), and the whole test set has been run that way: with the declared classes the "
          "verdicts are identical to the full inputs on 740 of 740 task verdicts (`docs/analysis/rt_module_cost.md`, section 6). "
          "The same machinery narrows the list further: give a module only the classes of the column *for the check* (plus the "
          "aircraft if it measures against it) and compare the verdicts with the full run. What survives that is the class list "
          "a dedicated model has to cover; what breaks shows which of the other classes the rule really uses.", "",
          "```", "python scripts/run_module.py --module <module> --video <video> --inferences-dir out/testset/v2_inf/<video> \\",
          "    --subscription --subscription-parts gm --subscription-extra-gm <class,class>   # rows of these classes only",
          "```"]
    io.open(os.path.join(ROOT, "docs", "analysis", "module_dataset_needs.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    json.dump({"modules": rows, "class_to_modules": groups},
              io.open(os.path.join(ROOT, "docs", "analysis", "module_dataset_needs.json"), "w", encoding="utf-8", newline="\n"),
              indent=1)
    print(f"{len(free)} modules need nothing from the aircraft or the traffic; {len(small)} more stay within four classes")
    for r in free + small:
        print(" ", r["short"], "->", cell(r["classes_for_the_check"]), "+", cell(r["aircraft_classes"]), "| models:", cell(r["own_models"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
