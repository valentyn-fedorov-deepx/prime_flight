"""Regenerate docs/03_components.md, docs/04_modules.md, docs/05_module_logic.md
from the source-of-truth artefacts kept in this workspace:

  docs/arch_review/essential_inventory.json   (from cv-architecture-interactive.zip, 2026-09-07 baseline)
  docs/streaming_ref/module_map.json          (from G:/gat-streaming/docs, code audit of 27 modules)
  docs/DX_Modules_logic.xlsx                  (client Pass/Fail logic, camera split, ProdReady, tiering)

Run:  python scripts/build_docs.py
Idempotent; safe to re-run after any source is updated.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# ---------------------------------------------------------------- sources
inv = json.loads((DOCS / "arch_review" / "essential_inventory.json").read_text(encoding="utf-8"))
mmap = json.loads((DOCS / "streaming_ref" / "module_map.json").read_text(encoding="utf-8"))
wb = openpyxl.load_workbook(DOCS / "DX_Modules_logic.xlsx", data_only=True)

modules = {m["id"]: m for m in inv["manifest"]["modules"]}
components = {c["id"]: c for c in inv["manifest"]["components"]}
views = {v["id"]: v for v in inv["review_views"]}
mm_by_repo = {m["name"]: m for m in mmap["modules"]}

# check title (xlsx) -> repo (GitLab dxgat/detectors/<repo>)
CHECK_TO_REPO = {
    "Chocks and cones available and staged for arrival": "chocks-and-cones-available-and-staged-for-arrival",
    "Crew present 10 minutes prior to aircraft arrival": "crew-present-10-minutes-prior-to-aircraft-arrival",
    "FOD walk completed": "fod-walk-completed",
    "Safety huddle conducted at huddle cone": "pre-arrival-safety-huddle",
    "Employees wearing safety vests secured to body": "safety-vests-secured-to-body",
    "Safety zone confirmed clear": "safety-zone-confirmed-clear",
    "Hair policy": "hair-policy (no repo yet)",
    "Nose gear chocks applied immediately": "aircraft-chocks",
    "Cones placed in proper positions and timely": "cones-placed-in-proper-positions-and-timely",
    "Steering by-pass pin installed, or steering otherwise bypassed": "steering-by-pass-pin-installed-or-steering-otherwise-bypassed",
    "Lead marshaller and wing walkers in correct position": "lead-marshaller-and-wing-walkers-in-position",
    "Beltloader rear cone positioned after BL is in place": "bl_rear_cone",
    "Beltloader rear cone positioned after BL is in place to alert clearance": "bl_rear_cone",
    "All GSE guided into aircraft using approved hand signals": "hand-signals",
    "Post-arrival aircraft walk around inspection completed accurately": "post-arrival-aircraft-walk-around-inspection-completed-accurately",
    "Pre-departure walk around completed": "pre-departure-walk-around-completed",
    "Seat belts used on all GSE equipped with seat belts": "seat-belts-used-on-all-gse-equipped-with-seat-belts (out of scope, M25)",
    "3 stop brake check": "3-stop-brake-check",
    "Proper beltloader approach including 3 stop brake check and handsignals": "composite: hand-signals + 3-stop-brake-check",
    "All cargo bin doors opened and verified": "all-cargo-bin-doors-opened-and-verified",
    "Motorized GSE parked and properly chocked": "gse-chocks",
    "Handrails on GSE being used": "handrails-on-gse-being-used",
    "Safety handrails fully extended and used": "safety-handrails-fully-extended",
    "Main gear chocks removed only after aircraft is attached to pushback": "aircraft-chocks",
    "Conditioned air removed 10 mins prior to departure and properly stowed": "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed",
    "Cones are removed only after all GSE is clear of A/C and chocked": "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked",
    "Belt loader forward chock remained in place until unit is backed up clear of aircraft": "beltloader-chocks",
    "Pushback operator verifies steering bypass pin installation": "pin-verification",
    "Pushback does not start until wing walkers are in place and ready": "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready",
    "Pushback pathway confirmed clear of obstacles": "pushback-pathway-confirmed-clear-of-obstacles",
    "Wing walkers in proper position and using approved wands": "wing-walkers-in-proper-position-and-using-approved-wands",
    "Nose wheel chock removed from aircraft": "aircraft-chocks",
}


def norm(s: str) -> str:
    s = (s or "").replace("\n", " ").replace("  /", " ").replace(" / ", " ")
    s = re.sub(r"\s+", " ", s).strip(" -.\u00a0")
    return s


def cell(v) -> str:
    if v is None:
        return ""
    return re.sub(r"\s*\n\s*", " / ", str(v)).strip()


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|")


# ---------------------------------------------------------------- xlsx: logic sheet
def read_logic(sheet_name: str):
    ws = wb[sheet_name]
    rows, stage = [], ""
    for r in ws.iter_rows(values_only=True):
        if not any(c is not None for c in r):
            continue
        head = cell(r[0])
        if head.endswith(":") and not head.startswith("-"):
            stage = head.rstrip(":").strip()
            continue
        if not head.lstrip().startswith("-"):
            continue
        title = norm(head)
        rows.append({
            "stage": stage,
            "check": title,
            "pass": cell(r[1]), "fail": cell(r[2]), "no": cell(r[3]),
            "no_obst": cell(r[4]), "comment": cell(r[5]),
        })
    return rows


logic_rows = read_logic("Updated logic 2025")

# tier: explicit label in Edge-Friendly (col B/C == streaming|real-time), else post if in "Post analytics",
# else streaming if in "StreamingInternet Coverage Boun".
tier: dict[str, str] = {}
for r in wb["Edge-Friendly"].iter_rows(values_only=True):
    if not r or not r[0] or not str(r[0]).lstrip().startswith("-"):
        continue
    t = norm(str(r[0]))
    labels = {cell(x).lower() for x in r[1:4] if x is not None}
    if "real-time" in labels:
        tier[t] = "real-time"
    elif "streaming" in labels:
        tier[t] = "streaming"
post_set = {norm(str(r[0])) for r in wb["Post analytics"].iter_rows(values_only=True)
            if r and r[0] and str(r[0]).lstrip().startswith("-")}
stream_set = {norm(str(r[0])) for r in wb["StreamingInternet Coverage Boun"].iter_rows(values_only=True)
              if r and r[0] and str(r[0]).lstrip().startswith("-")}
for row in logic_rows:
    t = row["check"]
    if t not in tier:
        tier[t] = "post" if t in post_set else ("streaming" if t in stream_set else "?")

# cameras / prodready
cams: dict[str, dict] = {}
for r in wb["Tasks by cameras"].iter_rows(values_only=True):
    if not r or not r[0] or str(r[0]).startswith(("Tasks", "N-tasks")):
        continue
    cams[norm(str(r[0]))] = {"aircraft": cell(r[1]), "jet": cell(r[2]), "prod": cell(r[3])}


def cam_lookup(check: str) -> dict:
    if check in cams:
        return cams[check]
    for k, v in cams.items():  # tolerate trailing dots / minor wording
        if k.lower().startswith(check.lower()[:40]):
            return v
    return {"aircraft": "?", "jet": "?", "prod": "?"}


# ---------------------------------------------------------------- 03 components
out = ["# Shared components (E01–E33)\n",
       f"Джерело: `docs/arch_review/essential_inventory.json` (baseline {inv['manifest']['baseline_date']}, "
       "32 компоненти після виключення E23/M25). Повний текст — `docs/arch_review/ESSENTIALS.md`, "
       "інтерактив — `docs/arch_review/components.html` та `hierarchy.html`.\n",
       "Правила меж (з ревʼю): списки задач містять лише evidence, потрібний політиці; пороги, дедлайни, "
       "eligibility і фінальний Pass/Fail лишаються локальними в модулі; один ID = один контракт.\n",
       "| ID | Група | Компонент | Impl | Контракт | Хто споживає |",
       "|---|---|---|---|---|---|"]
consumers: dict[str, list[str]] = {c: [] for c in components}
for v in inv["review_views"]:
    for c in v["component_ids"]:
        consumers.setdefault(c, []).append(v["id"])
for c in inv["manifest"]["components"]:
    out.append(f"| {c['id']} | {c['group']} | **{md_escape(c['title'])}** | {c['implementation']} | "
               f"{md_escape(c['contract'])} | {', '.join(consumers.get(c['id'], []))} |")
out += ["", "## Групи", ""]
for g in sorted({c["group"] for c in components.values()}):
    ids = [c["id"] for c in components.values() if c["group"] == g]
    out.append(f"- **{g}**: {', '.join(ids)}")
(DOCS / "03_components.md").write_text("\n".join(out) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- 04 modules
STAGE_ORDER = ["Pre-arrival", "Arrival", "Post-arrival", "Download", "Upload", "Pre-departure",
               "Departure (Tow-Bar disconnect)", ""]
out = ["# Модулі (M01–M27) і pipeline-репозиторії (U01–U05)\n",
       "Зведення трьох джерел: архітектурне ревʼю (inputs/outputs/attention/local policy), "
       "аудит коду для стрімінгу (`streaming_ref/module_map.json`: stage/opens/closes/decision/verdict) "
       "і клієнтський xlsx (tier, камери, ProdReady). Логіка Pass/Fail — у `05_module_logic.md`.\n",
       "Легенда verdict (готовність до стрімінгу): NOW = стрімиться без змін коду · NOW_PX = без змін, але потребує кадрів · "
       "PATCH = 3-хунковий фікс як в aircraft-chocks · RETHINK = двопрохідний, перший прохід визначає геометрію · POST = за суттю пост-обробка.\n",
       "Tier (поділ клієнта, xlsx Edge-Friendly/Post analytics/Streaming): real-time · streaming · post.\n"]

by_stage: dict[str, list] = {}
for v in inv["review_views"]:
    by_stage.setdefault(v.get("stage", ""), []).append(v)

for stage in STAGE_ORDER:
    vs = by_stage.get(stage)
    if not vs:
        continue
    out.append(f"\n## {stage or 'Pipeline / utility (U)'}\n")
    for v in vs:
        repo = v["repo"]
        mm = mm_by_repo.get(repo, {})
        # find xlsx row by title
        xrow = next((r for r in logic_rows if r["check"].lower()[:35] == v["title"].lower()[:35]), None)
        check = xrow["check"] if xrow else v["title"]
        cm = cam_lookup(check)
        out.append(f"### {v['id']} · {md_escape(v['title'])}")
        out.append(f"- **Repo**: [{repo}]({v['repository_url']}) · локально `G:\\deepx_gat\\{repo}` · pinned `{v['commit'][:8]}`")
        if v.get("stage"):
            out.append(f"- **Tier / камери / ProdReady**: {tier.get(check, '?')} · Aircraft={cm['aircraft']}, Jet={cm['jet']} · ProdReady={cm['prod']}")
        if mm:
            out.append(f"- **Стрімінг-аудит**: stage={mm.get('stage')} · opens=«{mm.get('opens')}» → closes=«{mm.get('closes')}» · "
                       f"decision={mm.get('decision')} · preventive={mm.get('preventive')} · passes={mm.get('passes')}, "
                       f"pixels={mm.get('pixels')}, models={mm.get('models')} · deps={', '.join(mm.get('deps', []))} · **verdict={mm.get('verdict')}**")
            if mm.get("why"):
                out.append(f"  - чому: {md_escape(mm['why'])}")
            if mm.get("measured"):
                out.append(f"  - зміряно: {md_escape(mm['measured'])}")
        out.append(f"- **Компоненти**: {', '.join(v['component_ids'])}"
                   + (f" (+proposed: {', '.join(v['supporting_component_ids'])})" if v.get("supporting_component_ids") else ""))
        out.append(f"- **Inputs**: {md_escape(v['inputs'])}")
        out.append(f"- **Outputs**: {md_escape(v['outputs'])}")
        if v.get("local_policy"):
            out.append(f"- **Local policy**: {md_escape(v['local_policy'])}")
        out.append(f"- **Attention**: {md_escape(v['attention'])}")
        out.append("")

# modules present in module_map but not in review (e.g. seat belts) – note them
extra = [m for m in mmap["modules"] if m["name"] not in {v["repo"] for v in inv["review_views"]}]
if extra:
    out.append("\n## Поза активним скоупом ревʼю, але є в аудиті коду\n")
    for m in extra:
        out.append(f"- `{m['name']}` — {m.get('check')} · verdict={m.get('verdict')} · {md_escape(m.get('why', ''))}")
(DOCS / "04_modules.md").write_text("\n".join(out) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- 05 module logic
out = ["# Клієнтська логіка модулів (DX_Modules logic.xlsx, аркуш «Updated logic 2025»)\n",
       "Це **контракт із клієнтом** щодо того, коли модуль каже Pass / Fail / Not observed / Not observed with obstacles. "
       "Будь-яка зміна тригера при переносі в real-time має зберігати цю семантику або бути явно погоджена. "
       "Файл-джерело: `docs/DX_Modules_logic.xlsx`.\n",
       "| Стадія | Перевірка | Repo | Tier | Cam A/J | Prod | Pass | Fail | Not observed | NO with obstacles | Коментар |",
       "|---|---|---|---|---|---|---|---|---|---|---|"]
for r in logic_rows:
    cm = cam_lookup(r["check"])
    out.append("| " + " | ".join(md_escape(x) for x in [
        r["stage"], r["check"], CHECK_TO_REPO.get(r["check"], "?"), tier.get(r["check"], "?"),
        f"{cm['aircraft']}/{cm['jet']}", cm["prod"], r["pass"], r["fail"], r["no"], r["no_obst"], r["comment"]]) + " |")

out += ["", "## Merge logic (дві камери → один вердикт)", "",
        "Пріоритет: **Fail → Pass → Not observed**. Якщо задача бігла на обох камерах, Fail на будь-якій = Fail; "
        "Pass на одній + Not observed на іншій = Pass; Not observed лише коли обидві Not observed.", "",
        "| Wing \\ Cone | fail | pass | notObserved |", "|---|---|---|---|",
        "| fail | fail | fail | fail |", "| pass | fail | pass | pass |", "| notObserved | fail | pass | notObserved |", "",
        "## Розподіл задач по камерах (аркуш «Tasks by cameras»)", "",
        "| Перевірка | Aircraft | Jet | ProdReady |", "|---|---|---|---|"]
for k, v in cams.items():
    out.append(f"| {md_escape(k)} | {v['aircraft']} | {v['jet']} | {v['prod']} |")
out += ["", "Підсумок з аркуша: Aircraft — 12 задач на обох камерах, 18 лише cone, 0 лише wing; "
        "Jet — 3 на обох, 13 лише cone, 8 лише wing.", "",
        "## Tier за клієнтським поділом", ""]
for t in ["real-time", "streaming", "post", "?"]:
    names = [c for c, tt in tier.items() if tt == t]
    if names:
        out.append(f"- **{t}** ({len(names)}): " + "; ".join(names))
(DOCS / "05_module_logic.md").write_text("\n".join(out) + "\n", encoding="utf-8")

print("written:", *(p.name for p in [DOCS / "03_components.md", DOCS / "04_modules.md", DOCS / "05_module_logic.md"]))
print("logic rows:", len(logic_rows), "| tiers:", {t: sum(1 for x in tier.values() if x == t) for t in set(tier.values())})
unmapped = [r["check"] for r in logic_rows if r["check"] not in CHECK_TO_REPO]
if unmapped:
    print("UNMAPPED checks:", unmapped, file=sys.stderr)
