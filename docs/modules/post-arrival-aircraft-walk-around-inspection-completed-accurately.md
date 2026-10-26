# M17 · Post-arrival aircraft walk around inspection completed accurately

> Checks that a worker walks around the aircraft after it stops. The module turns every worker's path into a top-down
> drawing next to an outline of the aircraft, and a small trained network (CNN) decides whether any drawing looks like a
> complete walk-around.

## At a glance

| | |
|---|---|
| Checks | M17 · Post-arrival aircraft walk around inspection completed accurately |
| Stage | Post-arrival |
| Looks at | from the moment the aircraft stops until a belt loader stops at the aircraft, or at most 5 minutes |
| Cameras | cone camera, aircraft only (not run for jets) |
| Uses | tracks of the aircraft, persons and belt loaders; General Model (GM) aircraft-part and person boxes (aircraft outline), vehicle and `obstacle` / `side_obstacle` boxes (blocked view); video frames: yes |
| Own models | walk-around CNN `best_model.pth` — scores each path drawing; it also runs stock YOLOv8m-pose (keypoints for distance), Depth Anything V2 and MobileSAM (aircraft outline) |
| Runs on | GPU when available, else CPU; the worker settings file says CPU — to confirm |
| Real time | post-processing only — whole paths are judged when the inspection window closes |
| Production version | tdv_cone @ a0d9ee4 (2026-07-27) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | The trajectory model says True for a worker's path around the aircraft (the path is preprocessed and turned into an image). |
| Fail | The model says False for every observed path. |
| Not observed | No workers are visible. |
| Not observed — view blocked | The view is blocked: blocked frames / all frames > 0.6. |

Client note: paths are followed until the belt loader arrives, or for 5 minutes after the aircraft arrives.

## How it decides

1. **Phases.** Follows one aircraft track taller than **250 px**. When the tracker reports it stopping, the arrival phase
   starts; when it is stopped (still for **3 s**), the inspection window opens.
2. **Approach frames.** Before the stop, every **16 frames** (2 s), it keeps the frame and the biggest aircraft-nose box
   if the nose has moved (the last **7**).
3. **Window end.** A belt loader centred in the left **20 %** of the image, labelled by the tracker as at a cargo door in
   more than 10 % of its last **32 frames** (4 s), is reported stopped — or **2400 frames** (5 min) have passed.
4. **Aircraft outline.** On the first window frame with a usable person (tallest person ≥ **150 px**, one clear of the
   image border), MobileSAM cuts out the aircraft parts and the person, and Depth Anything V2 estimates depth, scaled by
   the person's distance. The nose positions from step 2 give the aircraft's axis; an outline is drawn on a top-down
   canvas (70 m × 60 m). No outline → Not observed.
5. **Worker positions.** In every window frame YOLOv8m-pose runs on each person crop. Distance comes from the box height,
   assuming a **1.75 m** person (scaled up at most **×2** when only part of the body is visible); the angle comes from the
   box centre with a **65°** field of view.
6. **Blocked frames.** A frame is blocked when vehicle and obstacle boxes cover more than **50 %** of a fixed area
   (15–50 % of the width, 20–60 % of the height).
7. **Path cleaning** at the window end: tracks are cut at gaps over **1.5 s** or jumps over **6.5 m**; points closer than
   **5 m** (10 m for a small nose) or farther than **55 m** are dropped; paths are smoothed and those under **8 points**
   dropped; pieces of different track ids within **25 s** and **25 m** of each other are chained into candidate
   walk-arounds (at most **300**, sampled).
8. **Scoring.** Each path and candidate is drawn on the aircraft canvas; the CNN gives each drawing a probability.
9. **Verdict.** Fewer than **150 frames** (19 s) in the window → Not observed; no worker paths → Not observed; more than
   **60 %** blocked frames → Not observed, unless the best drawing and at least **8** drawings score ≥ 0.97; best drawing
   ≥ **0.97** → Pass; otherwise Fail.

## Settings

