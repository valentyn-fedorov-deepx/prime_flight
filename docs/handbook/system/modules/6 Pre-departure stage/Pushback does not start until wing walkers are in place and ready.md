# Pushback does not start until wing walkers are in place and ready

*In plain words: pushback waits until the wing walkers are in place and ready.*

> When the pushback starts, a wing walker should be on each side of the aircraft. This check makes sure the pushback
> does not start before they are in place. In practice the module checks that, in the first 30 seconds of the pushback,
> a person walks along each side of the aircraft in the same direction, using only boxes and tracks from the cone camera.

## Status

| | |
|---|---|
| How accurate it is | 56 of 68 turnarounds correct (82 %) on the monthly test |
| Fail turnarounds it caught | 16 of 17 |
| In production | the version of April 2026 |
| Who looks after it | to assign |
| Biggest open problem | It checks walking along after the pushback has started, not readiness before it, and its right-side test is likely broken (almost always true). |

## What the client wants

*Pushback does not start until wing walkers are in place and ready*

| Verdict | When |
|---|---|
| Pass | Two wing walkers, one on each side of the aircraft, in the first 30 seconds after the departure starts: each path is within 50 degrees of the aircraft's path and goes the same way, and the sides are confirmed by position. |
| Fail | 0 or 1 wing walker in total, with no blocked view on the side where a wing walker is missing. |
| Not observed | There was no departure stage. |
| Not observed, view blocked | Fail was not triggered, and a side was blocked in more than 60 % of the frames of those 30 seconds. |

A verdict is the answer of a check: Pass, Fail or Not observed; a stage is a part of the turnaround; a frame is one
picture of the video (8 per second).

## When and where it looks

The check covers the stages before departure and the departure with pushback. The module looks at the first 30 seconds
after the aircraft starts moving back, once it has stood still for 60 seconds in a row; at the end of a video, 20
seconds are enough. It uses the cone camera (which looks towards the aircraft nose), for aircraft and jets; the code
does not check the camera.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object on a frame):
  pushback tugs, aircraft wings and tail, and the front wheel (for an on-screen note). As view blockers: belt loaders,
  service vehicles (ground support equipment: tugs, belt loaders, fuel trucks, tractors), trailers, fuel trucks, air
  conditioning units, vehicles, and "obstacle" or "side obstacle" boxes.
- **From the tracker:** the aircraft track (the aircraft followed from frame to frame; stopped or moving, and the
  tracker's arrival) and the people tracks.
- **From the video itself:** nothing; pictures are read only to draw an annotated video.
- **Own models:** none. It runs on an ordinary processor.

## How it decides, step by step

1. **People and aircraft.** Every frame, the widest aircraft track and the people tracks, leaving out tug drivers
   (centre inside a tug box and more than 35 % of the person's box inside it) and people standing between the left wing
   and the tug.
2. **Parked.** The tracker reports the aircraft stopped on 480 frames (60 seconds) in a row. Any other status, or the
   aircraft missing for more than 10 frames (1.25 seconds), restarts the count.
3. **Departure start.** The first moving frame after parking, confirmed after 64 moving frames (8 seconds); a stopped
   frame before that discards it.
4. **Positions.** From the departure start, a rough position seen from above for each person and the aircraft: a
   direction from the box's place across the picture (the camera sees 60 degrees) and a distance from the box height (a
   person taken as 1.75 metres tall, the aircraft as 7 metres).
5. **Blocked sides.** From the tracker's arrival, a frame is blocked when boxes cover fixed parts of the picture. A big
   box in the middle (centre between 37 % and 60 % of the width, at least 14 % of the picture and 40 % of its width)
   blocks both sides. A box starting in the leftmost 18 % (at least 0.85 % of the picture and 7 % of its width, not a
   person) blocks the left side, as do boxes centred between 6 % and 37 % of the width (each at least 1.2 % of the
   picture) covering 2.2 % together. Boxes centred between 68 % and 91 % (each at least 0.6 %), plus a tug in the right
   part of the picture, block the right side when they cover 1.4 % together. Boxes whose top is low in the picture do
   not count.
6. **Decision moment.** 30 seconds after the departure start, once the aircraft's estimated distance is growing (at the
   end of a video, 20 seconds are enough). The aircraft box must have shrunk by at least 18 % between the first and the
   last 3 seconds of movement; otherwise the departure is discarded and the module waits for the next.
7. **Paths.** Each path needs at least 13 points (about 1.6 seconds) in the window; it is smoothed over 11 frames and
   fitted with a straight line. A person is a wing walker when the line is within 50 degrees of the aircraft's and both
   move the same way.
