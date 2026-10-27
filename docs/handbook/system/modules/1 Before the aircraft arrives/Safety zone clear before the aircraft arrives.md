# Safety zone clear before the aircraft arrives

> In the last two minutes before the aircraft stops, no ground vehicle may move through the safety zone it rolls into.
> After the stop, the module builds the zone (the "diamond") from the path of the aircraft's front wheel and the cones,
> then goes back over those two minutes and watches for vehicles moving in it.

## Status

| | |
|---|---|
| How accurate it is | 63 of 68 turnarounds correct (93 %) on the monthly test |
| Fail turnarounds it caught | 13 of 13 |
| In production | the version of March 2026 |
| Who looks after it | to assign |
| Biggest open problem | The last 30 seconds before the aircraft stops are never checked, though the rule covers the full last 2 minutes. |

## What the client wants

*Safety zone confirmed clear*

| Verdict | When |
|---|---|
| Pass | The safety zone is visible and clear during the last 2 minutes before the aircraft arrives. |
| Fail | The safety zone is visible and a belt loader, fuel truck, trailer, pushback tug or other service vehicle is seen moving in it during those 2 minutes. |
| Not observed | The diamond area is not visible, the zone built is too small, the aircraft did not arrive, or there is no pre-arrival stage. |
| Not observed, view blocked | Something blocks the view for more than 30 seconds in the pre-arrival stage. |

A verdict is the answer of a check: Pass, Fail or Not observed. The diamond area is the safety zone itself. Service
vehicles are ground support equipment: tugs, belt loaders, fuel trucks, tractors. The pre-arrival stage is the part
(stage) of the turnaround before the aircraft arrives.

## When and where it looks

It scores the time from 2 minutes to 30 seconds before the aircraft stops, ending a little later when the straight final
approach is shorter than about 25 seconds. The stop is the frame (one picture; the cameras take 8 per second) on which
the tracker (the part that follows objects from frame to frame) reports it, after more than 4 seconds standing still.
It runs on the cone camera (which looks towards the aircraft nose), for aircraft and jets; the camera type only changes
a label on the drawing.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object): cones and the
  aircraft's front wheel, for the zone; belt loaders, fuel trucks, trailers, pushback tugs, other service vehicles, any
  other vehicle and vehicles marked as standing in the way, as moving vehicles or view blockers; people, to leave them
  out.
- **From the tracker:** the aircraft track (a track is the same object followed from frame to frame) and its stop. The
  module follows the vehicles itself.
- **From the video itself:** yes, in the second pass.
- **Own model:** a ready-made outlining model (not trained by us) that draws each vehicle's exact outline so its motion
  can be measured. It runs on an ordinary processor in production; on a graphics card when given one (to confirm).

## How it decides, step by step

1. **First pass** (boxes and tracks only, up to the stop): collects steady cones (taller than wide, over 500 square
   pixels, in one place for more than 5 seconds in total) and, while an aircraft at least 200 pixels tall is tracked,
   the front wheel nearest its centre. The picture is 1,920 × 1,080 pixels.
2. Fits a straight line to the wheel positions of the last 15 seconds before the stop and keeps those of the last 2
   minutes that lie on it, cut where 3 in a row (counting back from the stop) are off it. The first and last kept
   positions are the far and near ends of the approach.
3. Builds the zone from these two points plus, on each side, the cone closest to that picture edge at the zone's
   mid-height. No cone on the left: the picture's edge; none on the right: a point mirrored from the wheel path. No
   wheel line: zone not visible; both diagonals under 200 pixels: area too small.
4. **Scored time:** from 2 minutes to 30 seconds before the stop, or to 5 seconds before the straight approach began if
   that is later.
5. **Second pass** (reading the pictures): a vehicle box larger than 600 × 400 pixels with its centre in the left 75 %
   blocks the view; if its bottom edge overlaps the zone by more than 10 %, the frame is "not observed". Without a zone,
   every frame is "not observed".
6. It follows the other vehicles itself, ignoring pushback tugs within 1,000 pixels of the aircraft's centre (they may
   be towing it), and measures motion by following points inside each vehicle's outline, with people blanked out.
7. A frame is "fail" when a moving vehicle has more than 30 % of its box's bottom strip (5 pixels high) inside the zone;
   otherwise "pass".
8. **Aircraft checks** (older rules): the arrival counts as filmed after more than 3 seconds of movement in a row
   without camera shake (point jumps over 50 pixels sideways or 5 up or down); the pre-arrival stage, when the stop comes
   more than 60 seconds into the video.
9. **Not observed** if the aircraft did not stop, or the arrival or pre-arrival stage was not filmed. Then **Fail** if
   "fail" frames add up to more than about 1.9 seconds; **Not observed** if "not observed" frames outnumber "pass"
   frames; otherwise **Pass**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Blocking vehicle | larger than 600 × 400 pixels, centre in the left 75 %; in the zone if overlap over 10 % | Frame "not observed" |
