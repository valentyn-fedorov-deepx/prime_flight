# Per-frame compute of the pose / person-crop modules (monthly test-set checkouts)

Date 2026-09-15. Scope: hand-signals, steering, pin-verification, lead-marshaller, wing-walkers, fod-walk, safety-vests,
hair-policy. Checkout = `scripts.testset.profiles.profile(<module>)["module_dir"]` (empty → `external/<module>`).
Method: read-only audit of those checkouts, sha256 of every weight file (first 16 hex), a non-executing scan of pickle
class references / tensor shapes and of the ONNX header, mmpose behaviour read from the overlay the test set runs
(`out/envs/mmpose1`, mmpose 1.3.1). **Nothing was run.** Machine-readable version with every field:
`pose_person.json` (same folder). `file:line` is relative to the module checkout unless a path is given.

Context from the task brief (contended batch runs, median ms per recorded frame; early-exiting modules look cheaper per
recorded frame than per active frame): safety-vests 28, hand-signals 10, lead-marshaller 5.7, pin-verification 3.9,
wing-walkers 3.2, fod-walk 3.0, steering 1.9. hair-policy: ≈0.9 CPU-s per frame on CPU (`tasks/notes/PF-Q1-18.md:168`).
One decoded 1920×1080×3 frame = 6.2 MB; buffer sizes below are code constants × 6.2 MB.

## 1. Summary table

"2 passes/call" = `flip_test=True` in the pose config: every pose call runs the backbone on the batch and on its mirror
(`mmpose/models/pose_estimators/topdown.py:102-104`).

