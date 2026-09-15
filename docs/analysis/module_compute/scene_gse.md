# Scene and GSE modules: per-frame compute inventory

**Date:** 2026-09-15 · **Author:** module-porter (read-only audit) · **Machine-readable companion:** `scene_gse.json` (same content, one object per module, sha256 of every weights file)

**Scope.** Nine pixel modules (main scope) and a confirmation pass on ten pixel-free modules. Each module was audited on the
checkout the monthly test set runs (`scripts/testset/profiles.py`, `MODULE_DIR`; empty = `external/<module>`).

**Method.**
- Code reading of each checkout, including its own `cv_common` / `db_worker` copies.
- Weights hashed with sha256; the first 16 hex characters are quoted.
- `.pt` / `.pth` / `.keras` archives were inspected without importing torch. ONNX input and head shapes were read by seeking through the protobuf.
- Nothing was run, nothing touched the GPU, and nothing under `external/` was modified.
- Refs are `file:line` relative to the module checkout unless they start with `G:/`.
- A script checked all 1 196 refs in the JSON for file existence and line range.

**Numbers.** The only milliseconds in this report are the lead's batch medians per *recorded* frame, measured on a
contended machine. Modules that exit early look cheaper per recorded frame than they are per active frame. Nothing here was timed.

**Risk classes.**
- **EXACT**: outputs expected bit-identical.
- **NEAR**: small numeric change.
- **SEMANTIC**: can change verdicts.

## 1. Summary

