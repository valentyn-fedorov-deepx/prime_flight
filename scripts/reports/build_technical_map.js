// One-page technical map: models, module weight, dependencies between modules, duplicated logic (A4, dense).
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  BorderStyle, ShadingType, LevelFormat, TableLayoutType,
} = require("docx");

const OUT = process.argv[2] || "PF_technical_map_one_page.docx";
const FONT = "Calibri";
const BODY = 14, SMALL = 13, HEAD = 17;
const DARK = "16213A", GREY = "5A6472";
const LINE = 204;

const run = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || BODY, bold: o.bold, italics: o.italics, color: o.color });
const para = (runs, o = {}) => new Paragraph({
  children: Array.isArray(runs) ? runs : [run(runs, o)],
  spacing: { before: o.before ?? 0, after: o.after ?? 22, line: o.line ?? LINE },
  numbering: o.num ? { reference: o.num, level: 0 } : undefined,
});
const heading = (text) => new Paragraph({
  children: [run(text, { size: HEAD, bold: true, color: DARK })],
  spacing: { before: 54, after: 14, line: LINE },
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "C9CDD3", space: 1 } },
  keepNext: true,
});
const rich = (text, o = {}) => text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean)
  .map((p) => p.startsWith("**") ? run(p.slice(2, -2), { ...o, bold: true }) : run(p, o));
const bullet = (text) => para(rich(text), { num: "bul", after: 6 });

const border = { style: BorderStyle.SINGLE, size: 3, color: "C9CDD3" };
const borders = { top: border, bottom: border, left: border, right: border };
const cell = (text, width, o = {}) => new TableCell({
  width: { size: width, type: WidthType.DXA }, borders,
  margins: { top: 10, bottom: 10, left: 42, right: 42 },
  shading: o.shade ? { type: ShadingType.CLEAR, fill: o.shade, color: "auto" } : undefined,
  children: [new Paragraph({ children: rich(text, { size: SMALL, bold: o.bold }), spacing: { before: 0, after: 0, line: 196 } })],
});
const table = (widths, rows) => new Table({
  width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED,
  rows: rows.map((r, i) => new TableRow({ children: r.map((t, j) => cell(t, widths[j], i === 0 ? { bold: true, shade: "E9ECF1" } : {})), tableHeader: i === 0 })),
});

const W = 11906 - 2 * 520;
const children = [];
children.push(new Paragraph({ children: [run("Prime Flight / RampVision — technical map: models, module weight, dependencies, duplicated logic", { size: 23, bold: true, color: DARK })], spacing: { before: 0, after: 6 } }));
children.push(para([run("6 October 2026 · Valentyn Fedorov · from the architecture review (docs/arch_review), the consumption matrix and compute audits (docs/analysis: module_consumption, module_compute, module_dataset_needs), the real-time measurements (rt_module_cost, rt_environment, rt_optimisation_plan) and the GM / tracker as-is reports. Live milliseconds: one camera at 8 fps on an RTX 5070 Ti with the card kept busy, 125 ms budget per frame; post seconds: clean single jobs on a 36-min event.", { size: 13, color: GREY })], { after: 30 }));

