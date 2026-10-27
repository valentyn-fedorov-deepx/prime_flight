"""Build the shared documentation folder (Word and Excel files) from the handbook in docs/handbook.

    python scripts/build_handbook.py --out G:/RampVision_Docs_v2

Every page of docs/handbook is a markdown file; this turns them into Word documents under the folder names people see:

    Start here.md                        -> Start here.docx
    teams/<team>/...                     -> 1 Teams/<Team>/...            (teams/cv/how-to -> 1 Teams/CV/How-to)
    system/...                           -> 2 System/...                  (system/shared -> 2 System/Shared parts)
    research/<team>/...                  -> 3 Research/<Team>/...

and adds what is computed: the owner and review line under every title (research reports carry their own date line), the
turnaround-stage picture and the latest monthly-test numbers on every check page, the numbers of the System overview,
the client rules (from the client's workbook through docs/05_module_logic.md) and the Modules index workbook.

Run `python scripts/handbook_module_data.py` first after a new monthly report. Files of the previous build that are no
longer produced are removed (the list is kept in out/handbook/manifest.json).
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import openpyxl  # noqa: E402
import pypandoc  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402

from handbook_lib import STAGE_ORDER, clean, md_table, polish, safe, stage_bar, style_tables  # noqa: E402

HB = os.path.join(ROOT, "docs", "handbook")
REF = os.path.join(HB, "_build", "reference.docx")
WORK = os.path.join(ROOT, "out", "handbook")
TEAM_NAMES = {"cv": "CV", "mlops": "MLOps", "backend": "Backend", "data": "Data", "edge": "Edge"}
FOLDER_NAMES = {"architecture": "Architecture", "requirements": "Requirements", "shared": "Shared parts",
                "modules": "Modules", "how-to": "How-to"}
STAGE_LABELS = {"Pre-arrival": "Before arrival", "Arrival": "Arrival", "Post-arrival": "After the stop",
                "Download": "Unloading", "Upload": "Loading", "Pre-departure": "Before departure",
                "Departure": "Departure"}
OWNERS = [  # first match on the source path
    ("system/modules/", "CV team (owner of the check to assign)"),
    ("system/shared/Pose models", "Valentyn Fedorov (CV)"),
    ("system/shared/", "Yurii Luchko (CV)"),
    ("system/architecture/Edge", "Vladyslav Ivashchuk (Edge) with Maksym Chernyshev (MLOps)"),
    ("system/architecture/", "Maksym Chernyshev (MLOps)"),
    ("teams/cv/", "Valentyn Fedorov (CV team lead)"),
    ("teams/mlops/", "Maksym Chernyshev (MLOps)"),
    ("teams/backend/", "Aryan Singh (Backend)"),
    ("teams/data/", "Denys Filimonov (Data)"),
    ("teams/edge/", "Vladyslav Ivashchuk (Edge)"),
    ("", "Valentyn Fedorov (lead)"),
]


def target(rel: str) -> str:
    """docs/handbook-relative markdown path -> output-relative .docx path."""
    parts = rel[:-3].split("/")
    if parts[0] == "teams":
        parts = ["1 Teams", TEAM_NAMES.get(parts[1], parts[1])] + [FOLDER_NAMES.get(p, p) for p in parts[2:]]
    elif parts[0] == "system":
        parts = ["2 System"] + [FOLDER_NAMES.get(p, p) for p in parts[1:]]
    elif parts[0] == "research":
        parts = ["3 Research", TEAM_NAMES.get(parts[1], parts[1])] + parts[2:]
    return "/".join(parts) + ".docx"


def reviewed(rel: str) -> str:
    """The date of the last commit of the page; today for a page not committed yet or changed since."""
    path = os.path.join(HB, *rel.split("/"))
    dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", path], capture_output=True, text=True).stdout
    last = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%ad", "--date=short", "--", path],
                          capture_output=True, text=True).stdout.strip()
    return dt.date.today().isoformat() if dirty or not last else last


class Build:
    def __init__(self, out: str):
        self.out = out
        self.made: list[str] = []

    def docx(self, rel_out: str, md: str, resdir: str | None = None) -> str:
        path = os.path.join(self.out, *rel_out.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        args = [f"--reference-doc={REF}"] + ([f"--resource-path={resdir}"] if resdir else [])
        pypandoc.convert_text(md.replace("<br>", "; "), "docx", format="gfm-raw_html", outputfile=path, extra_args=args)
        style_tables(path)
        self.made.append(path)
        return path

    def sheet(self, rel_out: str, title: str, header: list, rows: list, widths: list, links: dict) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = title
        ws.append(header)
        for r in rows:
            ws.append(list(r))
        for c in ws[1]:
            c.font = Font(name="Arial", bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F4E79")
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.font = Font(name="Arial")
                c.alignment = Alignment(vertical="top", wrap_text=True)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions
        for (r, c), link in links.items():
            cell = ws.cell(row=r, column=c)
            cell.hyperlink = link
            cell.font = Font(name="Arial", color="1F5FBF", underline="single")
        path = os.path.join(self.out, *rel_out.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        wb.save(path)
        self.made.append(path)

    def copy(self, src: str, rel_out: str) -> None:
        path = os.path.join(self.out, *rel_out.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy2(src, path)
        self.made.append(path)


def with_meta(md: str, rel: str) -> str:
    """The owner and review line under the title; research reports have their own date line."""
    if rel.startswith("research/"):
        return md
    owner = next(o for prefix, o in OWNERS if rel.startswith(prefix))
    meta = f"*Owner: {owner} · Last reviewed: {reviewed(rel)} · Next review: first week of next month*"
    m = re.match(r"\s*(# .+\n)", md)
    return (m.group(1) + "\n" + meta + "\n" + md[m.end():]) if m else meta + "\n\n" + md


def accuracy_rows(module: dict) -> tuple[str, str]:
    acc, fails = [], []
    several = len(module["checks"]) > 1
    for c in module["checks"]:
        t = c["monthly_test"]
        label = f"{c['plain_name']}: " if several else ""
        if not t:
            acc.append(f"{label}not in the monthly test")
            fails.append(f"{label}—")
            continue
        acc.append(f"{label}{t['correct']} of {t['labelled']} turnarounds correct ({t['percent']} %) on the monthly test")
        fails.append(f"{label}{t['fails_caught']} of {t['fails_labelled']}" if t["fails_labelled"]
                     else f"{label}no turnaround in the monthly test was labelled Fail")
    return "; ".join(acc), "; ".join(fails)


def fresh_status(md: str, module: dict) -> str:
    """Replace the two accuracy rows of the Status block with the latest monthly-test numbers."""
    acc, fails = accuracy_rows(module)
    md = re.sub(r"^\| How accurate it is \|.*$", lambda _: f"| How accurate it is | {acc} |", md, count=1, flags=re.M)
    return re.sub(r"^\| Fail turnarounds it caught \|.*$", lambda _: f"| Fail turnarounds it caught | {fails} |", md,
                  count=1, flags=re.M)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="the shared folder to write, e.g. G:/RampVision_Docs_v2")
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    b = Build(os.path.abspath(a.out))
    data = json.load(io.open(os.path.join(HB, "_data", "modules.json"), encoding="utf-8"))
    by_output = {m["output"]: m for m in data["modules"]}

    # every handbook page
    for dirpath, _dirs, files in os.walk(HB):
        rel_dir = os.path.relpath(dirpath, HB).replace("\\", "/")
        if rel_dir.split("/")[0] in ("_data", "_build"):
            continue
        for f in sorted(files):
            if not f.endswith(".md") or f == "STYLE.md":
                continue
            rel = f if rel_dir == "." else f"{rel_dir}/{f}"
            md = io.open(os.path.join(dirpath, f), encoding="utf-8").read()
            module = by_output.get(f"docs/handbook/{rel}")
            if module:
                md = fresh_status(md, module)
            if rel == "system/System overview.md":
                md = overview_numbers(md, data)
            out = b.docx(target(rel), with_meta(md, rel), resdir=dirpath)
            if module:
                png = os.path.join(WORK, safe(module["repository"]) + "_stages.png")
                stage_bar(module["stages"], png, STAGE_LABELS)
                polish(out, png)
            elif rel.startswith("system/"):
                polish(out)

    # client rules: generated from the client's workbook
    rules = clean(io.open(os.path.join(ROOT, "docs", "05_module_logic.md"), encoding="utf-8").read())
    b.docx("2 System/Requirements/Client rules.docx",
           "# Client rules — Pass, Fail and Not observed for every check\n\n"
           "*Owner: Valentyn Fedorov (lead) with Oksana (QA) · Source: the client's workbook next to this page*\n\n" + rules)
    b.copy(os.path.join(ROOT, "docs", "DX_Modules_logic.xlsx"), "2 System/Requirements/Client rules (client original).xlsx")

    # the index of the checks
    rows, links = [], {}
    for m in sorted(data["modules"], key=lambda m: (m["folder"], m["plain_title"])):
        acc, fails = accuracy_rows(m)
        page = target(m["output"][len("docs/handbook/"):])
        rows.append([m["folder"].split(" ", 1)[1], m["plain_title"], ", ".join(m["stages_plain"]), acc, fails,
                     re.sub(r"[`*]", "", m["glance"].get("Real time", "")), "to assign", "open"])
        links[(len(rows) + 1, 8)] = os.path.relpath(os.path.join(b.out, *page.split("/")),
                                                    os.path.join(b.out, "2 System", "Modules")).replace("\\", "/")
    b.sheet("2 System/Modules/Modules index.xlsx", "Checks",
            ["Stage folder", "Check", "Stages it looks at", "Accuracy on the monthly test", "Fail turnarounds caught",
             "Real time", "Who looks after it", "Page"],
            rows, [24, 52, 34, 46, 26, 46, 14, 8], links)

    # remove what the previous build made and this one did not
    manifest = os.path.join(WORK, "manifest.json")
    old = json.load(io.open(manifest, encoding="utf-8")) if os.path.exists(manifest) else []
    now = sorted(os.path.relpath(p, b.out).replace("\\", "/") for p in b.made)
    for rel in set(old) - set(now):
        p = os.path.join(b.out, *rel.split("/"))
        if os.path.exists(p):
            os.remove(p)
    for dirpath, dirs, files in sorted(os.walk(b.out), reverse=True):  # empty folders left behind
        if dirpath != b.out and not dirs and not files:
            os.rmdir(dirpath)
    json.dump(now, io.open(manifest, "w", encoding="utf-8"), indent=1)
    print(f"{len(now)} files in {b.out}")
    return 0


def overview_numbers(md: str, data: dict) -> str:
    scored = sorted(((c["monthly_test"]["percent"], c["plain_name"]) for m in data["modules"] for c in m["checks"]
                     if c["monthly_test"]), key=lambda x: x[0])
    lo, hi = scored[0][0], scored[-1][0]
    weakest = ", ".join(f"{name.lower()} ({p} %)" for p, name in scored[:5])
    text = (f"On the monthly test ({data['monthly_test']['turnarounds']} turnarounds the client checked by hand) the checks "
            f"give the right verdict in **{lo} to {hi} %** of the turnarounds. The weakest: {weakest}. Per check, with the "
            "turnarounds labelled Fail that each one caught: *Modules / Modules index*.")
    return md.replace("{{ACCURACY_RANGE}}", f"{lo}–{hi} %").replace("{{ACCURACY_TEXT}}", text)


if __name__ == "__main__":
    raise SystemExit(main())
