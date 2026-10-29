# Cones placed in proper positions and timely

*In plain words: cones placed in the right positions on time.*

> Safety cones are put around a parked aircraft: under the wing, in front of the engines and under the tail. The check
> makes sure they are there while the aircraft stands at the gate. The software counts the frames on which the General
> Model (the shared detector) finds enough cones of each kind between the arrival and the departure, and gives Not
> observed when the places where the cones should stand were hidden.

## Status

| | |
|---|---|
| How accurate it is | 62 of 69 turnarounds correct (90 %) on the monthly test |
| Fail turnarounds it caught | 2 of 2 |
| In production | the version of March 2026 |
| Who looks after it | to assign |
| Biggest open problem | "On time" is never checked: cones are counted over the whole stay and Fail comes only at the departure, so late cones are not caught. |

## What the client wants

The client calls this check *Cones placed in proper positions and timely*.

| Verdict | When |
|---|---|
| Pass | The cone camera sees 1 wing cone and 2 engine cones (only 1 wing cone for a jet) for at least 100 frames (12.5 seconds), and the wing camera sees 1 tail cone for at least 100 frames. |
| Fail | At least one cone is detected on fewer than 100 frames. |
| Not observed | The aircraft is not detected. |
| Not observed, view blocked | Blocked frames make up more than 65 % of the full turnaround. |

A verdict is the answer of a check: Pass, Fail or Not observed. A frame is one picture of the video; the cameras take 8
per second. The check's name asks for proper positions and timeliness, but the rule only counts cones; it names no
position test and no deadline. The client puts the check in its real-time group (checks wanted while the turnaround
happens).

## When and where it looks

The module counts over the whole stay, from the moment the aircraft has been stopped for 5 seconds in total until its
departure is confirmed: the stages (parts of the turnaround) arrival, after the aircraft stops, unloading, loading and
before departure.

It runs on both cameras for both aircraft types the client distinguishes (aircraft and jets): the cone camera (looks
towards the nose) checks the wing and engine cones, the wing camera (looks along the wing) the tail cone. The client
merges the two: Fail on either camera gives Fail; Pass on one and Not observed on the other gives Pass. The production
settings file that lists the checks per camera names only the cone camera here (to confirm).

## What it looks at

- **From the General Model:** wing, engine and tail cones; aircraft parts (nose, wing, engines, tail). As things that can
  hide the cone places: pushback tugs, belt loaders and other service vehicles (ground support equipment: tugs, belt
  loaders, fuel trucks, tractors), trailers, fuel trucks, vehicles, people, ladders and objects labelled "obstacle" or
  "side obstacle". A detection is a box the detector draws around an object.
- **From the tracker:** only the aircraft track (the aircraft followed from frame to frame), moving or stopped.
- **From the video itself:** nothing for the decision; pictures are read only for an annotated video.
- **Own models:** none (a cone model file and helper code ship with the module but are never used). It runs on ordinary
  processors.

## How it decides, step by step

1. **Main aircraft:** the widest aircraft track on each frame. It has arrived once stopped for 5 seconds in total (not in
   a row). An arrival within the first 12 seconds of the video means "arrival not observed": the aircraft was already
   parked.
2. **Departure.** After 8 seconds of movement without stopping again, the departure start is set 4 seconds before the
   first moving frame. 30 seconds after that start, the aircraft's box over the first 3 seconds of the movement is
   compared with the last 3 seconds. A shrink of at least 17.5 % (the aircraft moves away) confirms the departure and the
   module decides at once; otherwise it was a false departure and counting goes on. At the last frame of the video it
   decides anyway.
3. **Cones on a frame.** Cone camera: at least 1 wing cone and, for aircraft that are not jets, at least 2 engine cones.
   Wing camera: at least 1 tail cone (for jets, tail cones left of the engine are ignored). From the arrival until the
   departure movement starts, each frame with the required number of one kind adds one to that kind's count. Any box of
   the cone class counts; its position is not checked further.
4. **Aircraft parts** (nose, left wing, engines, tail) come from the part boxes on the aircraft; a part missing for up to
   10 seconds is replaced by its recent average.
5. **Hidden places,** counted only on frames without the required cones: the nose or left wing not found; an obstacle in
   the zone under the left wing, in front of the engines or under the tail (a tow bar under the nose is ignored); the
   wing or tail zone at the edge of the picture; or, with no aircraft visible, a large obstacle (at least 5.4 % of the
   picture) over the centre of the picture.
