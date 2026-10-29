# Beltloader rear cone positioned after BL is in place

*In plain words: belt loader rear cone placed after the belt loader is in place.*

> A belt loader is the vehicle with a conveyor belt that carries bags to and from a cargo door. Once it stands at the
> door, a cone must be placed behind it. The check makes sure every belt loader at a door gets its cone. The software
> takes each loader the tracker reports standing at a cargo door, looks for a cone at the loader's rear corner, and needs
> to see one there for more than 10 seconds in a row.

## Status

| | |
|---|---|
| How accurate it is | 62 of 68 turnarounds correct (91 %) on the monthly test |
| Fail turnarounds it caught | 12 of 14 |
| In production | the version of June 2025 (the decision logic last changed in May 2025) |
| Who looks after it | to assign |
| Biggest open problem | The cone must be seen for more than 10 seconds in a row, and one frame without it restarts the count, while the client asks for 100 frames (12.5 seconds) in total. |

## What the client wants

The client calls this check *Beltloader rear cone positioned after [the belt loader] is in place to alert clearance*.

| Verdict | When |
|---|---|
| Pass | The belt loader's rear cone is seen on at least 100 frames (12.5 seconds). |
| Fail | The rear cone is detected on fewer than 100 frames. |
| Not observed | No stopped belt loader is detected near the aircraft. |
| Not observed, view blocked | There were obstacles for 1 minute in total. |

A verdict is the answer of a check: Pass, Fail or Not observed. A frame is one picture of the video; the cameras take 8
per second. The rule does not say "in a row", so 100 frames read as a total. The client puts the check in its real-time
group (checks wanted while the turnaround happens) and marks it as not ready for production.

## When and where it looks

The stages (parts of the turnaround) are the time after the aircraft stops and the unloading. The module works from the
aircraft's arrival to its departure, both as the tracker marks them (the arrival after about 4 seconds standing still,
the departure after about 10 seconds of movement). Cones count only while a loader stands, stopping or stopped, at the
door.

Cameras: for aircraft both cameras, for jets the wing camera (the client's two aircraft types). The cone camera (looks
towards the aircraft nose) checks the loader at the front cargo door, the wing camera (looks along the wing) the loader
at the rear cargo door. When both run, the client merges the results: Fail on either camera gives Fail; Pass on one and
Not observed on the other gives Pass. The production settings file that lists the checks per camera names only the cone
camera here (to confirm).

## What it looks at

- **From the General Model:** cones of four kinds (general cones, belt loader cones, engine cones, wing cones); any of
  them counts as "the cone". The rear cargo door, rear wheels and the aircraft engine, to choose the loader. A detection
  is a box the detector draws around an object.
- **From the tracker:** the aircraft (arrival and departure) and the belt loaders (a track is the same object followed
  from frame to frame): moving or stopped, and the tracker's door label, "front" or "back" door.
- **From the video itself:** nothing.
- **Own models:** none. It runs on ordinary processors.

## How it decides, step by step

1. **Start and end.** The module waits for the tracker's arrival flag on the first aircraft track of the frame and stops
   at its departure flag.