| module (batch ms/rec. frame) | checkout | models: architecture, input, calls per frame in the window, batched? | pixel work and buffers | passes, length reads, when it decides | duplicated shared components |
|---|---|---|---|---|---|
| handrails-on-gse-being-used (31) | `_branches/…@per_component_improvement` f2c4793 | torchvision EfficientNet-B0 handrail classifier, 224², RGB beltloader crop: **1/frame**<br>smp Unet MiT-B0 segmentation, 320×256: 1/frame when extended<br>DWPose-l ONNX 288×384 on the person crop (±0.5w, ±0.2h, YUV-equalised BGR): **1 per climber, not batched**<br>timm EfficientNet-B0 hand-contact classifier, 224² warped handrail patches: ≤1 batched call/frame | `get_im0s` on **every recorded frame from frame 1** (`main.py:882`)<br>full-frame BGR→RGB per window frame (`:1061`)<br>full-frame 3-channel mask `warpAffine` (`:298-301`)<br>`warpPerspective` per check point (`:1170`)<br>buffers: 20-frame patch deque; a crop-mask reference per climber per frame, kept for the session (`:537`) | 1 pass; no length reads<br>decides after the loop: departure break (box shrink > 0.18, `:934-938`) or end of video | own departure confirmation (`:28-50`)<br>beltloader-at-door fallbacks (`:987-1028`)<br>stair detector (`:196-262`) |
| pre-departure-walk-around-completed (26) | `_branches/…@tdv_cone` e407de2, np1_walkaround venv + keras-torch shim | YOLOv8m-pose 640 per person crop, **not batched, every frame from the stop to the departure** (`code/walk_around/detection_processor.py:44`)<br>TDV build: Depth Anything V2 ViT-B 518×924 (≤8 per attempt) + MobileSAM per box, retried until built<br>VGG-style CNN (`best_acc.keras` torch twin), 224² per canvas at the decision<br>**On Fail:** YOLOv8m-pose `track` @1280 on every 4th frame of a second decode of up to 720 s | iterates every frame (decode + unused letterbox)<br>full-frame copy + timestamp overlay per frame (`main.py:91, 104-118`); the overlay is burned into ≤7 buffered TDV frames<br>debug PNG/CSV writes enabled | 1 pass, plus a second decode on Fail<br>no length reads<br>decides at departure confirmation (8 s moving + 30 s + box shrink), over a retrospective 480 s window | own six-phase stage machine; departure, beltloader and pushback detectors<br>identity recombination<br>second person tracker (BoT-SORT) in the rescue |
| safety-zone-confirmed-clear (10) | default 91676a5 | MobileSAM vit_t, full frame at 1024: one encoder pass per **re-seeding vehicle** (its first update, then every 10 LK updates), **`set_image` repeated per vehicle** (`cv_common/tracked_object.py:185`) | pass 2 reads + 2 copies **every frame 1..stop_frame** (`main.py:1032-1033`)<br>always-on full-frame blends, 8-10 per rendered frame (`:53-67`)<br>2 gray conversions + LK per vehicle<br>1 previous frame kept | 2 passes (pass 1: stop_frame, cone clusters, wheel line, zone)<br>no length reads<br>decides at T_arr (pass-2 break) | own norfair vehicle tracking + SAM/LK motion (`:990-994, 1410-1446`)<br>arrival-stage block twice |
| safety-handrails-fully-extended (8.4) | default 8b9a2a9 | same EfficientNet-B0 handrail classifier, 224²: **every 8th frame**, label held in between (`main.py:283-291`) | `get_im0s` + full-frame BGR→RGB on **every** window frame; only 1 of 8 is used (`:277-284`) | 1 pass; no length reads<br>decides after the loop (departure break or end) | beltloader at door via `bl_type` + stopped; beltloader id handover |
| post-arrival-aircraft-walk-around-inspection-completed-accurately (6.8) | `_branches/…@tdv_cone` a0d9ee4, venv | YOLOv8m-pose 640: **crops batched per frame**, every POST_ARRIVAL frame<br>TDV once: Depth Anything V2 ≤8 + MobileSAM per box<br>small CNN `best_model.pth`, 224², batch 64 at the decision | iterates every frame (decode + unused letterbox)<br>full-frame copy per frame (`main.py:73`)<br>≤7 buffered full frames | 1 pass; no length reads<br>decides at the DOWNLOAD transition (beltloader stopped or 300 s), then breaks | own phase machine and beltloader-stopped rule<br>ground coordinates<br>identity recombination |
| gse-chocks (6.1) | `_branches/…@per_component_improvement` d3f92a5 | RTMPose-l ONNX 192×256 per (stationary GSE × person in its action ROI), **not batched**<br>timm EfficientNet-B0 difference classifier, 224² from a 43×428 strip: ≤1 per stationary GSE per 10 s, ≤6 at departure | `get_im0s` per GSE track on every frame with a GSE (`main.py:1793, 1798`)<br>static-scene template match per stationary GSE per frame<br>buffers: **≤24 + 8 full frames per stationary GSE**, ≤6 averaged checks, stop/departure images | 1 pass; `dataset.nframes` in a print<br>decides per GSE at departure or end of video | stop/departure events from tracker private counters<br>box median; obstacle IoU association |
| aircraft-chocks (5.7) | default fa00478 | same timm EfficientNet-B0 architecture, **different weights**, 224² from 214×428: event-driven, ≤1 per rear wheel per frame | `get_im0s` per rear-wheel detection from T_arr to T_dep (`main.py:1653`)<br>1-2 static-scene template matches per wheel per frame<br>buffers: **≤81 stop + ≤81 main + 16 + 16 full frames per wheel** | **2 passes**; pass 1 computes the median pushback over [T_dep−120 s, T_dep−60 s]<br>`number_of_frames` fallback (`:1266`)<br>decides after pass 2 at T_dep | arrival-stage block; T_arr/T_dep by `==`; pushback_attached; beltloader hysteresis |
| conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed (2.4) | `_branches/…@new_logic` 960bfe1 | ultralytics YOLO11s-seg at imgsz 992 (rect 576×992): **every 16th frame** in the window, results held in between (`main.py:578-585, 829`)<br>`best28_full.onnx` never loaded | one full-frame copy per inference<br>held `Results` object (frame copy + GPU masks) | 1 pass; `dataset.nframes` in a print and in the last-frame fallback<br>decides at departure confirmation | own arrival/departure counters; jet/aircraft typing |
| pre-arrival-safety-huddle (1.9) | `_branches/…@green_cone_median` a1210c5 | **no learned model** | `get_im0s` only on frames with a GM cone, including the 60 s tail<br>RG-chromaticity median per cone crop | 1 pass; no length reads<br>decides after the loop; breaks at arrival + 60 s | norfair cone tracking; PlaneArrivalDetector |

## 2. Costs every module pays in the batch runner

18 of the 19 checkouts carry the same `cv_common` content (ac5098d2; beltloader-chocks differs only in line endings); post-arrival carries c11573b8 and has no `get_frame`.
`db_worker/ML_worker.py` is byte-identical (5a4aa83d content) in all 19, although the pre-departure and all-cargo exports name pin 6efc0b05. The real-time adapter is `G:/prime_flight/pf/rt/prod_module.py`.

