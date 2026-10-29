# Stage detector

The stage detector is the part that knows where in the turnaround we are. A turnaround is split into stages (parts of
the turnaround): before the aircraft arrives, arrival, after the aircraft stops, unloading, loading, before departure,
and departure and pushback. The stage detector reads the tracker's output frame by frame (a frame is one picture of the
video; the cameras take 8 per second) and announces the key moments as they happen: the aircraft stopped, a belt loader
reached a cargo door, the last belt loader left, the pushback tractor was attached, the aircraft started to leave. Real
time needs it: it decides which checks run at each moment and gives every check the same moments. Today it exists as a
design, a placeholder and a few pieces of code, not as working software.

## Status

| | |
|---|---|
| In production | No. In post-processing (after the turnaround) checks take the arrival and departure from the tracker or work them out, and find other moments themselves. The real-time worker has a placeholder that replays one recorded turnaround's timeline |
| Last change | October 2026: the real-time worker got its stage detector step, still the placeholder. September 2026: the work was planned in detail; the first events taken from the tracker output exist in the project's code |
| Next step | Write the rules as a table, run them on recorded tracker output, compare with production and with labelled turnarounds, then put them into the real-time worker |
| Who looks after it | Maksym Chernyshev (owner of the architecture) |

## What it does

- **Gating.** Only the checks of the current stage run: 4 to 9 at a time instead of all 27 modules on every frame. In a study
  of August 2026, time windows alone saved 73–76 % of the frames the checks process, with no risk of missing anything.
- **One owner of the moments.** Every check takes the arrival, the departure, the belt loader moments and the pushback
  attachment from the same place, instead of working them out itself.
- **Every frame carries** the current stage, the events that fired on it (almost always none) and the moments of
  earlier events. A check that looks back runs from the start of its stage and reports at its end; no video is replayed.
- **Only the past.** It decides from frames already seen and never waits for the end of the recording.
- **Not its job:** the expected arrival and departure times from the flight schedule.
- **In the real-time worker** this step also runs the main detector of the General Model, our aircraft's track (the
  aircraft followed from frame to frame), the camera type, the aircraft type and the airline. Checks that belong before
  the arrival run from the start; all others wait until the stage and the aircraft type are known. When the aircraft
  arrives, the previous 10 minutes are not run through the checks again.

## What it finds

**Stages**

| Stage | Starts when | Notes |
|---|---|---|
| Before the aircraft arrives | the recording starts | |
| Arrival | our aircraft comes into view and drives in | the August study used the first frame of our aircraft's track |
| After the aircraft stops | the aircraft stopped | |
| Unloading | a belt loader stands at a cargo door | not yet built for the wing camera |
| Loading | (no reliable signal yet) | in 62 of 94 studied turnarounds the belt loader never leaves between unloading and loading |
| Before departure | the last belt loader left | with no belt loader, counted from the stop |
| Departure and pushback | the aircraft started to leave | ends 60 seconds later |

When the view does not allow a decision (for example, a camera looking into a vehicle cabin for 18 minutes) the answer
must be "undetermined", not "absent".

**Events**

| Event | What happens at the gate | Rule in the design | Known |
|---|---|---|---|
| Aircraft stopped (arrival) | our aircraft parks | the tracker's arrival: stopped for more than 4 seconds at full height, dated back to the start of the stop | about 7 seconds after it comes to rest |
| Belt loader at the door | a belt loader parks against a cargo door | its box overlaps the aircraft's by more than 20 % and it is stopped; the tracker today uses door boxes instead (which one is still to decide) | with the door rule, at least 4 seconds after it comes to rest |
| Belt loader left | the last belt loader drives away | the belt loader labelled at a door starts moving, or its track ends | about 2 seconds after it starts to move |
| Pushback attached | the tractor is connected to the nose wheel | the nose geometry fits and the pushback tractor's box stands still for some seconds (the number is still to fix) | not measured yet |
| Aircraft started to leave (departure) | the pushback begins | the tracker's departure: 10 seconds of motion | at the earliest about 12 seconds after it starts to move |

Around these: the start and end of the session (one turnaround on one camera), the departure plus 60 seconds, and two
deadlines counted from the arrival: 30 seconds (nose wheel chock placed immediately) and 4 minutes (steering bypass pin).

## How it works, step by step (the design)

1. Start in "before the aircraft arrives".
2. When our aircraft comes into view and drives in, move to "arrival".
3. When the tracker confirms the arrival, fire "aircraft stopped", dated to the start of the stop; move to "after the
   aircraft stops" and start the 30-second and 4-minute deadlines.