// ---------------------------------------------------------------- models
children.push(heading("1 · Which models run, where, and what each costs"));
children.push(table([1500, W - 1500], [
  ["Stage", "Models and measured cost"],
  ["General Model (one job per video, two decodes)", "Three fp16 ONNX YOLO heads on every frame: **GM YOLOv8m @1088** (apron classes; 4.3 ms pure inference, 8.5 ms busy), **chocks YOLOv8 @1280** (22.6 MB; 5.6 ms pure, +3.0 ms on top of GM), **vehicle YOLOv8m @1088** (52 MB; 8.3 ms pure, +5.8 ms). All three 19.2 ms busy, **11.1 ms through TensorRT**. Beside them: **MobileSAM vit_t** (40.7 MB) mask of the main aircraft every frame for its motion state; **entity YOLOv5 @1280** (14.7 MB) every 8th frame up to 40 hits; **camera cone/wing EfficientNet-B0** (16.3 MB) on every post-arrival frame with the main aircraft, on CPU through PIL; tail classifier (0.4 MB). The second run re-decodes the whole video to label obstacle / side_obstacle rows and the main aircraft. Production: 207 ms per frame (1.7× slower than recording)."],
  ["Tracker (one job per video, pixels every frame)", "**Three DeepSORT instances** (belt loader, workers, GSE) with one re-id net `scripted_ckpt.t7` (46 MB) — 8.3 ms per frame; instance masks at (re)initialisation: **plane YOLO11s-seg** (20.6 MB) and **BL/GSE YOLO26s-seg** (23.4 MB); FAST keypoints + PyrLK optical flow on ≤250 points per object; `estimate_sigma` noise estimate every 2 s (2.3 ms; 100 ms per frame on the master pin). Per class busy: airplane 4.9 ms, +person 7.7, +belt loader 20.7, all four 26.2 (belt loader path 9.6, aircraft 4.0, GSE 2.4). Production pin 36–49 ms per frame; v2 byte-identical."],
  ["Modules with own models (13 of 27)", "**safety-vests**: Swin-T orientation (3 classes, 256) + Swin-T vest (2 classes, 256) + ResNet-18 presence gate (192) + HSV rules, every person every frame — **18.8 ms, 5.2 cores**. **handrails-on-gse**: EfficientNet-B0 handrail (224) + Unet MiT-B0 (320×256) + DWPose-l ONNX (288×384) + EfficientNet hand classifier — **12.5 ms, 4.9 cores**. **HRNet-W48 COCO 256×192** (269 MB, one identical file) in **hand-signals, steering, lead-marshaller, wing-walkers**, flip test on (two backbone passes per call). **pin-verification**: SimCC ResNet-50 288×384. **gse-chocks**: RTMPose-l ONNX per (GSE × person), not batched + EfficientNet-B0 difference classifier. **aircraft-chocks**: EfficientNet-B0 difference classifier (other weights) + template matching per rear wheel. **safety-zone**: MobileSAM encoder per re-seeding vehicle + its own norfair truck tracker. **conditioned-air**: YOLO11s-seg @992 every 16th frame (`best28_full.onnx` never loaded). **fod-walk**: MoveNet Thunder ONNX per person, not batched. **safety-handrails**: the same EfficientNet-B0 handrail classifier every 8th frame. **walk-arounds**: YOLOv8m-pose 640 per person crop (pre-departure: every frame, not batched) + Depth Anything V2 ViT-B 518×924 + MobileSAM for the TDV build + a small CNN; own Python environments. **hair-policy**: two EfficientNet-B0 (Pyarmor build, WSL, CPU). **steering** also a tsai InceptionTime time-series classifier. Loaded by nobody: HRNet-W48 384×288 (255 MB, in all four HRNet checkouts), `wand_detector.pt`, `worker_type_classifier.pkl`, `v4_probe_head.npz`."],
]));

// ---------------------------------------------------------------- heaviest
children.push(heading("2 · The heaviest modules (live own work per frame · CPU · RAM · post job on the whole event · batch ms per recorded frame)"));
children.push(table([2050, 1150, 900, 850, 1050, 1000, W - 7000], [
  ["Module", "live ms/frame", "cores", "RAM GB", "post job s", "batch ms", "why"],
  ["safety-vests", "**18.8**", "5.2", "1.7", "370", "28.2", "two Swin-T + ResNet-18 on every person of every frame, whole session; decides at session end"],
  ["handrails-on-gse", "**12.5**", "4.9", "2.8", "249", "30.7", "four networks per belt-loader visit (classifier, segmentation, pose, hand classifier); session end"],
  ["wing-walkers", "5.1", "5.0", "1.9", "111", "3.2", "HRNet-W48 on all persons from departure start to +60 s; p95 85 ms, latency p95 1.4 s"],
  ["gse-chocks", "3.3", "2.0", "2.4", "76", "6.1", "RTMPose per GSE × person, not batched; difference classifier per 10 s; three tracked classes; session end"],
  ["lead-marshaller", "2.5", "3.4", "2.4", "59", "5.7", "HRNet-W48 on all workers while the plane approaches; full-frame CLAHE copy; 96-frame buffer"],
  ["safety-handrails", "2.4", "4.6", "1.3", "46", "8.4", "reads and converts every window frame, uses 1 of 8"],
  ["hand-signals · safety-zone · aircraft-chocks", "0.3 · 0.3 · 0.5 (pass 1 only)", "2.8 · 1.1 · 2.2", "3.1 · 1.8 · 1.9", "91 · 83 · 38", "10.1 · 10.3 · 5.7", "two passes: the whole cost sits in the second pass that live cannot run (`KeyError: 1`); safety-zone pays MobileSAM + a second vehicle tracker"],
  ["the 14 pixel-free modules", "0.1–1.5", "0.6–0.9", "0.75", "7–20", "1.2–4.9", "rows only; their cost is what they drag in: the vehicle head +5.8 ms, belt-loader tracking +15.7 ms"],
]));
children.push(para(rich("Twenty modules together on one camera: 56 ms of 125 (GM 22.4 + tracker 26.6 + hand-off 7.3), 4.2 cores on average with 100 % bursts of 8, 18 GB RAM, GPU 24.5 % busy — the shared part is ≈85 % of the frame path and the modules' own work is the small part. In batch the peak stage is download/upload: handrails-on-gse 30.7 + vests 28.2 + safety-handrails 8.4 + gse-chocks 6.1 + aircraft-chocks 5.7 + 3-stop 3.4 + beltloader-chocks 2.7 + bl_rear_cone 2.4 + cargo 1.4 = **89 ms per recorded frame**, 3–4× over the budget; the walk-arounds add 26.1 (pre-departure) and 6.8 (post-arrival) and stay post."), { after: 20 }));