| module | checkout | models (architecture, input, calls per frame in the window, batched) | pixel work and buffers | passes, length reads, when it decides | duplicated shared components |
|---|---|---|---|---|---|
| hand-signals (M13) | `external/hand-signals`, default HEAD 60c0faf (≠ pin 6bd027f2); runner + `out/envs/mmpose1`; numpy1 no | HRNet-W48 td-hm COCO 192×256 (sha 0e67c6167d6a10fe), full-frame CLAHE, box +10 %, 2 passes/call. (a) 1 call/frame while a beltloader moves and workers are in the ROI; (b) on the stop frame of a new beltloader, one call per buffered frame in (f−240, f−40] — up to ≈200 calls. Batched per frame. Measured 375 calls / 462 persons on zHxIAF2vUGxJ | copy + full-frame CLAHE per call (:554-555, :358); two full-frame masks + bitwise_and + 2 sums every frame after arrival (:183-196); **buffer ≤ 240 raw frames ≈ 1.49 GB** (:758) | **2 passes**: door prepass from frame 1 to arrival + 480 door boxes (or the end), then re-parse (:761-797); no length read; decides per beltloader at its stop (:649-650), report after the loop; breaks at departure (:867-870) | BL at door / stop and visit handover (:502-520, :632-665); door prepass; workers ROI (:128-200); jet/airplane type whose result is never used (:675-717, :919-920) |
| steering (M26) | `external/steering-…`, default HEAD 60dca73 = pin; runner + mmpose1 | HRNet-W48 (same sha), YCrCb equalizeHist on the box +20 %/+10 %, **batch 1**, 2 passes/call: 0 calls on most frames, up to 200 sequential calls on a trigger frame (stop episode centred 100 frames back). tsai InceptionTime (bfa75c6ce2f6e6da) on (1, 57, 200), 1 per trigger, GPU; MinMaxScaler (03248ad564e45926). Measured 310 pose calls + 2 classifier calls on MwCSLbQ7QvXQ | get_im0s + full-frame copy every frame for ≤ 240 s after arrival (:284, :818-823); **buffer 200 raw frames ≈ 1.24 GB** (:260); 200 full-frame copies per trigger, also for frames without the person (:510-512) | 1 pass; no length read; 100-frame look-ahead (12.5 s lag, :453); Pass latched at the trigger (:861-869), Fail/NO at arrival + 240 s (:790-801); early exit 5 s later | arrival-stage block from `_p0/_st` (:198-228); own velocity / stop-episode detector (:345-493) |
| pin-verification (M16) | `external/pin-verification`, default HEAD 8e1863c = pin; runner + mmpose1 | SimCC ResNet-50, 288×384 (sha 9e3c7ee446c0cc3a; file tag 45c3ba34 ≠ sha), raw frame, raw box, 2 passes/call: 1 call/frame with near-wheel workers after pushback attachment and before departure − 10 s; batched per frame; cuda:0 hard-coded (:499). Measured 3 calls on zHxIAF2vUGxJ | get_im0s without copy on pose frames only (:816); every frame `to_state_dict()` just to log 4 fields (:99-101) and `draw_OF_points(None)` over ≤ 250 points (:642); `print(data_samples)` per call (:829) | **2 passes**: pass 1 to departure or last frame (median pushback 120–60 s before departure, departure_frame) (:504-549); reads `number_of_frames` (:530); Pass latched (:858-866), Fail/NO after the loop; exits 80 frames after Pass or departure + 15 s | pushback_attached (:662-684); departure cut-off from pass 1 (:763); wheel / pushback ROIs; obstacles |
| lead-marshaller (M15) | `external/_branches/…@pre_arrival_departure` 9e1a9f0; runner + `out/envs/sklearn161` + mmpose1; **numpy1 yes** | HRNet-W48 (same sha), 2 passes/call. Path A: full-frame CLAHE, box +10 %, 1 call/frame while the plane approaches (all workers, batched). Path B: raw buffered frames, raw boxes, once at the decision. SVC pipeline (6a049e293cf13f2d) 1 predict/frame on all workers (CPU); RandomForest (74fb67d1012e8a19) and 2 GradientBoosting pipelines (893f608cd177a307, 5ecf5ddccf278a5d) once at the decision | path A copy + CLAHE per frame (:166-167); full-frame copy per frame with workers while no plane is visible, **buffer ≤ 96 frames ≈ 0.60 GB** (:930, :1079); matplotlib figure + savefig at the decision (:477-560) | 1 pass; `nframes` only in prints / report text (:992, :1197); decides at the tracker `arrival_frame` (:866, :1106-1158); exits 10 s later | start_moving (:874-878); false / passing plane logic (:1033-1048); obstacle sides; pseudo depth. No `_p0` block on this branch |
| wing-walkers (M27) | `external/_branches/…@obstruction_hand_signals` 3460afc; runner + mmpose1; **numpy1 yes**; device "0" | HRNet-W48 (same sha), full-frame CLAHE, box +10 %, 2 passes/call: 1 call/frame for all persons (minus pushback drivers) from departure movement start to +60 s; batched. Wand YOLOv5 not loaded on this branch (:810) | copy + CLAHE per frame (:248-249); no frame buffer; figure + 2 pickle dumps at the decision (:379-392, :1046-1060) | 1 pass; `nframes` in the decision condition (:988, :1010); decides at start_moving + 60 s, or resets on a false departure (:982-1012); break | own T_arr 5 s / T_dep 8 s with bbox-area reset (:130-158, :993-1003); jet/aircraft type (:65-98); pushback-driver filter; obstacle logic |
| fod-walk (M11) | `external/_branches/fod-walk-completed@dev` a30826f; runner; cv_common + `modules` overlay | MoveNet SinglePose Thunder v4 ONNX (7fae4dc3cdd07ebd), int32 NHWC 256×256 letterbox from the raw box, BGR→RGB: 1 run per person ≥ 20 px per frame until the first airplane track appears; **not batched** (graph batch fixed at 1). Production pins CPU `onnxruntime==1.14.1` | crop slices per person (:443); arrival frame read and drawn on **in place** without write_video (:145-176); `to_state_dict()` + `draw_OF_points(None)` per frame (:386-387) | 1 pass; no length read; decides at the tracker `arrival_frame` and breaks (:500-548) | PlaneArrivalDetector (`cv_common/modules/plane_arrival_detector.py:85-229`); camera-blocked filter; corridor / pseudo depth |
| safety-vests (M23) | `external/_branches/…@tdv_cone` 8f58d7e; runner | Swin-T 3-class orientation 256 (175e87d3668a5c9c), 1 call/frame batched over persons matched to a vest; Swin-T 2-class vest 256 (b0a5f34b168a97f6), ≤ 1 call/frame batched; ResNet-18 presence gate 192 bicubic (4bcb3e3f2a242f24), 1 call per eligible person, **not batched**. Session end, Pass videos only: YOLOv8m-pose 640 (dbe539ea268db253) 1 call per buffered crop, not batched; ResNet-18 v4 CNN 224×112 (66d4a8f79a4843c2), batches of 64 | decodes **every frame** and builds a discarded 1280 letterbox (`cv_common/utils/datasets.py:226-231`); full-frame copy + putText every frame (:367-368); per-person HSV contour analysis (:152-221); JPEG q95 crops every 12th frame, ≤ 20 000 pairs (`v4_override.py:90-141`); no frame buffer | 1 pass over the whole video, no early exit; no length read; decides at session end, then the v4 Pass→Fail override (:490-501) | person–vest association (:401-409); orientation by classifier, not keypoints |
| hair-policy | `external/hair-policy` master 8a343bf; **WSL launcher**, CPython 3.8 venv, device cpu, 2 threads | config names two torchvision EfficientNet-B0 2-class state dicts: hair (190ea0473a253df4), inside/outside (93640745399b6e71); mediapipe is a dependency. Input, calls and batching **unreadable** (Pyarmor build) | unreadable; measured ≈0.9 CPU-s per frame | unreadable; `docs/05_module_logic.md:13`: "executed throughout the entire video" | unreadable |