| Towing pushback | within 1,000 pixels of the aircraft centre | Ignored |
| Crossing | over 30 % of the bottom strip inside the zone | Frame "fail" |
| Fail time | more than about 1.9 seconds in total | Fail |
| Scored time | 2 minutes to 30 seconds before the stop (or 5 seconds before the straight approach) | What is checked |
| Wheel line | fitted on the last 15 seconds | Which wheel positions build the zone |
| Steady cone | taller than wide, over 500 square pixels, over 5 seconds in place | Zone corners |
| Wheel collection | aircraft at least 200 pixels tall | When wheels count |
| Smallest zone | diagonals of 200 pixels | Smaller: Not observed |
| Earliest stop | 60 seconds into the video | Earlier: Not observed |
| Arrival movement | over 3 seconds; shake over 50 or 5 pixels | Arrival filmed |

The blocking size, towing distance and crossing share are in the settings file; the rest is in the code.

## What it reports

- **Sentence.** Pass: "The safety zone was clear." with the 2-minute span. Fail: "<vehicle type> <number> crossed the
  safety zone on <time>." per vehicle. Not observed names the reason, for example "Built area is too small", "Safety
  zone is not visible (front wheel trajectory is not detected)", "There was an obstacle for more than 30 seconds" or
  "No pre-arrival stage".
- **Timeline entry:** one Pass or Fail block from the start of the video to the stop; none for Not observed.
- **Files:** a drawing file (zone, cones, front wheels, blockers, vehicle states); a picture of the stop frame with the
  zone on every run that reaches the stop; an annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on 63 (93 %). It caught all 13 turnarounds labelled Fail, so its 5 errors are all on
turnarounds labelled Pass or Not observed where it said something else. Our sources do not say which ones.

## Known problems

- **The last half minute is not checked.** The scored time ends about 30 seconds before the stop; the rule covers the
  full 2 minutes. A vehicle crossing just before the stop gives Pass instead of Fail.
- **Not the client's blocked-view rule.** Not observed comes when blocked or zone-less frames outnumber clear ones; the
  rule's "more than 30 seconds" only picks the report text. "Fail" frames over about 1.9 seconds give Fail even on a
  mostly blocked view.
- **"Fail" time adds up** over all vehicles and need not be continuous.
- **Own vehicle tracking.** Motion comes from the module's own tracking, as the shared tracker lacks some of these
  vehicle types. A new vehicle starts as "moving": the shared library sets a "stopped" flag that the vehicle's state
  does not read (seen in our copy; production's: to confirm). This can add "fail" frames.
- **Fallback corners.** Without a cone on a side, that corner of the zone is the picture's edge or a mirrored wheel
  point, not a cone.
- **Old pieces.** Older arrival rules (camera-shake filter, 60 seconds) in both passes; a label the module does not know
  stops it with an error; its description file describes an older zone.

## In real time

It cannot run in real time as it is. It reads the video twice: the first pass builds the zone only at the stop, and the
second goes back over the 2 minutes before, which in real time have already gone by. As the wheel path is known at the
stop, a one-pass version is planned. Building the zone earlier, to warn before a crossing, needs a prediction of the
aircraft's path and changes when the check decides, which must be agreed with the client. Of all checks, this one would
gain the most from real time.

The first pass alone on a 36-minute test turnaround: own work 0.25 milliseconds per frame; with the shared General Model
(main detector plus vehicle part) and tracker, 19.2 of the 125 milliseconds each frame may take (15 %). As a
post-processing job (after the turnaround), both passes take about 83 seconds. The client's split puts this check in
the streaming group.

## For developers

- **Module code:** M24. **Repository:** `dxgat/detectors/safety-zone-confirmed-clear`; production `master` @ `91676a5`
  (2026-03-24), the same as the default branch.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, ...)`: first pass, zone, second pass,
  decision; `select_wheel_trajectory_points()`, `get_diamond()`, classes `Zone`, `Cone`, `get_report()`; functions at
  the top only draw. Outlines: MobileSAM; vehicles tracked with norfair.
- **Run:** `dvc pull`, then `python main.py --source <video>.mp4 --inferences-dir <dir> --weights-dir weights [--device
  cpu] [--write-video]`; reads both ndjson files and the video. Production: `db_worker/model_starter.py` calls `detect()`.
- **Keys:** `full_frame_obstacled.width` 600, `.height` 400, `.center_offset` 0.75; `pushback.plane_distance` 1000;
  `zone.intersect_thresh` 0.3. Code: `l_th_sec` 120, tail 30 s / 5 s, `fit_traj_sec` 15, > 15 fail frames, blocker
  overlap 0.1, pre-arrival 60 s, `Cone._threshold` 5 s (> 40 hits), cone > 500 px², aircraft ≥ 200 px, diagonals 200 px,
  strip 5 px, arrival > 24 frames, shake 50 / 5 px.
- **Code places:** step 1 `main.py:867-959, 747-764`; 2 `:571-619, 962-968`; 3 `:632-677, 696-745, 985-987`; 4
  `:969-976, 1010, 1145-1233`; 5 `:1049-1089, 1306-1395`; 6 `:990-994, 1409-1446`; 7 `:1450-1483, 716-745`; 8
  `:1092-1138`; 9 `:1521-1538, 800-828`.
- **Dependencies:** pins `cv_common` dd5b554, `db_worker` 5a4aa83 (local `cv_common` holds ac5098d); mobile-sam (GitHub
  01ea8d0), norfair 1.0.0, timm, torch; `weights/mobile_sam.pt` (40.7 MB) by DVC. Logic diagram: `.doc/Safety
  Zone.svg`; Confluence, 2023-09-29 (older than the 2026 zone logic).