| # | cost | batch (where) | real-time adapter | shared candidate |
|---|---|---|---|---|
| R1 | Every frame read runs `letterbox` to **1280×768** plus a contiguous CHW/RGB copy. `get_im0s` returns only `img0`; the walk-arounds unpack `img` and ignore it. | `cv_common/utils/datasets.py:268-272` (`get_frame`), `:227-231` (iteration); `global_config.yaml:4` | **Still done.** `LiveDataset._items` calls the same `cv_common` letterbox with img_size 1280 and builds the CHW copy for every `get_frame` and every iterated frame (`prod_module.py:168-171, 177-196, 315-316`). | **EXACT**: return only `img0` (no module in scope reads the letterboxed array). |
| R2 | A `print` per frame read, on top of each module's own per-frame prints. The orchestrator redirects stdout to a per-step log file, so every print is a file write. | `datasets.py:265`, `:217`; `scripts/testset/orchestrate.py:324-330` | The dataset print is gone (`LiveDataset` has no print, `prod_module.py:151-202`); module prints still run. | **EXACT**: drop them. |
| R3 | One `json.loads` of a GM line and of a tracker line per frame; the tracker file is 287 078 694 B / 17 280 lines, about **16.6 KB per frame**. Two-pass modules (aircraft-chocks, safety-zone) parse everything **twice**. | `db_worker/ML_worker.py:240-248, 257-280`; `tasks/notes/PF-Q1-18.md:66-72` | **Still one parse per module process** (`_row`, `prod_module.py:360-365`; each adapter opens its own files, `:330-332`). `LiveFeed.meta` **pops** each row (`:106-113`), so a second `load_metadata()` from frame 1 hits a consumed row: two-pass modules cannot run their second pass there and fail. | **EXACT**: parse once in the branch and hand parsed rows to every module. |
| R4 | Each track restore copies `state_dict`, converts every `to_numpy` key (`_p0`, `_st`, up to about 250 points) with `np.array` and every `to_status` key to `Status`. `Airplane`/`Vehicle.from_state_dict` copy the dict once more. | `cv_common/tracked_object.py:604-616`; `transport.py:129-144, 200-208` | **Unchanged**: parsed dicts go to the unchanged module code (`prod_module.py:360-377`). | **EXACT**: restore once per frame in a shared adapter, only the classes a module reads. |
| R5 | `JsonLogger(..., None)` opens **`None.ndjson` inside the module checkout** and serialises plus writes one frame per frame change (0.4-22.9 MB per run). | `cv_common/log_utils.py:31, 85-123`; `scripts/run_module.py:231, 284` | **Unchanged**: the adapter also passes `JsonLogger(..., None)` after `chdir` into the module folder (`prod_module.py:286, 324`). | Verdict-EXACT; whether the overlay log is kept is a product decision. |
| R6 | `--no-video` is added only when the mp4 is gone. Otherwise pixel-free modules get the real `LoadImages`: the VideoCapture is opened and `CAP_PROP_FRAME_COUNT` read, but nothing is decoded. `--write-video` is never passed. | `scripts/testset/orchestrate.py:300-317` | The adapter never opens the file (`prod_module.py:318`) and serves the frame count from the manifest, logged as non-causal (`:163-166, 227-230`). | n/a |

## 3. Model identity (sha256 = first 16 hex)

### 3.1 handrails-on-gse vs safety-handrails: the same EfficientNet-B0 handrail classifier

**Same model, same preprocessing code, same crop formula; different beltloader choice and cadence.**

| | handrails-on-gse @per_component_improvement | safety-handrails (default) |
|---|---|---|
| weights | `efficientNetb0_300_epoch_…_v3_26_09_2023.pth` **`31aae690e256c54b`**, 16 388 351 B | same file, same sha256 |
| code | `local_models/efficientnet.py` **`234cddf0d1645d31`** | `efficientnet.py` `234cddf0d1645d31` (byte-identical) |
| architecture | torchvision `efficientnet_b0`, `classifier[1]=Linear(1280,2)`, 4 052 175 params, fp32 (`efficientnet.py:29-37`) | same |
| preprocessing | full-frame `cvtColor(BGR2RGB)` → slice → `ToPILImage` → `Resize((224,224))` → `ToTensor` → ImageNet `Normalize`; batch 1; softmax argmax (`efficientnet.py:20-27, 39-48`) | same |
| crop | beltloader box, top raised by `int(0.3*h)`, clamped to ≥ 0 (`main.py:149-150`); slice `main.py:1061-1062` | same shift, **no clamp** (`main.py:77`); slice `main.py:279-280` |
| which beltloader | tracker `bl_type` (`main.py:987`); if none matches: wing engine/back-wheel (`:988-997`), wing enface (`:1000-1009`), cone front-door rule (`:1011-1028`); largest box (`:1043`) | tracker `bl_type`; the cone camera drops beltloaders overlapping and in front of a rear wheel; no fallbacks; largest box (`main.py:235-248`) |
| cadence | every frame with a stopped active beltloader (`main.py:1065`) | only `frame_number % 8 == 0`, label held (`main.py:283-291`) |