## 2. Shared findings

**Identical model.** HRNet-W48 td-hm COCO 256×192, `td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth`
(269 176 125 B, sha256 0e67c6167d6a10fe), with an identical config file (sha256 40b6c83573144c66), is loaded by
hand-signals (:734-739), steering (:653-657), lead-marshaller (:946-951) and wing-walkers (:797-802). mmpose preprocessing
is identical: box ×1.25, aspect fix, warpAffine INTER_LINEAR, ImageNet mean/std, BGR→RGB, flip test.

What each module passes in:

| module | image | box | batch |
|---|---|---|---|
| hand-signals | full-frame CLAHE, clip 4.0, tiles 16×16 (`main.py:43-51`) | +10 % (`main.py:537`) | persons of the frame |
| wing-walkers | same CLAHE code (`helpers.py:208-216`) | +10 % (`main.py:243`) | persons of the frame |
| lead-marshaller path A | same CLAHE code (`main.py:295-303`) | +10 % (`main.py:161`) | workers of the frame |
| lead-marshaller path B | raw buffered frame | raw box | wing walkers of the buffered frame |
| steering | YCrCb equalizeHist on the box region, pasted into a frame copy | +20 % / +10 % | 1 |

The stage windows barely overlap (approach / after arrival / 240 s after arrival / departure). Only hand-signals and
steering overlap, and they preprocess differently. So the share is one model instance, not shared results.

**Present, loaded by nobody.**
- `hrnet_w48_coco_384x288_dark-741844ba_20200812[ copy].pth` (255 012 316 B, sha256 741844ba1678a257) sits in all four
  HRNet checkouts.
- wing-walkers `wand_detector.pt` (YOLOv5, 3a85f450b0416369).
- lead-marshaller `worker_type_classifier.pkl` and `worker_type_classifier_kn.pkl`.
- safety-vests `v4_probe_head.npz` (CLIP path disabled, `v4_config.yaml:25`) and `fail_guard.py` (not imported).
- None of the eight checkouts has a model that is loaded but not used for the verdict. On its default branch,
  wing-walkers loaded the wand detector without running it; this branch no longer loads it.