2. **Choosing the door.** The cone camera looks only at loaders the tracker labels "front", the wing camera only at
   "back". The tracker gives the label once a loader has stood at that cargo door for 1 second and removes it when the
   loader drives off. On the cone camera, loaders standing behind a rear wheel are dropped. On the wing camera, if no
   "back" loader is there, it takes a loader hidden by the engine, or one standing face-on below the rear door (seen
   end-on, covering most of the door's width).
3. **One loader per frame:** the biggest of these.
4. **Same loader, new number.** A new track number that appears within 10 seconds of the last loader is treated as the
   same loader (the tracker sometimes loses an object and gives it a new number). Loaders seen for less than 10 seconds
   are forgotten once they have been gone for 2 seconds.
5. **Steady box.** The loader's box is smoothed: the module takes the middle value (median) of its last 2 seconds of
   boxes. The height of the first full smoothed box is the reference height, H.
6. **Search area.** Frames in which the tracker reports the loader moving are skipped. Otherwise the module builds a
   search area at the loader's bottom corner:
   - cone camera: from 1 H left to 1 H right of the loader's left edge, from 0.1 H above to 0.2 H below its bottom edge;
   - wing camera, loader left of the door: from 1 H left to 1.5 H right of its left edge, from 0.1 H above to 0.3 H below
     its bottom edge;
   - wing camera, loader right of the door (or face-on and not clearly left of it): at the bottom-right corner, from
     0.5 H inside to 1 H outside its right edge, from 0.2 H above to 0.1 H below its bottom edge.
7. **Counting.** Each checked frame with any cone whose bottom centre lies in the area adds one; a checked frame without
   one sets the count back to zero. More than 80 frames in a row (10 seconds) and the loader is "coned".
8. **Verdict** at the departure or the end of the video. Only loaders followed for more than 60 seconds, first to last
   frame, are judged. None: **Not observed**. All coned: **Pass**. Otherwise **Fail**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Frames in a row with a cone for "coned" | 80 frames (10 seconds); the client says 100 frames | Fewer: the loader fails |
| Shortest loader visit that is judged | 60 seconds | Shorter visits are ignored |
| New track number merged into the last loader | within 10 seconds | Fewer duplicate loaders |
| Short-lived loaders dropped | seen less than 10 seconds, checked 2 seconds after they vanish | Fewer false loaders |
| Window for smoothing the loader box | 2 seconds | Fixes the height H that sizes the area |
| Blocking box size and place (vehicles, people, ladders, cones) | wider than 60 % of the picture, centre between 30 % and 100 % of the width | Only shows "Camera is blocked!" on the annotated video; no effect on the verdict |
| Overlap limit for a loader staying in place | 0.8 | Not used by the code |
| Search area (in the code) | see step 6 | Where a cone counts |
| Tracker door label | 1 second at the door | Which loaders count as at the door |

## What it reports

- **Sentence:** "All of the beltloaders were confirmed coned." or "Not all of …", then one line per judged loader:
  "Beltloader <id> was [NOT ]coned (<start> - <end>)." The times are 10 seconds either side of the moment the cone was
  registered, or the loader's first to last frame. Not observed: "No beltloaders were detected in use."
- **Timeline entry** (the stretch of video the website marks): one per judged loader, Pass or Fail, from its first to
  its last frame.
- **Files:** a drawing file with the boxes and texts; an annotated video only when video writing is switched on.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 68 of them labelled for
this check. The module gave the client's verdict on 62 (91 %). The client labelled 14 Fail and the module said Fail on
12: 2 violations were missed, and the other 4 wrong verdicts were on turnarounds labelled Pass or Not observed. With 14
Fail labels the test does show that the check catches most missing cones. Our sources do not say which turnarounds were
wrong, or why.

## Known problems

- **10 seconds in a row instead of 100 frames in total.** The code needs more than 80 frames in a row; the client asks
  for 100 frames, without "in a row". The architecture review advises keeping the code's behaviour as the baseline and
  agreeing any change of the requirement separately.
- **Flicker restarts the count.** One checked frame without a detected cone resets the count, so a cone the detector
  misses now and then can turn a coned loader into a Fail.
- **No "view blocked" verdict.** Obstacles are found but only shown on screen; the client's "obstacles for 1 minute in
  total: Not observed" is not implemented. A hidden cone gives Fail instead of Not observed.
- **Any cone counts.** An engine or wing cone standing in the search area passes the check.
- **One loader per frame.** Only the biggest qualifying loader is checked; a loader that never gets the tracker's door
  label is never judged.
- **"Near the aircraft" is only the door label.** There is no size or aircraft-overlap test.
- **Out-of-date description.** The module's own description still describes an older version (a cone tracker, 100
  frames, a 5-second stop, skipping obstacles).
- **Cameras to confirm.** The production settings file lists the cone camera only; the client's sheet says both. Which
  cameras run the check in production is for Ihor, the technical lead, to confirm.

## In real time

