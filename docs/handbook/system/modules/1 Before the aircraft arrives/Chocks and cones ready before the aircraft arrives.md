# Chocks and cones ready before the aircraft arrives

> Before the aircraft rolls in, the crew must lay out at least 7 cones and 6 wheel chocks. The module counts the cones
> and chocks that the General Model (the shared detector) finds in the cone camera's pictures until the aircraft stops.

## Status

| | |
|---|---|
| How accurate it is | 61 of 68 turnarounds correct (90 %) on the monthly test |
| Fail turnarounds it caught | 20 of 24 |
| In production | the version of April 2026 |
| Who looks after it | to assign |
| Biggest open problem | A Pass is given without checking that the arrival and the time before it were filmed. |

## What the client wants

*Chocks and cones available and staged for arrival*

| Verdict | When |
|---|---|
| Pass | 7 cones and 6 chocks are seen at the stand before the aircraft arrives. |
| Fail | 7 cones and 6 chocks are not seen before the aircraft arrives. |
| Not observed | Something blocks the view, or the video does not show the time before the arrival. |
| Not observed, view blocked | The view is blocked for more than half of the time before the arrival, or there is a side obstacle. |

A verdict is the answer of a check: Pass, Fail or Not observed. A side obstacle is a vehicle at the edge of the picture
that the General Model marks as standing in the way.

## When and where it looks

The check covers the pre-arrival stage (a stage is a part of the turnaround; this one is the time before the aircraft
arrives). The module reads from the first frame of the video (one picture; the cameras take 8 per second) to the frame on
which the tracker (the part that follows objects from frame to frame) reports that the aircraft has stopped, once it has
stood still for more than 4 seconds. Without a reported stop, it counts to the end of the video. It runs on the cone
camera (which looks towards the aircraft nose), for aircraft and for jets; the module itself does not check which camera
filmed the video.

## What it looks at

- **From the General Model** (a detection is a box the detector draws around an object): cones and chocks; belt
  loaders, pushback tugs and other service vehicles (ground support equipment: tugs, belt loaders, fuel trucks,
  tractors), to drop chocks carried on them; vehicles, trailers, fuel trucks, people, ladders and "obstacle" or "side
  obstacle" boxes, to tell when the view is blocked.
- **From the tracker:** the aircraft track (a track is the same object followed from frame to frame): the widest
  aircraft and the moment it stopped.
- **From the video itself:** nothing; pictures are read only to draw an annotated video. **Own models:** none; it runs
  on an ordinary processor.

## How it decides, step by step

1. Reads the General Model's boxes and the aircraft track frame by frame, from the start to the frame where the tracker
   reports the stop; with several aircraft, it follows the widest.
2. On each frame counts the chocks and the cones taller than 30 pixels (the picture is 1,920 × 1,080 pixels). A chock
   touching a belt loader, pushback tug or other service vehicle, whose box is first enlarged by 20 % on each side,
   counts as carried and is dropped.
3. A frame with at least 7 cones adds to a cone counter, a frame with at least 6 chocks to a chock counter. A counter
   that passes 3 seconds of frames passes that object type for good. The frames need not follow each other, and cones
   and chocks need not be on the same frames.
4. Marks a frame as blocked when one large box stands in the lower half of the picture, or touching smaller boxes there
   cover at least 2.2 % of it together (positions and sizes in the table below). A frame that already shows enough
   cones and chocks is not counted as blocked.
5. At the stop, the shared arrival check decides whether the arrival was filmed: the aircraft's box must have grown by
   more than 18 % (it looks bigger as it comes closer) between the first 3 seconds of its track and the last 8 seconds
   before the stop, so at least 11 seconds of track are needed. The pre-arrival stage counts as filmed if, also, the
   aircraft first appeared at least 11.25 seconds into the video. The check restarts after 10 seconds without an
   aircraft or when a larger one appears, and decides anyway after 5 minutes without a stop.
6. **Pass** if both cones and chocks passed. Otherwise **Not observed** if no aircraft was seen, if the arrival or the
   time before it was not filmed, or if blocked frames are at least half of the frames before the stop. Otherwise
   **Fail**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Objects on one frame | 7 cones, 6 chocks | Fewer do not count |
| Time each count must hold | 3 seconds in total | Less: no pass for that object |
| Smallest cone | 30 pixels tall | Smaller cones are ignored |
| Margin around vehicles | 20 % per side | Chocks touching it are dropped |
| Position of a blocking box | bottom edge below 52.5 % of the height; reaching past the outer 7.2 % of the width (5.8 % for service vehicles, fuel trucks, people) | Which boxes can block |
| Size of one blocking box | 1 % of the picture, rising to 2.7 % at the bottom edge | Smaller boxes do not block alone |
| Blocking group | boxes of 0.04 % or more, within 1 % of the width of each other, 2.2 % together | When small boxes block |
| Blocked share | 50 % of the frames before the stop | More: Not observed |
| Arrival check | box growth more than 18 %; first sighting 11.25 seconds into the video or later (90 seconds intended) | Less growth: arrival not filmed; earlier sighting: no pre-arrival stage |
| Arrival check time limits | 10 seconds without aircraft; 5 minutes without a stop | Restart; decide anyway |

## What it reports

