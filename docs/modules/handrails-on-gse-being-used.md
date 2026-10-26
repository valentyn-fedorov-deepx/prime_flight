# M14 · Handrails on GSE being used

> The module checks that every worker who walks up the belt loader (BL) holds the handrail. It finds the stopped belt loader at the camera's cargo door, checks that its handrails are extended, follows each worker on it with a whole-body pose model and looks for a hand on the handrail.

## At a glance

| | |
|---|---|
| Checks | M14 · Handrails on GSE being used |
| Stage | Download, Upload |
| Looks at | from the moment the aircraft stops until it departs, only frames where the belt loader at the camera's door is stopped |
| Cameras | cone camera (front belt loader) and wing camera (back belt loader) for aircraft; not used for jets |
| Uses | General Model (GM) classes `person`, `front_door`, `back_door`, `airplane_engine`, `back_wheel`; tracks of the aircraft, belt loaders (front / back label, stopped status) and persons; video frames: yes, every frame |
| Own models | handrail classifier (EfficientNet-B0) — extended or not; handrail segmentation (Unet MiT-B0); hand-contact classifier (EfficientNet-B0) — hand on the rail; plus the stock DWPose-l whole-body pose model |
| Runs on | GPU (the pose model is set to CUDA only) |
| Real time | ready, needs video frames — four models on every frame with a stopped belt loader; worker coverage is finalised only at the end |
| Production version | per_component_improvement @ f2c4793 (2026-07-09) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | Every worker detected on the belt loader touched the handrail while walking; the handrails are extended and no significant obstacle prevents detection. |
| Fail | At least one worker on the belt loader did not touch the handrail while walking, or handrail use is not consistent across the observed frames. |
| Not observed | No belt loader is detected, or no worker walks on it (poor visibility, obstruction, camera angle). |
| Not observed — view blocked | Handrail use cannot be confirmed because more than **80 %** of the belt loader area is obstructed. |

## How it decides

1. **Window.** Processing starts when the tracker marks the aircraft as arrived. It ends when the tracker reports departure and the aircraft box has shrunk by more than **18 %** while moving; otherwise it reads to the end of the video.
2. **Belt loader.** The belt loader the tracker labelled for this camera's door (front on cone, back on wing); if none, a geometric fallback (wing: under the engine or face-on under the back door; cone: at least **70 %** inside the aircraft box and lined up with the front door). The biggest wins; frames where it is not stopped are skipped. Its box is raised by **30 %** to include the handrails.
3. **Handrails.** On every such frame the classifier says extended or not. If extended, segmentation draws the handrail and its top edge gives the handrail line. On the wing camera the view is also classed as face-on or "left side" (belt loader right of the back door); this changes thresholds, and the left-side view has no blind check (step 6).
4. **Workers.** Tracked persons inside the belt loader box (feet above its lowest **20 %**, height over **20 %** of the belt loader height) are workers on it. Each gets a whole-body pose. Frames where a foot keypoint scores under **0.3** or the size is implausible do not count for coverage.
5. **Touch, by pose.** The centre of one hand (picked from the direction of the head or shoulders) must stay within a few pixels of the handrail line (about 1/60 of the belt loader height, 1/30 in the left-side view) for **5 frames** in a row (4 in the left-side view).
6. **Touch, by "blind check".** Square patches along the handrail are classified for a hand on the rail. **2** positive frames in a row (1 for a worker who came up the side stairs) confirm a touch for every worker seen on the belt loader in the last **20 frames** (2.5 s). No touch is possible while the handrails are not extended.
7. **Coverage.** At the end of the video, for each worker: the share of the handrail length (belt loader width if no handrail mask; face-on: vertical travel against 30 % of the belt loader height) that the worker's box passed.
8. **Per worker:** touch and coverage above **25 %** → Pass; no touch and coverage above **30 %** (40 % in the left-side view) → Fail; otherwise not evaluated.
9. **Verdict:** no belt loader → Not observed; no evaluated worker → Not observed; any failed worker → Fail; otherwise Pass.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `departure_bbox_change` | 0.18 | Aircraft box shrink that confirms departure and ends the window. |
| `cone.obstacle`, `wing.obstacle` | width 0.3, centre 0.3–1 | **Not used** by the code. |
| `camera_type_irrelevant` | False | **Not used** by the code. |
| Coverage (code) | 0.25 pass, 0.30 fail (0.40 left side) | Share of the handrail a worker must pass to be judged (`main.py:623-627`). |
| Pose touch (code) | 5 frames (4 left side) | Consecutive frames with the hand on the line (`main.py:488-523`). |
| Blind check (code) | 2 hits (1 via stairs), 20-frame memory | Patch hits needed; how long a worker stays eligible (`main.py:659-704, 870`). |