**Same architecture, different weights or preprocessing — sharing is SEMANTIC.**
- safety-vests: two Swin-T (different normalisation and crops) and two ResNet-18.
- hair-policy: two EfficientNet-B0.
- Four different COCO-17 keypoint models on person crops: HRNet-W48, SimCC-R50, MoveNet Thunder and YOLOv8m-pose. MoveNet
  and YOLOv8m-pose are used only for shoulder positions.

**Common plumbing every module pays for** (identical `cv_common/utils/datasets.py`, `db_worker/ML_worker.py`,
`cv_common/log_utils.py` in all checkouts).
- **Frame reader.** `get_im0s` decodes forward only (grab for skipped frames). Every decoded frame also gets a YOLOv5
  letterbox to 1280 plus a CHW copy that no module uses, and a print (`datasets.py:217, 226-231, 265, 267-272`).
- **Track restore.** Each module re-parses both ndjson lines itself. Every airplane restore copies the state dict and
  converts `_p0` (≤ 250 points) and `_st` to numpy (`cv_common/tracked_object.py:604-636`), including in modules that
  never read them.
- **JsonLogger** is always on (`scripts/run_module.py:284`) and writes one ndjson row per frame. Files left in the
  checkouts by the last test-set run range from 0.46 MB (hair-policy) to 13.7 MB (hand-signals).
- **mmpose pipeline.** `inference_topdown` rebuilds scope and pipeline from the config on every call
  (`mmpose/apis/inference.py:155-158`).

**Hazard before frames are shared between modules in one process.** fod-walk draws on the cached decoded frame without
copying it (`main.py:145-146, 162-176`). Every "hold by reference" candidate below assumes no module writes into shared
frames.

## 3. Lightening candidates per module

Risk classes:
- EXACT: bit-identical outputs expected.
- NEAR: small numeric change.
- SEMANTIC: can change verdicts.

Candidates that apply to every HRNet module and are not repeated below:
- **EXACT**: one shared HRNet-W48 instance; build the mmpose pipeline once; skip the reader letterbox; JsonLogger rows
  and prints off in the RT branch (the verdict is unaffected, but the per-frame overlay file is no longer produced).
- **NEAR**: ONNX Runtime / TensorRT / fp16.
- **SEMANTIC**: `flip_test=False` (config `:133`), frame subsampling, a smaller pose model.

### hand-signals
| id | risk | change → what disappears | evidence |
|---|---|---|---|
| H-E1 | EXACT | occlusion ratio on ROI-sized masks or integer rectangle arithmetic → two full-frame allocations, a full-frame bitwise_and and two full-frame sums per frame after arrival (reproduce cv2.rectangle clipping) | `main.py:183-196` |
| H-E2 | EXACT | drop `.copy()` before CLAHE (cvtColor allocates new arrays) → one full-frame copy per pose call | `main.py:554-555`, `:358` |
| H-E3 | EXACT | buffer CLAHE'd sampled regions (CLAHE on the full frame at buffering time, region of the warp +1 px) instead of raw frames → up to 240 frames ≈ 1.49 GB; CPU moves to buffering time. Raw crops would not be exact: CLAHE tiles see the whole frame | `main.py:549`, `:758`, `:338-364` |
| H-E4 | EXACT | batch runs: parse metadata once for both passes → the re-parse of the pass-1 range | `main.py:725`, `:797` |
| H-E8 | EXACT | remove the unused plane-type evaluation and the visualizer when not writing video | `main.py:872-873`, `:919-920`, `:740-741` |
| H-N2 | NEAR | merge the replay burst (≈200 calls on one frame) into larger batches; batch composition changes | `main.py:343-364` |
| H-S1 | SEMANTIC | causal door estimate instead of pass 1 (RETHINK) | `main.py:761-797`, `:157-161` |
| H-S3 | SEMANTIC | crop-local CLAHE or no CLAHE; pose on a subsample of the replay window | `main.py:43-51`, `:282` |