| Setting | Value | What it does |
|---|---|---|
| `post_arrival.max_walk_around_duration` | 300 s (2400 frames) | longest inspection window after the stop |
| `post_arrival.trajectory_temporal_threshold`, `trajectory_spatial_threshold` | 1.5 s (12 frames), 6.5 m | a longer gap or jump cuts a path |
| pass threshold (code) | 0.97 | drawing probability needed for Pass |
| `post_arrival.max_blocked_frame` | 0.6 | blocked share above which the verdict is Not observed |
| `post_arrival.false_no_override` | true | a strongly observed pass beats the blocked rule; `false` restores the literal client rule |
| minimum window (code) | 150 frames (19 s) | shorter windows → Not observed |
| `post_arrival.review_confidence_threshold` | 0.0 (off) | flags low-confidence verdicts for review; never changes the verdict |
| `post_arrival.gs1737.*` | both layers `false` | two Fail → Pass recovery layers, switched off |
| chaining (code) | 25 s, 25 m, ≤ 300 candidates | which track pieces are joined |
| `obstacle_*`, `worker_height`, `focal_length`, `max_duration_cone/wing`, `min_walk_around_duration` and others | — | not used by the code |

## What it reports

- The verdict for the task `post-arrival-aircraft-walk-around-inspection-completed-accurately`.
- Report text: only "Returned status: <verdict>".
- Smart timeline: one entry, `{Status, Start: window start frame, End: window end frame}` (as text).
- In the working folder `data/<video>/` (not sent to the website): `report.json` (best probability, blocked frames,
  confidence, reason), path CSVs, the drawings and the outline.
- The per-frame drawing log stays empty; an output video of the window only when video writing is on.

## Known issues and limits

- Accuracy (team analysis, June 2026, commit fbd803f): 70.6 % (36 of 51 videos) on the test-set labels, 46.4 % on the
  newer monthly labels (the two label sets agree on 56.9 %). One camera facing the nose cannot see the far side; the
  analysis puts the ceiling near 70 %.
- With up to 300 candidate drawings and "any drawing ≥ 0.97 → Pass", a random chain can pass.
- Errors out instead of Not observed if the aircraft never stops or the video ends inside the window, and if a second
  aircraft track id taller than 250 px appears before the stop.
- Only a belt loader in the left 20 % of the image ends the window (a "temporary fix" in the code).
- The outline needs the approach on video and a clear standing person.
- Chaining stops after 5 minutes of wall-clock time, so machine load can change the verdict.
- A leftover `data/<video>/report.json` makes a re-run re-score the cached paths without reading the video.
- The README describes an older checkpoint logic (`sources/`) that does not run; the July 2026 box-logging commit
  changed that unused code, so the website shows no boxes for this task.
- Never loaded: `best_acc.keras`, `sam_vit_b_01ec64.pth`.

## For developers

- **Repository:** `dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately`; production line
  `tdv_cone` @ `a0d9ee4`; default branch `main` @ `7112c99` (2025-06-19, the older checkpoint logic, 126 commits
  behind). Whether the last five commits (July 2026: decision policy, no workers → Not observed, recovery layers off)
  are deployed is to confirm.
- **Entry point:** `main.py` → `detect(...)`; `code/states.py` (`Gate`: phases, outline, belt-loader rule);
  `code/walk_around/walk_around.py` (positions, blocked frames, cleaning, drawings, CNN); `decision_policy.py`;
  `temp/plane_tdv_extractor.py` (outline); `preprocessing/` (cleaning, chaining); `model/predictor.py` (CNN).
- **Dependencies:** `cv_common` c11573b and `db_worker` 5a4aa83 (exported copies of the branch pins). Packages:
  ultralytics 8.2.48, MobileSAM, torch, vendored Depth Anything V2. Weights by DVC: `best_model.pth`, `yolov8m-pose.pt`,
  `depth_anything_v2_metric_vkitti_vitb.pth`, `mobile_sam.pt`. No Dockerfile on the branch.
- **Run locally:** from the repository root: `python main.py --source <video>.mp4 --inferences-dir <folder with GM and
  tracker ndjson> [--write-video] --cache_folder ./data`.
- **Code references:** step 1 `code/states.py:31-109, 325-335`; step 2 `plane_tdv_extractor.py:109-157`; step 3
  `states.py:112-189, 337-341`, `code/transport/beltloader.py:31-80`; step 4 `plane_tdv_extractor.py:163-355`,
  `states.py:366-372`, `walk_around.py:321-325, 423-446`; step 5 `detection_processor.py:34-92`,
  `distance_estimator.py:56-86`; step 6 `walk_around.py:65-68, 201-232`; step 7 `walk_around.py:276-304, 531-585`,
  `preprocessing/recombination.py:48-62, 205-298`; step 8 `walk_around.py:330-352`, `model/predictor.py:73-91`; step 9
  `decision_policy.py:41-89`, `walk_around.py:102-117`; result `main.py:136-146`, `states.py:301-310`.
