# Nose gear chocks applied immediately

*In plain words: nose wheel chock placed right after arrival.*

> Chocks are the wedges the ground crew puts against an aircraft's wheels so that it cannot roll. This check asks that
> the nose wheel is chocked within 30 seconds of the aircraft's arrival. The software finds the nose wheel and the
> chocks in the boxes of the General Model (the shared detector). The same module also gives two other checks of the
> client: *Main gear chocks removed only after aircraft is attached to pushback* and *Nose wheel chock removed from
> aircraft*.

## Status

| | |
|---|---|
| How accurate it is | 62 of 68 turnarounds correct (91 %) on the monthly test |
| Fail turnarounds it caught | 1 of 1 |
| In production | the version of January 2026 |
| Who looks after it | to assign |
| Biggest open problem | The 30 seconds start at the tracker's arrival moment, about 4 seconds after the aircraft stops, and a nose wheel hidden for a while is checked at its old place. |

## What the client wants

A verdict is the answer of a check: Pass, Fail or Not observed. "Arrival" is the moment the aircraft has stopped at the
gate.

| Verdict | When |
|---|---|
| Pass | The nose wheel was chocked within the first 30 seconds after arrival. |
| Fail | The nose wheel was seen, but not chocked within the first 30 seconds. |
| Not observed | The aircraft or the nose wheel was not seen, or there was no arrival stage, or something stood in the way. |
| Not observed, view blocked | All the frames of the arrival were blocked. |

A stage is a part of the turnaround; "no arrival stage" means the video does not show the aircraft driving in. A frame
is one picture of the video; the cameras take 8 per second. The client's sheet marks this check as ready for production
and puts it in its real-time group (checks wanted while the turnaround happens).

## When and where it looks

The first 30 seconds after the tracker's arrival moment. The tracker marks the arrival once the aircraft has stood still
for about 4 seconds, so in practice the window runs from about 4 to about 34 seconds after the aircraft stopped. The
check runs on the cone camera (the camera that looks towards the aircraft nose) for both aircraft types the client
distinguishes, aircraft and jets. The code does not check which camera filmed the video.

## What it looks at

- **From the General Model:** nose wheels, chocks (from a separate chock detector) and, as things in the way, cones,
  trailers, fuel trucks, ladders and objects labelled "obstacle". A detection is a box the detector draws around an
  object.
- **From the tracker:** the aircraft track (the same object followed from frame to frame): the arrival moment and the
  points the tracker follows on the aircraft, used to see whether it drove in.
- **From the video itself:** no pictures for this check.
- It runs on ordinary processors in production.

## How it decides, step by step

1. **Arrival and arrival stage.** The module starts on the tracker's arrival moment. There is an arrival stage if, before
   stopping, the aircraft moved smoothly for more than 3 seconds in a row: the points on it moved on average by at most
   50 pixels sideways and 5 pixels up or down from frame to frame.
2. **The nose wheel** is the largest nose wheel box overlapping the aircraft. It is chocked on a frame when a chock box
   touches the lower 40 % of the wheel box (slightly enlarged). When the wheel is not found, its last box is used.
3. **Pass** as soon as the wheel is chocked on more than 1 second of frames, with gaps under 2 seconds, within 30
   seconds after arrival.
4. At 30 seconds without that: **Fail**, or **Not observed** if something covered the wheel on 10 seconds of frames or
   more.
5. **Not observed** also when the nose wheel was never found; when it was not yet found at some moment of the first 35
   seconds and no chock was confirmed; when there was no arrival stage (checked before Pass, so a chocked wheel then
   also gives Not observed); or when the video ended before the 30 seconds were over.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Time after arrival to find the chock | 30 seconds | Later chocking gives Fail |
| Chocked frames that confirm it | more than 1 second, gaps under 2 seconds | Fewer: no Pass |
| Covered frames that make it Not observed | 10 seconds | Fewer: Fail instead of Not observed |
| Zone of the wheel a chock must touch | the lower 40 % of the slightly enlarged wheel box | Smaller: fewer chocks found |

These values are written in the code, not in the settings file.

## What it reports

- "Nose wheel chocks are applied immediately." or "Nose wheel chocks are not applied immediately within 30 seconds after
  stopping the aircraft.", with times.
- Not observed names the reason, for example "Nose wheel is not detected or there is an obstacle" or "No arrival stage".
- A timeline entry (the stretch of video the website marks) from 10 seconds before to 30 seconds after the arrival; its
  start and end are stored as text.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this
check. The module was right on 62 (91 %). Only 1 turnaround was labelled Fail, and the module caught it; with a single
Fail label the number cannot show whether the check catches violations. All 6 wrong verdicts were on turnarounds
labelled Pass or Not observed. Our sources do not say which turnarounds were wrong, or why.

## Known problems

- **The window starts late.** The 30 seconds start at the tracker's arrival moment, about 4 seconds after the stop, not
  at the stop itself.
- **A hidden nose wheel is checked at its old place,** because its last box is reused.
- **A rule that almost never fires (looks like a bug).** A rule meant to give Not observed when the nose wheel stays
  unseen for more than 5 seconds checks whether the arrival came within the first 30 seconds of the video, so it can
  only fire for such videos. "Within 30 seconds after the arrival" was probably meant (to confirm).
- **Exact frames.** The module starts on the exact frame the tracker marks as the arrival; if that frame is missing from
  the data, it never starts.
- **Who confirms:** the points marked "to confirm" are for the module's owner (to assign) to check on a labelled
  turnaround. Changes that would change a verdict the client sees are decided with the client's safety team.

## In real time

This check needs nothing from the future: it decides within 30 seconds of the arrival. But the module that computes it
reads the whole turnaround first, for its other checks, so the module as a whole cannot run in real time as it is. The
team rates it "needs a small patch": take the moments of arrival, departure and "pushback attached" from the stage
detector (the part that knows where in the turnaround we are). Cost on the team's test machine, one 36-minute
turnaround: the reading-ahead pass alone, with its share of the General Model and the tracker, needs 46.1 milliseconds of
the 125 milliseconds each frame may take at 8 frames per second (37 %).

## For developers

- **Module code in our workspace:** M02A. Task key in the monthly report: `aircraftchockfront`.
- **Repository:** `dxgat/detectors/aircraft-chocks`; production line `master` @ `fa00478` (2026-01-30). The module
  returns three lists (verdicts, reports, timelines) in the order M02A, M02B, M02C.
- **Code:** `FrontWheel` (nose rules); nose wheel `main.py:953-1060, 1615-1626, 1715-1749`; `installed_no` `:970`;
  M02A verdict `:1139-1211`; arrival, departure, arrival stage `:1431-1485` (> 24 frames with mean optical-flow shift
  ≤ 50 px across, ≤ 5 px vertically); nose chock zone `y1 + 0.6·h` with `add_offset` 0.2; nose rules 30 s / 1 s / 10 s
  / 35 s in code.
- **Run on one turnaround:** `python main.py --source <video>.mp4 --weights-dir weights --inferences-dir <folder>
  [--device cpu] [--write-video]`.
- **Real time:** verdict PATCH in `docs/04_modules.md`; group B in `docs/analysis/rt_module_selection.md`.
- **Sources:** `docs/modules/aircraft-chocks.md`, `docs/analysis/module_review_2026-10.md`, `docs/05_module_logic.md`.
