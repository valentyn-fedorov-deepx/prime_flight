# All cargo bin doors opened and verified

> After the aircraft stops, the crew opens the cargo doors and a belt loader (the conveyor vehicle that carries bags up
> to the hold) drives up to each door. This check makes sure that the cargo door a camera can see was open for at least
> a minute and that a belt loader stood at it for at least 10 seconds. It counts the pictures in which the General Model
> sees the open door and follows the belt loaders with the tracker.

## Status

| | |
|---|---|
| How accurate it is | 68 of 68 turnarounds correct (100 %) on the monthly test |
| Fail turnarounds it caught | 4 of 4 |
| In production | the version of April 2026 |
| Who looks after it | to assign |
| Biggest open problem | A blocked view gives Fail instead of Not observed, because the obstacle check never runs. |

## What the client wants

*All cargo bin doors opened and verified*

| Verdict | When |
|---|---|
| Pass | The open door is seen in at least 480 frames (60 seconds) — the front door on the cone camera, the back door on the wing camera — and a belt loader came to that door and stayed near it for at least 10 seconds. |
| Fail | The door is not seen open long enough, or no belt loader came to it, and nothing blocked the view. |
| Not observed | The video has no arrival stage (it does not show the aircraft arriving), or the Pass condition was not met and something stood in front of the camera for 60 seconds between the aircraft's stop and its departure. |
| Not observed, view blocked | No separate rule: a blocked view is part of Not observed above. |

A verdict is the answer of a check: Pass, Fail or Not observed. A frame is one picture of the video; the cameras take 8
per second.

## When and where it looks

Unloading (a stage is a part of the turnaround): from the moment the tracker reports the aircraft as arrived (standing
still for more than 4 seconds) until the departure (moving for 10 seconds), or until 10 seconds after both Pass
conditions are confirmed. For aircraft both cameras run it: the cone camera (looks towards the aircraft nose) checks the
front cargo door, the wing camera (looks along the wing) the back cargo door. For jets, only the wing camera.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object): the front cargo door
  on the cone camera or the back cargo door on the wing camera; on the cone camera also the aircraft's rear wheels.
- **From the tracker** (a track is the same object followed from frame to frame): the aircraft — stopped, arrived,
  departed — and the belt loaders, with the tracker's label of the door each one serves (front or back) and whether it
  is moving or stopped.
- **From the video itself:** nothing; it works only from boxes and tracks.
- **Its own models:** none. It runs on an ordinary processor.

## How it decides, step by step

1. **Main aircraft.** In every frame it follows the widest aircraft track.
2. **Was the arrival filmed?** When the aircraft stops, or after 5 minutes of following it, the module compares the
   typical aircraft box of the first 3 seconds with that of the last 8 seconds. Growth of 18 % or less (the aircraft did
   not come closer), or less than 11 seconds of following, gives Not observed, "No arrival stage". An aircraft already in
   view in the first 11.25 seconds of the video gives Not observed, "No pre-arrival stage". An aircraft missing for 10
   seconds is forgotten; another one takes over only if its box is bigger.
3. **Window.** Frames before the arrival are skipped; reading stops at the departure.
4. **Door.** It counts the frames in which the General Model sees the door (with several boxes, the most confident one).
   More than 480 frames (60 seconds) in total, not necessarily in a row, confirm the door.
5. **Which belt loader.** The belt loaders the tracker labelled for this door (front on the cone camera, back on the wing
   camera); on the cone camera one that touches a rear wheel and stands behind it is dropped. If none is left: a belt
   loader that spans the door (give or take 30 % of its own width) with more than 20 % of its box inside the aircraft
   box. The biggest wins. A new track number within 10 seconds keeps the old counters; a belt loader seen for less than
   10 seconds is forgotten after 2 seconds gone.
6. **Approach.** Each frame in which that belt loader is stopping or stopped and its box covers more than 5 % of the door
   box adds to a counter. More than 80 frames (10 seconds) in total: a belt loader approached the door.
7. **Early end.** 10 seconds after both conditions are confirmed, the module stops reading.
8. **Verdict**, in this order: Pass if both conditions hold; Not observed "No arrival stage"; Not observed "No
   pre-arrival stage"; the obstacle case (it never fires); Fail if an aircraft was seen; otherwise Not observed, "No
   plane was observed".

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Open-door time | 480 frames (60 seconds) | Door frames needed; also the length of the obstacle case, which is off |
| Belt loader at the door | 80 frames (10 seconds) | Stopped frames in which it must cover the door |
| Door cover | more than 5 % of the door box | Fixed in the code |
| New track number, same belt loader | within 80 frames (10 seconds) | The counters carry over |
| Short-lived belt loader | seen less than 10 seconds, gone 2 seconds | Its record is dropped |
| Obstacle size and timing | 35 % of the picture; 2 and 10 seconds | Not used: the obstacle check is off |
| Arrival filmed | growth over 18 %, first 3 seconds against last 8, decided within 5 minutes | Shared arrival check |
| Pre-arrival filmed | aircraft first seen after 11.25 seconds (90 frames) | Shared arrival check; described as 90 seconds |