A single classifier instance behind a call memoised by `(frame_id, crop box)` is **EXACT**: identical inputs give identical outputs.

### 3.2 aircraft-chocks vs gse-chocks: same architecture, **not** the same difference classifier

**Different weights and different input formation; sharing one model or one input rule is SEMANTIC.**

| | aircraft-chocks (default) | gse-chocks @per_component_improvement |
|---|---|---|
| weights | `effnetb0_ext_fix_993.pt` **`8211b62aa9c367aa`**, 16 331 050 B | `effnetb0_small_clean_64_960.pt` **`e6453d73c4e59538`**, 16 328 049 B |
| architecture | `timm.create_model('efficientnet_b0', num_classes=1)` + state dict (`main.py:1228-1229`), 4 050 894 params | same (`main.py:1624-1625`) |
| input image | grey reference and current crops (bbox + 10 %) → 512×256 `INTER_AREA`; centre template; `matchTemplate` over the **whole** template; `stack(clip(match−template+127), template, match)` → PIL → `Resize(224,224)` → ImageNet normalisation; sigmoid ≥ 0.5 (`complex_difference.py:21-34, 36-59, 74-80, 122-142`) | same chain (`complex_difference.py:21-34, 54-58, 79-85, 127-138`), **except** that template and search are cut to the **bottom 20 %** (`:45-46, 48, 51`), so the net sees a 43×428 strip |
| score gate | always classifies (the score check is commented out, `:139-140`) | returns `None` when the match score < 0.8 (`:144-145`) |
| static-scene check | `simple_difference.py:35` `TM_CCORR_NORMED` | `simple_difference.py:35` `TM_CCOEFF_NORMED` |

### 3.3 Pose models: DWPose-l (handrails) vs RTMPose-l (gse-chocks)

| | handrails-on-gse | gse-chocks |
|---|---|---|
| file | `dw-ll_ucoco_384.onnx` **`724f4ff2439ed61a`**, 134 399 116 B (`local_config.yaml:5`, `main.py:842`) | `rtmpose-l-4dba18fc.onnx` **`cff059fd58a2c0d5`**, 110 596 989 B (`local_config.yaml:5`) |
| ONNX | input `[batch,3,384,288]`, opset 11; `head.final_layer` `[133,1024,7,7]` → **133 whole-body keypoints incl. hands** | input `[batch,3,256,192]`, opset 11; `head.final_layer` `[17,1024,7,7]` → **17 body keypoints** |
| runtime | onnxruntime, CUDA EP only; YOLOX detector disabled, the crop is the box (`local_models/dwpose/wholebody.py:10-25`) | onnxruntime CUDA+CPU EP (`onnx_model_utils.py:111-125`) |
| crop and preprocessing | person box ±0.5w / ±0.2h (`main.py:414-420`); YUV equalise (`local_models/dwpose/__init__.py:37-46`); affine with padding 1.25; RGB-ordered mean/std on BGR data | person box ±0.25w / ±0.1h (`main.py:739-745`); affine with padding 1.25; RGB-ordered mean/std on BGR data (`onnx_model_utils.py:95-106`) |

Same SimCC family, but different weights, input size, keypoint set and crop rule: they are **not interchangeable**. Handrails needs the hand keypoints.

### 3.4 Byte-identical weights across modules

| file | sha256 | bytes | used by | notes |
|---|---|---|---|---|
| `mobile_sam.pt` | `6dbb90523a35330f` | 40 728 226 | safety-zone (full-frame vehicle re-seed), post-arrival and pre-departure (TDV masks) | MobileSAM vit_t, 10.1 M params. Sharing the instance is EXACT; sharing embeddings only when the same frame is encoded. All three pass BGR as "RGB". |
| `yolov8m-pose.pt` | `2d0c64408d6b4015` | 53 262 566 | post-arrival (batched crops), pre-departure (per crop, and the rescue as a second instance) | Instance sharing is EXACT. Per-frame results are **not** shareable: batching mixed crop shapes switches to a square 640 letterbox. |
| `depth_anything_v2_metric_vkitti_vitb.pth` | `4dad67a7cc10b462` | 389 964 656 | both walk-arounds (TDV) | 97.5 M params |
| `best_acc.keras` | `9b2df8cb8edd8bfe` | 44 254 701 | pre-departure only; **present but never loaded** in post-arrival | Keras 2.15 Sequential, 224×224×3 |
| `sam_vit_b_01ec64.pth` | `ec2df62732614e57` | 375 042 383 | **loaded by neither** walk-around | dead file in both |
| handrail classifier `.pth` | `31aae690e256c54b` | 16 388 351 | handrails-on-gse, safety-handrails | see 3.1 |

