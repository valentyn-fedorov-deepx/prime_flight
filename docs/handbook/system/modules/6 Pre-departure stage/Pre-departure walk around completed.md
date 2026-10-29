# Pre-departure walk around completed

*In plain words: walk-around inspection before departure.*

> Before the aircraft leaves, a worker must walk around it to inspect it. The module turns each worker's movement in the
> last minutes before the departure into a path drawn on a picture of the aircraft seen from above, and a small image
> classifier decides whether that path is a walk-around.

## Status

| | |
|---|---|
| How accurate it is | 39 of 55 turnarounds correct (71 %) on the monthly test |
| Fail turnarounds it caught | 21 of 27 |
| In production | the version of July 2026 |
| Who looks after it | to assign |
| Biggest open problem | When no worker is seen it gives Fail instead of the client's Not observed, and its blocked-view rule is switched off. |

## What the client wants

*Pre-departure walk around completed*

| Verdict | When |
|---|---|
| Pass | The path model says "yes" for a worker's path around the aircraft (the path is cleaned and turned into a picture). |
| Fail | The model says "no" for every path seen. |
| Not observed | No workers are visible. |
| Not observed, view blocked | The view is blocked: blocked frames are more than 60 % of all frames. |

The client adds: the check covers the 5 minutes before the departure, but not before the last belt loader leaves. A
verdict is the answer of a check: Pass, Fail or Not observed; a frame is one picture of the video (8 per second).

## When and where it looks

The check belongs to the stage before departure (a stage is a part of the turnaround). The worker paths come from a
window that ends when the departure starts and begins 8 minutes earlier, but not earlier than about 30 seconds before
the last belt loader left. The verdict comes 30 seconds after the aircraft starts moving. It uses the cone camera (which
looks towards the aircraft nose), for aircraft only; the client does not run it for jets.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object on a frame): the
  aircraft's parts (nose, wings, engines, tail, wheels, doors); the pushback tug and other vehicles, for the
  blocked-view count and the tug test.
- **From the tracker:** the tracks (objects followed from frame to frame) of the aircraft, the people and the belt
  loaders.
- **From the video itself:** yes, every frame, for the pose model and the picture from above.
- **Own model:** a small image classifier, trained by us, scores a picture of one path from 0 to 1 for "this is a
  walk-around". **Ready-made models:** a pose model (finds a person's joints; used for distance), a depth model (how far
  each point of the picture is) and an outline model (cuts out the aircraft); the last two build the picture from
  above. These three need a graphics card; the classifier runs on the processor.

## How it decides, step by step

