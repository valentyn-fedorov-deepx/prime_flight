# Tracker

The tracker follows the objects the General Model found from one frame (one picture of the video; the cameras take 8
per second) to the next, in one camera's recording of a turnaround. It gives each aircraft, belt loader, service vehicle
(ground support equipment: tugs, belt loaders, fuel trucks, tractors) and person a number that stays the same while the
object is in view; an object followed like this is a track. For the aircraft and the vehicles it says whether they are
moving, stopping or stopped, marks when the aircraft arrived and started to leave, and tells which belt loader stands at
which cargo door. Checks read these answers to reach their verdict (Pass, Fail or Not observed).

## Status

| | |
|---|---|
| In production | The version of February 2026, with a matching shared-library version whose exact revision is to confirm (Maksym Chernyshev) |
| Last change | February 2026: new outline models for the aircraft and vehicles; the picture-noise check every 2 seconds instead of every frame |
| Next step | A version with byte-for-byte the same tracks and debug video in about half the time; waiting for its cluster test (Maksym Chernyshev) |
| Who looks after it | Yurii Luchko and Valentyn |

## What it does

It runs as one job per camera recording, after the General Model and before the checks. It reads the General Model's
boxes (where objects are) and the video pictures (how they move). It follows:

- **the aircraft**: one object for the whole recording, always number 1, fed by the General Model's box of our aircraft;
- **belt loaders, service vehicles and people**, with three trackers. Each predicts where an object will be and matches
  it to the new boxes by position and overlap; for people also by how they look (a re-identification network).

Pushback tractors, trailers, cones and other vehicles are not followed, so the tracker cannot tell when the pushback
tractor is attached. Nothing is restarted within a recording and no object is deleted: one run covers the whole
turnaround. Run piece by piece, it would restart every object and counter.

## What it finds

**Identity.** Numbers are counted per kind, so a person and a belt loader can share one. A lost belt loader or service
vehicle that comes back keeps its object number: a new belt loader track covering more than 30 % of the largest box an
old one had in its last 10 seconds takes over that object; a new service vehicle overlapping a known one by more than
25 % does the same. A track counts after 1 second for vehicles (0.75 seconds for people) and is kept 20 seconds after it
is lost (12.5 seconds for people). People get a number and a box only.

**Motion state** of the aircraft, belt loaders and service vehicles. The tracker picks up to 250 corner points inside the
object's outline (drawn by a segmentation model) and follows them from frame to frame. A frame is "still" when more than
half of the points moved less than a tolerance of 0.002 × box height ÷ the object's real height (7 metres for the
aircraft, 3 for a belt loader, 2 for a service vehicle), with a minimum of 0.1 pixel. New points are picked every 2
seconds for the aircraft, 1.25 seconds for belt loaders, 0.6 seconds for service vehicles.

| State | Meaning | Rule |
|---|---|---|
| moving | drives | 9 moving frames in a row (about 1.1 seconds) while stopping, or 17 (about 2.1 seconds) after a stop |
| stopping | has just come to rest | from the first still frame |
| stopped | stands | on the 24th still frame (3 seconds) |
| proceeding | starts again after a stop | after 6 moving frames (0.75 seconds) |
| unobserved | a belt loader hidden by another vehicle | a service vehicle or trailer box (plus 10 %) covers more than 80 % of a stopped belt loader that is between 10 % and 90 % of the picture width and at least 30 pixels tall; its box freezes |

A new stop counts when it lies more than 5 % of the box width from the previous one; the count restarts when the object
drives off. Frames where the box area jumps by more than 1.5 times are skipped.

**Arrival and departure of the aircraft**

- *Arrival*: "stopped" for more than 32 frames in a row (4 seconds) with a box taller than 95 % of its usual height (from
  the General Model). The arrival is then set back to the first frame of that stop. As the aircraft first needs 3 seconds
  to count as stopped, the arrival is known about 7 seconds after it comes to rest.
- *Footage before the arrival*: yes when the arrival is confirmed 60 seconds or more into the recording.
- *Approach seen*: yes when, before arriving, the aircraft moved smoothly (no jump over 50 pixels sideways or 5 pixels up
  or down per frame) for more than 3 seconds in a row.
- *Departure*: after the arrival a counter rises by 1 on every moving frame (up to 80) and falls by 10 on any other
  frame; the departure is set when it first reaches 80 (10 seconds), at the earliest about 12 seconds after the aircraft
  starts to move.