Other weights:
- handrails smp Unet MiT-B0 `13c5f321659ee6f3`.
- hand-contact EfficientNet-B0 `7fc4e4fdf8db0d4d`.
- conditioned-air YOLO11s-seg `1a24fb38ea03ae4f`; its `best28_full.onnx` `47c42e531ab78f47` is never loaded.
- post-arrival CNN `best_model.pth` `480c6f871f125e8c`.
- The shared tracker's `mobile_sam.pt` was not hashed here (cv_trackers is outside the scope).

## 4. Heaviest per-frame work (structural ranking, no timings)

1. **handrails-on-gse.** Full-frame read on every recorded frame (`main.py:882`). On every stopped-beltloader frame: classifier + segmentation (when extended) + full-frame 3-channel mask warp + one unbatched DWPose-l per climber + handrail warps and a batched hand classifier.
2. **pre-departure walk-around.** Every frame gets decode, letterbox, a full-frame copy and an overlay. YOLOv8m-pose runs per person crop, unbatched, on every frame from the stop to the departure, because the 480 s window is applied only at the decision. Debug artefacts are on. On Fail, up to 720 s of video is decoded a second time with pose tracking at 1280.
3. **safety-zone.** Pass 2 reads and double-copies every frame up to the stop, and 8-10 full-frame blends run per rendered frame without `write_video`. In the scored window, every re-seeding vehicle gets a MobileSAM full-frame encoder pass and every vehicle gets full-frame LK.
4. **gse-chocks.** RTMPose per stationary GSE × person, and a template match per stationary GSE per frame. Memory holds up to 24 + 8 full frames per stationary GSE, and departed GSEs keep their 24.
5. **aircraft-chocks.** The metadata is parsed twice, with 1-2 template matches per rear wheel per frame. Up to 81 + 81 + 16 + 16 full-frame references are kept per wheel. The classifier itself is sparse.
6. **post-arrival.** Every frame is decoded and copied, with batched pose per POST_ARRIVAL frame. The heavy TDV build (depth ×8 + SAM per box) runs once.
7. **conditioned-air.** YOLO11s-seg at 992 once per 16 window frames. **huddle**: crop colour statistics on frames with cones.

## 5. Lightening candidates per module

### handrails-on-gse-being-used
- **EXACT**:
  - Read the frame only after the arrival / active-beltloader / stopped gates (`main.py:882` → before `:1059`).
  - Convert only the beltloader crop to RGB (`:1061-1062`).
  - Share one memoised handrail classifier with safety-handrails (§3.1).
  - Warp a single-channel global mask; the three channels are identical and only `np.any` is read (`:298-301, 338-339`).
  - Drop the never-read `handrail_mask` reference from `_coverage_data` (`:537` vs `:547-620`).
  - Build the hand classifier with `pretrained=False`; strict `load_state_dict` replaces every tensor (`local_models/efficientnet_reg.py:15`, `main.py:847-848`).
  - Cache the `front_door` median, which is O(history) per access (`:46-50`).
  - Remove the print and `putText(None)` calls (`:875, 529-531`).
- **NEAR**: batch the DWPose crops of a frame; TensorRT or fp16 for all four models (`:1187-1212`).
- **SEMANTIC**:
  - Classify every 8th frame like safety-handrails, or subsample pose (`:1065, 1074, 1212`).
  - Use stage-detector departure and beltloader-at-door instead of the box-shrink and fallback rules (`:28-50, 917-941, 987-1028`).

### pre-departure-walk-around-completed
- **EXACT**:
  - Drop the per-frame copy, timestamp and annotation drawing when there is no writer, but **keep the overlay on frames entering the TDV queue**; depth sees it (`main.py:91, 104-118`; `code/states.py:1138-1157`; `code/walk_around/temp/plane_tdv_extractor.py:155`).
  - SAM `set_image` once per attempt frame (`plane_tdv_extractor.py:45, 302-316`).
  - Remove the unused per-canvas CSV parse (`code/walk_around/walk_around.py:287-291`).
  - Load depth and SAM lazily; remove `import tensorflow` (`walk_around.py:9`); reuse the loaded pose weights for the rescue (`code/walk_around/gs1737_addons.py:202-204`).
  - Drop verdict-unused debug writes and prints.
  - Remove the dead `sam_vit_b_01ec64.pth`.
  - In the post branch, run a metadata-only prepass, then pose only on [window start, departure start]. In real time, prune trajectories older than 480 s (`code/states.py:810-819`).
