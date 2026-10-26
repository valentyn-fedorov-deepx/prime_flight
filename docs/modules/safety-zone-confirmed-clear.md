# M24 · Safety zone confirmed clear

> Checks that no ground vehicle moves through the safety zone in the last two minutes before the aircraft stops. It builds the zone ("diamond") from the front-wheel approach path and the cones, then watches vehicles moving in it.

## At a glance

| | |
|---|---|
| Checks | M24 · Safety zone confirmed clear |
| Stage | Pre-arrival |
| Looks at | From 2 min before the aircraft stops until 30 s before the stop (a little later when the straight approach is shorter than about 25 s) |
| Cameras | Cone camera, for aircraft and jets (the camera flag only changes an overlay label) |
| Uses | General Model: `cone`, `front_wheel` (zone); BL (belt loader), GSE (ground support equipment), fuel truck, trailer, pushback, vehicle and obstacle boxes (moving vehicles, view blockers); `person` (masked out). Tracks: aircraft. Video frames: yes (second pass) |
| Own models | MobileSAM (stock segmentation model, not trained by us) — outlines each tracked vehicle so its motion can be measured |
| Runs on | CPU in the production image; GPU when a GPU device is passed (to confirm) |
| Real time | Needs a new first pass — the zone is built only after the stop; a second pass then scores the 2 minutes before it |
| Production version | `master` @ 91676a5 (2026-03-24) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The safety zone is visible and clear during the last 2 min before the plane arrives. |
| Fail | The safety zone is visible and a belt loader, fuel truck, trailer, GSE or pushback is detected moving in it during the last 2 min before the plane arrives. |
| Not observed | The diamond area is not visible, or the built area is too small, or the plane did not arrive, or there is no pre-arrival stage. |
| Not observed — view blocked | Obstacles for more than 30 s in the pre-arrival stage. |

## How it decides

1. First pass, detections and tracks only, up to the tracker's stop: collects stable cones (taller than wide, over **500 px²**, seen in one place more than **40** times) and, while an aircraft at least **200 px** tall is tracked, the front wheel nearest its centre.
2. Fits a straight line to the wheel positions of the last **15 s** before the stop and keeps the positions of the last **120 s** that lie on it, cut where 3 in a row (counting back from the stop) are off the line. The first and last kept positions are the far and near ends of the approach.
3. Builds the zone from these two wheel points plus, on each side, the cone closest to that image edge at the zone's mid-height. No cone on the left → the image edge; none on the right → a point mirrored from the wheel path. No wheel line → zone not visible; both diagonals under **200 px** → area too small.
4. Scored window: from **120 s** before the stop to **30 s** before it, or to **5 s** before the straight approach began if that is later.
5. Second pass, reading video frames. A vehicle box larger than **600 × 400 px** with its centre in the left **75%** of the image is a view blocker; if its bottom edge overlaps the zone by more than **10%**, the frame is "not observed". With no zone, every frame is "not observed".
6. Tracks the other vehicles itself, ignoring pushbacks within **1,000 px** of the aircraft centre (towing). Motion comes from optical flow on points inside each vehicle's MobileSAM outline, with people masked out.
7. A frame is "fail" when a vehicle in the moving state has more than **30%** of its bottom edge strip inside the zone; otherwise "pass".
8. Aircraft checks (older rules): arrival seen after more than **24 frames** (3 s) of movement in a row without camera-shake jumps (over 50 px sideways or 5 px vertically); pre-arrival seen when the stop comes later than **60 s** into the video.
9. Verdict: **Not observed** if the aircraft did not stop or the arrival or pre-arrival was not seen. Then **Fail** if more than **15** frames (≈1.9 s) are "fail"; **Not observed** if "not observed" frames outnumber "pass" frames; otherwise **Pass**.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `full_frame_obstacled.width` / `.height` | 600 / 400 px | A vehicle box larger than this… |
| `full_frame_obstacled.center_offset` | 0.75 | …with its centre left of 75% of the width blocks the view |
| `pushback.plane_distance` | 1,000 px | Pushbacks closer to the aircraft centre are ignored |
| `zone.intersect_thresh` | 0.3 | Share of a moving vehicle's bottom strip inside the zone that counts as a crossing |
| `l_th_sec`, tail cut (code) | 120 s; 30 s / 5 s | Start and end of the scored window |
| `fit_traj_sec` (code) | 15 s | Part of the approach used to fit the wheel line |
| Fail frames (code) | 15 | More "fail" frames than this give Fail |
| Blocker in zone (code) | 10% | Overlap that makes a frame "not observed" |
| Pre-arrival (code) | 60 s | The stop must come later |

