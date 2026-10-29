# Nose wheel chock removed from aircraft

*In plain words: nose wheel chock removed only after the pushback is attached.*

> Chocks are the wedges the ground crew puts against an aircraft's wheels so that it cannot roll. This check asks that
> the nose wheel chock comes off only after the pushback tug (the vehicle that pushes the aircraft back from the gate) is
> attached. The client places it in the departure stage, when the tow bar is disconnected. The software finds the nose
> wheel, the chocks and the tug in the boxes of the General Model (the shared detector). The same module also gives two
> other checks of the client: *Nose gear chocks applied immediately* and *Main gear chocks removed only after aircraft is
> attached to pushback*.

## Status

| | |
|---|---|
| How accurate it is | 60 of 68 turnarounds correct (88 %) on the monthly test |
| Fail turnarounds it caught | 0 of 1 |
| In production | the version of January 2026 |
| Who looks after it | to assign |
| Biggest open problem | The check never sees a removal: it passes when the chock is still there after the tug is attached, and the client's Fail for a video that ends before the removal is missing. |

## What the client wants

A verdict is the answer of a check: Pass, Fail or Not observed.

| Verdict | When |
|---|---|
| Pass | The nose wheel chocks were removed only after the aircraft was attached to the tug. |
| Fail | The nose wheel chocks were removed before the attachment, or the video stops before the removal can be seen. |
| Not observed | The aircraft or the nose wheel was not detected, or something stood in the way. |
| Not observed, view blocked | All frames were blocked. |

The client's sheet marks this check as ready for production and puts it in its real-time group (checks wanted while the
turnaround happens).

## When and where it looks

From the moment the tug is attached until the departure the tracker marks (after about 10 seconds of movement). The
stages are the time before departure and the departure with the pushback. It runs on the cone camera (the camera that
looks towards the aircraft nose) for aircraft and jets. The code does not check which camera filmed the video.

## What it looks at

- **From the General Model:** nose wheels, chocks (from a separate chock detector), the aircraft nose and the tug; as
  things in the way, cones, trailers, fuel trucks, ladders and objects labelled "obstacle". A detection is a box the
  detector draws around an object.
- **From the tracker:** the aircraft track (the same object followed from frame to frame): arrival and departure.
- **From the video itself:** no pictures for this check.
- It runs on ordinary processors in production.

## How it decides, step by step

1. **Reading ahead for the tug.** Before the real work the module reads the General Model's boxes up to the departure
   (or the end of the video) and keeps the biggest pushback box of each frame. The middle position (median) of the boxes
   seen from 120 to 60 seconds before the departure is the tug's final position, where it stood while attached. This
   needs boxes on more than 1 second of frames in that minute; otherwise there is no final position.
2. **Tug attached.** On each frame, a pushback box that overlaps the final position by more than 80 % (shared area
   divided by the area both boxes cover) adds one to a counter; a frame without one takes one off. Past 5 seconds of
   frames, the tug is attached. Without a final position, a tug next to the nose and less than 0.3 aircraft heights
   below the aircraft counts instead; this backup counter never goes down.
3. **The nose wheel** is the largest nose wheel box overlapping the aircraft; a chock counts when its box touches the
   lower 40 % of the wheel box (slightly enlarged). When the wheel is not found, its last box is used.
4. After the attachment: if the nose chock is still seen (for more than 3 seconds, gaps under 2 seconds), it counts as
   removed after the attachment: **Pass**.
5. If it has been missing for more than 5 seconds while nothing covered the wheel, and is not seen again before the
   departure: **Fail**.
6. **Not observed** when the tug's final position covers more than half of where the nose wheel stood before the
   attachment, when the tug is never attached, or when the nose wheel was never found.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Chock seen after the attachment | more than 3 seconds, gaps under 2 seconds | Pass |
| Chock missing while the wheel is visible | more than 5 seconds | Fail |
| Tug covering the nose wheel's place | more than half | Not observed |
| Tug rules | final position from 120 to 60 seconds before departure; overlap over 80 %; 5 seconds net | When the tug counts as attached |

These values are written in the code, not in the settings file.

## What it reports

- "Nose wheel chocks are removed after aircraft is attached to pushback." or "… removed before aircraft is attached to
  pushback."
- Not observed names the reason, for example "No visible pushback attached" or "Chock removal could not be visually
  confirmed because pushback obstructed the wheel."
- A timeline entry (the stretch of video the website marks) 10 seconds either side of the decision moment; its start and
  end are stored as text.

## How accurate it is

The monthly test is the set of the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this
check. The module was right on 60 (88 %). The single turnaround labelled Fail was missed; 7 more wrong verdicts were on
turnarounds labelled Pass or Not observed. One Fail label cannot show whether the check catches violations. Our sources
do not say which turnarounds were wrong, or why.

## Known problems

- **The removal is never seen.** Pass means "the chock was still seen after the attachment". The rule also gives Fail
  when the video stops before the removal can be seen; that case is missing, so a chock still visible at the end gives
  Pass.
- **Wrong time on a Fail.** The reported time is the last frame without a chock (near the departure), not the moment the
  chock disappeared.
- **The tug can be confused.** Obstacles can spoil the attachment test, or another tug or vehicle can be taken for it
  (known from the team's notes on the module). The backup test next to the nose never counts down, so short false
  sightings add up.
- **A hidden nose wheel is checked at its old place,** because its last box is reused.
- **Exact frames.** The module stops on the exact departure frame the tracker marks; if that frame is missing from the
  data, it never stops.
- **Who confirms:** changes that would change a verdict the client sees are decided with the client's safety team.

## In real time

Not as it is. The module reads the whole turnaround first to find the tug's final position; in real time the earlier
frames are gone. The team rates it "needs a small patch": take the moment "pushback attached" from the stage detector
(the part that knows where in the turnaround we are). In a test version fed with a live "pushback attached" moment, the
moment this check uses moved earlier by 7 to 444 seconds, so its verdicts have to be measured again before it runs in
real time. Cost on the team's test machine, one 36-minute turnaround: the reading-ahead pass alone, with its share of
the General Model and the tracker, needs 46.1 milliseconds of the 125 milliseconds each frame may take at 8 frames per
second (37 %).

## For developers

- **Module code in our workspace:** M02C. Task key in the monthly report: `nose_wheel_chock`.
- **Repository:** `dxgat/detectors/aircraft-chocks`; production line `master` @ `fa00478` (2026-01-30). The module
  returns three lists (verdicts, reports, timelines) in the order M02A, M02B, M02C.
- **Code:** first pass `main.py:1240-1286`; pushback attached `:1523-1549`; nose wheel `:953-1060, 1615-1626,
  1715-1749`; M02C verdict `:1139-1211`; pushback-cover rule `:1760-1763`; `get_aircraft_report`. Nose rules 3 s / 5 s
  in code; pushback window `deque(maxlen=120*fps)`, first half, > 8 boxes, IoU 0.8, > 40 frames; nose fallback 0.3
  aircraft heights.
- **Real time:** verdict PATCH in `docs/04_modules.md` (`main_stream.py`; M02C anchor −7 to −444 s); group B in
  `docs/analysis/rt_module_selection.md`.
- **Sources:** `docs/modules/aircraft-chocks.md`, `docs/analysis/module_review_2026-10.md`, `docs/05_module_logic.md`.
