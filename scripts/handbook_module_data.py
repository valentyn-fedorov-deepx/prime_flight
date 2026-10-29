"""The facts of every check page of the plain-language handbook in one file, so every writer uses the same numbers.

One entry per row of the client's table (DX_Modules logic.xlsx, sheet "Updated logic 2025", through
docs/05_module_logic.md): 31 checks under the client's own names, in the table's order and stages. Each carries the
module that computes it (27 modules; one module gives three checks, one check is combined from two others, one has a
module that does not run in production), the stages it looks at, the client's rules, accuracy on the monthly test
report, the production version, the code-review finding and the sources to read.

    python scripts/handbook_module_data.py            # writes docs/handbook/_data/modules.json

Run it again after a new monthly report: the accuracy fields change, nothing else.
"""

from __future__ import annotations

import collections
import difflib
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.testset import common as TC  # noqa: E402

OUT = os.path.join(ROOT, "docs", "handbook", "_data", "modules.json")
STAGES = ["Pre-arrival", "Arrival", "Post-arrival", "Download", "Upload", "Pre-departure", "Departure"]
# the stages of the client's table -> (stage key, folder of the check pages); the table spells "disconnet"
TABLE_STAGES = {
    "Pre-arrival stage": ("Pre-arrival", "1 Pre-arrival stage"),
    "Arrival stage": ("Arrival", "2 Arrival stage"),
    "Post-arrival stage": ("Post-arrival", "3 Post-arrival stage"),
    "Download stage": ("Download", "4 Download stage"),
    "Upload stage": ("Upload", "5 Upload stage"),
    "Pre-departure stage": ("Pre-departure", "6 Pre-departure stage"),
    "Departure stage (Tow-Bar disconnet)": ("Departure", "7 Departure stage (Tow-Bar disconnect)"),
}
STAGE_PLAIN = {
    "Pre-arrival": "before the aircraft arrives",
    "Arrival": "arrival",
    "Post-arrival": "after the aircraft stops",
    "Download": "unloading",
    "Upload": "loading",
    "Pre-departure": "before departure",
    "Departure": "departure and pushback",
}
PLAIN_TITLE = {
    "3-stop-brake-check": "Three-stop brake check",
    "aircraft-chocks": "Aircraft wheel chocks: placed on arrival, removed only after the pushback is attached",
    "all-cargo-bin-doors-opened-and-verified": "All cargo bin doors opened and verified",
    "beltloader-chocks": "Belt loader forward chock stays in place until the belt loader backs away",
    "bl_rear_cone": "Belt loader rear cone placed after the belt loader is in place",
    "chocks-and-cones-available-and-staged-for-arrival": "Chocks and cones ready before the aircraft arrives",
    "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed":
        "Conditioned air hose removed 10 minutes before departure and stowed",
    "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked":
        "Cones removed only after all service vehicles are clear of the aircraft and chocked",
    "cones-placed-in-proper-positions-and-timely": "Cones placed in the right positions on time",
    "crew-present-10-minutes-prior-to-aircraft-arrival": "Crew present 10 minutes before the aircraft arrives",
    "fod-walk-completed": "Foreign object debris walk completed",
    "gse-chocks": "Motorized service vehicles parked and chocked",
    "hair-policy": "Hair policy",
    "hand-signals": "Service vehicles guided to the aircraft with approved hand signals",
    "handrails-on-gse-being-used": "Handrails on service vehicles being used",
    "lead-marshaller-and-wing-walkers-in-position": "Lead marshaller and wing walkers in position",
    "pin-verification": "Pushback driver checks the steering bypass pin",
    "post-arrival-aircraft-walk-around-inspection-completed-accurately": "Walk-around inspection after arrival",
    "pre-arrival-safety-huddle": "Safety huddle at the huddle cone",
    "pre-departure-walk-around-completed": "Walk-around inspection before departure",
    "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready":
        "Pushback waits until the wing walkers are in place and ready",
    "pushback-pathway-confirmed-clear-of-obstacles": "Pushback path clear of obstacles",
    "safety-handrails-fully-extended": "Safety handrails fully extended and used",
    "safety-vests-secured-to-body": "Safety vests worn and fastened",
    "safety-zone-confirmed-clear": "Safety zone clear before the aircraft arrives",
    "steering-by-pass-pin-installed-or-steering-otherwise-bypassed": "Steering bypass pin installed",
    "wing-walkers-in-proper-position-and-using-approved-wands":
        "Wing walkers in position with approved wands during pushback",
}
TASK_PLAIN = {"aircraftchockfront": "Nose wheel chock placed right after arrival",
              "aircraftchockback": "Main gear chocks removed only after the pushback is attached",
              "nose_wheel_chock": "Nose wheel chock removed only after the pushback is attached",
              "seat_belts": "Seat belts worn on the service vehicles that have them",
              "stopbrake-and-handsignals": "Belt loader approach: three brake stops and hand signals"}
