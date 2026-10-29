# Post-arrival aircraft walk around inspection completed accurately

*In plain words: walk-around inspection after arrival.*

> After the aircraft stops, a worker should walk around it to inspect it. The check makes sure this walk-around happens.
> The software turns every worker's path into a drawing seen from above, next to an outline of the aircraft, and a small
> neural network trained by the team decides whether any drawing looks like a complete walk-around.

## Status

| | |
|---|---|
| How accurate it is | 42 of 55 turnarounds correct (76 %) on the monthly test |
| Fail turnarounds it caught | 17 of 21 |
| In production | the version of July 2026 |
| Who looks after it | to assign |
| Biggest open problem | One camera facing the aircraft nose cannot see the far side of the aircraft, so the module has to judge walk-arounds it can only partly see. |

## What the client wants

The client calls this check *Post-arrival aircraft walk around inspection completed accurately*.

| Verdict | When |
|---|---|
| Pass | The path model says "yes" for a worker's path around the aircraft (the path is cleaned up and turned into a picture first). |
| Fail | The model says "no" for every path it saw. |
| Not observed | No workers are visible. |
| Not observed, view blocked | The camera's view is blocked on more than 60 % of the frames. |

The client adds: paths are followed until the belt loader arrives, or for 5 minutes after the aircraft arrives. A
verdict is the answer of a check: Pass, Fail or Not observed. A frame is one picture of the video; the cameras take 8 per
second. The client puts the check in its post-processing group (checks judged after the turnaround) and marks it as not
ready for production.

## When and where it looks

The stage (part of the turnaround) is the time after the aircraft stops. The inspection window opens when the aircraft
has stood still for 3 seconds and closes when a belt loader (the vehicle with a conveyor belt that serves a cargo door)
stops at the aircraft, or after 5 minutes at most. Before the stop, the module also keeps a few pictures of the
approaching aircraft.

It runs on the cone camera (the camera that looks towards the aircraft nose), for aircraft only; it is not run for jets
(the client's two aircraft types).

## What it looks at

- **From the tracker:** the aircraft, people and belt loaders (a track is the same object followed from frame to frame).
- **From the General Model:** aircraft parts and people (for the aircraft outline); vehicles and objects labelled
  "obstacle" or "side obstacle" (for the blocked view). A detection is a box the detector draws around an object.
- **From the video itself:** yes, every frame of the window and some frames of the approach.
- **Own models:**
  - the walk-around network, trained by the team: it gives each path drawing a probability of being a complete
    walk-around;
  - three standard models, not trained by the team: a pose model that finds a person's joints (shoulders, elbows,
    knees and so on), which here helps to estimate the person's distance; a depth model that estimates how far each
    point of the picture is from the camera; and a cut-out model that traces the exact outline of an object, here the
    aircraft parts and a person.
- It runs on a graphics card when one is available, otherwise on ordinary processors; the production settings file says
  processors (to confirm).

## How it decides, step by step

1. **Phases.** The module follows one aircraft track taller than 250 pixels. When the tracker reports it stopping, the
   arrival phase starts; when it is stopped (still for 3 seconds), the inspection window opens.
2. **Approach pictures.** Before the stop, every 2 seconds, it keeps the frame and the biggest aircraft nose box if the
   nose has moved (the last 7 of them).
3. **End of the window:** a belt loader centred in the left 20 % of the picture, marked by the tracker as at a cargo door
   on more than 10 % of its last 4 seconds, is reported stopped; or 5 minutes have passed.
