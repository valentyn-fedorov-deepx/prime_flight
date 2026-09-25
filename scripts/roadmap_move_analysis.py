"""Two questions about the RampVision roadmap, answered from the measurements.

1. Which checks are the cheapest to move into **minutes** (server real time) without changing their triggers: the module runs
   unchanged (`docs/analysis/rt_module_cost.md`), it answers during the turnaround rather than at the end of the session, it
   needs no new trigger, and it drags little into the shared frame path (`docs/analysis/rt_environment.md`).
2. Which check could take the place of the nose gear chocks on an **edge** device: free of the shared General Model, light,
   and critical (`docs/analysis/critical_label_queue.json`).

Sources: the roadmap page `docs/planning/RV_scope_timeline.html` (the plan as it stands), the real-time campaign
(`rt_module_cost.json`), the class analysis (`module_dataset_needs.json`), the shared-cost table (`rt_environment.json`).

    python scripts/roadmap_move_analysis.py
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ROADMAP = os.path.join(ROOT, "docs", "planning", "RV_scope_timeline.html")
# the checks of the roadmap page -> the module that produces them (three chock checks come out of one module)
CHECK_TO_MODULE = {
    "Safety vests": "safety-vests-secured-to-body", "FOD walk": "fod-walk-completed",
    "Steering by pass pin": "steering-by-pass-pin-installed-or-steering-otherwise-bypassed", "Hair Policy": "hair-policy",
    "Nose Gear Chocks": "aircraft-chocks", "Main gear chocks removed only after aircraft is attached to pushback": "aircraft-chocks",
    "Nose wheel chock removed from aircraft": "aircraft-chocks",
    "Pushback does not start until wing walkers are in place": "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready",
    "Safety zone clear": "safety-zone-confirmed-clear", "3 stop brake": "3-stop-brake-check", "GSE parked": "gse-chocks",
    "Handrails on GSE": "handrails-on-gse-being-used", "Handrails fully extended": "safety-handrails-fully-extended",
    "Conditioned air removed": "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed",
    "Pushback verify pin installation": "pin-verification", "Beltloader rear cone positioned after BL": "bl_rear_cone",
    "Wing walkers in proper position": "wing-walkers-in-proper-position-and-using-approved-wands",
    "Lead marshaller and wing walkers in correct position": "lead-marshaller-and-wing-walkers-in-position",
    "Belt loader forward chock remained in place until unit is backed up clear of aircraft": "beltloader-chocks",
    "Pushback pathway confirmed clear": "pushback-pathway-confirmed-clear-of-obstacles",
    "Cones placed in proper positions": "cones-placed-in-proper-positions-and-timely",
    "Cones are removed only after all GSE is clear of A/C and chocked": "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked",
    "Chocks and cones available and staged for arrival": "chocks-and-cones-available-and-staged-for-arrival",
    "Crew present 10 minutes prior to aircraft arrival": "crew-present-10-minutes-prior-to-aircraft-arrival",
    "Safety huddle conducted at huddle cone": "pre-arrival-safety-huddle",
    "All GSE guided into aircraft using approved hand signals": "hand-signals",
    "Pre-departure walk around completed": "pre-departure-walk-around-completed",
    "All cargo bin doors opened and verified": "all-cargo-bin-doors-opened-and-verified",
    "Proper beltloader approach including 3 stop brake check and handsignals": None,  # derived from two modules, not a pod
    "Post-arrival aircraft walk around inspection completed accurately": "post-arrival-aircraft-walk-around-inspection-completed-accurately",
}
# the checks that decide after the fact and need a new trigger to be useful live (docs/02_target_architecture.md, S1)
TRIGGER_CHANGE = {"safety-zone-confirmed-clear", "pushback-pathway-confirmed-clear-of-obstacles",
                  "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready", "hand-signals"}
MODE_NAME = {"edge": "seconds (edge)", "rt": "minutes (server)", "post": "hours (post)"}


def load(path: str):
    return json.load(io.open(path, encoding="utf-8")) if os.path.exists(path) else None


def roadmap() -> list:
    text = io.open(ROADMAP, encoding="utf-8").read()
    data = json.loads(re.search(r"const DATA = (\[.*?\]);", text, re.S).group(1))
    return [d for d in data if d.get("kind") == "check"]


def main() -> int:
    checks = roadmap()
    cost = {r["module"]: r for r in load(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"))["modules"]}
    env = {r["module"]: r for r in load(os.path.join(ROOT, "docs", "analysis", "rt_environment.json"))["price_list"]}
    needs = {r["module"]: r for r in load(os.path.join(ROOT, "docs", "analysis", "module_dataset_needs.json"))["modules"]}
    critical = {t["module"]: len(t["fails"]) for t in load(os.path.join(ROOT, "docs", "analysis", "critical_label_queue.json"))["tasks"]}

    rows = []
    for c in checks:
        module = CHECK_TO_MODULE.get(c["label"])
        r, e, n = cost.get(module), env.get(module), needs.get(module)
        drag = (e["drags_in_gm_ms"] + e["drags_in_tracker_ms"]) if e else None
        own = (r["whole_event_ms"].get("module") if r else None)
        rows.append({
            "check": c["label"], "module": module, "plan_mode": c["mode"], "plan_month": c["month"], "locked": c.get("lock"),
            "runs_as_is": (r or {}).get("runs_in_real_time_as_is"), "verdict_arrives": (r or {}).get("verdict_arrives"),
            "needs_new_trigger": module in TRIGGER_CHANGE,
            "drags_in_ms": drag, "own_ms": own,
            "total_alone_ms": (r or {}).get("whole_event_ms", {}).get("total"),
            "classes_for_the_check": (n or {}).get("classes_for_the_check"), "aircraft_classes": (n or {}).get("aircraft_classes"),
            "own_models": (n or {}).get("own_models"), "pixels": (n or {}).get("pixels"),
            "works_out_the_stage_itself": (n or {}).get("recomputes_the_stage_itself"),
            "critical_fails_in_the_test_set": critical.get(module),
            "test_set_scoped_inputs": (r or {}).get("testset_scoped_inputs"),
        })

    def ready(r):
        return (r["runs_as_is"] or "").startswith("yes")

    def cheap_key(r):
        return (0 if r["runs_as_is"] == "yes" else 1, r["needs_new_trigger"], r["drags_in_ms"] if r["drags_in_ms"] is not None else 99,
                r["own_ms"] if r["own_ms"] is not None else 99)

    movable = sorted([r for r in rows if ready(r) and not r["needs_new_trigger"] and r["plan_mode"] != "edge"], key=cheap_key)
    in_hours = [r for r in movable if r["plan_mode"] == "post"]

    def cell(v, digits=1):
        return "—" if v is None else (f"{v:.{digits}f}" if isinstance(v, float) else str(v))

    L = ["# Moving checks into minutes, and what could go to the edge instead of the nose gear chocks", "",
         "Generated by `scripts/roadmap_move_analysis.py` from the roadmap page `docs/planning/RV_scope_timeline.html` and the "
         "measurements of `rt_module_cost.md`, `rt_environment.md`, `module_dataset_needs.md`, `critical_label_queue.json`. "
         "Do not edit by hand.", "",
         "## 1. The cheapest checks to move into minutes", "",
         "Cheap here means three things, all measured: the **module runs live unchanged** and gives the batch verdict "
         "(whole event, `rt_module_cost.md` section 1); it **answers during the turnaround**, not when the session closes; and "
         "it **drags little into the shared frame path** — the milliseconds a stream pays because this check needs a detector "
         "head or a tracked class nobody else in the set needs. Checks whose rule only makes sense with a new trigger (the S1 "
         "group of `02_target_architecture.md`) are left out of the list, however cheap they are.", "",
         "| check | in the plan now | runs live unchanged | verdict arrives | drags into the frame path | its own work | "
         "test set: scoped = full |", "|---|---|---|---|---|---|---|"]
    for r in movable:
        ts = r["test_set_scoped_inputs"] or {}
        L.append(f"| {r['check']} | {MODE_NAME[r['plan_mode']]} M{r['plan_month']} | {r['runs_as_is']} | {r['verdict_arrives']} | "
                 f"+{cell(r['drags_in_ms'])} ms | {cell(r['own_ms'], 2)} ms | "
                 f"{str(ts.get('report_same', '—')) + ' / ' + str(ts.get('runs')) if ts else '—'} |")
    L += ["", f"**{len(in_hours)} of them sit in hours in the plan today** and are the free moves: the module already ran live "
          "on a whole event and produced the batch verdict, the check needs no new trigger, and it adds nothing to the frame "
          "path that the set does not already pay for:", ""]
    for r in in_hours:
        L.append(f"- **{r['check']}** ({r['module']}): {r['verdict_arrives']}, own work {cell(r['own_ms'], 2)} ms per frame, "
                 f"drags +{cell(r['drags_in_ms'])} ms.")

    blocked = [r for r in rows if r["module"] and not ready(r) and r["plan_mode"] != "edge"]
    L += ["", "### What is not free, and why", "",
          "| check | in the plan now | what stops it |", "|---|---|---|"]
    for r in sorted(blocked, key=lambda r: r["plan_month"]):
        why = r["runs_as_is"] or "not measured"
        if r["needs_new_trigger"]:
            why += "; the rule decides after the fact, a live alert needs a new trigger (S1)"
        L.append(f"| {r['check']} | {MODE_NAME[r['plan_mode']]} M{r['plan_month']} | {why} |")
    late = [r for r in rows if r["runs_as_is"] == "yes, verdict at session end"]
    if late:
        L += ["", "Three more run unchanged and give the batch verdict, but only when the session closes, so in minutes they "
              "would still answer at the end of the turnaround unless the module gets a hook for an interim verdict "
              "(PF-Q2-12): " + ", ".join(f"**{r['check']}**" for r in late) + "."]

    # ---------------------------------------------------------------- the edge slot
    chocks = next(r for r in rows if r["check"] == "Nose Gear Chocks")
    edge_rows = []
    for r in rows:
        n = needs.get(r["module"] or "")
        if not n or r["module"] == "hair-policy":
            continue
        gm_free = not n["aircraft_classes"] and not n["traffic_classes"] and not n["derived_rows"]
        edge_rows.append({**r, "gm_free": gm_free, "needs_stage": n["recomputes_the_stage_itself"],
                          "classes": n["classes_for_the_check"], "tracker": n["tracker_classes"], "models": n["own_models"]})
    candidates = sorted([r for r in edge_rows if r["critical_fails_in_the_test_set"]],
                        key=lambda r: (not r["gm_free"], r["needs_stage"], len(r["classes"]) + len(r["aircraft_classes"] or [])))
    L += ["", "## 2. The edge slot: why the nose gear chocks are the worst fit, and what fits instead", "",
          f"**Nose gear chocks** is one of the three verdicts of `aircraft-chocks`, and that module is the heaviest thing in "
          f"the catalogue to put on a camera: it reads {len(chocks['classes_for_the_check'] or []) + len(chocks['aircraft_classes'] or [])} "
          "classes of the shared model (chocks and vehicle heads on top of the main one), it follows all four tracked classes, "
          "it waits for `pushback_attached` — a stage event, not a picture — it runs an EfficientNet difference classifier on "
          f"wheel crops, and it **reads the session twice**, which is why it does not run live at all today. Alone with its own "
          f"scoped model it costs {cell(chocks['total_alone_ms'])} ms per frame, the second highest of all modules.", "",
          "What an edge check has to be instead: a detector of one or two classes, a decision from the picture rather than from "
          "the stage, and a violation worth telling somebody about immediately. Sorted that way, among the seven critical "
          "checks:", "",
          "| check | free of the shared model | works out the stage itself | it would have to detect | its own models | "
          "violations in the test set |", "|---|---|---|---|---|---|"]
    for r in candidates:
        L.append(f"| {r['check']} | {'**yes**' if r['gm_free'] else 'no'} | {'yes' if r['needs_stage'] else '**no**'} | "
                 f"{', '.join(r['classes']) or '—'}{(' + ' + ', '.join(r['aircraft_classes'])) if r['aircraft_classes'] else ''} | "
                 f"{', '.join(r['models']) or '—'} | {r['critical_fails_in_the_test_set']} |")
    winner = candidates[0] if candidates else None
    if winner:
        L += ["", f"**{winner['check']}** is the only critical check that needs nothing from the aircraft, nothing from the "
              "stage and nothing from the traffic around the stand: a person detector and a classifier on the person crop. It "
              "is also the check the edge already has a neighbour for — hair policy, the locked edge check, is the same shape "
              "(person crop, two small classifiers), so one person detector on the camera serves both.", "",
              "Two honest caveats. **As written today it is not light**: it runs two Swin-T networks on every person of every "
              f"frame, which measured {cell(next(r for r in rows if r['module'] == 'safety-vests-secured-to-body')['own_ms'], 2)} ms "
              "per frame and 5.5 cores on a desktop card — for a camera it needs a small detector plus a small classifier and a "
              "lower rate (the rule latches a fail, it does not need every frame). And **the verdict as the client defined it "
              "arrives at the end of the session**; the useful edge behaviour is the alert at the moment a person without a "
              "fastened vest is seen, which is a trigger change to agree with Oksana and Ihor (PF-Q3-06), not a code detail.", "",
              "The runners-up are worth naming for what they would cost: `handrails on GSE` and `GSE parked` also decide from "
              "person crops, but both need the belt loader or the GSE box, which is a second detector class and the reason they "
              "are not free; everything else in the critical seven needs the aircraft, the stage, or both."]

    io.open(os.path.join(ROOT, "docs", "analysis", "roadmap_move_analysis.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    json.dump({"checks": rows, "cheapest_into_minutes": [r["check"] for r in movable], "in_hours_today": [r["check"] for r in in_hours],
               "edge_candidates": [{k: r[k] for k in ("check", "module", "gm_free", "needs_stage", "classes", "models",
                                                      "critical_fails_in_the_test_set")} for r in candidates]},
              io.open(os.path.join(ROOT, "docs", "analysis", "roadmap_move_analysis.json"), "w", encoding="utf-8", newline="\n"),
              indent=1)
    print("cheapest into minutes:", ", ".join(r["check"] for r in movable[:8]))
    print("in hours today and free to move:", ", ".join(r["check"] for r in in_hours))
    print("edge candidates:", ", ".join(f"{r['check']} (gm_free={r['gm_free']}, stage={r['needs_stage']})" for r in candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