- **NEAR**:
  - Batch pose crops; this switches to a square letterbox when crop shapes differ.
  - fp16 or TensorRT for pose, depth, SAM and the CNN.
- **SEMANTIC**:
  - Replace the rescue re-decode with shared GM+tracker person tracks (`gs1737_addons.py:197-232`). It needs 750 s of past pixels, which the real-time branch does not have.
  - Stage-detector anchors instead of the six-phase machine.
  - Shared identities instead of recombination; its BFS has a wall-clock cap.

### safety-zone-confirmed-clear
- **EXACT**:
  - Without `write_video`, draw only the stop-frame PNG (`main.py:53-67, 1033, 1148-1233`).
  - Read pixels only on tracker frames and the stop frame; drop `raw_frame`, which only feeds a thumbnail (`:1032-1033, 1145-1146`).
  - One `set_image` per frame for all re-seeding vehicles (`cv_common/tracked_object.py:185`).
  - Gray conversions once per frame (`cv_common/tracked_object.py:377-378`).
  - Zone intersection on the box ROI instead of full-frame masks (`main.py:716-728`).
  - Do not retain per-vehicle SAM masks (`cv_common/tracked_object.py:195`).
  - Remove the pass-1 arrival-stage copy (`main.py:914-949`).
  - In batch, parse the metadata once.
- **NEAR**: fp16 or TensorRT for MobileSAM; GPU resize; shared LK pyramids.
- **SEMANTIC**:
  - Shared tracker tracks and `_status` instead of own norfair + SAM + LK (`main.py:990-994, 1410-1446`).
  - A causal single pass instead of waiting for `stop_frame`.
  - Longer re-seed periods.

### safety-handrails-fully-extended
- **EXACT**:
  - Read and convert the frame only when `frame_number % 8 == 0` (`main.py:277-284`).
  - Convert only the crop, keeping the unclamped negative top (`:77, 279-280`).
  - Shared memoised classifier (§3.1).
  - Parse tracks once (`:177-178, 226-227`).
  - Remove the log-only obstacle filter and prints (`:155, 201-223`).
- **NEAR**: fp16 or TensorRT.
- **SEMANTIC**: change the `% 8` cadence or the held label.

### post-arrival-aircraft-walk-around-inspection-completed-accurately
- **EXACT**:
  - Drop `im0s.copy()`; nothing writes into the frame on this branch (`main.py:73`).
  - Do not letterbox in iteration, and retrieve pixels only for TDV-candidate frames and person frames.
  - SAM `set_image` once per attempt frame; stop part segmentation at the first non-empty mask (`code/walk_around/temp/plane_tdv_extractor.py:44-51, 245-311`).
  - Release the TDV frame queue once the TDV exists (`:80`).
  - Share model instances with pre-departure (identical files, §3.4).
  - Remove the never-loaded `best_acc.keras` and `sam_vit_b_01ec64.pth`.
- **NEAR**: fp16 or TensorRT; move the TDV build and completion off the frame loop.
- **SEMANTIC**: subsample pose; stage-detector window; shared identities instead of recombination.

### gse-chocks
- **EXACT**:
  - Fetch the frame once per frame, only when some GSE is STOPPING/STOPPED (`main.py:1793, 1798`).
  - Compute the check image once; it is computed twice (`:1306, 1365`).
  - Share one static-scene score between stop capture and diff capture on stop frames 2..8 (`:1181-1185, 1244-1247`).
  - Cache pose per (frame, person) across GSEs (`:731-747`).
  - Store crops with a containment check instead of full frames in all difference buffers (`:1171, 1266, 1306, 1365, 1388`).
  - Parse tracks once; log boxes without `to_state_dict()` (`:136, 1750-1768`).
- **NEAR**: batch the RTMPose crops; TensorRT or fp16 for both models.
- **SEMANTIC**:
  - Release `_diff_frames` at departure; a stale window is reused today (`:1145-1156`).
  - Subsample the static test or pose.
  - Share weights or the input rule with aircraft-chocks (§3.2).

### aircraft-chocks
- **EXACT**:
  - Fetch the frame lazily, inside the difference phases (`main.py:1653`).
  - Crop at append and average crops; np.mean of 8 uint8 frames is per pixel (`:620, 700, 810, 636, 723, 826`).
  - Keep only the padded stop crop instead of `_stop_img` (`:555-564`).
  - Clear the stop buffers of wheel candidates not selected at T_arr+10 s (`:1660-1680`).
  - Restore only the airplane fields that are read (`:1253-1264`).
  - Drop the print and `putText(None)` (`:1324, 1338`).