It can run in real time as it is: it reads only boxes and tracks, once and in order, on frames already seen. A Pass is
known once the cone has stood 10 seconds behind a loader that has been at the door for 60 seconds. Like the other ready
checks, it needs the stage detector (the part that knows where in the turnaround we are) to switch it on and off for its
stages. Before real time it should stop logging every box and track from the first frame (14.1 megabytes per run).

On one 36-minute test turnaround it gave the same verdict and sentence live as post-processing (after the turnaround),
at the moment of the departure. Giving it only the boxes and tracks it reads, as the real-time branch does, changed
nothing on the monthly test (77 of 77 runs). Its own work is 0.37 milliseconds per frame (1.47 with all other checks
running). With its share of the General Model and the tracker, which here follows the aircraft and the belt loaders, it
needs 41.6 of the 125 milliseconds each frame may take at 8 frames per second (33 %). As a post-processing job it takes
12 seconds.

Where another aircraft stood in view before the real one arrived, the live feed took it for the arriving one; on four
test turnarounds this changed the verdict (three became Not observed, one Not observed became Pass). This is a problem of
the shared live feed, planned for the stage detector, not of the module.

## For developers

- **Module code in our workspace:** M05.
- **Repository:** `dxgat/detectors/bl_rear_cone`; production line `main` @ `12429f5` (2025-06-19; last logic change
  `d75f1f8`, 2025-05-14); default branch the same. Side branch `plane_type_cone_roi` (`1ce83b5`, 2025-06-12: jet /
  aircraft split on the wing camera, new cone area) is not in production.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, cone_camera, weights_dir,
  json_logger)`; all logic in `main.py`: `find_beltloader`, `manage_beltloader` / `manage_old_beltloaders`, the
  `Beltloader` class (smoothing, view side, search area, cone count) and `make_inference`. Task name
  `beltloader_rear_cone`.
- **Run on one turnaround:** `python main.py --source <video>.mp4 --inferences-dir <folder with GM and tracker ndjson>
  --local-inferences [--cone-camera] [--write-video] [--save-csv]`. The local `__main__` names the worker
  `safety-handrails-fully-extended` (copied from another module).
- **Settings keys:** `min_cone_threshold` 80; `min_bl_stay_time_thresh` 480; `min_bl_swap_time_thresh` 80;
  `min_bl_init_frames_thresh` 80, `bl_init_check_delay` 16; `bl_bbox_window_length` 16; `cone.` / `wing.`
  `obstacle_width` 0.6, `obstacle_center_range` [0.3, 1.0] (message only); `min_bl_stay_iou_thresh` 0.8 (unused).
  In code: cone classes `cone`, `beltloader_cone`, `engine_cone`, `wing_cone`; search areas in `update_cone_roi`
  (`main.py:128-161`); face-on test in `update_view_side` (`:100-126`); tracker door label after 8 frames
  (`cv_trackers/local_utils/bl_utils.py:4-133`).
- **Code places:** step 1 `main.py:251-260, 410-422`; step 2 `:262-292, 345-347`; step 3 `:295`; step 4 `:297-320,
  373`; step 5 `:72-89`; step 6 `:100-161, 446-455`; step 7 `:163-181, 397-402`; step 8 `:23-50, 194-196, 468`;
  obstacle message `:199-233, 405-407`.
- **Dependencies:** `cv_common` 86731e4 (not in the local archive; local copy ac5098d), `db_worker` 5a4aa83. numpy,
  opencv-python, norfair (through `cv_common`), torch (only `no_grad`). No weights.
- **Real time and sources:** `docs/04_modules.md` (NOW), `docs/analysis/rt_module_selection.md` (group A, 2.4 ms per
  recorded frame, 14.1 MB of logs), `docs/analysis/rt_module_cost.md` (events `7PytHarRNqmT`, `beqQ5Q0FoFWP`,
  `jI6tTM7YdhNE`, `bH2llDkvWIg9`); `docs/modules/bl_rear_cone.md`, `docs/analysis/module_review_2026-10.md`.
