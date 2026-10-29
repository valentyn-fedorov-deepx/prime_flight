# Crew present 10 minutes prior to aircraft arrival

*In plain words: crew present 10 minutes before the aircraft arrives.*

> The crew must be at the stand well before the aircraft arrives. The module counts the people that the General Model
> (the shared detector) finds in each cone-camera picture and, when the aircraft stops, checks that at least three were
> seen for long enough between 12 and 8 minutes before the stop.

## Status

| | |
|---|---|
| How accurate it is | 62 of 68 turnarounds correct (91 %) on the monthly test |
| Fail turnarounds it caught | 22 of 25 |
| In production | the version of February 2026 |
| Who looks after it | to assign |
| Biggest open problem | When nobody is detected at all it gives Fail, even where the rule says Not observed (view blocked, pre-arrival stage too short). |

## What the client wants

*Crew present 10 minutes prior to aircraft arrival*

| Verdict | When |
|---|---|
| Pass | Three workers are seen for more than 10 seconds in total between 12 and 8 minutes before the arrival. |
| Fail | Three workers are not seen for that long in that window. |
| Not observed | The video has no pre-arrival stage, or it is shorter than 4 minutes. |
| Not observed, view blocked | The view is blocked in more than 70 % of the pre-arrival stage. |

A verdict is the answer of a check: Pass, Fail or Not observed. The pre-arrival stage is the part (stage) of the
turnaround before the aircraft arrives. The client's sheet gives the time in frames (pictures; the cameras take 8 per
second), which is 10 seconds. So the rule asks for three workers for a short time around ten minutes before the
arrival, not for ten minutes of presence.

## When and where it looks

The module reads from the first frame of the video to the frame on which the tracker (the part that follows objects from
frame to frame) reports that the aircraft has stopped, once it has stood still for more than 4 seconds. People are
counted from 12 to 8 minutes before the stop, or, in shorter videos, from the start to 1 minute before the stop. It runs
on the cone camera (which looks towards the aircraft nose), for aircraft and for jets; the module itself does not check
which camera filmed the video.

## What it looks at

- **From the General Model** (a detection is a box the detector draws around an object): people, to count the crew;
  pushback tugs, trailers and other service vehicles (ground support equipment: tugs, belt loaders, fuel trucks,
  tractors; belt loaders and fuel trucks are not used here), to tell when the view is blocked.
- **From the tracker:** the aircraft track (a track is the same object followed from frame to frame): the widest
  aircraft, whether it moves, the points the tracker follows on it, and the moment it stopped.
- **From the video itself:** nothing; pictures are read only to draw an annotated video. **Own models:** none; it runs
  on an ordinary processor.

## How it decides, step by step

1. Reads the General Model's boxes and the aircraft track frame by frame from the start of the video.
2. A frame is blocked when a pushback tug, trailer or other service vehicle box is wider than 30 % of the picture (576 of
   its 1,920 pixels) with its centre in the right 70 %. Blocked frames are counted and otherwise skipped: no people are
   counted and the aircraft is not updated.
3. On every other frame it counts all people anywhere in the picture and notes the frames with 3 or more.
4. It follows the widest aircraft. The arrival counts as filmed once the tracker shows it moving for more than 3 seconds
   in a row; a jump of the tracked points of over 50 pixels sideways or 5 pixels up or down between frames counts as
   camera shake and restarts that count. The pre-arrival stage counts as filmed when the stop comes more than 60
   seconds into the video.
5. It decides once, on the frame where the tracker reports the stop, in this order: stop within the first 60 seconds →
   **Not observed**; nobody detected at all → **Fail**; blocked frames more than 70 % of the frames before the stop →
   **Not observed**; stop less than 4 minutes into the video → **Not observed**; arrival movement not filmed → **Not
   observed**.
6. Count window: 12 to 8 minutes before the stop. If the stop comes less than 12 minutes into the video, the window runs
   from the start of the video to 1 minute before the stop.
7. **Pass** if more than 10 seconds of frames in the window had 3 or more people; otherwise **Fail**. The frames need not
   follow each other or show the same people.
8. It runs 60 seconds more only to draw the result, then stops. If the aircraft never stops: **Not observed**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| People on a frame | 3 | Fewer do not count |
| Time with 3 people | more than 10 seconds in total | Less: Fail |
| Count window | 12 to 8 minutes before the stop | Where people are counted |
| Window for short videos | start of the video to 1 minute before the stop | Used when the stop is less than 12 minutes in |
| Shortest pre-arrival stage | 4 minutes (also the window length) | Shorter: Not observed |
| Earliest stop | 60 seconds into the video | Earlier: Not observed |
| Blocking box | wider than 30 % of the picture, centre in the right 70 % | Which frames are blocked |
| Blocked share | 70 % of the frames before the stop | More: Not observed |
| Arrival movement | more than 3 seconds in a row | Less: Not observed |
| Camera shake | point jump over 50 pixels sideways or 5 pixels up or down | Restarts the movement count |
| Largest crew in the report | the largest number of people seen for more than 1.25 seconds | Report text only |

Not used: the settings file's 12-minute value (the code has 12 minutes written in) and three older values (0.33, 10,
three matching thresholds).

## What it reports