### steering
| id | risk | change → what disappears | evidence |
|---|---|---|---|
| S-E1 | EXACT | hold the decoded frame by reference (cap.read returns a new array; the module copies before writing) → one full-frame copy per frame for ≤ 240 s | `main.py:284`, `datasets.py:258`, `main.py:511` |
| S-E2 | EXACT | per recording, no copy for frames without the person; save/equalise/restore the region instead of copying the frame → up to 200 full-frame copies per trigger | `main.py:510-527` |
| S-E3 | EXACT | buffer the warp regions of every person track present instead of 200 full frames (any track can later trigger) → ≈1.24 GB becomes proportional to person area | `main.py:260`, `:284`, `:508-524` |
| S-E5 | EXACT | move the arrival-stage block verbatim into the stage detector (same arithmetic, same fields; prove by parity) | `main.py:198-228` |
| S-N1 | NEAR | batch the ≤ 200 single-bbox pose calls of a recording | `main.py:510-527` |
| S-S1 | SEMANTIC | pose on a subsample of the clip (classifier expects 200 steps → retrain) | `main.py:614-635` |
| S-S2 | SEMANTIC | decide without the 100-frame look-ahead (trigger-change) | `main.py:453`, `:497-498` |

### pin-verification
| id | risk | change → what disappears | evidence |
|---|---|---|---|
| P-E1 | EXACT | remove `print(data_samples)`; `merge_data_samples` only with write_video → a merge and an array dump per pose call | `main.py:820`, `:829` |
| P-E2 | EXACT | parse the tracker line once per frame → a second `Track().from_json` pass | `main.py:634-642`, `:777-781` |
| P-E3 | EXACT | log box/class/id/status directly instead of `to_state_dict()`; skip `draw_OF_points`/`draw_bbox` with img None → a state serialisation and a ≤ 250-point loop per frame | `main.py:99-101`, `:641-642`, `cv_common/tracked_object.py:511-516` |
| P-E4 | EXACT | batch runs: parse metadata once for both passes; build the mmpose pipeline once | `main.py:493`, `:554` |
| P-N1 | NEAR | SimCC-R50 in ONNX Runtime / TensorRT / fp16 | `main.py:496-499` |
| P-S1 | SEMANTIC | remove pass 1 (median pushback and departure_frame from the future) in favour of the stage detector's pushback_attached (PATCH) | `main.py:504-549`, `:665`, `:763` |
| P-S2 | SEMANTIC | flip test off, or the shared HRNet-W48 instead of SimCC-R50 (different model and crop scale) | simcc config `:55` |

### lead-marshaller
| id | risk | change → what disappears | evidence |
|---|---|---|---|
| L-E1 | EXACT | hold buffered frames by reference, then keep only the warp regions of the buffered worker boxes (path B uses raw pixels and raw boxes) → a copy per frame and up to 96 frames ≈ 0.60 GB | `main.py:1076-1079`, `:930`, `:607` |
| L-E2 | EXACT | drop `.copy()` before CLAHE | `main.py:166-167` |
| L-E3 | EXACT | remove the dead `bboxes_for_pose`, the matplotlib figure / savefig, file logging and per-frame prints | `main.py:1058`, `:1073`, `:477-560`, `:885`, `:987-992`, `:1167` |
| L-S2 | SEMANTIC | stage-detector events instead of start_moving and the false-plane logic | `main.py:874-878`, `:1033-1048` |

### wing-walkers
| id | risk | change → what disappears | evidence |
|---|---|---|---|
| W-E1 | EXACT | drop `.copy()` before CLAHE → a full-frame copy per frame of the departure window | `main.py:248-249` |
| W-E2 | EXACT | skip plot_points/savefig (keep `figure_data`, it feeds `analyze_trajectories`) and the two pickle dumps | `main.py:379-392`, `:410-445`, `:1046-1060` |
| W-N1 | NEAR | buffer CLAHE'd warp regions and run pose at the decision only for workers classified as wing walkers → pose on everyone else; memory side exact, batch composition changes | `main.py:237-253`, `:456-506` |
| W-S1 | SEMANTIC | stage-detector departure anchors instead of the own 5 s / 8 s rules (moves the pose window) | `main.py:130-158`, `:950-952` |

