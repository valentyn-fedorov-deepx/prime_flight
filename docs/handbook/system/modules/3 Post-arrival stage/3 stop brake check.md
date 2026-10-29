# 3 stop brake check

*In plain words: three-stop brake check.*

> A belt loader (the vehicle with a conveyor belt that serves a cargo door) must test its brakes on the way to the
> aircraft: three stops, then the fourth, final stop at the cargo door. The check makes sure every belt loader does this.
> The tracker counts each loader's stops, and the module judges each loader when it parks next to the aircraft.

## Status

| | |
|---|---|
| How accurate it is | 54 of 68 turnarounds correct (79 %) on the monthly test |
| Fail turnarounds it caught | 39 of 43 |
| In production | the version of May 2026 (the decision logic last changed in February 2025) |
| Who looks after it | to assign |
| Biggest open problem | The tracker resets a loader's stop count after any stop of 3 seconds or more, so a long brake-check stop wipes the earlier ones, and reversing, which the client names as the reason for a reset, is never checked. |

## What the client wants

The client calls this check *3 stop brake check*.

| Verdict | When |
|---|---|
| Pass | Every loader that stopped at the aircraft made 3 stops before the final (fourth) stop. |
| Fail | At least one of the loaders that stopped made fewer than 3 stops. |
| Not observed | No loader stops were detected. |
| Not observed, view blocked | None: the client's rule has no blocked-view case. |

The client adds: if a loader moves in reverse, its stop count starts again. A verdict is the answer of a check: Pass,
Fail or Not observed. The client puts the check in its streaming group, between the real-time group (checks wanted while
the turnaround happens) and the post-processing group (checks judged after it), and marks it as not ready for
production. Its list also has a combined check, *Proper beltloader approach including 3 stop brake check and
handsignals*, built from this check and *All GSE guided into aircraft using approved hand signals*; how the two
are combined is to confirm.

## When and where it looks

The stages (parts of the turnaround) are the time after the aircraft stops and the unloading. The module works from the
aircraft's arrival to its departure, as the tracker marks them (the arrival after about 4 seconds standing still, the
departure after about 10 seconds of movement), and judges each loader when it parks next to the aircraft.

