"""Shared definitions for the monthly test-set run: report task names, check names, module routing, verdict rules.

Sources:
  * the monthly CI report (`out/testset/monthly_report_parsed.json`, parsed from `monthly-html-report.html`): 69 events,
    31 task columns, per task the videos the CI ran it on, the previous / new / validated verdicts;
  * `external/db_worker/ml_setting/ml_global_config.json`: which module produces which task;
  * `docs/05_module_logic.md`: the client's camera split per check (Aircraft / Jet → Cone / Wing / Both / -) and the
    two-camera merge rule (Fail > Pass > Not observed);
  * module code: the order of the tasks a multi-task module returns (`aircraft-chocks` returns
    `[front_placed, main_status, front_removed]`).
"""

from __future__ import annotations

import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# report task name -> check name in the client's camera split table
TASK_CHECK = {
    "wing-walkers-in-proper-position-and-using-approved-wands": "Wing walkers in proper position and using approved wands",
    "crew-present-10-minutes-prior-to-aircraft-arrival": "Crew present 10 minutes prior to aircraft arrival",
    "chocks-and-cones-available-and-staged-for-arrival": "Chocks and cones available and staged for arrival",
    "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed": "Conditioned air removed 10 mins prior to departure and properly stowed",
    "pushback-pathway-confirmed-clear-of-obstacles": "Pushback pathway confirmed clear of obstacles",
    "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked": "Cones are removed only after all GSE is clear of A/C and chocked",
    "stopbrake": "3 stop brake check",
    "aircraftchockfront": "Nose gear chocks applied immediately",
    "aircraftchockback": "Main gear chocks removed only after aircraft is attached to pushback",
    "nose_wheel_chock": "Nose wheel chock removed from aircraft",
    "cargo_doors": "All cargo bin doors opened and verified",
    "loaderchock": "Belt loader forward chock remained in place until unit is backed up clear of aircraft",
    "cones_in_position": "Cones placed in proper positions and timely",
    "beltloader_rear_cone": "Beltloader rear cone positioned after BL is in place to alert clearance",
    "fodwalk": "FOD walk completed",
    "gse_chocks": "Motorized GSE parked and properly chocked",
    "handsignals": "All GSE guided into aircraft using approved hand signals",
    "handrails": "Handrails on GSE being used",
    "wingwalker": "Lead marshaller and wing walkers in correct position",
    "pinveref": "Pushback operator verifies steering bypass pin installation",
    "huddle": "Safety huddle conducted at huddle cone",
    "pushback": "Pushback does not start until wing walkers are in place and ready",
    "safetyhandrails": "Safety handrails fully extended and used",
    "safetyvests": "Employees wearing safety vests secured to body",
    "safetyzone": "Safety zone confirmed clear",
    "steering": "Steering by-pass pin installed, or steering otherwise bypassed",
    "hair-policy": "Hair policy",
    "post-arrival-aircraft-walk-around-inspection-completed-accurately": "Post-arrival aircraft walk around inspection completed accurately",
    "pre-departure-walk-around-completed": "Pre-departure walk around completed",
    "stopbrake-and-handsignals": "Proper beltloader approach including 3 stop brake check and handsignals",
    "seat_belts": None,
}

# tasks computed from other tasks' event verdicts (not a module)
DERIVED = {"stopbrake-and-handsignals": ("stopbrake", "handsignals")}

# extra modules not listed in db_worker's ml_global_config
EXTRA_TASK_MODULE = {"hair-policy": "hair-policy"}

# task order of multi-task module outputs, from the module code (overrides the config order if they differ)
TASK_ORDER_OVERRIDE = {"aircraft-chocks": ["aircraftchockfront", "aircraftchockback", "nose_wheel_chock"]}

VERDICTS = ("pass", "fail", "notObserved")


def load_report(path: str | None = None) -> dict:
    path = path or os.path.join(ROOT, "out", "testset", "monthly_report_parsed.json")
    return json.load(io.open(path, encoding="utf-8"))


def load_task_modules(path: str | None = None) -> tuple[dict, dict]:
    """(task -> module, module -> [tasks in output order])."""
    path = path or os.path.join(ROOT, "external", "db_worker", "ml_setting", "ml_global_config.json")
    cfg = json.load(io.open(path, encoding="utf-8"))["models"]
    task_module, module_tasks = {}, {}
    for module, m in cfg.items():
        names = [t["name"] for t in m["tasks"]]
        module_tasks[module] = TASK_ORDER_OVERRIDE.get(module, names)
        for n in names:
            task_module[n] = module
    for task, module in EXTRA_TASK_MODULE.items():
        task_module[task] = module
        module_tasks.setdefault(module, [task])
    return task_module, module_tasks


def parse_camera_split(md_path: str | None = None) -> dict:
    """check name -> (aircraft cameras, jet cameras) from the 'Task split by cameras' table."""
    md_path = md_path or os.path.join(ROOT, "docs", "05_module_logic.md")
    text = io.open(md_path, encoding="utf-8").read()
    section = text.split("## Task split by cameras", 1)[1].split("\n## ", 1)[0]
    split = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] not in ("Check", "") and not set(cells[0]) <= set("-"):
            split[cells[0]] = (cells[1], cells[2])
    return split


def normalize_status(value) -> str | None:
    """Module status string -> 'pass' | 'fail' | 'notObserved' (None for missing)."""
    if value is None:
        return None
    s = re.sub(r"[\s_\-]", "", str(value)).lower()
    if s == "pass":
        return "pass"
    if s == "fail":
        return "fail"
    if s.startswith("notobserved") or s.startswith("no"):
        return "notObserved"
    return str(value)


def merge_cameras(verdicts: list) -> str | None:
    """Client merge rule for a task run on several cameras: Fail > Pass > Not observed. None if nothing ran."""
    vs = [v for v in verdicts if v is not None]
    if not vs:
        return None
    if "fail" in vs:
        return "fail"
    if "pass" in vs:
        return "pass"
    if all(v == "notObserved" for v in vs):
        return "notObserved"
    return vs[0]


def derive_stopbrake_handsignals(stopbrake: str | None, handsignals: str | None) -> str | None:
    """Rule inferred from the report's 'New output' column (69 events, no exception): pass only if both pass,
    Not observed only if both are Not observed, otherwise fail."""
    if stopbrake is None or handsignals is None:
        return None
    if stopbrake == "pass" and handsignals == "pass":
        return "pass"
    if stopbrake == "notObserved" and handsignals == "notObserved":
        return "notObserved"
    return "fail"


def task_statuses_from_run(run: dict, module_tasks: list) -> dict:
    """run_module.py result JSON -> {task: normalized status} (empty if the run failed)."""
    if not run or "error" in run:
        return {}
    status = run.get("status")
    if isinstance(status, list):
        return {t: normalize_status(s) for t, s in zip(module_tasks, status)}
    if len(module_tasks) != 1:
        return {module_tasks[0]: normalize_status(status)}
    return {module_tasks[0]: normalize_status(status)}