# stages a check looks at, where they are not simply the stages of its module
CHECK_STAGES = {"aircraftchockfront": ["Arrival"],
                "aircraftchockback": ["Arrival", "Pre-departure"],
                "nose_wheel_chock": ["Pre-departure", "Departure"],
                "seat_belts": ["Post-arrival"]}
TASK_BY_NAME = {"seat belts used on all gse equipped with seat belts": "seat_belts"}  # TASK_CHECK has no name for it


def read(rel: str) -> str:
    return io.open(os.path.join(ROOT, rel), encoding="utf-8").read()


def glance(md: str) -> dict:
    sec = re.search(r"^## At a glance\s*\n(.*?)(?=^## )", md, flags=re.S | re.M)
    rows = {}
    for line in (sec.group(1).splitlines() if sec else []):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 2 and c[0] and not set(c[0]) <= set("-: "):
            rows[c[0]] = c[1]
    return rows


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def client_rules() -> list:
    rows, in_tab = [], False
    for line in read("docs/05_module_logic.md").splitlines():
        if line.startswith("| Stage | Check"):
            in_tab = True
            continue
        if in_tab:
            if not line.startswith("|"):
                break
            if line.startswith("|---"):
                continue
            c = [re.sub(r"\s+/\s+", " ", x.strip()).strip(" /") for x in line.strip().strip("|").split("|")]
            rows.append(dict(stage=c[0], check=c[1], repo=c[2], tier=c[3], cameras=c[4], production_ready=c[5],
                             pass_=c[6], fail=c[7], not_observed=c[8], not_observed_blocked=c[9],
                             notes=c[10] if len(c) > 10 else ""))
    return rows


def rule_for(check: str, rules: list) -> dict | None:
    keys = {norm(r["check"]): r for r in rules}
    k = norm(check)
    if k in keys:
        return keys[k]
    for kk, r in keys.items():
        if kk.startswith(k) or k.startswith(kk):
            return r
    m = difflib.get_close_matches(k, keys, n=1, cutoff=0.6)
    return keys[m[0]] if m else None


def task_for(check: str) -> str | None:
    k = norm(check)
    if k in TASK_BY_NAME:
        return TASK_BY_NAME[k]
    for task, name in TC.TASK_CHECK.items():
        n = norm(name or "")
        if n and (n == k or n.startswith(k) or k.startswith(n)):
            return task
    return None


def module_facts() -> dict:
    """repository -> what the technical page and the source list say about its module."""
    review = {}
    for line in read("docs/analysis/module_review_2026-10.md").splitlines():
        m = re.match(r"\| ((?:M\d\d)[A-C–\-]*|HP) · [^|]+ \| (.+) \|$", line)
        if m:
            review[m.group(1)] = m.group(2).strip()
    facts = {}
    for line in read("docs/modules/_SOURCES.md").splitlines():
        m = re.match(r"\| ((?:M\d\d[A-C]?(?:, )?)+|HP) \| ([^|]+) \| ([^|]+) \| `([^`]+)` \|", line)
        if not m:
            continue
        ids, repo, production, code_dir = (x.strip() for x in m.groups())
        page = f"docs/modules/{repo}.md"
        if not os.path.exists(os.path.join(ROOT, page)):
            continue
        g = glance(read(page))
        named = [x.strip().lower() for x in re.split(r"[,;]", g.get("Stage", ""))]
        first = ids.split(",")[0].strip()
        facts[repo] = {
            "internal_ids": ids,
            "stages": [s for s in STAGES if s.lower() in named],
            "production_version": production,
            "glance": g,
            "code_review_finding": review.get("M02A–C" if first.startswith("M02") else first, ""),
            "sources": {"technical_page": page, "code": f"external/{code_dir}", "client_rules": "docs/05_module_logic.md",
                        "code_review": "docs/analysis/module_review_2026-10.md",
                        "real_time": ["docs/04_modules.md", "docs/analysis/rt_module_selection.md",
                                      "docs/analysis/rt_module_cost.md"]},
        }
    return facts