**Belt loaders at the doors.** While a belt loader is stopped and visible, it is "front" when it overlaps the largest
front cargo door box and reaches more than 60 % across it, "back" when it overlaps the rear door box. With no door
detected, staying where it was labelled (overlap above 80 %) counts. The label needs 1 second in a row and is cleared when
the belt loader moves; otherwise it is "undefined".

**Output.** One line per frame, numbered by position from 1: the aircraft, belt loaders, people, service vehicles. Each
entry holds the track number, the box (the General Model's box for the aircraft, a smoothed estimate for the rest), the
kind, a score that is always 0, the full internal state (39 fields for the aircraft, 34 for vehicles) and the door label.
A recording gives 0.6–1.2 gigabytes before compression, mostly lists of motion points.

**The debug video.** On by default: every frame with the boxes, outlines and motion points drawn on it. It changes
nothing in the tracks but takes about 40 % of the tracker's time. People watch it, so it stays (decided 27 October 2026);
the work is to draw it faster. The largest cost was the outlines (38 % of the time): each object created a full-size
colour picture and processed the whole frame three times, though its outline covers a small part of it.

## How it works, step by step

1. Load the recording and its General Model file (the newest, or a chosen version).
2. Pair each frame with the next line of that file, by position.
3. Hand belt loader boxes (except nearly square ones), service vehicle and person boxes to their three trackers.
4. Every 2 seconds measure the picture noise; above 0.5, smooth the frames on the graphics card.
5. Create the aircraft at its first box and update it on every frame that has one.
6. Belt loaders: a hidden one becomes "unobserved"; otherwise update its motion and, while stopped, run the door rule. A
   new track first tries to take over an old belt loader.
7. Re-match or create service vehicles and update them the same way; give people a number and a box.
8. For each vehicle: renew the points when due, follow them, drop those moving unlike the rest, update the state.
9. Write each frame 5 frames late. While the aircraft is in a stop that is not yet an arrival, hold the frames; once the
   arrival is confirmed, write its moment into all of them.
10. At the end write the rest, report "processed" (or "error"), compress and upload the file.

## How fast it is and what it costs

- One job per recording in Google's cloud: one NVIDIA T4 graphics card, 3.3 processor cores, 8 gigabytes of memory. The
  median recording (87 minutes) takes about 1.3 hours, about 112 milliseconds per frame (September 2026): about 19 % of
  the computing time of a video. Real time allows 125 milliseconds per frame, so production is close to the limit.
- **The new version** (October 2026) draws each outline only inside its box, writes the video in the background, updates
  the three trackers at the same time, computes only the part of the noise estimate it uses, makes no frame copies and
  prints per-frame logs only on request. Production against it, on a quiet test machine:

| Run | Tracks and debug video | Milliseconds per frame |
|---|---|---|
| Full 36-minute turnaround (17,280 frames) | identical byte for byte | 70.7 → 33.2 (−53 %); 20.4 → 9.6 minutes |
| Busy 2.5-minute stretch, two rounds each | identical in all four runs | 83.0 → 42.5 (−49 %) |

- About three quarters of the saving is less work, so it should carry over to the 3.3-core job. Estimate for production,
  to confirm on the cluster: the tracker job about 1.3 → 0.65 hours per median recording, the computing part of time to
  result about 4.2 → 3.5 hours, about 9 % off the processing bill.
- In the real-time worker the tracker needs about 2 processor cores to keep up (estimate from test-machine measurements).

## How good it is

- How often identities swap or stops are missed has not been measured against hand-labelled turnarounds: not known yet
  (to confirm with Yurii Luchko).
- Two production runs on the busy stretch: same identities and states; 6 of 3,186 object-frames differ in counters.
- The February 2026 outline change kept the same 4 identities there, but the motion state differs on 2.8 % of
  object-frames: the new outlines move the start and end of stops.
- The project's frame-by-frame version, with fixed random numbers, gives output byte-identical to production; the
  arrival and belt loader moments taken from it match production on one full recording.

## Which checks depend on it

- 25 checks read the aircraft track, 14 people, 11 belt loaders, 3 service vehicles.
- Moving or stopped state: 18 checks; arrival moment: 11; departure moment: 6; footage before arrival: 1.
- Nine checks redo the arrival-stage rules (a stage is a part of the turnaround) from the motion points: aircraft
  wheel chocks, cargo doors, chocks and cones before arrival, crew present before arrival, foreign object debris walk,
  lead marshaller and wing walkers, safety huddle, safety zone, steering bypass pin.
- Door labels: belt loader forward chock, belt loader rear cone, handrails on service vehicles, safety handrails,
  aircraft wheel chocks.
- Motorized service vehicles parked and chocked reads four internal counters of service vehicles.
- Checks load the whole internal state back, and newer shared-library versions refuse unknown fields: every field must
  stay, and adding one breaks them.

## Known problems

1. **No version mark** in the file; a new field breaks checks.
2. **Internal fields in use**: nine checks need the motion points, which make the file 14–22 times larger than the
   General Model's.
3. **Arrival written back in time**: known about 7 seconds after the stop begins, with output held meanwhile (about 6
   minutes in one sample where the aircraft stayed "stopping"); about 60 frames get a stray copy of the arrival field. The
   General Model's own stop moment differs by about 7 seconds: two owners of one moment.
4. **The aircraft only where the General Model drew it**: when that box disappears the track ends; in 4 of 7 sample
   recordings no departure was found.
5. **Camera type ignored**: production never tells the tracker the camera, so wing recordings get the cone-camera door
   rules ("back" never appeared in 7 samples) and the wing rule (a belt loader below a main wheel, at the engine) never
   runs.
6. **Two meanings of "belt loader at the door"**: door boxes here; overlap with the aircraft box above 20 % in the
   three-stop brake check.
7. **Stale objects**: a vehicle parking hours later where an old one stood can inherit its number, stop count and door
   counters.
8. **Shared outline memory**: belt loaders and service vehicles share one stored outline result per frame. A service
   vehicle renewing its points on the same frame as a belt loader gets the wrong result, no points, and a frozen state
   until its next renewal.
9. **Not repeatable**: points, and their colours in the debug video, are picked at random without a fixed starting value;
   the vehicle look-matching network runs in training mode, so an object's look depends on the others in the frame. Two
   runs differ slightly; the debug video always differs.
10. **Frame numbers by position**: a lost frame shifts all later ones. If a recording ends while the aircraft is stopping
    before its arrival, the last frames can land under wrong numbers (whether this happened in production: to confirm).
11. **Small things**: it cannot work from boxes alone; "processed" is reported before the upload (effect to confirm);
    three door settings are never read; the aircraft, door and obstacle thresholds are fixed in the code.

## What changes next

1. **Cluster test of the new version** (Maksym Chernyshev): production plus an option to fix the random numbers, against
   the new version, both with the same fixed numbers on the five recordings of the General Model test. Expected:
   identical tracks and debug video in about half the time.
2. **Exact savings in the shared library** (a separate change): the grey picture once per frame instead of twice per
   object, a faster in-box test, outlines drawn on their box.
3. **Not planned**: fixing the random numbers by default, which would change the points production picks.
4. **Real time**: the frame-by-frame version with switches that trade exactness for speed, each after a verdict check.
   The real-time worker copies the aircraft track from the stage detector and follows only people, belt loaders and
   service vehicles.
5. **Events for the stage detector**: arrival, departure, belt loader at the door, belt loader left. Once checks take the
   arrival from it, the real-time record can drop the motion points and become about 10.8 times lighter.

## For developers

- `dxgat/utils/cv_trackers`: production `optimization` @ `bd43c3c` (2026-02-28), `cv_common` from `tracker_optimization`
  (≈ `2759daf`); default `master` @ `b5d350c`.
- Entry `db_worker/model_starter.py --model trackers` → `tracker.detect()`; `cone_camera` never passed
  (`tracker.py:66`, `model_starter.py:166`). Door rule `local_utils/bl_utils.py`; state machine
  `cv_common/tracked_object.py`; arrival and departure `cv_common/transport.py`; DeepSORT `deep_sort_pytorch/`.
- Weights: `yolo11s-seg_plane.pt`, `yolo26s_seg_bl_gse_tr10_noalb.pt`, `scripted_ckpt.t7`, `mobile_sam.pt` (unused).
- Keys `stopping_time_thres` 24, `moving_time_thres` 8, `proceeding_time_thres` 16, `init_dots_lifetime` 16/10/5,
  `gse_iou_reinit_thresh` 0.25, `estimate_sigma_interval` 2; unread `bl_rel_inter_thresh`, `door_offset`,
  `min_iou_bl_type`.
- Output `gs://cv-modules-topics/<video>/trackers<commit>.ndjson`.
- New version: local branch `pf/q4-02-tracker-exact-speedups` (`7e1b867` `TRACKER_SEED`, `f1add44`); patches
  `tasks/patches/cv_trackers/`; proof `scripts/tracker_exact_ab.py`. Sources `docs/models/trackers.md`,
  `docs/analysis/tracker_current.md`, `tasks/notes/PF-Q4-02*.md`.