### fod-walk
| id | risk | change → what disappears | evidence |
|---|---|---|---|
| F-E1 | EXACT | apply the vehicle-occupant filter before MoveNet → one preprocessing + session run per occupant crop per frame (their orientation only reaches a plot label) | `main.py:443`, `:446-456`, `:449-451` |
| F-E2 | EXACT | skip the arrival-frame read and ROI drawing without write_video → a decode request and in-place drawing on the shared frame (prerequisite for frame sharing) | `main.py:145-146`, `:162-176`, `:225-227` |
| F-E3 | EXACT | log plane fields directly instead of `to_state_dict()`; skip `draw_OF_points`/`draw_bbox` with img None | `main.py:385-387`, `:490` |
| F-E4 | EXACT | no prints / JsonLogger rows; compute `driver_detected` once | `main.py:295`, `:446`, `:454` |
| F-N1 | NEAR | dynamic-batch export and one run per frame; CUDA/TensorRT instead of the production CPU provider | `onnx_thunder_inference.py:43`, `:89-92` |
| F-S1 | SEMANTIC | shoulder order from a shared pose model, or orientation every N frames per track | `onnx_thunder_inference.py:111-121` |

### safety-vests
| id | risk | change → what disappears | evidence |
|---|---|---|---|
| V-E1 | EXACT | skip `im0s.copy()` and putText without write_video → a full-frame copy per frame | `main.py:367-368`, `:464-480` |
| V-E2 | EXACT | iterate frames without the YOLOv5 letterbox + CHW copy → a resize to 1280 and a copy per frame | `datasets.py:226-231`, `main.py:365` |
| V-E3 | EXACT | drop the per-crop `.copy()` before PIL (PIL copies non-contiguous slices itself) | `classifier_utils.py:44` |
| V-E4 | EXACT | no per-person prints / JsonLogger rows | `main.py:402`, `:436`, `:446-447` |
| V-N1 | NEAR | Swin-T ×2 in TensorRT / ORT / fp16 | `classifier_utils.py:15-25` |
| V-N2 | NEAR | batch the presence gate over the persons of a frame; batch YOLOv8m-pose over the buffered crops | `main.py:84-96`, `v4_override.py:207-214` |
| V-S1 | SEMANTIC | classify every N frames (the 20-vote consensus counts frames); smaller or shared backbone; raw crops instead of JPEG in the v4 buffer (the verifier was calibrated on JPEG) | `main.py:129-149`, `:326-356`, `v4_override.py:134` |

### hair-policy
| id | risk | change → what disappears | evidence |
|---|---|---|---|
| HP-0 | prerequisite | get the plaintext source (or a build loadable with GPU torch) from the owners; without it nothing below can be verified | `main.py:1-3`, `scripts/testset/wsl_run_module.sh:5-10` |
| HP-N1 | NEAR | same EfficientNet-B0 weights on GPU instead of CPU | `profiles.py:47`, `:89` |
| HP-E1 | EXACT, unverified | drop the 7 weight files that `local_config.yaml` does not reference → image size only; confirm with a file-access trace of one CPU run | `local_config.yaml:8-10` |
| HP-S1 | SEMANTIC | temporal subsampling or a shared crop classifier | `docs/05_module_logic.md:13` |

## 4. Open points

- hair-policy: invocation, crops, preprocessing, buffers and decision timing are not readable. The plaintext history ends
  at 7e07648 (2023-09-07), with a different algorithm and different weights.
- fod-walk: which ONNX Runtime provider executes MoveNet in the test-set runs. The interpreter lists TensorRT, CUDA and
  CPU. The TensorRT provider needs its DLL directory registered (`docs/analysis/gm_speed.md:93`), which fod-walk does not
  do.
- steering: whether tsai `get_X_preds` applies the pickled training augmentations at inference.
- Every EXACT candidate that changes code, rather than only deleting logging, still needs an L2 parity run
  (`scripts/run_module.py`, batch vs changed) before it counts.