4. **Aircraft outline.** On the first window frame with a usable person (the tallest person at least 150 pixels tall and
   one clear of the picture's border), the cut-out model traces the aircraft parts and the person, and the depth model
   estimates depth, scaled by that person's distance. The nose positions from step 2 give the aircraft's axis. The
   outline is drawn on a map seen from above, 70 by 60 metres. No outline: **Not observed**.
5. **Worker positions.** On every window frame the pose model runs on each person's cut-out. The distance comes from the
   box height, assuming a person is 1.75 metres tall (scaled up at most 2 times when only part of the body is visible);
   the direction comes from the box centre, with a 65-degree field of view.
6. **Blocked frames.** A frame is blocked when vehicle and obstacle boxes cover more than 50 % of a fixed area (from
   15 % to 50 % of the picture's width and from 20 % to 60 % of its height).
7. **Cleaning the paths** at the end of the window. Tracks are cut at gaps longer than 1.5 seconds or jumps longer than
   6.5 metres. Points closer than 5 metres (10 metres when the nose looks small) or farther than 55 metres are dropped.
   Paths are smoothed, and those with fewer than 8 points are dropped. Pieces of different tracks within 25 seconds and
   25 metres of each other are chained into candidate walk-arounds; if there are more than 300, a random 300 are kept.
8. **Scoring.** Each path and each candidate chain is drawn on the aircraft map, and the network gives each drawing a
   probability.
9. **Verdict.** A window shorter than 150 frames (19 seconds): **Not observed**. No worker paths: **Not observed**.
   More than 60 % blocked frames: **Not observed**, unless the best drawing and at least 8 drawings in all score 0.97 or
   more. Best drawing 0.97 or more: **Pass**. Otherwise **Fail**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Longest inspection window after the stop | 5 minutes | Paths after it are not judged |
| Gap and jump that cut a path | 1.5 seconds; 6.5 metres | How paths are split |
| Probability needed for Pass (in the code) | 0.97 | Lower: more Pass |
| Blocked share for Not observed | 60 % of the frames | More blocked: Not observed |
| A strong pass beats the blocked rule | on | Off restores the client's literal rule |
| Shortest window (in the code) | 150 frames (19 seconds) | Shorter: Not observed |
| Flag for low-confidence verdicts | off (0.0) | Marks verdicts for review; never changes them |
| Two "recovery" layers that can turn Fail into Pass | both off | Off: no Fail is turned into Pass |
| Chaining of path pieces (in the code) | 25 seconds, 25 metres, at most 300 candidates | Which pieces are joined |

The obstacle settings, the worker height, the focal length, the window lengths per camera, a minimum walk-around length
and other values in the settings file are not used by the code.

## What it reports

- **Sentence:** only "Returned status: <verdict>".
- **Timeline entry** (the stretch of video the website marks): one entry from the start to the end of the window,
  stored as text.
- **Files:** in the module's working folder, not sent to the website: a report with the best probability, the blocked
  frames, a confidence and the reason; tables of the paths; the drawings and the outline. The drawing file for the
  website stays empty; an output video of the window only when video writing is switched on.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 55 of them labelled for
this check. The module gave the client's verdict on 42 (76 %). The client labelled 21 Fail and the module caught 17: it
missed 4 turnarounds where the walk-around was not done, and gave 9 other wrong verdicts on turnarounds labelled Pass or
Not observed. With 21 Fail labels the test does show how well it catches missing walk-arounds.

The team's own analysis in June 2026, on an earlier version, found 70.6 % (36 of 51 videos) against the test labels and
46.4 % against the newer monthly labels; the two sets of human labels agreed with each other on only 56.9 % of the
videos. One camera facing the nose cannot see the far side of the aircraft; that analysis put the reachable accuracy
near 70 %.

## Known problems

- **A chance chain can pass.** The client asks for a worker's path around the aircraft. With up to 300 candidate
  drawings and "any drawing at 0.97 or more gives Pass", a chance chain of path pieces from different tracks can reach
  the threshold and give Pass.
- **Errors instead of Not observed.** The module stops with an error, instead of giving Not observed, when the aircraft
  never stops, when the video ends inside the window, or when a second aircraft track taller than 250 pixels appears
  before the stop.
- **A strong pass beats the blocked rule.** The client gives Not observed above 60 % blocked frames; the module gives Pass
  when at least 8 drawings score 0.97 or more. Switching the setting off restores the client's rule.
- **Not observed for reasons the client did not write:** a window shorter than 19 seconds, or no aircraft outline.
- **Only a belt loader in the left 20 % of the picture ends the window** (marked in the code as a temporary fix).
- **The outline needs the approach on video and a clearly visible standing person.**
- **The verdict can depend on machine load.** Chaining stops after 5 minutes of computer time, not video time.
- **A leftover report changes a re-run.** A report file left in the working folder makes a new run re-score the stored
  paths without reading the video.
- **No boxes on the website.** The module's own description describes an older logic that no longer runs; the July 2026
  change meant to log boxes for the website changed that unused code.
- **Two model files in the repository are never loaded.**
- **Deployment to confirm.** Whether the last five changes of July 2026 (the decision rules, "no workers gives Not
  observed", the recovery layers switched off) are deployed in production is to confirm, as is whether production runs
  it on a graphics card or on processors. Both are for Ihor, the technical lead.

## In real time

Post-processing only. The module judges whole paths when the inspection window closes; a part of a walk-around is not a
part of the answer, so the question cannot be answered before the walk-around ends. Its paths need the cut-out, depth and
pose models over the whole stage. It is not hosted in the real-time branch, because it runs in its own software
environment. The client also puts the check in its post-processing group. Its real-time cost was not measured.

## For developers

- **Module code in our workspace:** M17.
- **Repository:** `dxgat/detectors/post-arrival-aircraft-walk-around-inspection-completed-accurately`; production line
  `tdv_cone` @ `a0d9ee4` (2026-07-27); default branch `main` @ `7112c99` (2025-06-19, the older checkpoint logic, 126
  commits behind). Whether the last five commits (July 2026: decision policy, no workers → Not observed, recovery layers
  off) are deployed: to confirm.
- **Entry point:** `main.py` → `detect(...)`; `code/states.py` (`Gate`: phases, outline, belt-loader rule);
  `code/walk_around/walk_around.py` (positions, blocked frames, cleaning, drawings, CNN); `decision_policy.py`;
  `temp/plane_tdv_extractor.py` (outline); `preprocessing/` (cleaning, chaining); `model/predictor.py` (CNN). Task name
  `post-arrival-aircraft-walk-around-inspection-completed-accurately`; working folder `data/<video>/` (`report.json`).
- **Run on one turnaround:** from the repository root, `python main.py --source <video>.mp4 --inferences-dir <folder
  with GM and tracker ndjson> [--write-video] --cache_folder ./data`.
- **Settings keys:** `post_arrival.max_walk_around_duration` 300 s; `post_arrival.trajectory_temporal_threshold` 1.5 s,
  `trajectory_spatial_threshold` 6.5 m; `post_arrival.max_blocked_frame` 0.6; `post_arrival.false_no_override` true;
  `post_arrival.review_confidence_threshold` 0.0; `post_arrival.gs1737.*` both false. In code: pass threshold 0.97;
  minimum window 150 frames; chaining 25 s / 25 m / ≤ 300; aircraft track > 250 px; person ≥ 150 px; canvas 70 × 60 m;
  1.75 m person, scale ≤ ×2, 65° field of view; blocked area x 0.15–0.50, y 0.20–0.60, > 50 %; nose sampling every 16
  frames, last 7; window end: belt loader centre in left 20 %, door label > 10 % of 32 frames. Unused: `obstacle_*`,
  `worker_height`, `focal_length`, `max_duration_cone/wing`, `min_walk_around_duration` and others.
- **Code places:** step 1 `code/states.py:31-109, 325-335`; step 2 `plane_tdv_extractor.py:109-157`; step 3
  `states.py:112-189, 337-341`, `code/transport/beltloader.py:31-80`; step 4 `plane_tdv_extractor.py:163-355`,
  `states.py:366-372`, `walk_around.py:321-325, 423-446`; step 5 `detection_processor.py:34-92`,
  `distance_estimator.py:56-86`; step 6 `walk_around.py:65-68, 201-232`; step 7 `walk_around.py:276-304, 531-585`,
  `preprocessing/recombination.py:48-62, 205-298`; step 8 `walk_around.py:330-352`, `model/predictor.py:73-91`; step 9
  `decision_policy.py:41-89`, `walk_around.py:102-117`; result `main.py:136-146`, `states.py:301-310`.
- **Dependencies:** `cv_common` c11573b and `db_worker` 5a4aa83 (exported copies of the branch pins). ultralytics
  8.2.48 (YOLOv8m-pose), MobileSAM, torch, vendored Depth Anything V2. Weights by DVC: `best_model.pth` (walk-around
  CNN), `yolov8m-pose.pt`, `depth_anything_v2_metric_vkitti_vitb.pth`, `mobile_sam.pt`; never loaded: `best_acc.keras`,
  `sam_vit_b_01ec64.pth`. No Dockerfile on the branch.
- **Accuracy analysis:** team analysis of June 2026 at commit `fbd803f`.
- **Real time and sources:** `docs/04_modules.md` (POST), `docs/analysis/rt_module_selection.md` (not in real time v1),
  `docs/analysis/rt_module_cost.md` (not hosted: own Python environment);
  `docs/modules/post-arrival-aircraft-walk-around-inspection-completed-accurately.md`,
  `docs/analysis/module_review_2026-10.md`.