## What it reports

- **Sentence.** Pass: "There are open front cargo doors on video for 480 frames and a beltloader N approached them.
  (start - end)", with "back" on the wing camera. Fail: which condition failed (the door, the belt loader or both), the
  number of frames with the door open and the time span. Not observed: "No arrival stage", "No pre-arrival stage" or
  "No plane was observed".
- **Timeline entry:** Pass — from the first open-door frame to the end of the evidence; Fail — from the stop to the
  departure or the last frame read; Not observed — none.
- **Files:** a drawing file for every frame; an annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on all 68 and caught all 4 labelled Fail. With only 4 Fail labels, the 100 % cannot show how
well it catches violations in general.

## Known problems

- **The obstacle case never fires.** The code calls the obstacle search in a way that switches it off; the rule gives
  Not observed when the Pass condition is not met and something stood in front of the camera for 60 seconds. So a
  blocked view gives Fail. This came with a rewrite in June 2025; the older default line still has a working check.
- **An extra Not observed case.** "No pre-arrival stage" is not in the client's rule. The shared arrival check is
  described as waiting 90 seconds but waits 90 frames (11.25 seconds): the value is not multiplied by the frame rate.
  Intended value: to confirm.
- **"Open" means "seen".** The module trusts the General Model's door box; it does not check that the door is
  mechanically open.
- **Aircraft seen but never stopped.** No frame is checked and the verdict is Fail, unless the arrival check said "No
  arrival stage". Whether this is intended: to confirm.
- **One door per camera.** "All doors" come only from merging the two cameras' verdicts (Fail on either gives Fail).
- **The Pass sentence always says "480 frames"**, whatever the real count.
- **An outdated note.** The architecture review's "no belt loader check" describes an older version.
- **Wing-camera door label (to confirm):** production may not tell the tracker the camera (no back-door label in 7
  sample videos); the wing camera would then rely on step 5's fallback. The tracker's owner can confirm.

## In real time

It can run as it is: one pass over the boxes and tracks, no pictures. Pass is known as soon as both conditions hold,
Fail only at the departure. It needs the arrival moment from the stage detector (the part that knows where in the
turnaround we are); until then it still reads the tracker's internal motion fields.

On a 36-minute test turnaround in the real-time test setup it gave the same verdict (Pass) and sentence as
post-processing, 164 seconds after the stop; fed only the boxes and tracks it reads, it matched on all 77 test runs.
Own work: about 0.9 milliseconds per frame; with the shared General Model and tracker parts, 32.9 of the 125
milliseconds each frame may take (26 %), on a faster graphics card than production's. As a post-processing job: about
8 seconds.

In live runs where another aircraft in view was taken for the arriving one, its verdict changed on 5 turnarounds, mostly
to Not observed: a problem of the shared live feed, for the stage detector to solve. The client's split puts this check
in the post-processing group.

## For developers

- **Repository:** `dxgat/detectors/all-cargo-bin-doors-opened-and-verified`; production `bl_approach` @ `3422bdc`
  (2026-04-14); default `master` @ `c60aed2` (2025-06-19: no belt loader approach, no arrival checks, working obstacle
  check). Workspace module code: M03.
- **Entry point:** `main.py` → `detect(...)`; logic in `main.py` (`make_inference`, `Beltloader`, `find_beltloader`,
  `manage_beltloader`, `manage_old_beltloaders`, `handle_obstacles`, `handle_plane_anomaly`); `PlaneArrivalDetector`
  in `cv_common/modules/plane_arrival_detector.py`.
- **Dependencies:** `cv_common` @ `dd5b554`, `db_worker` @ `6efc0b0` (exported copy); the pin lacks `cv_common/modules`,
  which the export adds from its `modules` branch (production build: to confirm). No weights; CPU.
- **Run on one turnaround:** `python main.py --source <video.mp4> --inferences-dir <GM and tracker ndjson folder>
  [--cone-camera] [--write-video] [--json-fn <name>]`; settings `local_config.yaml` over `cv_common/global_config.yaml`;
  production: `db_worker/model_starter.py` imports `detect`.
- **Settings keys** (table order): `min_opened_doors_frames`, `min_frames_near_doors`, door cover 0.05 at `main.py:94`,
  `min_bl_swap_time_thresh`, `min_bl_init_frames_thresh` + `bl_init_check_delay`, `obstacle_min_area_ratio` +
  `max_no_obstacle_frames` + `arrival_confirmation_offset`; arrival defaults at `plane_arrival_detector.py:61-77`
  (`prearrival_min_frames` 90 is not multiplied by fps, line 77).
- **Code places:** step 1 `main.py:286-338`; 2 `main.py:375, 407-411`, `plane_arrival_detector.py:85-149, 196-229`;
  3 `main.py:436-447`; 4 `main.py:452-464`; 5 `main.py:116-140, 143-174`; 6 `main.py:91-102, 503-517`; 7
  `main.py:426-434`; 8 `main.py:21-64`; obstacle path `main.py:184-220, 241-283`, off because of `camera_config=None`
  (`main.py:420-421`; flag only at `main.py:214`).
