"""Build the technical audit document (current state, for management) from docs/reports/audit_inventory.json.

    python scripts/reports/audit_inventory.py
    python scripts/reports/build_audit_docx.py [docs/reports/PF_technical_audit_state.docx]
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INV = os.path.join(ROOT, "docs", "reports", "audit_inventory.json")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "reports", "PF_technical_audit_state.docx")
DARK = RGBColor(0x16, 0x21, 0x3A)
GREY = RGBColor(0x5A, 0x64, 0x72)

doc = Document()
sec = doc.sections[0]
sec.orientation = WD_ORIENT.LANDSCAPE
sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
sec.left_margin = sec.right_margin = Cm(1.4)
sec.top_margin, sec.bottom_margin = Cm(1.3), Cm(1.2)
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(9.5)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
normal.paragraph_format.space_after = Pt(3)


def para(text: str, size: float = 9.5, bold: bool = False, color=None, after: float = 4):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    if color is not None:
        r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(after)
    return p


def rich(parts: list, size: float = 9.5, after: float = 4):
    p = doc.add_paragraph()
    for text, bold in parts:
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.bold = bold
    p.paragraph_format.space_after = Pt(after)
    return p


def heading(text: str, size: float = 13, before: float = 12):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    r.font.color.rgb = DARK
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    return p


def shade(cell, fill: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def margins(cell, top=30, bottom=30, left=60, right=60):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for name, val in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        el = OxmlElement(f"w:{name}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def table(headers: list, rows: list, widths_cm: list, font_pt: float = 8, header_fill: str = "E9ECF1"):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    t.autofit = False
    hdr = t.rows[0]
    trPr = hdr._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(font_pt)
        shade(c, header_fill)
        margins(c)
        c.width = Cm(widths_cm[i])
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            c = cells[i]
            c.text = ""
            text = "—" if val is None or val == "" else str(val)
            bold = False
            if text.startswith("**") and text.endswith("**"):
                text, bold = text[2:-2], True
            r = c.paragraphs[0].add_run(text)
            r.font.size = Pt(font_pt)
            r.bold = bold
            c.paragraphs[0].paragraph_format.space_after = Pt(0)
            margins(c)
            c.width = Cm(widths_cm[i])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def cut(text, n: int):
    if text is None:
        return "—"
    text = str(text).replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


SHORT = {  # module repository -> a readable name
    "3-stop-brake-check": "3-stop brake check", "aircraft-chocks": "aircraft chocks (3 verdicts)",
    "all-cargo-bin-doors-opened-and-verified": "cargo doors opened", "beltloader-chocks": "belt loader forward chock",
    "bl_rear_cone": "belt loader rear cone", "chocks-and-cones-available-and-staged-for-arrival": "chocks and cones staged",
    "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed": "conditioned air removed",
    "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked": "cones removed after GSE clear",
    "cones-placed-in-proper-positions-and-timely": "cones placed", "crew-present-10-minutes-prior-to-aircraft-arrival": "crew present",
    "fod-walk-completed": "FOD walk", "gse-chocks": "GSE parked and chocked", "hand-signals": "hand signals",
    "handrails-on-gse-being-used": "handrails on GSE used", "lead-marshaller-and-wing-walkers-in-position": "lead marshaller and wing walkers",
    "pin-verification": "pushback pin verification", "post-arrival-aircraft-walk-around-inspection-completed-accurately": "post-arrival walk-around",
    "pre-arrival-safety-huddle": "safety huddle", "pre-departure-walk-around-completed": "pre-departure walk-around",
    "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready": "pushback waits for wing walkers",
    "pushback-pathway-confirmed-clear-of-obstacles": "pushback pathway clear", "safety-handrails-fully-extended": "handrails fully extended",
    "safety-vests-secured-to-body": "safety vests", "safety-zone-confirmed-clear": "safety zone clear",
    "steering-by-pass-pin-installed-or-steering-otherwise-bypassed": "steering bypass pin",
    "wing-walkers-in-proper-position-and-using-approved-wands": "wing walkers with wands",
}
STAGE = {"PRE_ARR": "before arrival", "ARR_POST": "arrival", "DOWNLOAD": "belt loader at the door", "PRE_DEP": "before departure",
         "DEP": "pushback / departure", "ALL": "whole session"}
DECISION = {"INSTANT": "one detection → Fail", "EVENT": "verdict at the event", "DEADLINE": "Fail if not seen in time",
            "LOOKBACK": "judges the window before the moment", "WHOLE": "needs the whole event"}
CLASS_WORDS = {"airplane": "aircraft", "airplane_nose": "nose", "airplane_tail": "tail", "airplane_wing": "wing", "airplane_engine": "engine",
               "front_wheel": "front wheel", "back_wheel": "rear wheel", "beltloader": "belt loader", "gse": "GSE", "pushback": "pushback",
               "fuel_truck": "fuel truck", "trailer": "trailer", "ladder": "ladder", "vehicle": "vehicle", "air_conditioning": "air unit",
               "cone": "cones", "engine_cone": "engine cone", "wing_cone": "wing cone", "tail_cone": "tail cone", "beltloader_cone": "BL cone",
               "chock": "chocks", "person": "people", "front_door": "front door", "back_door": "rear door", "obstacle": "obstacles",
               "side_obstacle": "side obstacles", "safety_vest": "vests", "wand": "wands", "tow_bar": "tow bar", "roi": "a drawn zone",
               "safety_zone": "the safety zone"}


def family(model_name: str) -> str:
    n = (model_name or "").lower()
    if any(k in n for k in ("pose", "hrnet", "simcc", "rtmpose", "dwpose", "movenet", "keypoint")):
        return "pose (body keypoints)"
    if any(k in n for k in ("seg", "sam", "mask")):
        return "segmentation"
    if any(k in n for k in ("yolo", "detector", "detection")):
        return "object detector"
    if any(k in n for k in ("classif", "gate", "difference", "resnet", "efficientnet", "swin", "cnn")):
        return "image classifier"
    if any(k in n for k in ("time-series", "inceptiontime", "scaler", "minmax")):
        return "time-series classifier"
    if "hsv" in n or "colour" in n or "color" in n:
        return "colour rule"
    if "depth" in n:
        return "depth estimation"
    return "model"


def version_of(filename: str) -> str:
    f = filename or ""
    m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s?(\d{4})", f, re.I)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"
    m = re.search(r"v(\d+(?:\.\d+)+)", f)
    if m:
        return "v" + m.group(1)
    m = re.search(r"(\d{2})_(\d{2})_(\d{4})", f)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", f)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return "—"


def plain_events(events: list) -> str:
    text = " ".join(events).lower()
    found = []
    if "arrival stage" in text or "t_arr" in text or "arrival" in text:
        found.append("arrival")
    if "t_dep" in text or "depart" in text or "moving" in text and "t_arr" in text:
        found.append("departure")
    if "pushback_attached" in text or "pushback attached" in text:
        found.append("pushback attached")
    if "bl at door" in text or "bl active" in text or "bl fully_stopped" in text or "bl approach" in text or "bl entering" in text:
        found.append("belt loader at the door")
    if "aircraft type" in text:
        found.append("aircraft type")
    if "gse stop" in text:
        found.append("GSE stop / departure")
    if "own norfair" in text or "own velocity" in text:
        found.append("its own tracking")
    return ", ".join(dict.fromkeys(found)) or "—"


inv = json.load(io.open(INV, encoding="utf-8"))
mods = [m for m in inv["modules"] if m["m_id"]]

# ------------------------------------------------------------------------------------------------------------ title
para("DXGAT / RampVision — technical audit: the current state", size=20, bold=True, color=DARK, after=2)
para("6 October 2026 · Valentyn Fedorov · what the system runs today: the modules and what each checks, the models behind them and how "
     "old they are, when each check is active during a turnaround, how long everything takes, and where the same logic is written "
     "several times. Based on the architecture review of 7 September and the measurements of 8 September – 1 October.",
     size=9, color=GREY, after=8)

# ------------------------------------------------------------------------------------------------------------ 1. system
heading("1 · What runs today and how long it takes")
rich([("Everything is post-processing. ", True),
      ("Two cameras at the gate record 1080p at 8 fps in one-minute chunks and upload them; after the turnaround the chunks are merged into "
       "one full-turn video per camera; then three jobs run one after another on that file — the General Model (detects everything on "
       "the apron), the trackers (follow the aircraft, belt loaders, GSE and people), and one job per check — and the verdicts "
       "(Pass / Fail / Not observed) land in MongoDB and on RampVision. ", False),
      ("A result arrives about 24 hours after the recording: ", True),
      ("on the median of 148 production videos, 9.5 h for the last chunk to reach the bucket, 2.5 h of merge, 2.4 h of General Model, "
       "1.3 h of trackers and 0.9 h of modules. Each GPU job runs on one Tesla T4 with about 4 CPU cores and 12 GB of memory.", False)], after=4)
table(["stage", "what it does", "models", "time on a typical (87-minute) video"],
      [["merge", "finds, orders and merges the chunks into one video", "a small classifier for the capture boundary", "1.7 h waiting + 0.8 h running"],
       ["General Model", "detects aircraft, parts, equipment, cones, chocks, people on every frame; decides the camera, the aircraft type and the airline; reads the video twice", "3 YOLO detectors, MobileSAM, an airline detector, two small classifiers", "2.4 h (207 ms per frame — 1.7× slower than the recording)"],
       ["trackers", "follows every object over time: identity, stops and movement, who is at which door", "2 re-identification networks, 2 segmentation networks, optical flow", "1.3 h (112 ms per frame)"],
       ["modules (27)", "the check logic, one job per module; 13 of them also look at the pixels", "13 of 27 carry models of their own (pose, classifiers, segmentation)", "0.9 h in total; 7 s to 6 min per module on the reference event"],
       ["reporting", "writes verdicts, reports and the smart timeline", "—", "minutes"]],
      [2.6, 10.0, 7.0, 7.2])

# ------------------------------------------------------------------------------------------------------------ 2. shared models
heading("2 · The shared models (run once per video for all checks)")
table(["model", "what it is for", "version", "when it runs", "size MB", "time per frame"],
      [[g["name"], {"GM YOLOv8m (apron classes)": "the main detector: aircraft and parts, cones, chocks, equipment, people",
                    "Chocks YOLOv8 v4.3": "a second detector just for chocks, at higher resolution",
                    "Vehicle YOLOv8m": "a third detector for vehicles and ground equipment",
                    "MobileSAM vit_t (main-aircraft mask)": "an outline of the main aircraft for its movement state",
                    "Entity (airline) YOLOv5": "which airline (six logos)",
                    "Camera cone/wing EfficientNet-B0 v1.8.1": "which camera this is (cone or wing)",
                    "Tail classifier": "aircraft type (jet / aircraft)"}.get(g["name"], "—"),
        version_of(g["file"]), g["cadence"], g["size_mb"], f"{g['ms_busy']} ms" if g["ms_busy"] is not None else "small"]
       for g in inv["shared"]["general_model"]],
      [6.2, 8.6, 2.6, 5.4, 1.6, 2.4])
para("Trackers: two re-identification networks (one trained for people; for belt loaders and GSE a generic ImageNet ResNet-34 used as is), "
     "two segmentation networks (aircraft; belt loader and GSE), classic optical flow on up to 250 points per object, and a noise "
     "estimate of the frame every two seconds. Together 26 ms per frame on a modern desktop GPU, 112 ms on the production T4.",
     size=9.5, after=4)

# ------------------------------------------------------------------------------------------------------------ 3. module inventory
heading("3 · The checks: what each module verifies, when it is active, what it looks at")
para("27 module repositories implement the client's 30 checks (the chock module gives three verdicts; “proper belt loader approach” is "
     "derived from two others). Window: the part of the turnaround the check is active in. Looks at: the detections it reads from the "
     "General Model and the objects it follows through the trackers. Pixels: whether the module also reads the images itself.",
     size=9, color=GREY, after=3)
rows_a = []
for m in mods:
    gm_words = [CLASS_WORDS.get(c, c) for c in m["gm_classes"]]
    trk_words = [CLASS_WORDS.get(c, c) for c in m["tracker_classes"]]
    models = "; ".join(cut(x["name"], 36) for x in m["models"]) if m["models"] else "none"
    rows_a.append([m["m_id"], SHORT.get(m["module"], m["module"]), cut("; ".join(m["checks"] or []), 58),
                   f"{STAGE.get(m['stage'], m['stage'] or '—')} · {DECISION.get(m['decision'], '—')}",
                   cut(", ".join(gm_words), 64), ", ".join(trk_words) or "—",
                   "yes" if m["pixels"] else "no", models])
table(["M", "module", "the check", "window · how it decides", "looks at (General Model)", "follows (trackers)", "pixels", "own models"],
      rows_a, [1.15,3.6, 5.4, 4.4, 4.8, 2.6, 1.1, 4.2], font_pt=7.5)

# ------------------------------------------------------------------------------------------------------------ 4. run times
heading("4 · How long each check runs, and whether it already runs live")
para("Post job: one clean job on the 36-minute reference event. Batch: median cost per recorded frame when the monthly test set runs "
     "(the usual way they run today). Live: the module's own work per frame inside the real-time branch, the shared models excluded. "
     "Runs live as is: whether the unchanged module gives the same verdict in real time.", size=9, color=GREY, after=3)
rows_b = []
for m in sorted(mods, key=lambda m: -(m["post_job_s"] or 0)):
    rows_b.append([m["m_id"], SHORT.get(m["module"], m["module"]),
                   f"{m['post_job_s']:.0f} s" if m["post_job_s"] else ("own environment" if m["m_id"] in ("M17", "M19") else "—"),
                   f"{m['batch_ms_per_recorded_frame']:.1f} ms" if m["batch_ms_per_recorded_frame"] else "—",
                   f"{m['live_ms_per_frame']:.1f} ms" if m["live_ms_per_frame"] else "—",
                   {"yes": "yes", "yes, verdict at session end": "yes, but only answers when the camera stops",
                    "yes, report shifts": "yes (the report shifts slightly)", "no: two passes": "no — reads the recording twice",
                    "not hosted": "no — its own Python environment"}.get(m["runs_in_real_time_as_is"], m["runs_in_real_time_as_is"] or "—")])
table(["M", "module", "post job", "batch per frame", "live per frame", "runs live as is"], rows_b,
      [1.15,6.0, 2.6, 2.8, 2.6, 7.4], font_pt=8)
rich([("Where the time goes. ", True),
      ("Two modules dominate: safety vests (6 min on the reference event — two transformer classifiers on every person of every frame, the "
       "whole session) and handrails on GSE (4 min — four networks per belt-loader visit). The twelve checks that read only detections cost "
       "seconds each. In batch the busiest part of a turnaround is the belt loader at the door: nine checks active together, 89 ms of work per "
       "recorded frame against a real-time budget of 125 ms. The shared General Model and trackers are about 85 % of a real-time frame; the "
       "modules' own work is the small part.", False)], after=4)

# ------------------------------------------------------------------------------------------------------------ 5. models in modules
heading("5 · The models inside the modules")
para("Thirteen modules carry models of their own, on top of the shared layer. Size is the weights file.", size=9, color=GREY, after=3)
rows_m = []
for m in mods:
    for x in m["models"]:
        rows_m.append([m["m_id"], SHORT.get(m["module"], m["module"]), cut(x["name"], 54), family(x["name"]),
                       version_of(x["file"]), f"{x['size_mb']:.0f}" if x["size_mb"] else "—"])
table(["M", "module", "model", "kind", "version / date", "MB"], rows_m, [1.15,5.4, 9.6, 3.6, 3.2, 1.4], font_pt=8)
rich([("Shared and repeated. ", True),
      ("One pose network (HRNet-W48, 269 MB) is the same file in four modules — hand signals, steering, lead marshaller, wing walkers — "
       "each loading its own copy. EfficientNet-B0 appears six times for different jobs. MobileSAM is in four places. Five different "
       "pose stacks serve ten modules. Several weights files sit in the checkouts and are loaded by nobody (a second 255 MB HRNet in all "
       "four pose modules, a wand detector, a worker-type classifier, an air-unit detector).", False)], after=4)

# ------------------------------------------------------------------------------------------------------------ 6. repeated logic
heading("6 · Where the same logic is written several times")
n_stage = sum(1 for m in mods if m["recomputes_stage"])
n_priv = sum(1 for m in mods if m["private_fields"])
rich([(f"{n_stage} of the 27 modules work out the stage of the turnaround themselves ", True),
      ("(when the aircraft arrived, when it left) instead of taking it from one place, and ", False),
      (f"{n_priv} reach into the tracker's internal fields ", True),
      ("to do it — so every change of the tracker reaches them. The same arrival block is copied word for word in nine modules; six more "
       "have their own rules; the code base has five different definitions of “departure”. “Pushback attached” is computed twice, and that "
       "is why those two modules read the recording twice. “Belt loader at the door” exists in five variants. Two modules recompute the "
       "aircraft type although the General Model publishes it. The modules are pinned to ten different revisions of the shared library, "
       "and seven of the checkouts the monthly test runs differ from the revisions the review inspected.", False)], after=3)
rows_e = []
for m in mods:
    if m["events_recomputed"]:
        rows_e.append([m["m_id"], SHORT.get(m["module"], m["module"]), plain_events(m["events_recomputed"])])
table(["M", "module", "what it recomputes on its own"], rows_e, [1.15,6.0, 20.0], font_pt=8)

heading("7 · What the review flagged: what the code verifies against what the checklist says")
rows_r = [[m["m_id"], SHORT.get(m["module"], m["module"]), cut(m["attention"].split(". ")[0].rstrip(".") + ".", 150)] for m in mods if m["attention"]]
table(["M", "module", "note"], rows_r, [1.15,6.0, 20.0], font_pt=8)

doc.save(OUT)
print("written", OUT)