// ---------------------------------------------------------------- dependencies
children.push(heading("3 · Dependencies between modules: what they share"));
children.push(bullet("**Inputs (architecture review, 29 tasks × 32 concepts):** camera-obstacle status E07 is read by 23 tasks, aircraft layout E03 by 13, arrival context E01 by 11, belt-loader service status E09 by 10, departure context E02 by 7, chocks/cones detections E04 by 6, worker tracks E11 by 5, chock analysis E14 by 5 (the three chock verdicts, gse-chocks, beltloader-chocks), workers-near-equipment E13 by 4, pushback attachment E10 by 3 (main-gear and nose-wheel chocks, pin verification), ground areas E19 by 3 (FOD corridor, safety zone, pushback path — three different polygons), handrail state E16 by 2 (the same EfficientNet classifier), walk-around evidence E18 by 2; one proposed reuse: the learned pin-installation actions (E24, steering) for pin verification, which today uses posture heuristics."));
children.push(bullet("**GM classes:** cone feeds 22 checks, person 17, beltloader 9, back_door 8, front_door 7, chock 5, pushback 4; the derived rows obstacle / side_obstacle (exact copies of boxes of classes 12/3/31/15, synthesised in GM's second run from the front-wheel geometry) are read by 12 modules as if they were detections; only two modules read confidence at all. **Tracker:** 24 of 27 modules derive the stage themselves and 19 read private optical-flow fields (`_p0`, `_st`, `_of_dots_lifetime`, `_status`), so every tracker version change reaches them; the belt loader is the expensive dependency — 9 checks need it, and it costs +15.7 ms of tracking for the first of them."));
children.push(bullet("**Model sharing:** HRNet-W48 ×4 (identical file; one instance per host is EXACT, shared results are not: windows barely overlap and the preprocessing differs — full-frame CLAHE vs YCrCb on the box); EfficientNet-B0 ×6 (handrail ×2 same weights, difference classifier ×2 different weights, camera classifier in GM, hair policy ×2 — sharing beyond the handrail pair is SEMANTIC); MobileSAM ×4 (GM main aircraft, tracker masks, safety-zone, walk-around TDV); five different pose stacks for ten modules (HRNet, SimCC ResNet-50, RTMPose-l, DWPose-l, MoveNet, YOLOv8-pose); safety vests and hair policy both run a person crop — the only pair free of the aircraft and the stage. **Derived tasks:** proper belt-loader approach = 3-stop + hand-signals; aircraft-chocks gives three verdicts; seat belts out of scope."));