6. **Per kind of cone:** Pass with at least 100 frames (12.5 seconds). Otherwise Not observed if the arrival was not
   observed or no departure was seen; otherwise Not observed if hidden frames make up at least 63 % of the time from
   the arrival to the departure start; otherwise Fail.
7. **Verdict:** any kind Fail gives Fail; otherwise any Not observed gives Not observed; otherwise Pass. No aircraft at
   all, or one that never stopped, gives Not observed.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Frames with the required cones for Pass | 100 frames (12.5 seconds) | Fewer: Fail or Not observed |
| Cones needed on one frame (in the code) | wing 1, engine 2, tail 1 | Fewer: the frame does not count |
| Stopped time that marks the arrival | 5 seconds in total | When counting starts |
| Arrival too early to be observed | first 12 seconds of the video | Not observed instead of Fail |
| Movement before a departure is checked | 8 seconds (6 for jets, never applied) | When counting stops |
| Departure start; confirmation | 4 seconds before the first moving frame; 30 seconds after the start | When the module decides |
| Box shrink that confirms a departure | 17.5 % (11 % for jets, never applied) | Real or false departure |
| Memory for a missing aircraft part | 10 seconds | How long its average stands in |
| Hidden share for Not observed (in the code) | 63 % | Above it, Fail becomes Not observed |
| Zone shapes; smallest obstacle | fractions of the part sizes; 0.25 % of the picture | Which boxes hide a cone place |

Four values in the settings file are not used, and the code reads one value the file lacks, on a path that never runs.

## What it reports

- **Sentence,** built per kind of cone, for example "Wing cone(s) were successfully placed for N frames (Pass). Engine
  cone(s) were placed only for N frames (Fail)." (the client sees frames, not seconds). Not observed texts such as "Zone
  under wing was obstructed, was out of frame (not Observed).", "… not observed due to incomplete arrival and departure
  (Not observed).", "No plane detected" or "Plane hasn't been detected."
- **Timeline entry** (the stretch of video the website marks): for Pass, per kind of cone, from 14.5 seconds before to 8
  seconds after the moment it reached 100 frames; for Fail and Not observed, from the arrival to the departure start (or
  the end of the video). Start and end are stored as text.
- **Files:** a drawing file with the aircraft's state, cone counts, hidden-zone events and obstacle boxes; an annotated
  video only when video writing is switched on.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, all labelled for this
check. The module gave the client's verdict on 62 (90 %). Only 2 were labelled Fail and it caught both; two Fail labels
cannot show whether the check catches violations. All 7 wrong verdicts were on turnarounds labelled Pass or Not
observed. Our sources do not say which ones, or why.

## Known problems

- **"On time" is not checked.** There is no deadline after the arrival; Fail is decided only at the departure or the end
  of the video, so late cones still pass. A time limit would be a rule change to agree with the client.
- **"Proper positions" is only the cone's label.** Any wing, engine or tail cone box counts wherever it stands (except
  the jet tail cone filter), and wing and engine cones are counted separately, not on the same frames. A misplaced cone
  can give Pass.
- **Not observed is wider than the rule.** The client gives it when no aircraft is seen or more than 65 % of the full
  turnaround is blocked. The module also gives it for an unseen arrival or departure, and for places hidden during at
  least 63 % of the stay, so some turnarounds the client would call Fail get Not observed.
- **The jet departure rules never apply.** The code compares the aircraft type with "jet" in lower case, but the General
  Model writes "JET" or "AIRCRAFT", so the 6-second threshold and the 11 % shrink are never used (to confirm how the type
  is passed). The rule that skips engine cones for jets uses the right spelling.
- **The jet direction check never runs.** It waits for the value "not evaluated", but the field starts empty, so a jet's
  tail zone is always placed for one direction.
- **The main aircraft can switch.** It is the widest track on each frame, with no identity check; a larger aircraft
  passing by can take its place.
- **It needs the video length** for the last-frame decision, which a live stream does not know.
- **Old notes do not apply.** The architecture review's notes (40 % in the report text against 65 % in the code, results
  of different lengths) refer to the older default branch; in production every path returns three values and the limit
  is 63 %.