## What it reports

- **Verdict:** Pass, Fail or Not observed.
- **Report:** "All workers touched the handrail while walking on the beltloader." or "Not all workers touched the handrail…", followed by "ID: N Status: Pass/Fail Time: start--end" per evaluated worker. Not observed: "No beltloaders were detected." or "No workers walking on beltloader were detected. Possible obstruction or poor camera angle."
- **Smart timeline:** one Pass or Fail entry per evaluated worker, from the first to the last frame the worker was seen on the belt loader.
- **Overlay log** (ndjson); an annotated video with `--write-video` (`--debug` adds a debug panel).

## Known issues and limits

- **No "view blocked" verdict.** Obstacle boxes (trailers, GSE, very tall persons) are collected but never used; the obstacle settings have no effect. A blocked view ends as Not observed only when no worker is evaluated.
- **The blind check is not tied to a person.** A hand on the rail anywhere is credited to every worker seen on the belt loader in the last 2.5 s, so a worker who does not hold the rail can pass with a colleague.
- **Retracted handrails:** no touch can be found, so a worker who walks far enough fails (to confirm this is the intended reading of the rule).
- One belt loader per camera (the biggest at the door). Workers are kept for the whole video and never reset between belt loader visits.
- The production branch lacks master's start-up fix: the hand-contact classifier is built with `pretrained=True` and downloads ImageNet weights before ours are loaded (`local_models/efficientnet_reg.py:16`).
- The heaviest module per frame: every frame is read from frame 1; pose runs per worker, unbatched. DWPose gets BGR pixels with RGB-ordered normalisation (effect to confirm).

## For developers

- **Repository:** `dxgat/detectors/handrails-on-gse-being-used`; production line `per_component_improvement` @ `f2c4793`; default branch `master` @ `59fbced` (2026-04-10) (no cone-camera fallback, no stairs logic, older departure check, no crash guards; has the `pretrained=False` fix).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir, json_logger, debug)`. Classes in `main.py`: `Airplane` (departure by box shrink, front door), `Loader` (belt loader, handrail mask and line, view side, stairs), `Climber` (pose, touch, coverage); `make_inference` (verdict). Models in `local_models/`. Flowchart `assets/gse-handrails-detailed-flowchart.png`; logic diagram (Confluence, 2023): https://docs.google.com/spreadsheets/d/1o3sXhGIcNc3jBgueqzXzIKSds6L4r9iYZZHv3RaCjEk/edit?gid=0#gid=0
- **Dependencies:** `cv_common` @ `33c188d`, `db_worker` @ `5a4aa83` (exported copy; the local export substitutes cv_common `ac5098d`). Packages: torch 2.5.1, timm 0.9.2, segmentation-models-pytorch 0.3.3, onnxruntime-gpu 1.16.3. Weights (DVC, 4 files): `efficientNetb0_300_epoch_general_classifier_dataset_safety_handrails_v3_26_09_2023.pth`, `safety_handrails_mit_b0_best_model_293_epoch_30_10_2023.pth`, `effnetb0_weighted_norm_aug_929.pt`, `dw-ll_ucoco_384.onnx`.
- **Run locally:** `python main.py --source <video.mp4> --inferences-dir <dir> --weights-dir weights [--cone-camera] [--local-inferences] [--write-video] [--debug]`; settings in `local_config.yaml` over `cv_common/global_config.yaml`.
- **Code references:** step 1 `main.py:911-941`; step 2 `main.py:145-150, 986-1056`; step 3 `main.py:1058-1110, 167-191`; step 4 `main.py:1180-1215, 423-449`; step 5 `main.py:452-531`; step 6 `main.py:1124-1178, 633-704, 1232-1235`, stairs `main.py:194-268, 1196-1207`; step 7 `main.py:534-627, 1243-1245`; steps 8-9 `main.py:64-112`.