4. When a stopped belt loader stands at a door, fire "belt loader at the door" for that belt loader; move to
   "unloading".
5. When the last labelled belt loader drives away or its track ends, fire "belt loader left"; move to "before
   departure".
6. Within that stage, fire "pushback attached" when the nose geometry fits and the tractor stands still long enough.
7. When the tracker confirms the departure, fire "aircraft started to leave"; stay in "departure and pushback" for 60
   seconds.
8. With every decision, store the frame and the signal that fired, so "why was this stage missed?" has a number as its
   answer; tell the worker which checks to start and stop.

## How fast it is and what it costs

- The rules read only the tracker's and the General Model's output, not the pictures; their own cost is not measured
  yet.
- In the real-time worker the stage detector step also runs the main detector (8.5 milliseconds per frame on our test
  machine) and the aircraft part of the tracker (4.0 milliseconds), out of a budget of 125 milliseconds per frame.
- An alert can never come before its event. The arrival is known about 7 seconds after the aircraft comes to rest (the
  design said 4 seconds; the tracker first needs 3 seconds to call the aircraft stopped), the departure about 12 seconds
  after it starts to move. In a test run on recorded video the arrival came out 7.5 seconds after its frame. The
  worker's design sends video in pieces of 30 frames (3.75 seconds), which can add up to 3.75 seconds more.

## How good it is

There is no complete stage detector yet, so no overall measurement. Pieces measured so far:

- **Events from the tracker output** (arrival, belt loader at the door, belt loader left): the same frames as
  production on one full recording: arrival at 7 minutes 39 seconds, a belt loader at the front door from 20 minutes 36
  seconds to 47 minutes 27 seconds.
- **Pushback attached** with the nose rule of the aircraft wheel chocks check: the production moment on 5 of 7
  recordings. On the other 2, production uses a rule that needs the whole recording (the usual position of the pushback
  tractor), and the new rule fires 23 and 2 seconds earlier.
- **The August 2026 study** of 88 labelled turnarounds found these blockers:
  - departure: a rule waiting for the aircraft box to shrink by 18 % saw only 3.2 % in a real departure, giving 9 false
    "absent"; the drop of the aircraft parts' heights below the presence threshold already works for the arrival;
  - a broken view must give "undetermined";
  - several turnarounds in one recording get stitched together;
  - wing camera: the belt loader logic is missing, so unloading and loading are always "undetermined";
  - jets: coverage never checked;
  - loading cannot be told from unloading in 62 of 94 recordings.
- **The real-time placeholder** fits one labelled turnaround only, because it replays that turnaround's timeline:
  arrival 9 minutes 39 seconds into the recording; 3 seconds later camera "cone", aircraft "jet", airline "united
  express"; departure at 1 hour 12 minutes 41 seconds; no belt loader events, because there the belt loader is behind
  the aircraft. It writes only two stages ("arrival" and "departure") and two events, and fixed boxes for people, cones
  and, between arrival and departure, the aircraft and other objects at the stand.

## Which checks depend on it

In the real-time plan, 11 checks run as they are (with gating and an end-of-session marker), 2 after a change to use
stage events, 9 after lightening; 5 stay out of real time (hand signals, safety zone, both walk-arounds, hair policy).

| Event | Checks that need it |
|---|---|
| Aircraft stopped | chocks and cones before arrival, crew present before arrival, lead marshaller and wing walkers, foreign object debris walk, safety huddle (decide at it); cargo doors (deadline after it); nose wheel chock placed (30 seconds); steering bypass pin (4 minutes); conditioned air (opens at it, to keep the whole hose history) |
| Belt loader at the door | three-stop brake check (decides when the belt loader stops at the aircraft); belt loader rear cone |
| Belt loader left | cones removed after service vehicles clear (from it to the departure); pushback path (opens at it) |
| Pushback attached | main gear and nose wheel chocks removed only after the pushback is attached; the pushback driver's pin check |
| Pushback moving, departure | pushback waits for wing walkers; wing walkers during pushback; belt loader forward chock; pushback path; conditioned air |
| End of the session | cones placed on time, conditioned air, pushback waits for wing walkers (today they read the recording's length) |

Moments of single objects (a service vehicle stopping, a worker leaving a belt loader) stay inside the checks for now.

## Known problems: why one owner matters

Today the same moments are worked out in many places, and every copy drifts:

- **Arrival.** The tracker's arrival and the General Model's own stop moment differ by about 7 seconds. Nine checks
  repeat the tracker's arrival-stage rules from its motion points with one copied block (the safety zone check holds it
  twice). Seven checks decide the arrival from the "stopped" state with their own waiting times (5 seconds in one, 60 in
  another) and seven the departure from "moving", waiting from no time at all to 30 seconds. Four checks compare frame
  numbers directly with the arrival or departure frame (three test for equality), which breaks when a frame is lost.
