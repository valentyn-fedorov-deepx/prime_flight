"""The order to move checks into real time, from what the campaign measured, and the roadmap page rewritten to match.

The order is not a wish list: a stream pays for a detector head or a tracked class **once**, and every check that needs the
same one after that costs only its own work. So the plan is built greedily on the marginal cost of each next check —
`GM[heads so far + its heads] - GM[heads so far]` plus the same for the tracked classes plus its own milliseconds
(`docs/analysis/rt_environment.md`) — and the checks that need no rework and answer during the turnaround come first.

Three checks are seeded at the front because the branch already runs them together live with their alert hooks planned
(3-stop, pushback pathway, pushback wing walkers: `tasks/notes/PF-Q2-10.md`, `docs/analysis/rt_module_cost.md`).

Waves, in the order the work unblocks itself:

  * **A** runs unchanged, answers during the turnaround, no new trigger — integration work only;
  * **B** runs unchanged but only answers when the session closes: needs the interim-verdict hook (PF-Q2-12);
  * **C** runs unchanged but the rule decides after the fact: needs a trigger agreed with the client (PF-Q3-06);
  * **D** does not run live at all yet: the module reads the session twice (PF-Q3-04, PF-Q2-11);
  * **E** stays in hours: not hosted by the branch, or derived from a check that is still in hours.

    python scripts/rt_priority_plan.py [--write-roadmap]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.roadmap_move_analysis import CHECK_TO_MODULE, TRIGGER_CHANGE, roadmap  # noqa: E402

ROADMAP = os.path.join(ROOT, "docs", "planning", "RV_scope_timeline.html")
HEAD_ORDER, CLASS_ORDER = ("gm", "chocks", "vehicle"), ("airplane", "beltloader", "gse", "person")
SEEDED = ["3-stop-brake-check", "pushback-pathway-confirmed-clear-of-obstacles",
          "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready"]
# the edge list, in the order the camera gets them. The nose gear chocks are off it: that verdict comes out of the heaviest
# module in the catalogue (two passes, two extra detector heads, four tracked classes, a stage event), while safety vests is
# the one critical check that needs nothing but a person and a crop — `docs/analysis/roadmap_move_analysis.md`.
EDGE_CHECKS = ("Hair Policy", "Safety vests")
WAVE_NOTE = {
    "A": "runs unchanged, answers during the turnaround, no new trigger",
    "B": "runs unchanged, but the verdict only comes when the session closes (interim-verdict hook, PF-Q2-12)",
    "C": "runs unchanged, but the rule decides after the fact (trigger change with the client, PF-Q3-06)",
    "D": "does not run live yet: the module reads the session twice (PF-Q3-04, PF-Q2-11)",
    "E": "stays in hours",
}


def load(path: str):
    return json.load(io.open(path, encoding="utf-8")) if os.path.exists(path) else None


def wave_of(cost: dict, module: str) -> str:
    runs = (cost.get(module) or {}).get("runs_in_real_time_as_is") or ""
    if runs.startswith("no") or not runs:
        return "D" if runs.startswith("no: two passes") else "E"
    if module in TRIGGER_CHANGE:
        return "C"
    if runs == "yes, verdict at session end":
        return "B"
    return "A"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-roadmap", action="store_true", help="rewrite the plan in docs/planning/RV_scope_timeline.html")
    ap.add_argument("--by-month", default="5,16,24", help="how many checks are in minutes by M3, M7, M12")
    ap.add_argument("--edge-by-month", default="1,2.5,3", help="how many checks are in seconds by M3, M7, M12 (2.5 by M7 puts "
                                                              "the second edge check on M6)")
    a = ap.parse_args()

    checks = roadmap()
    cost = {r["module"]: r for r in load(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"))["modules"]}
    env = load(os.path.join(ROOT, "docs", "analysis", "rt_environment.json"))
    gm_table, trk_table = env["price_list"], None
    gm_ms = load(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"))["gm_by_head_set_ms"]
    trk_ms = load(os.path.join(ROOT, "docs", "analysis", "rt_module_cost.json"))["tracker_by_tracked_classes_ms"]
    critical = {t["module"]: len(t["fails"]) for t in load(os.path.join(ROOT, "docs", "analysis", "critical_label_queue.json"))["tasks"]}
    price = {r["module"]: r for r in gm_table}

    def table_lookup(table: dict, wanted: set, order: tuple) -> float:
        key = "+".join(x for x in order if x in wanted)
        if key in table:
            return table[key]
        supersets = [v for k, v in table.items() if wanted <= set(k.split("+"))]
        return min(supersets) if supersets else max(table.values())

    # one row per check of the roadmap page; the three chock checks share one module
    rows = []
    for c in checks:
        module = CHECK_TO_MODULE.get(c["label"])
        r, p = cost.get(module), price.get(module)
        rows.append({"id": c["id"], "check": c["label"], "module": module, "locked": bool(c.get("lock")),
                     "plan_mode": c["mode"], "wave": "E" if not module else wave_of(cost, module),
                     "heads": set((r or {}).get("heads") or ["gm"]), "classes": set((r or {}).get("tracked") or ["airplane"]),
                     "own_ms": (r or {}).get("whole_event_ms", {}).get("module") or 0.0,
                     "verdict_arrives": (r or {}).get("verdict_arrives"), "critical": critical.get(module, 0),
                     "pixels": bool((p or {}).get("pixels")), "cpu_burst": (p or {}).get("cpu_cores_burst"),
                     "ram_gb": (p or {}).get("ram_gb")})
    hosted = {r["module"] for r in rows if r["wave"] == "E" and r["module"]}
    for r in rows:  # the walk-arounds and the derived belt loader task cannot move yet
        if r["module"] in (None, "hair-policy") or (r["module"] in hosted and r["wave"] == "E"):
            r["wave"] = "E"
        if r["module"] == "hand-signals":
            r["wave"] = "E"  # two passes AND a trigger change: it stays in hours until both are done

    # greedy order inside the minutes list: what the stream already pays for makes the next check cheaper
    order, heads, classes = [], {"gm"}, {"airplane"}
    left = [r for r in rows if r["wave"] in ("A", "B", "C", "D") and r["check"] not in EDGE_CHECKS]
    seeded = [r for m in SEEDED for r in left if r["module"] == m]
    for r in seeded:
        r["marginal_ms"] = round(table_lookup(gm_ms, heads | r["heads"], HEAD_ORDER) - table_lookup(gm_ms, heads, HEAD_ORDER)
                                 + table_lookup(trk_ms, classes | r["classes"], CLASS_ORDER) - table_lookup(trk_ms, classes, CLASS_ORDER)
                                 + r["own_ms"], 1)
        r["seeded"] = True
        heads |= r["heads"]
        classes |= r["classes"]
        order.append(r)
        left.remove(r)
    wave_rank = {"A": 0, "B": 1, "C": 2, "D": 3}
    while left:
        for r in left:
            r["same_module_already_in"] = any(x["module"] == r["module"] for x in order)
            r["marginal_ms"] = round(table_lookup(gm_ms, heads | r["heads"], HEAD_ORDER) - table_lookup(gm_ms, heads, HEAD_ORDER)
                                     + table_lookup(trk_ms, classes | r["classes"], CLASS_ORDER) - table_lookup(trk_ms, classes, CLASS_ORDER)
                                     + r["own_ms"], 1)
        nxt = min(left, key=lambda r: (wave_rank[r["wave"]], not r["same_module_already_in"], r["marginal_ms"], -r["critical"]))
        heads |= nxt["heads"]
        classes |= nxt["classes"]
        order.append(nxt)
        left.remove(nxt)
    edge = [r for name in EDGE_CHECKS for r in rows if r["check"] == name]
    stays = [r for r in rows if r not in order and r not in edge]

    # ---------------------------------------------------------------- the document
    def fmt(v, d=1):
        return "—" if v is None else f"{v:.{d}f}"

    milestones = [int(x) for x in a.by_month.split(",")]
    L = ["# The order to move the checks into minutes", "",
         "Generated by `scripts/rt_priority_plan.py` from the measurements (`rt_module_cost.json`, `rt_environment.json`, "
         "`critical_label_queue.json`) and the roadmap page. Do not edit by hand.", "",
         "## How the order is built", "",
         "A stream pays for a detector head or a tracked class once. The first check that needs the belt loader pays 15.7 ms "
         "for it; every belt loader check after that costs only its own work, which is under 2 ms for most of them. So the "
         "order is greedy on the **marginal** cost of the next check, not on its total cost, and the clusters fall out by "
         "themselves. Inside that, checks that need no rework come before those that do.", "",
         "The three checks the branch already runs together live, with their alert hooks planned, are seeded at the front: "
         + ", ".join(f"`{m}`" for m in SEEDED) + ".", "",
         "| # | check | wave | what it adds to the frame path | its own work | verdict arrives | violations in the test set |",
         "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(order, 1):
        L.append(f"| {i} | {r['check']}{' *(already running)*' if r.get('seeded') else ''} | {r['wave']} | "
                 f"+{fmt(r['marginal_ms'])} ms | {fmt(r['own_ms'], 2)} ms | {r['verdict_arrives'] or '—'} | "
                 f"{r['critical'] or '—'} |")
    L += ["", "Waves: " + "; ".join(f"**{k}** — {v}" for k, v in WAVE_NOTE.items()) + ".", "",
          "## What each wave needs from the platform", "",
          "| wave | checks | what has to be in place |", "|---|---|---|"]
    counts = {}
    for r in order:
        counts.setdefault(r["wave"], []).append(r["check"])
    needs = {
        "A": "the causal main-aircraft rule of the shared rows (PF-Q2-02: today it costs 2.9 points of accuracy on about one "
             "event in six), the stage detector for gating (PF-Q1-03), and a host that keeps 8 fps (PF-Q2-01: about 8 vCPU of a "
             "modern generation, 12 GB, a card no slower than a T4 with TensorRT heads)",
        "B": "everything wave A needs plus the interim-verdict hook: these three give the batch verdict, but only when the "
             "camera stops (PF-Q2-12)",
        "C": "everything wave A needs plus a trigger agreed with Oksana and Ihor: the rule as written decides after the fact, "
             "so a live alert is a new definition, not a port (PF-Q3-06)",
        "D": "the second pass removed: a stage event instead of the replay for the chock checks and pin verification "
             "(PF-Q3-04), single-pass safety zone (PF-Q2-11)",
    }
    for w in ("A", "B", "C", "D"):
        if counts.get(w):
            L.append(f"| {w} | {len(counts[w])}: {', '.join(counts[w])} | {needs[w]} |")
    L += ["", "## What stays in hours", "",
          "| check | why |", "|---|---|"]
    why_stay = {"hand-signals": "reads the session twice **and** decides after the fact: both a rework and a trigger change",
                "post-arrival-aircraft-walk-around-inspection-completed-accurately": "not hosted by the branch (its own Python "
                "environment), and post by nature: it needs the whole walk-around",
                "pre-departure-walk-around-completed": "not hosted by the branch (its own Python environment), and post by "
                "nature: the walk-around is judged on the whole lap",
                None: "derived from two other checks; it can only move when both of them have"}
    for r in stays:
        L.append(f"| {r['check']} | {why_stay.get(r['module'], 'not hosted by the branch')} |")
    L += ["", "## The edge list", "",
          "On the camera: " + ", ".join(f"**{r['check']}**" for r in edge) + ". The nose gear chocks were taken off it and "
          "joined their two sibling verdicts in wave D, because all three come out of `aircraft-chocks` — the module that "
          "reads the session twice, needs the chocks and vehicle heads on top of the main one, follows all four tracked "
          "classes and waits for a stage event. Safety vests took the slot: it is the only critical check that needs nothing "
          "from the aircraft, nothing from the stage and nothing from the traffic around the stand, and the camera already "
          "runs a person crop for hair policy, so one detector serves both (`roadmap_move_analysis.md`).", "",
          "It is not free either: as written it runs two Swin-T networks on every person of every frame (18.75 ms per frame, "
          "5.5 cores on a desktop card), so the camera needs a small detector, a small classifier and a lower rate — the rule "
          "latches a fail, it does not need every frame. And the client's verdict arrives at the end of the session; the "
          "useful behaviour on a camera is the alert at the moment somebody is seen without a fastened vest, which is a "
          "trigger to agree, not a port (PF-Q3-06).", "",
          "## The plan on the page", "",
          f"`{os.path.relpath(ROADMAP, ROOT)}` now carries this order, and the four checks that were sitting in hours although "
          "they already run live (crew present, safety huddle, chocks and cones staged, cargo doors) are in minutes. The page's "
          f"own pace parameters are set to {milestones[0]} checks in minutes by M3, {milestones[1]} by M7, {milestones[2]} by "
          "M12 — the measurement is what moved them: these modules are not being rewritten, they are being wired in and "
          "checked, so the constraint moves to the platform work (the aircraft rule, the stage detector, alerts, the host).",
          "", "Nothing here says the verdicts get better. They do not: a check that is Not observed in hours is Not observed in "
          "minutes. What changes is when the answer arrives, and that only becomes an alert once the alert service is there "
          "(M6 on the page)."]
    io.open(os.path.join(ROOT, "docs", "analysis", "rt_priority_plan.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    json.dump({"order": [{k: r[k] for k in ("id", "check", "module", "wave", "marginal_ms", "own_ms", "critical",
                                            "verdict_arrives")} for r in order],
               "stays_in_hours": [r["check"] for r in stays], "edge": [r["check"] for r in edge],
               "by_month": milestones},
              io.open(os.path.join(ROOT, "docs", "analysis", "rt_priority_plan.json"), "w", encoding="utf-8", newline="\n"), indent=1)

    if a.write_roadmap:
        text = io.open(ROADMAP, encoding="utf-8").read()
        data = json.loads(re.search(r"const DATA = (\[.*?\]);", text, re.S).group(1))
        by_id = {d["id"]: d for d in data}
        new = []
        for r in edge:
            item = by_id[r["id"]]
            item["mode"], item["lock"] = "edge", True
            new.append(item)
        for r in order:  # the minutes list, in this order
            item = by_id[r["id"]]
            item["mode"], item["lock"] = "rt", False
            new.append(item)
        for r in stays:
            item = by_id[r["id"]]
            item["mode"] = "post"
            new.append(item)
        new += [d for d in data if d.get("kind") != "check"]
        assert len(new) == len(data), (len(new), len(data))
        text = text.replace(re.search(r"const DATA = (\[.*?\]);", text, re.S).group(1), json.dumps(new), 1)
        edge_ms = [float(x) if "." in x else int(x) for x in a.edge_by_month.split(",")]
        params = re.search(r"const PARAMS = \[(.*?)\];", text, re.S).group(0)
        new_params = re.sub(r'\["s3", "Minutes: how many by M3", \d+\], \["s7", "Minutes: how many by M7", \d+\], \["s12", "Minutes: how many by M12", \d+\]',
                            f'["s3", "Minutes: how many by M3", {milestones[0]}], ["s7", "Minutes: how many by M7", {milestones[1]}], '
                            f'["s12", "Minutes: how many by M12", {milestones[2]}]', params)
        new_params = re.sub(r'\["e3", "Seconds: how many by M3", [\d.]+\], \["e7", "Seconds: how many by M7", [\d.]+\], '
                            r'\["e12", "Seconds: how many by M12", [\d.]+\]',
                            f'["e3", "Seconds: how many by M3", {edge_ms[0]}], ["e7", "Seconds: how many by M7", {edge_ms[1]}], '
                            f'["e12", "Seconds: how many by M12", {edge_ms[2]}]', new_params)
        text = text.replace(params, new_params, 1)
        io.open(ROADMAP, "w", encoding="utf-8", newline="\n").write(text)
        print("roadmap rewritten:", os.path.relpath(ROADMAP, ROOT))

    print(f"minutes: {len(order)} checks, hours: {len(stays)}, edge: {len(edge)}")
    for i, r in enumerate(order, 1):
        print(f"{i:2d}. [{r['wave']}] +{fmt(r['marginal_ms'])} ms  {r['check']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