- **NEAR**: fp16 or TensorRT; batch the two main checks that fire on the same frame (`:708-734`).
- **SEMANTIC**:
  - Remove pass 1 and take a causal `pushback_attached` from the stage detector (`:1240-1291, 1530-1549`).
  - Stage-detector arrival and beltloader events.
  - A shared wheel track.

### conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed
- **EXACT**:
  - Drop the frame `.copy()` before `predict` (`main.py:580`).
  - Hold host-side boxes instead of the `Results` object; this avoids per-box device syncs on held frames (`:614-617, 900`).
  - Incremental status counts instead of a `Counter` over 800 entries (`:217-225`).
  - Remove the dead `best28_full.onnx` and `util/yolov8_onnx.py`.
- **NEAR**: ONNX Runtime, TensorRT or fp16 at 576×992.
- **SEMANTIC**: skip mask decoding; a different 16-frame cadence; stage-detector T_arr/T_dep.

### pre-arrival-safety-huddle
- **EXACT**:
  - Update the plane first and skip the colour test on post-arrival tail frames (`main.py:384-390, 440-453`).
  - Apply the aspect gate before the pixel read (`:223-226`).
  - Remove `draw_OF_points(None)`, `putText(None)` and the prints (`:331-334, 399-406, 451`).
- **SEMANTIC**: subsample the colour test; shared cone tracks; stage-detector T_arr.

## 6. Pixel-free modules: confirmation on their test-set checkouts

**No model loads.** None of the ten decodes a frame in the test set.
- Every `dataset.get_im0s` is under `if write_video`, and `--write-video` is never passed.
- With the mp4 present, `load_source` still opens a `cv2.VideoCapture` and reads `CAP_PROP_FRAME_COUNT`; nothing is decoded.
- `cones-placed@not_observed_logic` ships `cones_helpers.py`, which imports torch/torchvision, but no file imports it. `weights/cones_v1.pt` (16.6 MB) is present and never referenced.

| module | checkout | frame read with video present | per-frame CPU that scales | always-on logging / drawing | early exit |
|---|---|---|---|---|---|
| 3-stop-brake-check | default 14685f4 | none (`main.py:263-264`); `load_source` `:243` | two `Track.from_json` passes (`:311-312, 359-360`); `draw_OF_points(None)` per beltloader (`:382`); print + `logging.info` to the run log per frame (`:261, 272-273, 373-377`) | airplane and beltloader states (`:320, 429`) | break at departure (`:324-333`) |
| all-cargo-bin-doors-opened-and-verified | bl_approach@3422bdc | none (`:382-383`); `dataset.nframes` in a per-frame print (`:385`) | `draw_OF_points(None)`, up to 250 `cv2.circle` per airplane frame (`:303`) | airplane state, door boxes, beltloader states (`:335, 209, 113, 128`) | break 10 s after doors + beltloader approach, or at departure (`:427-434, 443-447`) |
| beltloader-chocks | default 7056099 | none (`:403-404`) | JSON entry for **every** detection of 6 classes and **every** airplane/beltloader track from frame 1; airplane logged twice (`:183-189, 214-217, 228`) | yes (7.55 MB `None.ndjson`) | break at departure (`:456-459`) |
| bl_rear_cone | default 12429f5 | none (`:360-361`) | same pattern with 7 classes (`:213-219, 244-247, 258`) | yes (14.07 MB, the largest) | break at departure (`:419-422`) |
| chocks-and-cones-available-and-staged-for-arrival | not_observed_logic@2b4fca9 | none (`:298-299`); `dataset.nframes` print (`:301`) | `draw_OF_points(None)` (`:64`); pairwise NMS twice, the second only for logging (`obstacle_logic.py:95, 106-114`) | airplane state, cone/chock boxes, texts | break at arrival (`:329-333`) |
| cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked | default e2a25ba | none (`:101-102`) | **O(history)**: the cone window keeps growing while any transport box is anywhere in view; every frame it is flattened and converted into two numpy arrays that are **never read** (`:110-112, 275-286`); audit replay on one video: mean 2 005, max 5 670 boxes | cone/beltloader/vehicle boxes, 2 texts | break on `frame_number == departure_frame` (exact equality, `:151-155, 335-336`) |
| cones-placed-in-proper-positions-and-timely | not_observed_logic@d2a6898 | none (`:748-749`); `dataset.nframes` print **and in the decision** (`:751, 770, 780`) | part NMS per class, obstruction checks (`:111-182, 402-583`); display NMS and text wrapping (`:640-685`) | yes (22.9 MB) | return at departure confirmation or `frame == nframes` (`:764-799`) |
| crew-present-10-minutes-prior-to-aircraft-arrival | default 5cfd25c | none (`:63-64`) | `draw_OF_points(None)` (`:167`); `to_state_dict()` only for logging (`:157, 168`); reverse class lookup per detection (`:90`) | person boxes, texts, plane state | the verdict is fixed at arrival, **but the loop runs 60 s more** before breaking (`:43, 123-133`) |
| pushback-does-not-start-until-wing-walkers-are-in-place-and-ready | obstruction_plane_track@6979d19 | none (`:608-610`); `dataset.nframes` print **and in the trigger** (`:612, 664`) | **O(history)** `np.sum(np.array(not_observed_frames))` per frame only for a text (`obstacle_logic.py:126-137`); display NMS; 8-9 prints per frame | yes (14.6 MB); a trajectory PNG written every run regardless of `write_video` (`main.py:260-283, 289`) | break at departure confirmation (`:658-684`) |
| pushback-pathway-confirmed-clear-of-obstacles | default 104db85 | none (`:274-275`) | `draw_OF_points(None)` (`:334`); `to_state_dict()` for logging (`:152-155`); height statistics only for `putText(None)` (`:177-181, 338-341`) | plane state, parts, objects, texts | break at departure + 120 frames (`:504-505`); frames without detections skipped (`:294-295`) |

