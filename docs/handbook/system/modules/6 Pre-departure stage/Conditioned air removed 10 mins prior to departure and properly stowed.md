# Conditioned air removed 10 mins prior to departure and properly stowed

*In plain words: conditioned air hose removed 10 minutes before departure and stowed.*

> While the aircraft stands at the gate, a hose from an air conditioning unit can be connected to it. This check makes
> sure the hose was taken off at least 10 minutes before the departure starts. The module runs its own hose detector on
> the cone camera's pictures and follows, over the whole stay, whether the hose reaches the aircraft.

## Status

| | |
|---|---|
| How accurate it is | 66 of 68 turnarounds correct (97 %) on the monthly test |
| Fail turnarounds it caught | 3 of 4 |
| In production | the version of April 2026 |
| Who looks after it | to assign |
| Biggest open problem | "Properly stowed" is never checked on its own: a hose away from the aircraft, or not seen at all, counts as removed and stowed. |

## What the client wants

*Conditioned air removed 10 mins prior to departure and properly stowed*

| Verdict | When |
|---|---|
| Pass | The air conditioning hose was removed and properly stowed 10 minutes or more before the departure. |
| Fail | The hose was used but was not removed and/or not properly stowed 10 minutes or more before the departure. |
| Not observed | The hose was not used, or the aircraft nose (jet: the left engine) was never seen, or the departure was not seen. |
| Not observed, view blocked | Something blocked the view at the "10 minutes before departure" mark, and the hose had not been seen used, disconnected and stowed before it. |

A verdict is the answer of a check: Pass, Fail or Not observed. "Aircraft" and "jet" are the client's two aircraft
types.

## When and where it looks

The check belongs to the stage before departure (a stage is a part of the turnaround). The module watches the hose from
the aircraft's stop to the start of its departure; the verdict concerns the last 10 minutes before the departure and
comes about 26 seconds after the aircraft starts moving. It uses the cone camera (which looks towards the aircraft
nose), for aircraft and jets; the code does not check the camera.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object on a frame, one
  picture of the video, 8 per second): the aircraft nose, wings and engines. As view blockers: pushback tugs, belt
  loaders, service vehicles (ground support equipment: tugs, belt loaders, fuel trucks, tractors), trailers, fuel
  trucks, air conditioning units, vehicles, and "obstacle" or "side obstacle" boxes.
- **From the tracker:** the aircraft track (the aircraft followed from frame to frame), moving or stopped.
- **From the video itself:** yes, for the hose detector.
- **Own model:** a hose detector trained on our hose pictures; only its boxes are used. It runs on a graphics card (or
  the processor).

## How it decides, step by step

1. **Aircraft and type.** The widest aircraft track is the aircraft; it has arrived after 5 seconds of "stopped" in
   total. Frames showing a wing and an engine on it vote: engine above the wing "jet", below "aircraft"; after more than
   40 votes the majority wins (tie: aircraft). If the aircraft vanishes for 10 seconds before arrival, the votes are
   dropped (probably a passing aircraft).
2. **Connection point.** After arrival each frame needs the most confident nose box (jet: leftmost engine box), at
   least half on the aircraft box; otherwise the frame is skipped. Without a type, the hose is never checked.
3. **Hose boxes.** The detector runs every 2 seconds; its last boxes are reused in between. Dropped: boxes far left of
   the nose (aircraft) or right of it (jet); flat shadows under the nose up to 0.075 % of the picture; tow bar parts
   under the nose; after a first use, the small stowed tip on the gate (up to 0.14 % of the picture, with a longer hose
   piece higher up to its right).
4. **Blocked view.** A box lying partly on the aircraft and across the right edge of the connection point blocks the
   view: a pushback tug (aircraft only; at least 5 % of it on the aircraft) or another listed object of at least 1.5 %
   of the picture (10 % on the aircraft).