8. **Side.** A line parallel to the aircraft's path is drawn through the end of each path: beyond the aircraft's own
   line means right, otherwise left. A side also needs a person seen on that side of the aircraft box while it moves
   (left: centre left of a line 175 pixels inside the box's left edge).
9. **Per side.** A wing walker: present. None: Not observed if the side was blocked in at least 60 % of the window,
   otherwise Fail.
10. **Verdict.** Both sides present: **Pass**; a side failed: **Fail**; otherwise **Not observed**. No aircraft, no
    parking or no confirmed departure: **Not observed**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Parking time | 60 seconds in a row | When a departure can start |
| Moving time | 8 seconds | Departure start confirmed |
| Absence | 1.25 seconds | Longer: counts restart |
| Window | 30 seconds (end of video: 20) | Stretch that is checked |
| Box shrink | 18 % | Less: departure discarded |
| Path angle | 50 degrees | Who is a wing walker |
| Blocked share | 60 % | Side Not observed |
| Blocking areas | parts of the picture, as in step 5 | Where a box blocks a side |
| Shortest path | 13 points (about 1.6 seconds) | Shorter paths ignored |

Parking time and shortest path are fixed in the code; three values in the settings file are unused.

## What it reports

- **Sentence**, for example: 'Check result is "Fail": there was a wing-walker on the left side of the plane and there
  were no wing-walkers on the right side. Time : 00:46:24 -- 00:46:54'. Not observed without a departure: "Not enough
  moving frames of airplane were detected" or "No airplane was detected or no departure observed"; with too short an
  aircraft path: "Airplane movement path was too short".
- **Timeline entry:** one block with the verdict from the departure start to the decision; none without a departure.
- **Files:** per-frame drawings, a picture of all paths on every run, and an annotated video if switched on.

## How accurate it is

The monthly test (the client's validated turnarounds we measure on) has 69 turnarounds; 68 were labelled for this check
and the module matched 56 (82 %). Of the 17 labelled Fail it caught 16, so it rarely misses one: 11 of its 12 errors
are turnarounds labelled Pass or Not observed where it said something else. Which ones is not in our sources.

## Known problems

- **After the start, not before.** The evidence is walking along in the first 30 seconds after the start, not readiness
  before it (as the architecture review notes). The client's name says the pushback must not start until the walkers
  are ready; the verdict cannot show that.
- **Right-side test likely broken (to confirm).** It compares people's left-right positions with the top edge of the
  aircraft box instead of its right edge, so it is almost always true; the right side then rests on the path test alone.
- **Own timing.** 60 seconds parked and 8 seconds moving, instead of the tracker's moments; a video without 60 seconds of
  the parked aircraft gives Not observed.
- **Fixed blocking areas,** tuned for the cone camera view; people never count as blockers.
- **End point, not start.** The side test uses each path's end; the module's description says its start.
- **"Pushback attached" is only a note.** A front wheel within 315 pixels of the tug is shown on screen but not used.
- **End of video.** The 20-second fallback reads the video length; real time needs an end-of-session signal.
- **Cost.** An on-screen blocked-frame counter is recomputed over the whole history on every frame.

## In real time

The client puts this check in the "streaming" group: wanted during the turnaround, but seconds do not matter. It runs as
it is: one pass, no pictures, deciding about 30 seconds after the movement starts. It needs an end-of-session signal for
its end-of-video rule, and a value kept in shared program memory survives between runs and must be reset per turnaround.

In the real-time test setup it gave the post-processing (after the turnaround) verdict and sentence, 14 seconds after
the tracker's departure moment; on 68 test turnarounds the reduced real-time inputs changed nothing. Cost with the
General Model and the tracker: 22.4 of the 125 milliseconds a frame may take (18 %); own work 0.33 milliseconds alone,
2.8 with all checks; as a post-processing job, 13 seconds per turnaround. In live runs, on one turnaround where another
aircraft was in view first, the verdict changed from Pass to Fail: a problem of the shared live feed, for the stage
detector (the part that knows where in the turnaround we are).

The pushback start is where an alert would matter most, but the check decides after the fact. Warning before the tug
moves needs judging readiness before the movement: a change of the client's rule, to agree with the client.

## For developers

- **Module code:** M20. **Repository:** `dxgat/detectors/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready`;
  production `obstruction_plane_track` @ `6979d19` (2026-04-10); `master` @ `f3b041c` (2025-06-19) is older (one
  whole-frame blocking rule, 9 commits behind).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera,
  json_logger)`; `obstacle_logic.py` side blocking; `helpers.py` angle, distance, plots.
- **Run:** `python main.py --source <video>.mp4 --inferences-dir <dir> [--write-video] [--json-fn <name>]`;
  `local_config.yaml` overrides `cv_common/global_config.yaml`.
- **Keys:** `plane.depart_thd` 8, `plane.max_absence_frames` 10, `plane.target_mov_time` 30, `plane.min_departure_len`
  20, `plane.departure_bbox_change` 0.18, `degree_thresh` 50, `obstacle.not_observed_thr_ratio` 0.6,
  `obstacle.{central, left_side_single, left_side, right_side, pushback}.*`. In code: parking `fps * 60`, more than 12
  points, `len_thresh` 175, wheel 315 px. Unused: `plane.mov_reset_thr`, `plane.min_path_duration`,
  `message_display_duration`.
- **Code places:** step 1 `main.py:436-487, 635`; 2 `:96-107, 148-151`; 3 `:109-131`; 4 `:133-147, 417-433`; 5
  `:389-393`, `obstacle_logic.py:65-131`; 6 `:658-684`; 7 `:33-53, 185-258`; 8 `:176-182, 652-653` (right-side bug
  `:179`); 9–10 `:296-330, 726-734`.
- **Dependencies:** `cv_common` dd5b554 (export: ac5098d), `db_worker` 5a4aa83; scikit-learn 1.6.1, norfair,
  matplotlib, OpenCV; no weights (`download_weights.sh` fetches an unused old GM file).
