# Cones removed only after all service vehicles are clear of the aircraft and chocked

> Cones at the wings, engines and tail protect the aircraft while service vehicles (ground support equipment: tugs, belt
> loaders, fuel trucks, tractors) work next to it. This check makes sure the cones are taken away only after those
> vehicles have left. In practice the module compares the last moment it saw cones with the last moment it saw a belt
> loader at the aircraft, using only the General Model's boxes and the tracker.

## Status

| | |
|---|---|
| How accurate it is | 54 of 67 turnarounds correct (81 %) on the monthly test |
| Fail turnarounds it caught | 5 of 11 |
| In production | the version of November 2025 |
| Who looks after it | to assign |
| Biggest open problem | It never checks chocks, counts only belt loaders as service vehicles, and gives Pass when cones are still visible at departure. |

## What the client wants

*Cones are removed only after all GSE is clear of A/C and chocked* (GSE: the service vehicles; A/C: the aircraft)

| Verdict | When |
|---|---|
| Pass | Cones were removed, the vehicles were far enough from the aircraft and did not come near it after that. |
| Fail | Cones were removed, but a vehicle was too close to the aircraft or came near it after the removal. |
| Not observed | Cones were detected on fewer than 200 frames (25 seconds). |
| Not observed, view blocked | More than 65 % of the frames of the whole turnaround are blocked. |

A verdict is the answer of a check: Pass, Fail or Not observed; a frame is one picture of the video (8 per second).
The name also asks for chocked vehicles; the client's Pass and Fail conditions do not mention chocks.

## When and where it looks

The check belongs to the stage before departure (a stage is a part of the turnaround). The module reads the whole video
up to the tracker's departure moment (set after about 10 seconds of movement) and compares the last cone sighting with
the last time a belt loader was at the aircraft. It uses the cone camera (which looks towards the aircraft nose) for
aircraft and the wing camera (which looks along the wing) for jets, as the client split them. On the cone camera, a
tail cone must overlap the aircraft, and a belt loader right behind a rear wheel counts.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object on a frame): engine,
  wing and tail cones (the general "cone" class is not used), the front door, the rear wheels and "vehicle" boxes.
  Service vehicles, pushback tugs, trailers, belt loaders and fuel trucks serve only the hidden-cone test.
- **From the tracker:** the aircraft track (the aircraft followed from frame to frame) with the tracker's arrival and
  departure moments, and the belt loader tracks.
- **From the video itself:** nothing; pictures are read only to draw an annotated video.
- **Own models:** none (a cone model file is stored but never loaded). It runs on an ordinary processor.

## How it decides, step by step

1. **Aircraft.** On frames where the General Model found anything, the widest aircraft track is the aircraft. "Arrived"
   and "departed" are set on the exact frames the tracker gives for its arrival and departure moments.
2. **Cones.** Engine, wing and tail cones count (cone camera: a tail cone must overlap the aircraft box). A sighting
   needs cones on 8 frames in a row (1 second); the last frame of such a run becomes the *last cone moment*. Cones are
   counted over the whole video, also before arrival.
3. **Front door.** Between arrival and departure the module keeps the widest front door box and forgets it after about
   5 seconds without one.
4. **Belt loader at the aircraft.** The *last belt loader moment* is updated when a belt loader track lies more than
   70 % inside the aircraft box with its centre less than 500 pixels from the front door's centre; or (cone camera
   only) a belt loader track overlaps a rear-wheel box and stands right behind it; or a "vehicle" box stands right
   behind a rear wheel for 8 frames in a row (1 second), taken as the belt loader at the rear door. "Right behind" means
   overlapping the wheel box with the bottom edge higher in the picture than the wheel's, by less than 40 % of the
   wheel's height.
5. **Hidden cones.** On frames with a service vehicle, pushback tug, trailer, belt loader or fuel truck, the module
   compares those boxes with the cone boxes remembered from the last 16 frames without such vehicles (plus cones seen
   next to them). A vehicle box and a cone box that nearly coincide (shared area above 70 % of their combined area) mark
   the frame "cones hidden by a vehicle". Repeated cone boxes (above 90 %) should be skipped, but a coding mistake ends
   the whole test at the first repeat.
6. **End.** Reading stops at the departure frame.
7. **Verdict.** No 1-second cone run at all: **Not observed**. No departure: **Not observed**. Last cone moment at or
   after the last belt loader moment: **Pass**, also when no belt loader was ever seen at the aircraft. Otherwise, cones
   hidden by a vehicle after the last cone moment: **Not observed** (view blocked); else **Fail**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Cone run | 8 frames (1 second) in a row | What counts as a sighting |
| Door memory | about 5 seconds | Belt loader at the door |
| Belt loader at the door | over 70 % inside the aircraft, under 500 pixels from the door | Last belt loader moment |
| Rear vehicle | 8 frames (1 second) in a row | Last belt loader moment |
| "Right behind" margin | 40 % of the wheel height | Rear belt loaders |
| Hidden cone | shared area above 70 %; repeats above 90 %; last 16 vehicle-free frames | Not observed instead of Fail |
| Timeline width | 5 seconds either side | Reported time span |

Only the "right behind" margin comes from the settings file; the rest is fixed in the code. Six values in the settings
file are not used.

