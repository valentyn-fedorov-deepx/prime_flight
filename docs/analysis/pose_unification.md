# Pose models: one shared model for the pose modules (2026-10-13)

Question (PF-Q4-02): the modules run several different person-pose networks. Can one model serve all of them, does a
module's verdict change, and what does it save? In short: **RTMPose-l, already in production in gse-chocks, served all
seven pose modules of the test set with their code unchanged. 36 of 38 verdicts stayed the same and accuracy against
the labels is the same (32 of 38). Pose time fell by 58 %, the four HRNet modules' jobs by 28–39 %.** DWPose-l, the one
model that would also cover handrails, is twice as slow and lost two correct verdicts: it stays in handrails only.

## 1. What runs today

| module | model | input | flip test | weights | how the module calls it |
|---|---|---|---|---|---|
| hand-signals | HRNet-W48 COCO-17 (mmpose 1.3.1) | 192×256 | yes (2 passes) | 269 MB `.pth`, 63.6 M params | `mmpose.apis.inference_topdown`, all boxes of a frame |
| steering | HRNet-W48 (same file) | 192×256 | yes | same | one box per call |
| lead-marshaller (`pre_arrival_departure`) | HRNet-W48 (same file) | 192×256 | yes | same | all wing-walker boxes of a frame |
| wing-walkers (`obstruction_hand_signals`) | HRNet-W48 (same file) | 192×256 | yes | same | all person boxes of a frame |
| pin-verification | SimCC ResNet-50 COCO-17 (mmpose) | 288×384 | yes | 178 MB `.pth`, 43.3 M params | all near-wheel boxes of a frame |
| fod-walk (`dev`) | MoveNet SinglePose Thunder (ONNX) | 256×256 letterboxed crop | no | 25 MB, 6.3 M params | one person crop per call, only the shoulders' x order is read |
| gse-chocks (`per_component_improvement`) | **RTMPose-l body7** COCO-17 (ONNX, own runner) | 192×256 | no | 110 MB, 27.6 M params | one box per call |
| handrails-on-gse | DWPose-l whole body, 133 keypoints (ONNX) | 288×384 | no | 134 MB, 33.6 M params | needs the hands; no run in the test set |
| walk-arounds, safety-vests gate | YOLOv8-pose | — | — | — | not in this test |

Four HRNet copies, one SimCC, one MoveNet and one RTMPose-l: four different networks for the same 17 COCO body keypoints.
Inventory with file:line: `module_compute/pose_person.json`.

## 2. How the shared model was put in (no module code changed)

- `pf/pose/topdown_onnx.py` — one top-down runner for SimCC ONNX exports (RTMPose, DWPose). The crop is mmpose's own:
  box → centre/scale with padding 1.25, widened to the model aspect, one affine warp of the full frame, BGR→RGB, ImageNet
  mean/std; decoding is mmpose's SimCC rule. Checked against mmpose's test pipeline on real boxes: **0 px difference**
  (`scripts/pose_bench.py`, `geometry_check_vs_mmpose_pipeline`); unit tests `tests/test_pose_topdown.py`.
- Every ONNX run has the same input shape (batches of 4, padded). ONNX Runtime's CUDA provider pays **≈ 30 ms whenever the
  input shape differs from the previous run** (batch sizes alternating 1–6: 33 ms per run; a fixed batch of 4: 5 ms),
  whatever the cuDNN search mode. Padding does not change a box's output (checked bit for bit).
- `pf/pose/shims.py` serves the three pose interfaces the modules use — mmpose `init_model` / `inference_topdown`,
  fod-walk's MoveNet `PoseEstimation`, gse-chocks' `onnx_model_utils` — from that runner, installed before the module is
  imported (`scripts/run_module.py --pose-override rtmpose-l`). The module's own pose weights are not loaded.
  `--pose-timing` is the control: the module's own model, with the same call counters.

## 3. Model against model on the same boxes

`scripts/pose_bench.py`, zHxIAF2vUGxJ, 120 frames with persons, 280 person track boxes, one call per frame with all boxes
of the frame (as the modules call), RTX 5070 Ti, after a warm-up. Agreement is with HRNet-W48 (the model of four of the
five mmpose modules), on the keypoints HRNet itself scores ≥ 0.3, distance in box heights.

