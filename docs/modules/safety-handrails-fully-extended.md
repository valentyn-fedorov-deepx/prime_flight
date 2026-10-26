# M22 · Safety handrails fully extended and used

> The module checks that the belt loader (BL) parked at the camera's cargo door had its safety handrails extended for most of the time it stood there. Once per second a trained image classifier looks at the stopped belt loader and says "extended" or "not extended".

## At a glance

| | |
|---|---|
| Checks | M22 · Safety handrails fully extended and used |
| Stage | Download, Upload |
| Looks at | from the moment the aircraft stops until it departs, only frames where the belt loader at the camera's door is stopped |
| Cameras | cone camera (front belt loader) and wing camera (back belt loader) for aircraft; not used for jets |
| Uses | General Model (GM) class `back_wheel` (cone camera: drops the rear belt loader); `person`, `trailer`, `gse` only for an on-screen "camera blocked" note; tracks of the aircraft and belt loaders (front / back label, stopped status); video frames: yes |
| Own models | handrail classifier (EfficientNet-B0, ours; the same weights as M14) — handrails extended or not |
| Runs on | GPU if available, otherwise CPU |
| Real time | ready, needs video frames — one belt loader crop per second; each belt loader's result is final when it leaves (today computed at the end) |
| Production version | master @ 8b9a2a9 (2025-06-19; last logic change c7c5b6d, 2025-02-18) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | All belt loaders detected for more than 8 × 60 = **480 frames** have an extended ratio above **0.45**. |
| Fail | Any belt loader detected for more than **480 frames** has an extended ratio of 0.45 or less. |
| Not observed | No belt loader is detected near the aircraft. |
| Not observed — view blocked | No obstacles logic. |

The client sheet calls 8 × 60 frames "8 minutes"; at 8 frames per second it is **60 s**.

## How it decides

1. **Window.** Processing starts when the tracker marks the aircraft as arrived (stopped for more than 4 s) and stops when the tracker marks it departed (moving for 10 s).
2. **Which belt loader.** It keeps belt loader tracks the tracker labelled for this camera's door (front on cone, back on wing). On the cone camera, a belt loader that overlaps a rear wheel and stands behind it is dropped. The biggest remaining one is used; there are no geometric fallbacks.
3. **Track changes.** If a different belt loader track appears less than **120 frames** (15 s) after the last one was seen, it is treated as the same belt loader and continues its record.
4. **Stopped frames only.** Frames where the belt loader is not stopped are skipped.
5. **Classification.** Every **8th frame** (once per second) the classifier looks at the belt loader crop, with the box raised by **30 %** of its height to include the rails, and says extended or not extended. The label is held for the frames in between.
6. **Counting.** Each stopped frame adds the current label to the belt loader's record.
7. **Per belt loader**, at departure or at the end of the video: only belt loaders with more than **480 stopped frames** (60 s) are judged. If the share of "extended" frames is above **45 %**, it passes.
8. **Verdict:** no belt loader judged → Not observed; all judged belt loaders pass → Pass; any fails → Fail.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `min_extended_time_thresh` | 0.45 | Share of stopped frames with extended handrails needed to pass. |
| `min_bl_swap_time_thresh` | 120 (15 s) | A new belt loader track within this time is merged into the previous one. |
| `bl_min_detection_streak` | 4 frames | Consecutive frames before a belt loader's start time is recorded (timeline only). |
| `cone.obstacle`, `wing.obstacle` | width 0.3, centre 0.3–1 | Only for the "Camera is blocked!" overlay text; no effect on the verdict. |
| `camera_type_irrelevant` | True | **Not used** by the code. |
| Minimum stay (code) | 480 frames (60 s) | Hard-coded as `60 * 8` (`main.py:24`), not taken from the frame-rate setting. |
| Classification cadence (code) | every 8th frame | `main.py:283`. |
| Box raise (code) | 30 % | `main.py:77`. |

## What it reports

- **Verdict:** Pass, Fail or Not observed.
- **Report:** "All / Not all of the beltloaders had safety handrails extended for enough time.", then per judged belt loader "Beltloader N extended [NOT] long enough: X % (start – end)". Not observed: "Beltloaders were not detected".
- **Smart timeline:** one Pass or Fail entry per judged belt loader, from its first to its last frame.
- **Overlay log** (ndjson); an annotated video only with `--write-video`.

## Known issues and limits

- **Extension only.** The check is named "fully extended and used", but the module checks only extension; use of the handrails is M14.
- **Merging is broad.** Any belt loader track that appears within 15 s of the last one is merged into it, so two belt loaders served back to back can count as one.
- **Held labels.** One classification decides 8 frames. A new belt loader record starts as "not extended" until its first classification (up to 7 frames).
- **No top clamp.** After raising the box by 30 %, the top is not clamped at the frame edge (`main.py:77`). A belt loader near the top edge would give a wrong crop.
- Obstacles only print "Camera is blocked!" on the overlay. A hidden belt loader simply stops adding frames.
- Every stopped frame is decoded and converted, although only one in eight is classified.
- The README describes an older version (a YOLOv8 classifier and a 70 % aircraft-overlap rule). The streaming audit lists "models: 0", but the module has the classifier.

## For developers

- **Repository:** `dxgat/detectors/safety-handrails-fully-extended`; production line `master` @ `8b9a2a9`; default branch `master` @ `8b9a2a9` (the same; last logic change 2025-02-18).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir, json_logger)`. `main.py` holds `Loader` (per belt loader record, label history, extended ratio) and `make_inference` (verdict); `efficientnet.py` wraps the classifier (torchvision EfficientNet-B0, 224 × 224 input, softmax). Block diagram `assets/block_diagram.svg`; logic diagram (Confluence, 2023): https://docs.google.com/spreadsheets/d/1gkCMX5xdbsKiKXRAfofyUUpAslong_Um3HV3Xa1-XlA/edit?gid=0#gid=0
- **Dependencies:** `cv_common` @ `33c188d`, `db_worker` @ `5a4aa83` (the local clone substitutes cv_common `ac5098d`). torch and torchvision come from the `mmpose_base` image; other packages in `requirements.txt`. Weights (DVC): `efficientNetb0_300_epoch_general_classifier_dataset_safety_handrails_v3_26_09_2023.pth`.
- **Run locally:** `python main.py --source <video.mp4> --inferences-dir <dir> --weights-dir weights [--cone-camera] [--local-inferences] [--write-video] [--save-csv]`; settings in `local_config.yaml` over `cv_common/global_config.yaml`.
- **Code references:** step 1 `main.py:176-198`; step 2 `main.py:225-248`; step 3 `main.py:249-263`; step 4 `main.py:268-274`; step 5 `main.py:63-77, 276-288`; step 6 `main.py:89-102, 291`; steps 7-8 `main.py:23-46`; obstacle overlay `main.py:200-223`.
