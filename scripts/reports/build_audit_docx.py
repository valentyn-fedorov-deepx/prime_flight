"""Build the technical audit document (current state) from docs/reports/audit_inventory.json.

    python scripts/reports/audit_inventory.py
    python scripts/reports/build_audit_docx.py [docs/reports/PF_technical_audit_state.docx]
"""

from __future__ import annotations

import io
import json
import os
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
for side in ("left_margin", "right_margin"):
    setattr(sec, side, Cm(1.3))
sec.top_margin, sec.bottom_margin = Cm(1.2), Cm(1.1)
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(9)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
normal.paragraph_format.space_after = Pt(3)


def para(text: str, size: float = 9, bold: bool = False, color=None, after: float = 3, italic: bool = False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    if color is not None:
        r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(after)
    return p


def rich(parts: list, size: float = 9, after: float = 3):
    """parts: list of (text, bold)."""
    p = doc.add_paragraph()
    for text, bold in parts:
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.bold = bold
    p.paragraph_format.space_after = Pt(after)
    return p


def heading(text: str, size: float = 12, before: float = 10):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    r.font.color.rgb = DARK
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    return p


def shade(cell, fill: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def margins(cell, top=25, bottom=25, left=50, right=50):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for name, val in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        el = OxmlElement(f"w:{name}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def table(headers: list, rows: list, widths_cm: list, font_pt: float = 7.5, header_fill: str = "E9ECF1"):
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


inv = json.load(io.open(INV, encoding="utf-8"))
mods = [m for m in inv["modules"] if m["m_id"]]
by_name = {m["module"]: m for m in mods}

# ------------------------------------------------------------------------------------------------------------ title
para("DXGAT / RampVision — technical audit: the current state", size=18, bold=True, color=DARK, after=2)
para("6 October 2026 · Valentyn Fedorov · an inventory of what runs today: the modules, the models they run and their "
     "versions, what each reads from the shared layer, in which window of the turnaround it is active, how long it runs, "
     "and where the logic repeats. Sources: the static architecture review of 7 September (docs/arch_review), the "
     "consumption matrix and the model audits (docs/analysis), and the measurements of 8 September – 1 October (post jobs "
     "on the 36-minute reference event zHxIAF2vUGxJ; batch medians per recorded frame on the contended test-set machine; "
     "live milliseconds per frame on an RTX 5070 Ti with the card kept busy). Generated by scripts/reports/build_audit_docx.py "
     "from docs/reports/audit_inventory.json.", size=8.5, color=GREY, after=6)

# ------------------------------------------------------------------------------------------------------------ 1. system
heading("1 · What runs today, in what order, and how long it takes")
rich([("Everything is post-processing. ", True),
      ("The CameraBox records two 1080p streams at 8 fps (H.264, constant 4.0 Mbit/s each) in 1-minute chunks and uploads them to "
       "the bucket; after the turnaround the chunks are merged into one full-turn video per camera; then three GKE jobs run in "
       "sequence on that file — the General Model, the trackers, and one job per module — and the verdicts (Pass / Fail / Not "
       "observed) go to MongoDB and RampVision. On the median of 148 production videos (87 minutes of recording) the result "
       "arrives 20.3 h after the recording: 9.5 h for the last chunk to reach the bucket, 1.7 h waiting for merge, 0.8 h merging, "
       "2.4 h of General Model (207 ms per frame, 1.7× slower than the recording), 1.3 h of trackers, 0.9 h of modules. A "
       "production GPU job gets a Tesla T4 (14.6 GB), 3.9 vCPU of a 2013-generation Xeon and 12 GB of RAM.", False)], after=4)
table(["stage", "repository · entry", "what it computes", "time on the median video (87 min)", "per frame"],
      [["merge", "camera_software · merge.py", "finds, orders and merges the chunks; capture-boundary classifier", "1.7 h waiting + 0.8 h running", "—"],
       ["General Model", "general_model · main.py (job per video, two decodes)", "three YOLO heads, MobileSAM mask of the main aircraft, entity, camera type, aircraft type; the second run labels obstacle rows and the main aircraft", "2.4 h", "207 ms (prod T4); 19.2 ms busy on the RTX 5070 Ti, 11.1 with TensorRT"],
       ["trackers", "cv_trackers · tracker.py (job per video, pixels every frame)", "three DeepSORT instances, instance masks, optical flow, state machines per object, noise estimate", "1.3 h", "112 ms (prod); 26.2 ms busy on the RTX 5070 Ti (4 classes)"],
       ["modules", "dxgat/detectors/<27 repos> · main.py (job per module)", "the check logic on GM + tracker rows (and pixels for 13 of them)", "0.9 h in total", "0.1–18.8 ms of own work live; 1.2–30.7 ms per recorded frame in batch"],
       ["reporting", "db_worker · send_report.py", "verdicts, reports, smart timeline → MongoDB, buckets, RampVision", "minutes", "—"]],
      [2.3, 5.2, 9.2, 4.6, 5.6])

# ------------------------------------------------------------------------------------------------------------ 2. shared models
heading("2 · The shared layer: models that run for every module")
para("General Model job (general_model, production commit a0157a4): fp16 ONNX heads through onnxruntime CUDA; the other models in torch. "
     "Milliseconds: busy card, RTX 5070 Ti, the head's share of the three-head step.", size=8.5, color=GREY, after=2)
table(["model", "file (version)", "input", "when it runs", "size MB", "ms per frame"],
      [[g["name"], g["file"], g["input"], g["cadence"], g["size_mb"], g["ms_busy"] if g["ms_busy"] is not None else "—"] for g in inv["shared"]["general_model"]],
      [6.0, 7.2, 3.4, 5.6, 1.8, 3.0])
para("Trackers job (cv_trackers, production commit bd43c3c with cv_common tracker_optimization @2759daf): one tracker stream per video, "
     "four classes (aircraft, belt loader, GSE, person); the production job costs 36–49 ms per frame on this card, the v2 port is byte-identical.",
     size=8.5, color=GREY, after=2)
table(["component", "file", "input", "when it runs", "size MB", "ms per frame (busy, thread time)"],
      [[g["name"], g["file"], g["input"], g["cadence"], g["size_mb"] if g["size_mb"] is not None else "—", g["ms_busy"] if g["ms_busy"] is not None else "—"] for g in inv["shared"]["tracker"]],
      [7.4, 4.6, 3.2, 6.4, 1.8, 3.6])

# ------------------------------------------------------------------------------------------------------------ 3. module inventory A
heading("3 · The modules: what each one checks, when it is active, what it reads, what it runs")
para("27 module repositories implement the client's 30 checks (aircraft-chocks gives three verdicts; “proper belt loader approach” is derived "
     "from 3-stop and hand signals). Window: the stage the module is gated to and the events that open and close it (from the streaming "
     "audit of the code); decision: INSTANT = one detection → Fail, EVENT = verdict at the event, DEADLINE = Fail if not seen by T, "
     "LOOKBACK = the window before T, WHOLE = the whole event. GM classes: what the module reads for its decision (drawn-only classes "
     "excluded). Pixels: whether it decodes frames. Passes: how many times it reads the whole recording.", size=8.5, color=GREY, after=2)
rows_a = []
for m in mods:
    window = f"{m['stage'] or '—'}: {cut(m['opens'], 34)} → {cut(m['closes'], 34)} · {m['decision'] or '—'}"
    models = "; ".join(cut(x["name"], 40) for x in m["models"]) if m["models"] else "none"
    rows_a.append([m["m_id"], cut(m["module"], 42), cut("; ".join(m["checks"] or []), 60),
                   f"{m['tier'] or '—'} · {cut(m['cameras'], 26)}", window,
                   cut(", ".join(m["gm_classes"]), 60), ", ".join(m["tracker_classes"]) or "—",
                   f"{m['passes']} · {'yes' if m['pixels'] else 'no'}", models])
table(["M", "module (repository)", "check", "tier · cameras", "window · decision", "GM classes read", "tracker classes",
       "passes · pixels", "own models"], rows_a, [0.9, 3.6, 4.2, 2.4, 5.0, 3.6, 2.2, 1.4, 3.8], font_pt=7)

# ------------------------------------------------------------------------------------------------------------ 4. versions and times
heading("4 · Versions, pins and run times")
para("Reviewed pin: the commit the architecture review inspected (7 September); head: the checkout the monthly test set runs. "
     "cv_common / db_worker: the submodule revisions the module is pinned to (ten different cv_common pins across the set). "
     "Post job: a clean single job on the 36-minute reference event. Batch: median ms per recorded frame on the contended test-set "
     "machine (model loading and decoding included; an early-exiting module looks cheaper). Live: the module's own work per frame "
     "inside the real-time branch, the shared GM and tracker excluded. Real time as is: whether the unchanged module runs live with "
     "the post-processing verdict.", size=8.5, color=GREY, after=2)
rows_b = []
for m in mods:
    pin = m["reviewed_pin"] or "—"
    head = m["repo_head"] or "—"
    same = pin != "—" and head != "—" and (pin.startswith(head) or head.startswith(pin))
    rows_b.append([m["m_id"], cut(m["module"], 42), pin, head + ("" if same else " (≠ pin)"), m["cv_common_pin"] or "—",
                   m["db_worker_pin"] or "—",
                   f"{m['post_job_s']:.0f}" if m["post_job_s"] else ("own env" if m["m_id"] in ("M17", "M19") else "—"),
                   f"{m['batch_ms_per_recorded_frame']:.1f}" if m["batch_ms_per_recorded_frame"] else "—",
                   f"{m['live_ms_per_frame']:.2f}" if m["live_ms_per_frame"] else "—",
                   cut(m["runs_in_real_time_as_is"], 28), cut(m["verdict_arrives"], 34)])
table(["M", "module", "reviewed pin", "head", "cv_common", "db_worker", "post job s", "batch ms", "live ms", "real time as is",
       "verdict arrives (live)"], rows_b, [0.9, 4.0, 1.8, 2.2, 1.7, 1.7, 1.5, 1.4, 1.4, 3.6, 5.2], font_pt=7)
heavy = sorted((m for m in mods if m["post_job_s"]), key=lambda m: -m["post_job_s"])[:6]
rich([("The heaviest by post-job time: ", True),
      (", ".join(f"{m['module'].split('-')[0] if m['module'].startswith('safety') else m['module'][:24]} {m['post_job_s']:.0f} s" for m in heavy) +
       ". Per stage in batch the peak is download/upload (belt loader at the door → leaves): handrails-on-gse 30.7 + vests 28.2 + "
       "safety-handrails 8.4 + gse-chocks 6.1 + aircraft-chocks 5.7 + 3-stop 3.4 + beltloader-chocks 2.7 + bl_rear_cone 2.4 + cargo 1.4 = "
       "89 ms per recorded frame against a 125 ms budget; the walk-arounds (26.1 and 6.8) run in their own Python environments.", False)],
     size=8.5, after=4)

# ------------------------------------------------------------------------------------------------------------ 5. models in modules
heading("5 · Models inside the modules")
para("From the read-only audits of the checkouts the test set runs (sha256 of every weights file; nothing executed). The shared GM and "
     "tracker models are in section 2.", size=8.5, color=GREY, after=2)
rows_m = []
for m in mods:
    for x in m["models"]:
        rows_m.append([m["m_id"], cut(m["module"], 30), cut(x["name"], 46), cut(x["architecture"], 70), cut(x["file"], 44),
                       f"{x['size_mb']:.0f}" if x["size_mb"] else "—", x["sha256_16"] or "—", cut(x["framework"], 30), cut(x["cadence"], 60)])
table(["M", "module", "model", "architecture", "weights file", "MB", "sha256", "framework", "when it is called"], rows_m,
      [0.9, 2.8, 4.2, 5.6, 4.2, 1.0, 2.0, 2.6, 3.8], font_pt=6.5)
rich([("Shared and repeated: ", True),
      ("HRNet-W48 COCO 256×192 (sha 0e67c6167d6a10fe, 269 MB) is the same file in hand-signals, steering, lead-marshaller and wing-walkers, "
       "with the flip test on (two backbone passes per call); EfficientNet-B0 appears six times (the handrail classifier in two modules with the "
       "same weights, the difference classifier in aircraft-chocks and gse-chocks with different weights, the camera classifier in GM, two in "
       "hair policy); MobileSAM in four places (GM, tracker initialisation, safety-zone, the walk-around TDV build); five different pose stacks "
       "serve ten modules (HRNet, SimCC ResNet-50, RTMPose-l, DWPose-l, MoveNet, YOLOv8-pose). Present but loaded by nobody: HRNet-W48 384×288 "
       "(255 MB, in all four HRNet checkouts), wand_detector.pt, worker_type_classifier.pkl, v4_probe_head.npz, best28_full.onnx.", False)],
     size=8.5, after=4)

# ------------------------------------------------------------------------------------------------------------ 6. duplicated logic
heading("6 · Where the logic repeats, and what the review flagged")
n_stage = sum(1 for m in mods if m["recomputes_stage"])
n_priv = sum(1 for m in mods if m["private_fields"])
rich([(f"{n_stage} of 27 modules derive the turnaround stage themselves and {n_priv} read the tracker's private optical-flow fields. ", True),
      ("The same arrival block (movement_anomaly_custom from _p0/_prev_p0/_st → normal_moving_counter > 24 → have_arrival_stage; pre-arrival = "
       "arrival_frame > 60·fps) is copied verbatim in nine modules; six more carry their own T_arr / T_dep rules — five definitions of departure "
       "in the code base. pushback_attached is computed twice (aircraft-chocks, pin-verification: IoU > 0.8 with the median pushback box of the "
       "first pass, nose-geometry fallback) and is the reason both need a second pass. “Belt loader at the door” exists in five variants "
       "(3-stop, beltloader-chocks and bl_rear_cone, handrails-on-gse, safety-handrails, hand-signals). The aircraft type is recomputed from "
       "wing/engine geometry in two modules although GM publishes it. Every frame read letterboxes to 1280×768 and copies the frame for nothing "
       "(cv_common datasets.py). Three modules run their own trackers beside the shared one (safety-zone, huddle, seat-belts).", False)],
     size=8.5, after=3)
rows_e = []
for m in mods:
    if m["events_recomputed"]:
        rows_e.append([m["m_id"], cut(m["module"], 40), " · ".join(cut(e, 110) for e in m["events_recomputed"][:3]),
                       ", ".join(m["private_fields"][:5]) or "—"])
table(["M", "module", "events the module recomputes itself (file:line in the checkout)", "private tracker fields read"], rows_e,
      [0.9, 4.0, 16.0, 6.0], font_pt=6.5)
para("The review's attention notes (the static audit of 7 September): what the active code verifies against what the checklist names.",
     size=8.5, color=GREY, after=2)
rows_r = [[m["m_id"], cut(m["module"], 44), m["attention"] or "—"] for m in mods if m["attention"]]
table(["M", "module", "attention"], rows_r, [0.9, 4.6, 21.4], font_pt=7)

doc.save(OUT)
print("written", OUT)