// ---------------------------------------------------------------- duplicated logic
children.push(heading("4 · Where logic is duplicated"));
children.push(bullet("**Arrival stage:** the same block (`movement_anomaly_custom` from `_p0/_prev_p0/_st` → `normal_moving_counter > 24` → `have_arrival_stage`, pre-arrival = `arrival_frame > 60·fps`) is copied verbatim in **9 modules** (aircraft-chocks, cargo doors, chocks-and-cones, crew present, FOD walk, lead marshaller, huddle, safety-zone twice, steering); six more carry their own T_arr / T_dep rules (cones-placed 30·fps moving; pushback wing walkers STOPPED for 60 s; wing walkers stop/depart thresholds with reset; walk-arounds first STOPPED and 3·fps or immediate MOVING; pushback-pathway from the airplane status; hand-signals from `arrival_frame`) — **five definitions of departure** in the code base."));
children.push(bullet("**pushback_attached:** identical rule in aircraft-chocks and pin-verification (IoU > 0.8 with the median pushback box of pass 1 for > 5 s / > 10 s, nose-geometry fallback) — two copies, both the reason those modules need a second pass; pushback wing walkers uses a third (wheel–pushback distance < 315 px, display only). **Belt loader at the door / active:** five variants — 3-stop (relative intersection with the aircraft > 0.2 + stop counters), beltloader-chocks and bl_rear_cone (`bl_type == needed` + stopped), handrails-on-gse (`bl_type` + `is_stopped`), safety-handrails (+ rear-wheel filter + identity swap across track ids), hand-signals (`_status` + workers ROI). **Aircraft type** jet/airplane recomputed from wing/engine geometry in beltloader-chocks and hand-signals although GM publishes it."));
children.push(bullet("**Pixels and buffers:** every frame read letterboxes to 1280×768 and makes a CHW/RGB copy that nothing uses (`cv_common/utils/datasets.py`), paid by all pixel modules; full-frame CLAHE copies in three HRNet modules; the 200-frame buffer of steering and the 96-frame buffer of lead-marshaller (6.2 MB per frame); safety-handrails converts 8 frames to use 1. **Own trackers inside modules** beside the shared one: safety-zone (norfair trucks + cv_common Vehicle with pixel optical flow), huddle (norfair cones), seat-belts (norfair persons). **Infrastructure:** 10 different cv_common pins while `db_worker/ML_worker.py` is byte-identical in all 19 checkouts; two checkouts import helpers absent at their pin (PlaneArrivalDetector; departure / presence helpers); three DeepSORT id counters collide across classes and Kalman boxes are cast to int, so tracker boxes ≠ GM boxes; rows are joined by position, not frame id."));
// ---------------------------------------------------------------- stage map
children.push(heading("5 · Module map by stage (window the module is active in · decision type · inputs · live ms per frame) and the batch load per stage"));
children.push(table([1550, W - 1550 - 1050, 1050], [
  ["Stage", "Modules: window, decision (INSTANT one detection → Fail · EVENT verdict at the event · DEADLINE Fail if not seen by T · LOOKBACK window before T · WHOLE the whole event), inputs, live ms", "batch ms per recorded frame, sum"],
  ["PRE_ARR · start → T_arr", "chocks-and-cones (LOOKBACK, rows, 0.1) · crew-present (LOOKBACK, rows, 0.5) · FOD walk (LOOKBACK, pixels, MoveNet, 1.3) · huddle (LOOKBACK, pixels, no model, 0.9) · lead-marshaller (LOOKBACK, pixels, HRNet, 2.5) · safety-zone (T_arr − 2 min → T_arr, two passes, MobileSAM + own tracker, RETHINK)", "51.7 (vests 28.2 of it)"],
  ["ARR_POST · T_arr → …", "cones-placed (DEADLINE T_arr + limit, rows, 0.6) · steering (DEADLINE T_arr + 240 s, pixels, HRNet + InceptionTime, 0.7) · hand-signals (T_arr → GSE at the door, two passes, HRNet, RETHINK) · nose gear chocks (within 30 s of the stop; aircraft-chocks, two passes, EfficientNet difference) · post-arrival walk-around (WHOLE, POST, own environment)", "48.2 (+6.8 post)"],
  ["DOWNLOAD · BL appears → BL leaves", "3-stop (BL appeared → stopped at the door, intersection > 0.2; EVENT, rows, 0.6) · beltloader-chocks (BL at door → drove away, EVENT, rows, 0.3) · bl_rear_cone (EVENT, rows, 0.4) · cargo doors (DEADLINE end of stage / 480 frames, rows, 0.9) · gse-chocks (GSE stopped → drove away, EVENT, pixels, RTMPose + EfficientNet, 3.3, session end) · handrails-on-gse (BL at door → worker off the BL, EVENT, pixels, four networks, 12.5, session end) · safety-handrails (BL at door → drove away, EVENT, pixels, EfficientNet, 2.4)", "**89.0** — the peak, 3–4× the budget"],
  ["PRE_DEP · BL leave → T_dep", "conditioned-air (LOOKBACK T_dep − 10 min, pixels, YOLO-seg every 16th frame, 1.3) · cones-removed (EVENT BL leave → T_dep, rows, 1.5) · pin-verification (BL leave → pushback attached, two passes, SimCC pose, PATCH) · main-gear and nose-wheel chock removal (after pushback attached; aircraft-chocks, two passes) · pre-departure walk-around (WHOLE, POST, own environment)", "45.1 (+26.1 post)"],
  ["DEP · pushback → T_dep + 60 s", "pushback wing walkers (pushback attached → started moving, EVENT, rows, 0.3) · pushback-pathway (T_dep − 45 s → T_dep, INSTANT, rows, 0.5) · wing-walkers (T_dep − preparation → T_dep + 60 s, LOOKBACK, pixels, HRNet, 5.1)", "42.9"],
  ["ALL · start → end", "safety-vests (INSTANT: an unzipped vest → Fail, but the client verdict only at session end; pixels, two Swin-T + ResNet-18, 18.8, the only check free of the aircraft and the stage) · hair-policy (WSL, CPU, not hosted)", "28.2 all session"],
]));
children.push(para(rich("**What this means for the shared layer:** one stage detector replaces 9 + 6 copies of the stage and 2 of pushback_attached; one HRNet instance per host and the frame-reader fix are EXACT wins; one pose stack and shared segmentation masks are SEMANTIC and need the verdict gate; the belt-loader state (five variants) belongs in the tracker's published records, not in the modules."), { before: 16, after: 0 }));

const doc = new Document({
  creator: "Valentyn Fedorov", title: "Prime Flight technical map — one page",
  styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 180, hanging: 130 } } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 470, bottom: 420, left: 520, right: 520 } } }, children }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("written", OUT, buf.length, "bytes"); });