## What it reports

- The verdict and one report line: Pass "The safety zone was clear." with the 2 min span; Fail "<class> <id> crossed the safety zone on <time>." per vehicle; Not observed names the reason (for example "Built area is too small").
- Smart timeline: one Pass or Fail block from frame 1 to the stop; empty for Not observed.
- Overlay log (`JsonLogger` ndjson): zone, cones, front wheels, blockers, vehicle states. Each run that reaches the stop saves a PNG of the stop frame with the zone; an annotated video only when video writing is on.

## Known issues and limits

- The last 30 s or so before the stop are not scored; the rule says the last 2 min.
- The rule's "obstacles for more than 30 s" is not the trigger: Not observed comes when blocked or zone-less frames outnumber clear ones; 30 s only picks the report text. More than 15 "fail" frames give Fail even on a mostly blocked view.
- "Fail" frames are summed over all vehicles and need not be consecutive.
- Vehicle motion comes from the module's own tracking, not the shared tracker, which lacks some of these classes (architecture review). A new vehicle track starts as "moving": cv_common's `Vehicle` sets a stopped flag its status does not read (local copy; to confirm on the production pin).
- Without a cone on a side, that zone corner is a fallback point (image edge or mirrored wheel point), not a cone.
- Older arrival rules (camera-shake filter, 60 s) in both passes; a class id missing from `str2id` stops the module with an error; `README.md` describes an older zone construction.

## For developers

- **Repository:** `dxgat/detectors/safety-zone-confirmed-clear`; production line `master` @ `91676a5`; default branch `master` @ `91676a5` (the same).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, ...)`: first pass, zone, second pass, decision. Helpers: `select_wheel_trajectory_points()`, `get_diamond()`, classes `Zone` and `Cone`, `get_report()`; the functions at the top only draw.
- **Dependencies:** `git ls-tree HEAD`: cv_common `dd5b554`, db_worker `5a4aa83`; the local `cv_common` folder holds `ac5098d` content. mobile-sam (GitHub `01ea8d0`), norfair 1.0.0, timm, torch. Weights: `weights/mobile_sam.pt` (40.7 MB) through DVC (`gs://cv_weights/DVC`).
- **Run locally:** `dvc pull`, then `python main.py --source <video>.mp4 --inferences-dir <dir> --weights-dir weights [--device cpu] [--write-video]`; reads `general_model<video>.ndjson`, `trackers<video>.ndjson` and the video. In production `db_worker/model_starter.py` calls `detect()`.
- **Logic diagram:** `.doc/Safety Zone.svg`; Confluence modules database, [sheet of 2023-09-29](https://docs.google.com/spreadsheets/d/141AfyPxEQVMayuOTxz0d9qtCcVQsDahb-RHVVixrZcQ/edit?gid=1780460773#gid=1780460773) (older than the 2026 zone logic).
- **Code references:** step 1 `main.py:867-959, 747-764`; step 2 `:571-619, 962-968`; step 3 `:632-677, 696-745, 985-987`; step 4 `:969-976, 1010, 1145-1233`; step 5 `:1049-1089, 1306-1395`; step 6 `:990-994, 1409-1446`; step 7 `:1450-1483, 716-745`; step 8 `:1092-1138`; step 9 `:1521-1538, 800-828`.