**Surprises.**
- **Why cones-are-removed is the most expensive pixel-free module:** it flattens an ever-growing cone history and converts it with `np.array` every frame, and nothing reads the arrays.
- **Early-exit dilution in the per-recorded-frame medians:**
  - crew-present keeps working for 60 s after its verdict is fixed.
  - chocks-and-cones stops at arrival, so its median is spread over the pre-arrival part only.
- **Non-causal decision input:** cones-placed and pushback-does-not-start use `dataset.nframes` in the decision. It differs between real-video and `--no-video` runs whenever the container frame count differs from the GM line count (X4). In real time it is a non-causal read.
- **Per-point `cv2.circle` on a `None` image** (`draw_OF_points`) runs in 3-stop, all-cargo, chocks-and-cones, crew-present and pushback-pathway.
- **Airplane choice differs:** pushback-pathway follows the **last** airplane record, while beltloader-chocks and bl_rear_cone follow the **first**; the others use the largest.

**EXACT candidates (pixel-free).**
- A no-op JsonLogger.
- Skipping drawing and label formatting when `img_to_draw is None`.
- Parsing tracks once and restoring only the fields that are read.
- Deleting the unused arrays and the flatten in cones-are-removed (`:283-286`).
- Breaking right after the verdict in crew-present (`:123-133`).
- Skipping the O(history) counter text in pushback-does-not-start (`obstacle_logic.py:132-136`), and `save_figure=False`.
- In all-cargo, breaking as soon as the Pass inputs are frozen instead of 10 s later (reported exact by the audit; verify against `make_inference`).

**Not exact:**
- Capping the cones-are-removed window.
- Switching any module to a different airplane track.

## 7. Open questions and caveats

- **BGR fed as RGB:**
  - DWPose (handrails) and RTMPose (gse-chocks) receive BGR data normalised with RGB-ordered mean/std.
  - MobileSAM receives BGR as "RGB" in safety-zone and both walk-arounds.

  Every EXACT sharing plan must keep this.
- **Walk-around recombination** uses a BFS with a 5-minute wall-clock cap. If a test event hits it, verdicts depend on machine load and no speed change is strictly exact there.
- **Silent Fail/None paths:**
  - post-arrival fails with `TypeError` on result `None` if DOWNLOAD is never reached (`main.py:139`).
  - aircraft-chocks and gse-chocks may fall back to CPU in production (`cpu_base` image, `db_worker/model_starter.py` defaults `--device cpu`, `--write_video t`); check the GKE job spec.
- **Library versions:** checked in the test-set environments only — ultralytics 8.4.83 (global) and 8.2.48 (walk-around venv); prod pins differ.
- **GPU determinism:** the EXACT claims for batching or embedding reuse on the GPU assume deterministic kernels for identical inputs; confirm each once with a bit-compare before relying on it.
- **Agent results:** five of the nine main-scope audits and both pixel-free batches came from subagent reads. Their load-bearing refs were re-read and every ref in the JSON was range-checked. The 3-stop pixel-free record and the handrails record come from the parent's own reading.