def main() -> int:
    task_module, _module_tasks = TC.load_task_modules()
    report = json.load(io.open(os.path.join(ROOT, "out", "testset", "monthly_report_parsed.json"), encoding="utf-8"))
    acc = collections.defaultdict(collections.Counter)
    for e in report["events"]:
        for task, v in e["tasks"].items():
            truth, new = v.get("true"), v.get("new")
            if truth in ("pass", "fail", "notObserved") and new:
                a = acc[task]
                a["labelled"] += 1
                a["correct"] += new == truth
                a["fails_labelled"] += truth == "fail"
                a["fails_caught"] += truth == "fail" and new == "fail"
    facts = module_facts()
    rows = client_rules()
    name_of_task = {task_for(r["check"]): r["check"] for r in rows}
    checks = []
    for order, r in enumerate(rows, 1):
        task = task_for(r["check"])
        repo = task_module.get(task)
        f = facts.get(repo, {})
        derived = [name_of_task.get(t) for t in TC.DERIVED.get(task, ())]
        if task in CHECK_STAGES:
            stages = CHECK_STAGES[task]
        elif derived:
            parts = [facts.get(task_module.get(t), {}).get("stages", []) for t in TC.DERIVED[task]]
            stages = [s for s in STAGES if any(s in p for p in parts)]
        else:
            stages = f.get("stages") or [TABLE_STAGES[r["stage"]][0]]
        a = acc.get(task)
        stage_key, folder = TABLE_STAGES[r["stage"]]
        file_name = r["check"].replace("/", "-")  # no slash in a file name: "A/C" -> "A-C"
        checks.append({
            "order": order,
            "name": r["check"],
            "file_name": file_name,
            "stage": folder.split(" ", 1)[1],
            "stage_key": stage_key,
            "folder": folder,
            "task": task,
            "repository": repo,
            "derived_from": derived or None,
            "other_checks_of_module": [x["check"] for x in rows
                                       if x["check"] != r["check"] and repo and task_module.get(task_for(x["check"])) == repo],
            "internal_ids": f.get("internal_ids", ""),
            "plain_name": TASK_PLAIN.get(task) or PLAIN_TITLE.get(repo) or r["check"],
            "stages": stages,
            "stages_plain": [STAGE_PLAIN[s] for s in stages],
            "client_rule": r,
            "monthly_test": None if not a else {
                "correct": a["correct"], "labelled": a["labelled"],
                "percent": round(100 * a["correct"] / a["labelled"]),
                "fails_labelled": a["fails_labelled"], "fails_caught": a["fails_caught"]},
            "output": f"docs/handbook/system/modules/{folder}/{file_name}.md",
            "production_version": f.get("production_version", ""),
            "glance": f.get("glance", {}),
            "code_review_finding": f.get("code_review_finding", ""),
            "sources": f.get("sources", {"client_rules": "docs/05_module_logic.md"}),
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = {"monthly_test": {"source": "monthly test report (continuous-integration job of the client's monthly validation)",
                            "turnarounds": len(report["events"])},
           "client_table": "DX_Modules logic.xlsx, sheet \"Updated logic 2025\" (docs/05_module_logic.md)",
           "checks": checks}
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    no_task = [c["name"] for c in checks if not c["task"]]
    modules = sorted({c["repository"] for c in checks if c["repository"]})
    print(f"{len(checks)} checks, {len(modules)} modules -> {OUT}; checks without a monthly-test task: {no_task}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