- **Sentence.** Pass: "Three or more workers were present for enough time during prearrival stage." with the time span.
  Fail: the largest crew seen and how many frames had 3 or more people ("Enough number of workers were present less
  time than needed."), or "No workers where detected on pre-arrival stage." Not observed: "No arrival stage", "No
  pre-arrival stage", "There was an obstacle.", "The pre-arrival stage was very short (less than 4 minutes)." or "Plane
  did not arrive".
- **Timeline entry:** one Pass or Fail block from the window start (the video start when nobody was detected) to the
  stop; none for Not observed.
- **Files:** a drawing file with person boxes, worker counts, "Camera is blocked!" and the aircraft's state per frame; an
  annotated video only when video writing is on.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on 62 (91 %). Of the 25 labelled Fail it caught 22, so 3 of its 6 errors are missed
violations; the other 3 are turnarounds labelled Pass or Not observed where it said something else. With 25 Fail labels
the test does show that it catches most turnarounds without a crew; which turnarounds it got wrong is not in our sources.

## Known problems

- **Any three people count.** People are counted anywhere in the picture, frame by frame, so any three visible people
  count. This follows the client's rule, which counts frames with three workers, but nothing checks that the same crew
  is present, as the check's name suggests.
- **Nobody detected gives Fail too early.** "Nobody detected" is tested before the blocked-view, 4-minute and arrival
  tests, so such a video gets Fail even when the arrival was not filmed, the view was blocked over 70 % of the time or
  the stop came within 4 minutes. The rule says Not observed there.
- **Dead code for short videos.** Code meant to count over the whole pre-arrival stage of short videos never runs (its
  switch is always reset); only the window count is used.
- **Window edges move.** The window's start and end snap to the nearest frame with a detected person; when the window
  has none, frames just outside it can be counted.
- **Older arrival logic.** It uses the older arrival test (camera-shake filter, 60-second rule), not the shared arrival
  check of the other pre-arrival modules, so it can judge the same video's pre-arrival stage differently.
- **Unknown labels stop it.** If the General Model sends a label the module does not know, the module stops with an
  error.
- **An extra minute.** The verdict is fixed at the stop, but the module runs 60 seconds longer only to draw.

## In real time

It can run as it is: it reads each frame's boxes and tracks once, in order, needs no pictures, and decides at the stop,
which the tracker gives today and the stage detector (the part that knows where in the turnaround we are) will give in
real time. A warning before the arrival would need the scheduled arrival time, which the real-time feed lacks.

On a 36-minute test turnaround in the real-time test setup, it matched post-processing (after the turnaround) in verdict
and sentence; the verdict came 64 seconds after the stop because of the drawing minute. Own work: 0.54 milliseconds per
frame; with the shared General Model (main detector plus vehicle part) and tracker, 19.5 of the 125 milliseconds each
frame may take (16 %). As a post-processing job: about 12 seconds.

In live test runs, its verdict changed to Not observed on 5 turnarounds (2 Fail, 3 Pass), where another aircraft in
view was taken for the arriving one: a problem of the shared live feed, for the stage detector to solve. The
client's split puts this check in the post-processing group.

## For developers

- **Module code:** M10. **Repository:** `dxgat/detectors/crew-present-10-minutes-prior-to-aircraft-arrival`; production
  `main` @ `5cfd25c` (2026-02-12), the same as the default branch.
- **Entry point:** `main.py` → `detect(source, output_path, device, weights_dir, video_worker, write_video,
  cone_camera, json_fn, json_logger)`; all logic inside `detect()`; `get_max_value()` builds the report number.
- **Run:** `python main.py --source <video>.mp4 [--write-video] [--json-fn <name>]`; the video worker reads
  `general_model<video>.ndjson` and `trackers<video>.ndjson` from `../inferences_dir` (this `main.py` has no
  `--inferences-dir`); `local_config.yaml` overrides `cv_common/global_config.yaml`. Production:
  `db_worker/model_starter.py` calls `detect()`.
- **Keys:** `obstacle.width` 0.3, `obstacle.center` [0.3, 1]; `crew_presence.four_minutes_seconds` 240,
  `twelve_minutes_seconds` 720 (unused; code `12*60*fps`), `min_enough_workers_seconds` 10 (> 80 frames),
  `min_pre_arrival_seconds` 60, `prearrival_exclude_last_seconds` 60, `obstacle_frame_ratio_threshold` 0.7,
  `motion_anomaly_x_threshold` 50 / `_y_threshold` 5, `max_value_count_threshold` 10 (frames). Code: crew size 3,
  arrival movement `normal_moving_counter_custom > 24`, drawing tail `60 * fps`. Unused: `criteria_for_fail` 0.33,
  `criteria_for_n_o` 10, `matching_th`.
- **Code places:** step 1 `main.py:60-98`; 2 `:100-110`; 3 `:137-143`; 4 `:147-202`; 5 `:211-247, 259-260`; 6
  `:248-257, 280-289`; 7 `:290-306`; 8 `:123-133, 310-311`.
- **Dependencies:** pins `cv_common` dd5b554, `db_worker` 6efc0b0 (local `cv_common` holds ac5098d); torch 1.10; no
  weights; CPU image. Logic diagram: `.doc/Crew present.svg`; Confluence, 2023-07-10. Client sheet: "more than 80
  frames"; 4 minutes = 1,920 frames.