- **"Before arrival"** has different lengths: at least 30 seconds in the General Model, 60 seconds in the tracker and the
  nine copies, and 90 frames (11.25 seconds) in a shared helper of four checks whose comment says 90 seconds.
- **Belt loader at the door** has at least five local versions (overlap with the aircraft, door labels, a stop inside
  the workers' area, own speed rules, own in and out thresholds). Two checks recompute the aircraft type. Two compute
  "pushback attached" in a second pass over the whole recording, which real time cannot do.
- **Which aircraft is ours.** Without the whole recording, choosing "the longest aircraft track so far" can pick a
  neighbour or a passing aircraft, and 4 seconds of it standing still are enough for the tracker to declare an arrival.
  In a replay of 21 test turnarounds this changed 36 check verdicts (Pass, Fail or Not observed) on 10 turnarounds and
  moved the arrival by more than 4 seconds on 14 of 15, by up to 23 minutes; accuracy against the labels fell from 86.7 %
  to 83.8 %. The fix belongs to the owner of the turnaround: moments that can be reset when a new aircraft arrives after
  a departure, and the stand's geometry to tell our aircraft from a neighbour.
- **The placeholder** detects nothing: it writes one recorded turnaround's timeline, and only on that turnaround's clock.

## What changes next

1. Write the rules as a table (signal, rule, delay, how it fails), reusing the August study.
2. Run them on recorded tracker output, production files first, storing the evidence of each decision.
3. Fix the departure with the part-height signal; answer "undetermined" for a broken view.
4. Build the gating table for the real-time checks and show that gated checks give the same verdicts as checks that run
   all the time.
5. Put it into the real-time worker and measure each event's delay.

**Done when:** every event fires within its stated delay and never from later frames (cutting the stream at any frame
changes nothing before it); arrival and departure equal the production tracker's within 1 frame on the 90 test
recordings, or every difference is explained; stage boundaries on the 88 labelled turnarounds are at least as good as
in the August study; "pushback attached" is checked against the two checks that compute it today; gated and always-on
checks agree on 10 turnarounds; every event's delay is reported.

**Decisions needed:** loading when the belt loader does not leave (keep "undetermined", or add a signal such as cargo
doors or carts); where turnaround boundaries come from when one recording holds several (the camera box or the
detector); which "belt loader at the door" to keep; whether the stage detector owns the resettable moments and the
stand geometry.

## For developers

- Task PF-Q1-03 (Maksym Ch., todo; for the real-time alerts MVP PF-Q2-07); branch `pf/q1-03-stage-detector`; code
  `pf/stage/`; interfaces ADR-004. Stages `PRE_ARRIVAL`, `ARRIVAL`, `POST_ARRIVAL`, `DOWNLOAD`, `UPLOAD`,
  `PRE_DEPARTURE`, `DEPARTURE`, `END`, `undetermined`; events `T_ARR`, `BL_AT_DOOR`, `BL_LEAVE`, `PUSHBACK_ATTACHED`,
  `T_DEP`; frame fields `stage`, `events`, `anchors`.
- Pieces: `pf/tracker/events.py`, `pf/stage/pushback.py`, `scripts/stream_pipeline.py`; results
  `docs/analysis/stage/events_DjwtQRdZyt0sSk_production_vs_gmv2_trackerv2.json` (T_ARR 3669, BL_AT_DOOR 9888, BL_LEAVE
  22776), `pushback_attached_atlc5.json` (−183, −18 frames).
- Real-time worker `dxgat/detectors/realtime-pipeline` @ `8cd6e62`: `stage_detector.py`, `turn_ground_truth.py`
  (ZZqfaRUYiTRAMA.mp4), `stage_server.py`, `module_rules.json`, `frame_record.py`.
- Tracker rules `cv_common/transport.py` (32 and 80 frames), `local_utils/bl_utils.py`. Module copies
  `docs/analysis/module_consumption.md` §2.4; `prearrival_min_frames` 90 in M03, M06, M11, M18
  (`docs/analysis/module_review_2026-10.md`).
- Study `G:\gat_stages` (`STAGE_BOUNDARIES.md`, labels `gt_dataset.tsv`). Sources `docs/02_target_architecture.md`
  §5, `docs/analysis/rt_module_selection.md`, `streaming_v0.md`, `rt_module_cost.md` §7, `realtime_pipeline_alignment.md`.