- **Who confirms:** how the aircraft type reaches the module is for the module's owner (to assign) to check; which
  cameras run the check in production is for Ihor, the technical lead.

## In real time

It can run in real time as it is: it reads only boxes and the aircraft track, once and in order, and its verdict is final
when the departure is confirmed. Because it uses the video length, it needs an end-of-session marker (a signal that the
turnaround's video has ended). A deadline after the arrival ("on time") would change when it decides: a rule change to
agree with the client.

On one 36-minute test turnaround it gave the same verdict live as post-processing (after the turnaround), 10 seconds
after the departure; the numbers in its sentence shifted slightly when the tracker followed only the aircraft. Giving it
only the boxes and tracks it reads, as the real-time branch does, changed nothing on the monthly test (90 of 90 runs).
Its own work is 0.62 milliseconds per frame; with its share of the General Model and the tracker it needs 19.5 of the
125 milliseconds each frame may take (16 %). As a post-processing job it takes 13 seconds.

Where another aircraft stood in view before the real one arrived, the live feed took it for the arriving one and the
verdict changed on two test turnarounds (Not observed became Pass on one, Fail on the other): a problem of the shared
live feed, planned for the stage detector, not of the module.

## For developers

- **Module code in our workspace:** M09.
- **Repository:** `dxgat/detectors/cones-placed-in-proper-positions-and-timely`; production line `not_observed_logic`
  @ `d2a6898` (2026-03-25); default branch `master` @ `b2c53f6` (2025-09-22): older, 7 commits behind, before the
  refactor and the new Not observed logic (different YAML).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, weights_dir, write_video, cone_camera,
  json_logger, airplane_type)`; `db_worker/model_starter.py` passes the camera flag and, for this module only,
  `airplane_type`. `Plane` (arrival, departure, part memory), `record_cones_presence`, `determine_obstruction`,
  `get_decision`; `README.md`, `assets/flowchart.png`. Logic diagram (Confluence, 2026-03-12):
  https://docs.google.com/spreadsheets/d/1xXujLcsT1SQiaC8Bm9AWBjsLkBE3y__iIbO6sfao_As/edit?gid=0#gid=0
- **Run on one turnaround:** `python main.py --source <video>.mp4 --inferences-dir <folder> [--cone-camera]
  [--airplane_type JET|AIRCRAFT] [--write-video]`; without `--cone-camera` the wing-camera rules apply.
- **Settings keys:** `min_presence_frames` 100; `plane.stop_thd` 5 s, `plane.no_arrival_thr` 12 s,
  `plane.aircraft_departure_thd` 8 s, `jet_depart_thd` 6 s, `plane.movement_det_delay` 32 frames,
  `plane.departure_duration` 30 s, `plane.departure_bbox_change` 0.175, `weaker_departure_bbox_change` 0.11;
  `missing_part_thr` 10 s; `obstacle.*` (`min_area` 0.0025). In code: cones wing 1 / engine 2 / tail 1; hidden share
  0.63; `is_aircraft = airplane_type != 'JET'` (`main.py:704`) against `== 'jet'` (`:98, 106, 777`). Unused:
  `min_plane_type_frames_eval`, `jet_not_det_depart_thd`, `min_departure_len`, `min_plane_det_frames`; missing from
  the YAML: `min_plane_direction_frames_eval`.
- **Code places:** arrival `main.py:76-81`; departure start `:83-105`; confirmation and early decision `:764-799`; box
  shrink `:231-242`; part memory `:111-182`; cones per camera `:723-735`; counting `:315-345`; hidden zones `:402-583`;
  decision `:254-312`; end of video `:824-828`; jet direction `:208-229`.
- **Dependencies:** exported copy; branch pins `cv_common` dd5b554, `db_worker` 5a4aa83 (export: `cv_common` ac5098d).
  NumPy, OpenCV; no weights (`weights/cones_v1.pt`, `cones_helpers.py` unused); Docker base `cpu_base`.
- **Real time and sources:** `docs/04_modules.md` (NOW), `docs/analysis/rt_module_selection.md` (group A, 2.3 ms per
  recorded frame), `docs/analysis/rt_module_cost.md` (events `KB04bkqBI7ms`, `DZEwHETNWRBa`);
  `docs/modules/cones-placed-in-proper-positions-and-timely.md`, `docs/analysis/module_review_2026-10.md`.