- **Sentence.** Pass, for example: "There was enough cones and chocks. (Cones: 7, chocks: 6)." with the time span. Fail:
  "There wasn't enough cones and chocks." with the largest counts, or "There were enough cones and chocks, but they
  were present for less than 3 seconds." Not observed: "Airplane wasn't detected", "No arrival stage", "No pre-arrival
  stage" or "There were obstacles during prearrival stage".
- **Timeline entry:** one Pass or Fail block from the start of the video to the stop; none for Not observed.
- **Files:** a drawing file with, per frame, the cone, chock and blocking boxes, counts, blocked-view events and the
  aircraft's state; an annotated video only when video writing is on.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on 61 (90 %). Of the 24 labelled Fail it caught 20, so 4 of its 7 errors are missed
violations; the other 3 are turnarounds labelled Pass or Not observed where it said something else. With 24 Fail labels
the test does show that it catches most missing equipment; which turnarounds it got wrong is not in our sources.

## Known problems

- **11 seconds instead of 90.** The shared arrival check is described as needing the aircraft to appear 90 seconds into
  the video, but waits only 11.25 seconds. The rule gives Not observed without a pre-arrival stage; a video starting
  seconds before the aircraft appears can get Fail instead. Shared with *Foreign object debris walk completed* and
  *Safety huddle at the huddle cone*; production's copy of the shared library: to confirm.
- **Pass skips the arrival checks.** Pass needs neither an aircraft nor a filmed pre-arrival stage, so a video without
  the time before the arrival can get Pass instead of Not observed.
- **No side-obstacle rule.** The rule gives Not observed for a side obstacle; the module only counts side-obstacle boxes
  that pass its size and position test. A side obstacle alone can end as Fail.
- **No stop, no end.** Without a reported stop, counting runs to the end of the video, so equipment put out after the
  arrival counts and can give Pass.
- **Staged chocks dropped.** Chocks placed right next to a service vehicle are dropped like carried ones, which can give
  Fail.
- **Short aircraft track.** With less than 11 seconds of aircraft track before the stop, the module reports "No arrival
  stage", Not observed, unless it had already passed.
- **Old description.** The module's description file describes the old logic (60-second pre-arrival rule,
  camera-shake filter); no effect on the verdict.
- **Missing library part (to confirm).** The module uses a part of the shared library that its pinned version lacks;
  how the production build supplies it is to confirm.

## In real time

It can run as it is: it reads each frame's boxes and tracks once, in order, needs no pictures, and decides at the stop,
which the tracker gives today and the stage detector (the part that knows where in the turnaround we are) will give in
real time.

On a 36-minute test turnaround in the real-time test setup, it gave the same verdict and sentence as post-processing
(after the turnaround), at the moment of the stop. Own work: 0.09 milliseconds per frame; with the shared General Model
(main detector plus chock and vehicle parts) and tracker, 31.4 of the 125 milliseconds each frame may take (25 %). As a
post-processing job: about 7 seconds.

In live test runs, its verdict changed from Fail to Not observed on 4 turnarounds, where another aircraft in view was
taken for the arriving one: a problem of the shared live feed, for the stage detector to solve. The client's split
puts this check in the post-processing group.

## For developers

- **Module code:** M06. **Repository:** `dxgat/detectors/chocks-and-cones-available-and-staged-for-arrival`; production
  `not_observed_logic` @ `2b4fca9` (2026-04-29). `master` @ `1413225` (2025-06-19) is older: counts hard-coded 7/6
  (YAML 6/4), pre-arrival = stop after 60 s, any `obstacle` / `side_obstacle` box blocks.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, ..., json_logger, new_design)`;
  `get_decision()`; `obstacle_logic.py` (`determine_obstacles()` size curve); `visualization_overlay.py` (drawing);
  `cv_common/modules/plane_arrival_detector.py`.
- **Run:** `python main.py --source <video>.mp4 --inferences-dir <dir> [--write-video] [--new-design] [--json-fn
  <name>]` (reads `general_model<video>.ndjson`, `trackers<video>.ndjson`; `local_config.yaml` overrides
  `cv_common/global_config.yaml`). Production: `db_worker/model_starter.py` calls `detect()`.
- **Keys:** `quantity_thr.cone`/`.chock`, `presence_thr` (> 24 frames); `obstacle.position.{max_x1, min_x2,
  min_weaker_x2, min_y2}`; `obstacle.combined.{min_area, min_comb_area, w_margin}`; `obstacle.not_observed_thr_ratio`.
  In code: cone > 30 px, `add_offset(..., 0.2, 0.2)`, `min_area(y2)` 0.01 → 0.037·y2 − 0.01. Arrival detector:
  `area_change_thr`, `prearrival_min_frames` = 90 frames (docstring: seconds), windows 3 s + 8 s (88 frames), time-outs
  10 s / 300 s.
- **Code places:** step 1 `main.py:153-187, 321, 47-97, 329-333`; 2 `:168, 190-197, 335-338`; 3 `:200-211, 339`; 4
  `:360`, `obstacle_logic.py:92-183`; 5 `main.py:323-327`, `plane_arrival_detector.py:77, 85-149, 196-229`; 6
  `main.py:104-131, 402`.
- **Dependencies:** pins `cv_common` dd5b554, `db_worker` 5a4aa83 (export: `cv_common` ac5098d + `cv_common/modules`
  2759daf); no weights; CPU image. Logic diagram: Confluence modules database, 2023-07-10 (older logic).