5. **Frame status.** *In use*: a hose box reaches the connection point (aircraft: its left edge at or left of the nose's
   right edge; jet: its right edge right of the engine's). *Possibly in use*: a blocker touches the hose, or no hose is
   seen and a blocker reaches the hose's side of the picture (aircraft: right 13.5 %; jet: left 10 %). *Not used*:
   anything else.
6. **Smoothing.** The status changes only when 95 % of the last 800 checked frames (100 seconds), lying within 105
   seconds, agree; the change is dated to their start ("in use" to "possibly in use": 12.5 seconds later).
7. **Departure.** After arrival, 8 seconds of moving (jet: 6) without a stop start a departure, dated 4 seconds before
   the first moving frame. 30 seconds later the aircraft box must have shrunk 17.5 % (jet: 11 %) between the first and
   last 3 seconds of movement, or the departure is cancelled. On a video's last frame the tracker's departure replaces
   this test.
8. **Verdict**, looking back from the departure start. "In use" at any time in the last 10 minutes or at the 10-minute
   mark: **Fail**. "Possibly in use" at the mark: **Not observed** (view blocked), unless the hose had been in use for
   15 minutes and then went straight to "not used"; blocked periods are then ignored. "Not used" at the mark: **Pass**
   if an earlier "in use" period lasted at least 212.5 seconds (about 3.5 minutes), else **Not observed**. No status at
   all, or no departure by the end of the video: **Not observed**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Stopped time for "arrived" | 5 seconds in total | Start of watching |
| Moving time for a departure | 8 seconds (jet: 6), dated 4 seconds back | Departure start, 10-minute mark |
| Departure confirmation | 30 seconds; box shrink 17.5 % (jet: 11 %) | Verdict time, false departures |
| Type votes | more than 40 | Start of the hose check |
| Smoothing | 800 frames (100 seconds), 95 %, within 105 seconds; 12.5-second delay | Speed of status changes |
| Shortest use for Pass | 212.5 seconds | Shorter: Not observed |
| Long-use rule | 15 minutes | Blocked periods ignored |
| Deadline | 10 minutes | The client's rule |
| Detector rhythm | every 2 seconds | Pictures checked |
| Blocking box | 1.5 % of the picture; sides 13.5 % and 10 % | View blocked |
| Shadow, stowed tip | 0.075 %, 0.14 % of the picture | Hose boxes dropped |

Deadline, 15-minute rule, rhythm and side limits are fixed in the code; three settings-file values are unused.

## What it reports

- **Sentence.** Pass: "Conditioned air hose was seen disconnected and stowed at <time>, which is <time span> prior to
  departure at <time>." Fail: "Conditioned air hose was still in use on <time>, which is <time span> before the
  departure at <time>." Not observed: "Required airplane parts weren't observed", "Conditioned air was not used.",
  "There was an obstacle from <time> to <time> preventing reliable observation of whether the hose was used and
  disconnected.", "There was an obstacle preventing reliable observation of whether the hose was used." or "Airplane
  departure wasn't observed".
- **Timeline entry:** the verdict from the arrival to the departure start; none without a departure.
- **Files:** per-frame drawings (aircraft, parts, hose, blockers, status lines); an annotated video if switched on.

## How accurate it is

The monthly test (the client's validated turnarounds we measure on) has 69 turnarounds; 68 were labelled for this check
and the module matched 66 (97 %). It caught 3 of the 4 labelled Fail. With 4 Fail labels, the number mainly shows that
false alarms are rare; it cannot show how reliably a connected hose is caught. Which ones it got wrong is
not in our sources.

## Known problems

- **Position, not coupling.** "In use" means the hose box reaches the nose or engine box. A hose lying near the nose can
  count as in use, a connected hose hidden from view as not used.
- **"Properly stowed" is not checked.** The client's Pass needs it; the code counts a hose away from the aircraft, or
  unseen, as removed and stowed. A hose left on the ground can pass.
- **Short uses are lost.** Uses under 212.5 seconds never pass, changes under about 100 seconds are smoothed away, and a
  reused box counts up to 16 times. The rule has no minimum; short uses end as Not observed.
- **Jet position mix-up (to confirm).** One "hose clear of the blocker" test compares the hose's right edge (left-right)
  with the blockers' top edge (up-down), likely a coding mistake; jet frames with a blocker can get a wrong status.
- **No detector confidence limit (to confirm it is intended):** the library default of 0.25 applies.
- **Fixed numbers:** the 10-minute mark assumes 8 frames per second; side limits and blocker margins are in the code.
- **Old descriptions and files:** the architecture review and earlier audits describe the old code; the old air
  conditioning unit detector is stored but unused.

## In real time

The client puts this check in the "streaming" group: wanted during the turnaround, but seconds do not matter. It runs as
it is, with pictures for its detector: it reads each frame once, in order, and only looks back. The stage detector (the
part that knows where in the turnaround we are) must start it at the arrival, as it keeps the whole hose history; its
last-frame rule needs an end-of-session signal instead of the video length.

In the real-time test setup it gave the post-processing (after the turnaround) verdict and sentence, 10 seconds after
the tracker's departure moment; on the 4 test turnarounds still on disk, the reduced real-time inputs changed nothing.
Cost with the General Model and the tracker: 19.9 of the 125 milliseconds a frame may take (16 %); own work 1.26
milliseconds alone, 3.2 with all checks; as a post-processing job, 27 seconds per turnaround. It answers only after the
departure starts; warning before the deadline needs the planned departure time from the flight schedule, unused today.

## For developers

- **Module code:** M07. **Repository:** `dxgat/detectors/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed`;
  production `new_logic` @ `960bfe1` (2026-04-07), a 9-commit rewrite of `main` @ `940fdfc` (2025-06-19, old logic
  with an ONNX unit detector every 40 frames).
- **Entry point:** `main.py` → `detect()`; `Plane`, `AirConditioningHose`, `get_ac_hose_detections`,
  `determine_obstacles`, `determine_ac_hose_status`, `get_decision`. Logic diagram (Confluence):
  https://docs.google.com/spreadsheets/d/1HEcwdRgl3Pu8X6plJdPWup0uKyCe1otwTUXquB4ny_I/edit?gid=1532176923
- **Run:** `python main.py --source <video>.mp4 --weights-dir weights --inferences-dir <dir> [--write-video]`.
- **Keys:** `plane.stop_thd`, `aircraft_departure_thd`, `jet_depart_thd`, `movement_det_delay` (32 frames),
  `departure_duration`, `departure_bbox_change`, `weaker_departure_bbox_change`, `min_plane_type_frames_eval`;
  `ac_hose.status_frame_history`, `max_frame_history_gap` (40), `status_change_thd`, `usage_obstruction_delay` (100),
  `min_usage_frames` (1700), `stowed_tip_max_area`, `fp_small_hose_max_area`; `obstacle.min_area`,
  `nose_intersect_margin` (0.08). In code: 4 800 / 7 200 frames, `2 * fps`, 0.865 / 0.1. Unused:
  `plane.jet_not_det_depart_thd`, `min_departure_len`, `min_plane_det_frames`.
- **Code places:** type `main.py:51-80, 161-183`; arrival `:126-131`; connection point `:82-102, 894-896`; detector
  `:574-684, 829`; blocked view `:316-361`; status `:480-571` (jet mix-up `:520`); smoothing `:217-256`; departure
  `:147-155, 851-887`; verdict `:686-766, 909-917`.
- **Dependencies:** `cv_common` dd5b554, `db_worker` 5a4aa83 (export: ac5098d); ultralytics 8.3.226, torch 2.4.1,
  norfair; DVC `yolo11s_seg-det_ac_tr18_noalb.pt` (33 MB with the unused `best28_full.onnx`, `util/yolov8_onnx.py`).