| model | ms per call | ms per box | median distance to HRNet | within 10 % of the box height (all / arms) | score median |
|---|---|---|---|---|---|
| HRNet-W48, flip (today) | **42.2** | 18.1 | — | — | 0.74 |
| SimCC ResNet-50, flip (today, pin-verification) | 12.4 | 5.3 | 1.3 % | 93.9 % / 91.3 % | 7.70 (not calibrated) |
| **RTMPose-l** (shared) | **8.9** | 3.8 | 1.5 % | 92.9 % / 90.2 % | 0.57 |
| RTMPose-l on BGR (gse-chocks' way) | 8.2 | 3.5 | 1.5 % | 93.4 % / 91.0 % | 0.57 |
| RTMPose-l, flip | 11.4 | 4.9 | 1.4 % | 92.6 % / 90.2 % | 0.57 |
| DWPose-l, body keypoints | 13.9 | 6.0 | 1.3 % | 94.8 % / 92.4 % | 0.57 |

The two production-grade alternatives to HRNet (SimCC, RTMPose-l) differ from it about as much as each other; flip test
buys nothing measurable; channel order makes no difference. On fod-walk's crops the shoulder-order decision of MoveNet and
RTMPose-l agrees on 74 % of 209 crops (front/back is the ambiguous part of any pose model); on gse-chocks' crops the shared
runner moves the keypoints by a median 1.1 % of the box height against gse-chocks' own runner and keeps its low-confidence
decision on 95 %.

## 4. Module verdicts

Seven modules × the test videos on disk where they have a v2 result: 38 runs on 8 videos, the same v2 inferences, the same
flags; only the pose model differs (`scripts/testset/variant_run.py --reuse-v2`, `scripts/pose_gate_summary.py`,
`pose/gate_summary.json`; bench: `pose/bench_zHxIAF2vUGxJ.json`).

| module | own model | runs | same verdict with RTMPose-l | changed |
|---|---|---|---|---|
| hand-signals | HRNet-W48 | 6 | 6 | — |
| steering | HRNet-W48 | 4 | 4 | — |
| pin-verification | SimCC ResNet-50 | 4 | 3 | MwCSLbQ7QvXQ: Not observed → **Pass** (label: not observed) |
| lead-marshaller | HRNet-W48 | 6 | 6 | — |
| wing-walkers | HRNet-W48 | 6 | 5 | KB04bkqBI7ms: Fail → **Pass** (label: pass) |
| fod-walk | MoveNet Thunder | 6 | 6 | — |
| gse-chocks | RTMPose-l, own runner | 6 | 6 | — |
| **total** | | **38** | **36 (95 %)** | one moves to the label, one away: **correct 32 → 32 of 38** |

Control: the modules' own models rerun with the timing counters (`pose_ctl`) give 38 of 38 verdicts identical to the
stored v2 run, so the run-to-run noise is zero here and both changes come from the pose model. The pin-verification change
is fast: RTMPose-l saw a worker bent at the wheel on 12 frames in a row (the module's 1.5 s rule) and stopped; SimCC never
reached 12 in 379 calls. One video each way: with 4–6 runs per module the sample is too small to call a direction.

The same 38 runs with **DWPose-l** (body keypoints of the whole-body model, `pose_dw`): 36 the same, but both changes go
against the label — steering TtKESVA7IEIU pass → **fail** (label pass) and the same pin-verification video as above —
**correct 32 → 30**. Its pose time is 482 s against 251 s for RTMPose-l and 599 s for the modules' own models.

## 5. What it saves

The same machine, the same load (two module jobs at a time), the module's own model (`pose_ctl`) against the shared
model (`pose_rtm`); seconds summed over the runs, pose time measured around the pose call inside the module.

| module | pose calls | pose time, own → shared | ms per call | module wall time, own → shared |
|---|---|---|---|---|
| hand-signals | 2 602 | 156.0 → 22.5 s | 60.0 → 8.7 | 742 → 536 s (**−28 %**) |
| steering | 878 | 51.6 → 7.8 s | 58.8 → 8.9 | 149 → 96 s (**−36 %**) |
| pin-verification | 633 → 279 | 8.2 → 4.5 s | 13.0 → 16.3 | 185 → 166 s (−10 %) |
| lead-marshaller | 1 782 | 110.3 → 20.2 s | 61.9 → 11.4 | 339 → 235 s (**−31 %**) |
| wing-walkers | 2 622 | 150.6 → 23.2 s | 57.5 → 8.8 | 417 → 256 s (**−39 %**) |
| fod-walk | 21 297 | 105.3 → 151.7 s | 4.9 → 7.1 | 232 → 260 s (+12 %) |
| gse-chocks | 2 438 | 16.9 → 21.3 s | 7.0 → 8.7 | 669 → 589 s (same model; the −12 % is load noise) |
| **total** | | **599 → 251 s (−58 %)** | | **2 733 → 2 137 s (−22 %)** |

- The four HRNet modules: pose −84 % (468 → 74 s), module jobs −28 to −39 %, also no 269 MB checkpoint to load per job.
- pin-verification: SimCC is already light, the gain is small; its per-call figure includes the first-call warm-up of
  each session (≈ 0.35 s), heavy on runs of 3–12 calls.
- fod-walk is the one module that gets slower: MoveNet Thunder (6.3 M params) on one crop per call is cheaper than
  RTMPose-l on one crop per call; it calls pose 21 297 times on 6 videos (every person, every frame before the aircraft).
  Its verdicts do not change, so it can stay on MoveNet, or take poses from a shared per-frame batch in real time.
- Weights: one 110 MB file instead of HRNet 269 MB (×4 modules) + SimCC 178 MB + MoveNet 25 MB; hand-signals and
  wing-walkers also carry an unused 255 MB HRNet copy (`pose_person.json`, `files_present_not_loaded`).
- Real time: a shared pose step can batch all persons of a frame once for every pose module, but only after the modules
  also agree on the crop (offsets 0.1/0.1, 0.2/0.1, 0.25/0.1 or the raw box) and on the image fed (CLAHE in hand-signals,
  lead-marshaller and wing-walkers; histogram equalisation in steering). That is the next, separate test.

## 6. The GM's own models (the other half of the question)

Production GM (a0157a4) runs three detection heads every frame, plus MobileSAM, the entity detector and the camera
classifier. Read from the ONNX files (stem width and parameters):

| head | file name says | actually | classes | input | ms on the 5070 Ti (`gm_speed.md`) |
|---|---|---|---|---|---|
| GM | `GM_yolov8m_best_augmentation_march2024` | **YOLOv8n** (3.1 M params) | 25 | 1088 | 3.8 |
| vehicle | `VM_yolov8m_last_september2023` | YOLOv8m (25.8 M params) | 1 (`vehicle`) | 1088 | **8.0** |
| chocks | `chocks_v4.3_200ep_yolov8` | YOLOv8s (11.1 M params) | 1 (`chock`) | 1280 | 5.1 |

The one-class vehicle head is the biggest network of the GM and about half of its detection time (8.0 of 16.9 ms). On
four test videos (85 534 vehicle boxes, every 4th frame) **69 % of the vehicle boxes coincide (IoU ≥ 0.5) with a GM box of
a vehicle class** (of those: gse 27 %, trailer 24 %, beltloader 19 %, pushback 17 %, tow bar 10 %, fuel truck 3 %); 27 %
have no GM box even at IoU 0.3. So the vehicle head cannot simply be dropped (six modules read `vehicle`: aircraft-chocks,
cargo doors, cones-after-GSE, pin-verification, pushback-pathway, safety-zone), but it is the clear candidate to fold into
the GM head: teach the YOLOv8n GM the `vehicle` class (or retrain the vehicle head as a nano). That needs a training run
and the verdict gate on those six modules; it is not done here.

## 7. Recommendation

1. **One body-pose model, RTMPose-l, for the body-keypoint modules** (the seven here); DWPose-l stays in handrails, which
   needs the hands. Five networks become two. fod-walk can stay on MoveNet (cheaper for its one-crop calls, no verdict
   change either way) or move for uniformity.
2. Before production: the two changed verdicts go to Oksana / Ihor (a model change must not change the semantics
   silently), and the sample grows — 4 of the 12 pose-module videos of the monthly set are not on disk any more, and
   4–6 runs per module is small. Same gate: `variant_run.py --reuse-v2 "--module-args=--pose-override rtmpose-l"`.
3. Rolling it out in a module is small: the module keeps its code and installs the shim at its entry (or calls the
   runner directly); the weights file is the one gse-chocks already pulls.
4. Real time: one pose step per frame for all pose modules — after the crop and image rules are made common (§5), a
   separate test with the same gate.
5. GM: fold the vehicle class into the GM head (§6) — the largest single GM saving left, needs a training run (Denys's
   datasets, Yurii) and the gate on the six modules that read `vehicle`.

## 8. The whole validation set: 66 of 90 videos (run 2026-10-13/14, summary 2026-10-27)

`scripts/testset/pose_full_run.py` ran every pose module with its own model (`pose_ctl`) and with RTMPose-l (`pose_rtm`)
side by side, four jobs at a time, on the v2 GM / tracker inferences (the same for both); DWPose-l was dropped from the
run (twice as slow, already worse in §4). It stopped after 66 of the 90 videos with pose modules (24 videos, 185 runs
left). Summary: `out/pose/interim_summary3.json`, `out/testset/compare_pose_rtm_vs_pose_ctl_interim.json`; event
verdicts merged over cameras, truth from the monthly report.

| module | correct, own → RTMPose-l | changed (toward / away from the label) | module time, own → RTMPose-l | pose time |
|---|---|---|---|---|
| hand-signals | 53 → 53 of 55 | 0 | 15 033 → 12 647 s (−16 %) | 2 392 → 367 s |
| lead-marshaller | 53 → 53 of 55 | 0 | 6 187 → 4 187 s (−32 %) | 2 219 → 385 s |
| steering | 38 → 41 of 46 | 7 (5 / 2) | 3 439 → 1 489 s (−57 %, partly earlier exits) | 1 889 → 171 s |
| pin-verification | 35 → 36 of 46 | 4 (2 / 1, 1 neither) | 4 730 → 4 901 s (+4 %) | 284 → 167 s |
| gse-chocks (same model, shared runner) | 47 → 47 of 56 | 2 (1 / 1) | 14 946 → 14 937 s | 718 → 701 s |
| fod-walk | 53 → 52 of 57 | 1 (0 / 1) | 5 004 → 5 769 s (+15 %) | 2 781 → 3 473 s |
| **wing-walkers** | **47 → 36 of 55** | **13 (1 / 12)** | 7 258 → 5 483 s (−24 %) | 2 194 → 351 s |
| **total** | **326 → 318 of 370** (without wing-walkers 279 → 282) | 27 | 56 597 → 49 414 s (−13 %) | 12 477 → 5 614 s (−55 %) |

With fod-walk left on MoveNet: pose time −78 % (9 696 → 2 141 s), module time −14 %. Every module except wing-walkers
keeps or gains correct verdicts.

**What it means for production.** The pose runs inside the module jobs, so the GM job does not change. On the five
videos with production job times (`gs://cv-modules-logs`, 21–22.10: GM b6e1a3e, trackers, the module jobs) the five
modules whose model changes (hand-signals, steering, lead-marshaller, wing-walkers, pin-verification) take 105 of 2 181
pod minutes (5 %). With their local pose shares (job −13 %, −47 %, −31 %, −26 %, −3 %) the change saves about 21
minutes, **≈ 1 % of the pod time** (0.5–7 minutes per video); if HRNet is relatively slower on the T4 than here, up to
about 2–3 %. Time to result does not move: the modules run in parallel and none of these is the slowest (hand-signals
6–9 min; the slowest are handrails-on-gse 47–74 min, safety-zone up to 51, safety-vests up to 35). The value of the
change is two pose models instead of five and the real-time budget (60 → 9 ms per pose call), not post-processing time.

### Wing walkers: why it loses with RTMPose-l

- All 12 losses are the hand-signal rule: the walkers of both sides are found (from the tracks' paths, no pose
  involved), and with RTMPose-l one of them "does not signal" (11 × Pass → Fail, label pass; one Fail → Not observed,
  label fail). The one gain is KB04bkqBI7ms, where HRNet missed the right walker's signal.
- The rule (`main.py:314-323`, `:494-505`): a frame signals when a wrist is less than 4.8–8 % of the box height below
  its elbow and both points score ≥ 0.2; 8 such frames (1 s) in the 60 s window are enough.
- The persons are small: the median box is 57 px high, an arm about 10 px. Arm scores sit at the threshold for both
  models (median of min(wrist, elbow): HRNet 0.21, RTMPose-l 0.19; half of the boxes below 0.2). The rule measures
  whether the model ever puts a wrist at elbow height with some confidence for 8 frames, and HRNet does so about twice
  as often (wMk1umBGpV8f, 442 boxes: 19 % against 10 % of the frames). The thresholds were set on HRNet.
- Flip test and DWPose-l do not help (wMk1umBGpV8f: both Fail; DWPose-l scores lower still, median 0.12).
- The hand-signal part decides one of the 11 Fail labels (HwGR6Wvf7mE2K3, both models agree); the other Fails come from
  a missing walker or a blocked side, without the pose. 15 of the 55 videos do not depend on the pose at all.

Fix in progress: record both models' arm keypoints on the same walkers (`scripts/ww_pose_record.py`: the module decides
with HRNet; RTMPose-l on the CLAHE frame, on the raw frame, with flip test, and DWPose-l run on the same boxes) over the
40 pose-dependent videos (`scripts/ww_pose_batch.py`), then replay the rule offline for any model and thresholds
(`scripts/ww_pose_replay.py`; on KB04bkqBI7ms the replay gives the recorded verdicts of both runs). Target: the three
thresholds (`handsignals.conf_thr`, the margins, `min_frames`) for RTMPose-l that give HRNet's verdicts on the 40 videos,
recover the 11 passes and keep HwGR6Wvf7mE2K3 a Fail. New thresholds go to Oksana / Ihor with the verdict table before
production; the fallback is HRNet in wing-walkers only.