Cameras: for aircraft both cameras, for jets the wing camera (the client's two aircraft types), with separate settings
per camera. The cone camera looks towards the aircraft nose, the wing camera along the wing. When both run, the client
merges the results: Fail on either camera gives Fail; Pass on one and Not observed on the other gives Pass. The
production settings file that lists the checks per camera names only the cone camera here (to confirm).

## What it looks at

- **From the General Model:** service vehicles (ground support equipment: tugs, belt loaders, fuel trucks, tractors),
  pushback tugs and trailers, only to spot a blocked view (a detection is a box the detector draws around an object).
- **From the tracker:** the aircraft (arrival, departure, its box) and the belt loaders (a track is the same object
  followed from frame to frame): moving or stopped, and the stop count the tracker keeps for each loader.
- **From the video itself:** nothing.
- **Own models:** none. It runs on ordinary processors.

## How it decides, step by step

A frame is one picture of the video; the cameras take 8 per second.

1. **Settings per camera.** The module picks the cone camera or wing camera settings from the camera type the production
   system gives it.
2. **Blocked frames are skipped.** A service vehicle, pushback tug or trailer box wider than 50 % of the picture (cone
   camera) or 30 % (wing camera), with its centre in the middle band (cone camera: from 30 % to 100 % of the width; wing
   camera: from 10 % to 90 %), makes the module ignore the whole frame.
3. **Start and end.** It waits for the tracker's arrival flag and stops at the tracker's departure flag.
4. **Counting stops.** It follows every belt loader track; the tracker counts the stops. A stop counts when most of the
   points the tracker follows on the loader stand still and the stop is more than 5 % of the loader's width away from the
   previous one. If the loader stands still for 3 seconds and then drives on for 2 seconds, the count goes back to zero.
5. **Parked.** A loader is parked when it has been "stopped" for 5 seconds in a row, is at least 250 × 80 pixels (cone
   camera) or 200 × 60 pixels (wing camera), has left the place where its tracking started (its box overlaps its first
   box by less than half: shared area divided by the area both cover), and its left edge lies between 10 % and 85 % of
   the picture's width.
6. **Judged at parking.** More than 3 stops (three brake checks plus the final stop): the loader passes; otherwise it
   fails.
7. **Counted only at the aircraft.** The result counts only if the loader moved for at least 0.5 seconds before parking
   and more than 20 % of its box overlaps the aircraft's box.
8. **Moving again.** A parked loader that moves again for 2 seconds loses its result and is judged again at its next
   parking.
9. **Verdict:** any counted loader failed: **Fail**; all passed: **Pass**; none counted: **Not observed**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Time "stopped" before a loader counts as parked | 5 seconds | When a loader is judged |
| Movement after parking that clears the result | 2 seconds | The loader is judged again |
| Movement needed before parking | 0.5 seconds (the settings file's comments say 1 to 1.5 seconds) | Fewer: the result does not count |
| Smallest loader | cone camera 250 × 80 pixels; wing camera 200 × 60 pixels | Smaller loaders are never judged |
| Allowed band for the loader's left edge | 10 % to 85 % of the width | Loaders outside are not judged |
| Width of a blocking box (service vehicle, pushback tug, trailer) | cone camera 50 % (its comment says 30 %); wing camera 30 % | Wider boxes skip the frame |
| Where a blocking box's centre must be | cone camera 30 % to 100 %; wing camera 10 % to 90 % of the width | Which boxes skip the frame |
| Pass threshold (in the code) | more than 3 stops | Three brake checks plus the final stop |
| Overlap with the aircraft (in the code) | more than 20 % of the loader's box | Only loaders parked at the aircraft count |
| Tracker: stop that resets the count | 3 seconds | A stop this long resets the count once the loader drives on |

## What it reports

- **Sentence:** for Pass, "Beltloader <id> performed 3-stop-brake-checks on <hh:mm:ss>." per loader; for Fail,
  "Beltloader <id> failed on <hh:mm:ss>." per failing loader; for Not observed, "No stopped beltloaders were detected".
- **Timeline entry** (the stretch of video the website marks): one per loader of the final verdict's kind, from the
  loader's first frame after the arrival to the decision moment; empty for Not observed.
- **Files:** a drawing file with boxes, states and texts; an annotated video only when video writing is switched on.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 68 of them labelled for
this check. The module gave the client's verdict on 54 (79 %). The client labelled 43 Fail and the module caught 39: 4
violations were missed, and the other 10 wrong verdicts were on turnarounds labelled Pass or Not observed. With 43 Fail
labels the test does show how well the check catches missing brake checks. Our sources do not say which turnarounds were
wrong, or why.

## Known problems

- **A long brake check wipes the earlier stops; reversing is never checked.** The client resets the count when a loader
  reverses. The tracker resets it whenever a loader drives on after standing still for 3 seconds, in any direction. A
  brake-check stop longer than 3 seconds therefore wipes the earlier stops, and a correct approach can get Fail (to
  confirm on labelled videos).
- **A blocked view gives Not observed.** Blocked frames are only skipped, so a loader hidden by a large vehicle ends as
  Not observed; the client's rule has no blocked-view case.
- **The count belongs to the shared tracker.** A tracker change can change this verdict; the architecture review asks
  for a comparison on recorded turnarounds before any switch to a general tracker status.
- **A timeline start in the wrong form.** A loader's first timeline start is written as a list with one number, not a
  number; whether the website reads it is to confirm.
- **Several aircraft.** With several aircraft tracks in one frame, the last one listed wins. Report times assume 8
  frames per second from the start of the file.
- **Cameras to confirm.** The production settings file lists the cone camera only; the client's sheet says both.
- **Out-of-date description.** The module's own description mentions "the biggest plane" and cone classes copied from
  another module; the code does neither.
- **Who confirms:** the long-stop reset is for the module's owner (to assign) to check on labelled turnarounds; the
  cameras in production and how the combined check is built, for Ihor, the technical lead; the timeline format, for the
  website team.

## In real time

It can run in real time as it is. A loader's stop count is final when it parks, so its verdict could be given at that
moment: feedback right after the approach, not a warning before it, because the loader may still stop again until it
parks. Today the module gives one verdict for the turnaround, at the departure. Like the other ready checks, it needs the
stage detector (the part that knows where in the turnaround we are) to switch it on and off for its stages.

On one 36-minute test turnaround it gave the same verdict and sentence live as post-processing (after the turnaround),
at the departure. Giving it only the boxes and tracks it reads, as the real-time branch does, changed nothing on the
monthly test (77 of 77 runs). Its own work is 0.64 milliseconds per frame (1.61 with all other checks running). With its
share of the General Model and the tracker, which here follows the aircraft and the belt loaders, it needs 38.3 of the
125 milliseconds each frame may take at 8 frames per second (31 %). As a post-processing job it takes 16 seconds.

Where another aircraft stood in view before the real one arrived, the live feed took it for the arriving one; on four
test turnarounds this turned the check's Fail into Not observed. This is a problem of the shared live feed, planned for
the stage detector, not of the module.

## For developers

- **Module code in our workspace:** M01.
- **Repository:** `dxgat/detectors/3-stop-brake-check`; production line `master` @ `14685f4` (2026-05-07; last logic
  change `05cfc12`, 2025-02-18); default branch the same. The architecture review pinned `3a2337c` on
  `not_observed_handling` (a reworked `main.py`), which is not in production.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera,
  json_logger)`; the `Loader` class (counters, parked test, pass/fail), the frame loop and `get_reports` are all in
  `main.py`; thresholds in `local_config.yaml`. Task name `stopbrake`.
- **Run on one turnaround:** `python main.py --source <video>.mp4 --inferences-dir <folder with GM and tracker ndjson>
  [--cone-camera] [--write-video] [--json-fn <file>]`; `run_module.py` runs a batch of test videos.
- **Settings keys:** `stop_thresh` 40; `moving_thresh` 16; `moving_before_stop_thresh` 4; `min_width` × `min_height`
  cone 250 × 80, wing 200 × 60; `bl_roi` [0.1, 0.85]; `obstacle_width` cone 0.5, wing 0.3; `obstacle_center_range`
  cone [0.3, 1.0], wing [0.1, 0.9]. In code: pass if stop count > 3; aircraft overlap > 0.2 of the loader box; moved
  from the first box: IoU < 0.5. Tracker: `stopping_time_thres` 24 frames; stop point > 5 % of the loader width from the
  previous one (`cv_common/tracked_object.py`).
- **Code places:** step 1 `main.py:226-227`; step 2 `:278-304`; step 3 `:311-355`; step 4 `:359-371`,
  `cv_common/tracked_object.py:51-53, 247-266, 274-277`; step 5 `main.py:76-94, 176-185`; step 6 `:106-120`; step 7
  `:187-190, 379-403`; step 8 `:97-102, 388-391`; step 9 `:193-221, 444-459`.
- **Dependencies:** `cv_common` 86731e4 (not in the local archive; local copy ac5098d, and the CI builds with cv_common
  master), `db_worker` 5a4aa83. norfair, opencv-python, numpy, torch (only `no_grad`). No weights; Docker image on the
  CPU base image. On the real-time test machine the gap between the test-set accuracy and the monthly CI output comes
  from the module builds there (substituted `cv_common` copies), this module above all (`docs/analysis/rt_module_cost.md`,
  section 6).
- **Real time and sources:** `docs/04_modules.md` (NOW: the stop counter is final at parking),
  `docs/analysis/rt_module_selection.md` (group A, 3.4 ms per recorded frame), `docs/analysis/rt_module_cost.md`
  (events `7PytHarRNqmT`, `beqQ5Q0FoFWP`, `jI6tTM7YdhNE`, `63xitGPpUtLy`); `docs/modules/3-stop-brake-check.md`,
  `docs/analysis/module_review_2026-10.md`.