1. **Phases.** Its own sequence follows the turnaround: before arrival; arrival (an aircraft track at least 250 pixels
   tall, stopped or stopping); after arrival (60 seconds of continuous "stopped", or the tracker's arrival); belt loader
   work (a belt loader at an aircraft door for 5 seconds in a row); no belt loader (none for 10 seconds in a row; back
   after 5 seconds with one); departure.
2. **Departure.** After the 60-second stop, 8 seconds of movement start a departure; 30 seconds after the start the
   aircraft box must have shrunk by at least 18 %, or the departure is cancelled.
3. **Picture from above.** After arrival the module builds it once; if that fails, it draws a simple outline.
4. **Worker positions.** From "after arrival" to the departure, the pose model runs on every person on every frame.
   Distance comes from the person's height in pixels (taken as 1.75 metres, adjusted for the visible body parts);
   direction from the position across the picture (the camera sees 65 degrees).
5. **Checks at departure.** **Not observed** if the departure was never confirmed, the aircraft never reached "after
   arrival", or "after arrival" to the departure lasted less than 8 minutes. Otherwise the paths are cut to the window.
6. **Paths.** Points nearer than 5 metres (10 metres when the nose looks small) or farther than 55 metres are dropped; a
   track is split where it jumps more than 6.5 metres within 1.5 seconds; paths are smoothed; paths under 8 points are
   removed; pieces of one worker are joined across changes of track number.
7. **Classifier.** Each joined path is drawn on the picture from above and scored. Any score above 0.5: **Pass**;
   otherwise, also with no paths at all: **Fail**.
8. **Second chances on Fail** (they can only turn Fail into Pass). (a) Remove jumps over 5 metres and score again; above
   0.8: **Pass**. (b) Read the video again from 12 minutes before to 30 seconds after the departure at 2 frames per
   second, follow people with a separate pose model at a higher resolution, and give **Pass** when exactly one person
   sweeps across a wide part of the view (at least 0.8 radians, about 46 degrees, seen from the camera) over at least 30
   samples (about 15 seconds). Nobody doing so means nobody walked; two or more are taken as a working crowd.
9. **Tug check on Pass.** If the pushback tug hides the left wing in at least 75 % of the window's frames, or stands at
   the edge of the picture in at least 45 %, the Pass becomes **Not observed**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Worker window | 8 minutes (code default 7) | Window length; shortest stay accepted |
| Window limit at the belt loaders | 40 seconds before the "no belt loader" phase began | Window start |
| Belt loader present or absent | 5 or 10 seconds in a row | Belt loader phases |
| Departure | 60 seconds stopped, 8 seconds moving, checked after 30 seconds, box shrink 18 % | Departure moment |
| Pass score | 0.5 (code fallback 0.7) | Pass or Fail |
| Second scoring | on, above 0.8 | Fail to Pass |
| Re-reading | on; 0.8 radians, 30 samples, 12 minutes back, 2 frames per second | Fail to Pass |
| Track split | 6.5 metres within 1.5 seconds | Path pieces |
| Camera view | 65 degrees | Direction of workers |
| Tug test | wing hidden 75 %, at the edge 45 % | Pass to Not observed |
| Debug files | all on | Extra files |

Several settings-file values are unused; the distance uses constants in the code.

## What it reports

- **Sentence:** only "Returned status: <verdict>".
- **Timeline entry:** one block with the verdict from the start of the "before departure" phase to the departure start
  ("0" to "0" without a departure or after a short stay).
- **Files:** a technical report in the work folder (passing paths, the best path picture and its score, blocked frames,
  number of frames, which second chance changed the verdict) and debug files (path tables, path pictures, the picture
  from above). An annotated video only for belt loader frames, every 6th frame. The drawing file stays empty, as the phase
  sequence never writes to it (to confirm on a production output).

## How accurate it is

The monthly test (the client's validated turnarounds we measure on) has 69 turnarounds; 55 were labelled for this check
and the module matched 39 (71 %). Of the 27 labelled Fail it caught 21: 6 of its 16 errors are missed violations, the
other 10 are turnarounds labelled Pass or Not observed where it said something else. With 27 Fail labels, the test shows
it catches most missing walk-arounds. A note in the code says the lower Pass score and the two second chances
raised a 56-video monthly set from 39 to 46 correct (69.6 % to 82.1 %) in June 2026 without false Passes; which set
and version the monthly test used is to confirm.

## Known problems

- **No workers gives Fail.** The client's rule says Not observed.
- **Blocked-view rule switched off.** Blocked frames are counted, but the 60 % test is commented out; a blocked view
  never gives Not observed.
- **Window differs.** 8 minutes instead of 5; the re-reading looks back 12 minutes and ignores the belt loader limit.
- **Extra Not observed.** A stay under 8 minutes between "after arrival" and the departure gives Not observed (not in
  the client's rule). A departure confirmed while a belt loader is still at the aircraft shrinks the window to the last
  40 seconds, and the timeline entry then starts after it ends.
- **Rough positions.** Box height misleads when only the feet show; paths and the aircraft picture can be misaligned;
  joining fails when a worker is hidden behind the aircraft's rear or the tug (4 turnarounds in the team's notes); the
  classifier accepted a path that never reached the right side (2 turnarounds).
- **Test formula (to confirm).** A block marked as a test uses the cosine of 25 radians (about 0.99) in the distance.
  Pose runs on every person of every frame from the stop, since the window is applied only at the end (cost).
- **Stale results, a crash.** Earlier results in the work folder are reused instead of recomputed; two aircraft tracks
  taller than 250 pixels at once stop the module with an error.
- **Two producers (to confirm).** The default version of the post-arrival walk-around module also returns a verdict for
  this check; which one feeds production is unknown.
- **Build (to confirm).** The shared library version recorded with this code lacks a part the module imports (tests use a
  newer one); which one production runs is to confirm. There is no container recipe; its two
  machine-learning toolkits need separate software environments. Large unused files remain.

## In real time

The client puts this check in the "post" group (after the turnaround), and it stays there: the verdict judges the whole
window at the departure, and on Fail it re-reads up to 12.5 minutes of video. The
real-time branch does not host it (it runs in its own software environment). In post-processing tests it costs about 26
milliseconds per recorded frame (a rough figure from a busy machine).

## For developers

- **Module code:** M19. **Repository:** `dxgat/detectors/pre-departure-walk-around-completed`; production `tdv_cone` @
  `e407de2` (2026-07-27), 35 commits ahead of `main` @ `f2b6c36` (2025-06-19, older code).
- **Entry point:** `main.py` → `detect()` → `VideoProcessor` → `code/states.py` `Gate` →
  `code/walk_around/walk_around.py` `PostArrivalWalkAround` (add-ons `gs1737_addons.py`); top-down picture
  `code/walk_around/temp/plane_tdv_extractor.py`; belt loader presence `cv_common/modules/beltloader_presence_detector.py`.
  Logic diagram (Confluence): https://docs.google.com/spreadsheets/d/1mR-JCYcb5OCmSFqYyNG2NoiFXvgZROsrBPGk9CyrB9I/edit
- **Run:** `python main.py --source <video>.mp4 --inferences-dir <dir> --cache_folder ./data [--write-video]`, or
  `python single_run.py <video_id> <video_path>` (torch twin `keras_torch_shim.py`, validation only).
- **Keys:** `pre_departure.worker_window_sec` 480; `gs1737.cnn_threshold`, `outlier_second_pass`, `outlier_threshold`,
  `rescue_solo_track.*`; `post_arrival.trajectory_spatial_threshold`, `trajectory_temporal_threshold`; `camera.hfov`;
  `artifacts.*`. Unused: `post_arrival.max_*`, `min_walk_around_duration`, `max_blocked_frame`, `obstacle_*`,
  `seconds_between_parts`, `distance_estimation.*` (constants in `sources/config.py`).
- **Code places:** phases `code/states.py:597-620, 916-1006`; departure
  `cv_common/modules/plane_departure_detector.py:186-230`; positions `code/walk_around/detection_processor.py:34-49`,
  `distance_estimator.py:56-79`; final checks and window `states.py:778-819`; paths `walk_around.py:685-780`; CNN
  `:490-507`; add-ons `:515-558`; blocked rule commented out `:121-131`; tug `states.py:833-856`,
  `pushback_obstruction_detector.py:289-312, 519-573`.
- **Dependencies:** pins `cv_common` e4c5e36 (lacks `cv_common.modules`; CI uses master), `db_worker` 6efc0b0; torch
  2.2.0, ultralytics 8.2.48, tensorflow-cpu 2.15.1, mobile_sam; DVC 5 files, 903 MB (`best_acc.keras` CNN,
  YOLOv8m-pose, Depth Anything V2, MobileSAM). Unused: `sam_vit_b_01ec64.pth`, `code/walk_around_copy/`,
  `main_test_metric3d_surface.py`. No Dockerfile. Post-arrival module `main` @ 7112c99 also emits this verdict
  (`main.py:650-652`).
