"""The facts of every module page of the plain-language handbook in one file, so every writer uses the same numbers:
plain title, turnaround stages, the client's rules, accuracy on the monthly test report, the production version, the
code-review finding and the sources to read.

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
STAGE_FOLDER = {
    "Pre-arrival": "1 Before the aircraft arrives",
    "Arrival": "2 Arrival",
    "Post-arrival": "3 After the aircraft stops",
    "Download": "4 Unloading and loading",
    "Upload": "4 Unloading and loading",
    "Pre-departure": "5 Before departure",
    "Departure": "6 Departure and pushback",
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
TASK_PLAIN = {"aircraftchockfront": "nose wheel chock placed right after arrival",
              "aircraftchockback": "main gear chocks removed only after the pushback is attached",
              "nose_wheel_chock": "nose wheel chock removed only after the pushback is attached"}


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
            rows.append(dict(stage=c[0], check=c[1], tier=c[3], cameras=c[4], pass_=c[6], fail=c[7], not_observed=c[8],
                             not_observed_blocked=c[9], notes=c[10] if len(c) > 10 else ""))
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


def main() -> int:
    task_module, module_tasks = TC.load_task_modules()
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
    review = {}
    for line in read("docs/analysis/module_review_2026-10.md").splitlines():
        m = re.match(r"\| ((?:M\d\d)[A-C–\-]*|HP) · [^|]+ \| (.+) \|$", line)
        if m:
            review[m.group(1)] = m.group(2).strip()
    rules = client_rules()
    modules = []
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
        stages = [s for s in STAGES if s.lower() in named]
        first = ids.split(",")[0].strip()
        rid = "M02A–C" if first.startswith("M02") else first
        checks = []
        for task in module_tasks.get(repo, []):
            client_name = TC.TASK_CHECK.get(task, task)
            a = acc.get(task)
            checks.append({
                "client_check_name": client_name,
                "plain_name": TASK_PLAIN.get(task, PLAIN_TITLE[repo]),
                "client_rule": rule_for(client_name, rules),
                "monthly_test": None if not a else {
                    "correct": a["correct"], "labelled": a["labelled"],
                    "percent": round(100 * a["correct"] / a["labelled"]),
                    "fails_labelled": a["fails_labelled"], "fails_caught": a["fails_caught"]},
            })
        folder = STAGE_FOLDER[stages[0]] if stages else "7 Other"
        modules.append({
            "repository": repo,
            "internal_ids": ids,
            "plain_title": PLAIN_TITLE[repo],
            "stages": stages,
            "stages_plain": [STAGE_PLAIN[s] for s in stages],
            "folder": folder,
            "output": f"docs/handbook/system/modules/{folder}/{PLAIN_TITLE[repo].replace(':', ' -')}.md",  # no colons in Windows file names
            "production_version": production,
            "glance": g,
            "checks": checks,
            "code_review_finding": review.get(rid, ""),
            "sources": {"technical_page": page, "code": f"external/{code_dir}", "client_rules": "docs/05_module_logic.md",
                        "code_review": "docs/analysis/module_review_2026-10.md",
                        "real_time": ["docs/04_modules.md", "docs/analysis/rt_module_selection.md",
                                      "docs/analysis/rt_module_cost.md"]},
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = {"monthly_test": {"source": "monthly test report (continuous-integration job of the client's monthly validation)",
                            "turnarounds": len(report["events"])},
           "modules": modules}
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    missing = [m["repository"] for m in modules if any(c["client_rule"] is None for c in m["checks"])]
    print(f"{len(modules)} modules -> {OUT}; checks without a matched client rule: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