## What it reports

- **Sentence.** Pass: "Cones were removed after all GSE are backed off airplane. Time: <time> -- <time>" (5 seconds
  either side of the last cone moment). Fail: "Cones were removed before all GSE are backed off aircraft. Time: <time>
  -- <time>" (around the last belt loader moment). GSE means the service vehicles. Not observed: "There are no detected
  cones", "There is no departure stage. The GSE can still drive up to the airplane" or "There was an obstacle".
- **Timeline entry:** a Pass or Fail block over the same 10 seconds; none for Not observed.
- **Files:** per-frame drawings (aircraft, cones, belt loaders, rear vehicles, and status lines such as "Cones are placed
  and visible", "Cones are removed or out of view", "Transport overlap placed cones"); an annotated video if switched
  on.

## How accurate it is

The monthly test (the client's validated turnarounds we measure on) has 69 turnarounds; 67 were labelled for this check
and the module matched 54 (81 %). Of the 11 labelled Fail it caught 5: 6 of its 13 errors are missed violations, the
other 7 are turnarounds labelled Pass or Not observed where it said something else. Which of the problems below cause
the misses is to confirm on the labelled turnarounds.

## Known problems

- **Chocks are never checked.** The client's name says the vehicles must be chocked; an unchocked vehicle cannot make
  this check fail.
- **Only belt loaders count.** "All service vehicles" means belt loaders at the front door or behind a rear wheel; tugs,
  trailers and fuel trucks only feed the hidden-cone test. A fuel truck still at the aircraft when the cones go does not
  give Fail.
- **Removal is not checked.** Cones visible until the departure give Pass, although the client's Pass starts with
  "cones were removed".
- **Cones before arrival count.** Sightings before the aircraft arrives can set the last cone moment.
- **The client's limits are missing.** The 200-frame rule and the 65 % blocked rule are not in the code: a short cone
  sighting can still give Pass or Fail, and a mostly blocked view does not give Not observed by itself.
- **The hidden-cone test rarely fires (to confirm on data).** It needs a vehicle box and a cone box of almost the same
  size and place, which a large vehicle in front of a small cone is not. With the repeat mistake, hidden cones can end
  as Fail instead of Not observed.
- **Exact-frame moments.** Arrival and departure need the aircraft track on exactly the tracker's frame; if it is
  missing there, the departure is never seen and the verdict is Not observed.
- **Wasted work.** A growing cone list is copied into unread tables on every frame.
- **Local runs.** Started alone, the module is not told the camera and acts as on the wing camera.

## In real time

The client puts this check in the "real-time" group: the result is wanted within seconds. It can run as it is: one pass
over the boxes and tracks, no pictures, deciding between the last belt loader leaving and the departure. Today it waits
for the departure; in principle a Fail could be raised the moment the cones disappear while a belt loader is still at
the aircraft. The ever-growing cone list should be removed first.

In the real-time test setup it gave the post-processing (after the turnaround) verdict and sentence at the tracker's
departure moment; on 67 test turnarounds the reduced real-time inputs changed nothing. Cost with the General Model and
the tracker: 38.4 of the 125 milliseconds a frame may take (31 %), mostly the tracker following belt loaders; own work
1.5 milliseconds alone, 3.1 with all checks; as a post-processing job, 20 seconds per turnaround. In live runs its
verdict became Not observed on 3 turnarounds where another aircraft was in view first: a problem of the shared live feed,
for the stage detector (the part that knows where in the turnaround we are) to solve.

## For developers

- **Module code:** M08. **Repository:** `dxgat/detectors/cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked`;
  production `main` @ `e2a25ba` (2025-11-28), the default branch.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera,
  json_logger)`; `Plane` (front-door memory), `validate_cone_detection`, `is_overlap_and_right_behind`. Logic diagram
  (Confluence, 2023-07-10): https://docs.google.com/spreadsheets/d/10FxC1-9XI4tb_qIIo-W-_ebJaPUrKdeCeXbHobfj92I/edit?gid=0
- **Run:** `python main.py --source <video>.mp4 [--write-video] [--json-fn <name>]` (reads `../inferences_dir` or the
  bucket; `__main__` does not pass `--cone-camera`); `run_module.py` passes each video's camera type.
- **Keys:** `rear_bl_position_margin` 0.4. In code: run 8 frames, door `5 * fps`, 0.7 and 500 px, IoU 0.7 / 0.9, 16
  frames, ±40 frames. Unused: `obstacle_width`, `obstacle_center_range`, `beltloader_in_thres`, `beltloader_out_thres`,
  `stop_capture_window`, `cone_register_delay`.
- **Code places:** aircraft `main.py:127-155`; cones `:50-56, 158-208`; front door `:21-47, 210-212`; belt loader
  `:58-62, 214-246`; hidden cones `:274-309` (`break` `:298`, unused arrays `:283-286`); stop `:335-336`; verdict
  `:338-378`.
- **Dependencies:** `cv_common` 33c188d (local folder: ac5098d), `db_worker` 5a4aa83; opencv, numpy; torch 1.10 listed
  but no model used; `weights/cones_v1.pt` in DVC, never loaded; CPU image.
