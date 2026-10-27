# Can one graphics card run the checks while the turnaround happens?

*September to October 2026 · Valentyn (the prototype); the team's real-time worker is maintained by Maksym Chernyshev ·
Status: in progress. Three checks run live in the prototype; the stage detector, the alert service, the second camera
and most checks are not wired in yet*

## In short

Our prototype takes the camera's video frame by frame, runs the General Model, the tracker and three checks on one
desktop graphics card, and sends each verdict **about one second after the frame that decided it** (0.80 to 1.16
seconds). A frame costs **73 milliseconds of the 125** it may take, and the three checks kept their verdicts and
reports. Most of that second is the tracker holding its results for 6 frames to confirm new people; a switch to
answer at once exists but is not tested yet. The team's real-time worker runs the same General Model and tracker code,
split into containers on one shared card; its own extra costs are how it passes pictures between containers and how
long it waits for each piece of video.

## The question

A **frame** is one picture of the video; the cameras take 8 per second, so a live system has 125 milliseconds for each.
A **track** is the same object followed from frame to frame; a **verdict** is Pass, Fail or Not observed; a **stage** is
a part of the turnaround; **service vehicles** are the ground support equipment (tugs, belt loaders, fuel trucks,
tractors). Can the shared parts and the checks keep up with the camera on one graphics card, how soon after the deciding
moment does a verdict leave the system, and what is still missing?

## What we did

1. Built the chain in our workspace: a receiver that puts frames in order, fills lost pieces with placeholder frames and
   keeps each frame's absolute number; one video decoder; the rebuilt General Model with its three detector parts
   working side by side; the corrected rows (the aircraft and "view is blocked" rows, worked out from past frames only);
   the rebuilt tracker, one per turnaround; and the production modules, unchanged. Two of them run in their own
   processes and get only the data they declare; the third runs inside the main program with the full data.
2. Ran it at real-time speed on the 10.5 minutes of a 36-minute turnaround where three checks decide: the three-stop
   brake check, pushback path clear of obstacles, and pushback waits until the wing walkers are in place and ready.
   Frames were sent one by one over an emulated link of 10 megabits per second, on a quiet machine.

## What we found

### What each step costs

| Step | What it does | Time |
|---|---|---|
| Link | carries a frame from the camera | 0.060 seconds (waiting for 3.75-second pieces would cost 1.94 seconds) |
| Receiver | orders frames, fills gaps, keeps absolute frame numbers | 0.008 seconds of queue |
| Decoder | turns the video into pictures, in its own thread beside the main loop | 4.3 milliseconds |
| General Model | three detector parts side by side | 28.4 milliseconds |
| Corrected rows | aircraft and view-blocker rows from past frames only | 0.15 milliseconds |
| Tracker | follows aircraft, belt loaders, service vehicles and people | 42.0 milliseconds |
| Hand-over | data for the two checks in their own processes | 0.174 milliseconds; each check's own work 0.61 |
| **Main loop, whole frame** | | **73.3 milliseconds of 125** |

An earlier run of the same stretch, without the trimmed data described below, took 64.6 milliseconds per frame. The
General Model and the tracker, untouched in between, were about 20 % slower in the later run: noise from other work on
a shared desktop, not the change. The decisive minutes are also the expensive ones: on the quiet first 7 minutes of the
same turnaround a frame cost 44 milliseconds, so timing a budget on quiet footage underestimates it by about a third.

### How fast a verdict arrives

- A frame is processed 0.13 seconds after the camera saw it.
- The tracker publishes each frame's results 6 frames (0.75 seconds) late. When it confirms a new person it adds that
  person back into the frames it is still holding, so a worker is present from the first frame they appear. Around the
  arrival it also holds the aircraft's records until the arrival moment is final.
- The check needs about 0.6 milliseconds, and its verdict leaves the moment it is produced: to a file, a live web page,
  and (not wired yet) a message to the alert service. A slow receiver never holds up the frames.
- Measured: **0.80 to 1.16 seconds** after the deciding frame. On the whole turnaround with 3.75-second pieces instead of
  single frames, frames were processed 3 seconds after the camera saw them (median) and verdicts came 3.7 to 4.6
  seconds after the deciding frame.
- A switch lets the tracker publish at once. For checks that read no people nothing changes except the time (about 0.15
  seconds instead of 1); for checks that read workers a worker can appear up to 1 second later than in post-processing,
  so it needs a verdict check first. Not run yet.

### The verdicts, and what each check is given

| Check | Earlier run | Run with trimmed data | Report |
|---|---|---|---|
| Three-stop brake check (inside the main program, full data) | Not observed | Not observed | identical |
| Pushback path clear of obstacles (own process, declared data only) | Pass | Pass | identical |
| Pushback waits until the wing walkers are in place and ready (own process, declared data only) | Fail | Fail | identical |

The three-stop result is Not observed because the belt loader stopped before the 10.5-minute stretch began; on the
whole turnaround it is Fail, as in post-processing. The two pushback checks match post-processing of the whole turnaround.

A frame's data averages 13.5 kilobytes; a check given only what it declares gets 1.6 to 2.6 kilobytes. 76 % of the data
is the tracker's internal point data, which these checks do not read (some other checks do, to work out the arrival
themselves). Handing frames to the two separate checks went from 0.791 to 0.174 milliseconds per frame. The machine does
not feel this saving; what matters is that a check with a small, declared input can live in another process, container
or machine.

### What is not there yet

- **The stage detector.** The rules for when each check opens and closes are written, but nothing publishes the arrival,
  the belt loader leaving or the pushback attached yet, so every check runs from the first frame. The first run with the
  rules on starved every check: none ever opened. They are now off by default.
- **The alert service.** The sending side exists; the receiving end does not.
- **The second camera.** One run is one camera; the wing camera is a second copy of the same.
- **Most checks.** 3 of 11 candidates run; the video-reading checks need the shared picture buffer tested on a real run.

### What it would take on production hardware

For ten checks that do not read the video, the shared part per frame:

| | Standard detector runtime | Faster detector runtime |
|---|---|---|
| Test machine's card | 52.8 milliseconds | 43.6 milliseconds |
| A card like production's (detector 3 times slower, emulated) | 89.3 milliseconds | 60.2 milliseconds |
| Same, and the tracker also 3 times slower (the pessimistic case) | 144 milliseconds: falls behind | 114.9 milliseconds: keeps up |

With the faster runtime the tracker costs 2.7 times the General Model. Its biggest parts are the belt loader path (9.6
milliseconds, mostly a model that outlines each belt loader on every frame), three identity updates (8.3), the aircraft
path (4.0), the service vehicle path (2.4) and a noise check (2.3). So the next savings are in the tracker.

### The team's real-time worker

- **What it is.** One deployment that stays up. Its containers (separately packaged programs) share one graphics card in
  turns: intake (decoding), stage detector (main detector, aircraft track, belt loader arrival and leave, camera type,
  aircraft type, airline), General Model (only chocks, vehicles and view-blocker rows), trackers (people, belt loaders,
  service vehicles; the aircraft track is copied from the stage detector) and modules (a verdict only). The version of 6
  October adds an exit container that writes the box files, the alert picture and the messages that update the
  turnaround's records.
- **Same code.** Its General Model and tracker files are ours, copied unchanged except for import lines, so every
  measurement here applies to it. Two copies can drift apart; whether to share one package is open with Maksym.
- **The split helps.** By our measurements the same work comes to about 45 of 125 milliseconds there, because the
  aircraft is tracked once. The stage detector owning the aircraft is also the right place to decide which aircraft
  belongs to the turnaround, the cause of the live accuracy loss (see the report *Which checks can run in real time, and
  what does each one cost?*).
- **Its own costs.** Pictures travel between containers as compressed images inside text messages: 2.7 milliseconds to
  pack, 3.6 to unpack in each of three containers, about 13.5 milliseconds per frame here and about 22 on a production
  processor core. Our hand-over through shared memory costs 5 to 7 milliseconds for twenty checks; containers on one
  machine can share memory too, so most of this cost could go.
- **Waiting for pieces.** The first version took 30-frame pieces (3.75 seconds) pushed by the camera, so a frame could
  wait up to 3.75 seconds before its piece was complete. The version of 6 October reads the one-minute files the camera
  uploads; by the same reasoning a frame can wait up to a minute (not measured).
- **Not enough processor.** Its General Model and tracker containers get one processor core each. The tracker alone
  needs about 60 milliseconds per frame on one fast core here, about 100 on a production core, and falls behind (see
  the report *Can the General Model and the tracker skip every second frame?*).
- **Stand-ins.** Its modules and stage detector are stand-ins today; ours can run an unchanged production module on live
  data, which is what it needs next.

## What it means

- On the test machine one graphics card carries the shared parts and three checks with room to spare, and a verdict
  about one second after the deciding moment is real. Most of that second is a deliberate confirmation delay that can be
  shortened for checks that do not read people.
- For production the limits are processor cores and the slower card, not the checks.
- The worker can use everything measured here directly. Its cheapest wins: shared memory for pictures, two cores for
  the tracker, the faster detector runtime.

## What is next

1. Measure "publish at once" against the post-processing verdicts.
2. When the stage detector publishes its moments, switch the open-and-close rules on for one check and compare.
3. Check the trimmed data on all 69 turnarounds of the monthly test before it becomes the default; add the video-reading
   checks; connect the alert service when it exists.
4. In the worker: time each container on one of our turnarounds, replace a stand-in module with a real one and compare
   its verdict with post-processing, and close the verdict check for the faster runtime.

## For developers

- Tasks PF-Q2-13 (components: declared inputs, gates, `OutputBus`), PF-Q1-19 (prototype), PF-Q2-02 (branch;
  whole-event chunk run on the board: 64 ms, frame p50 3.0 s, verdicts 3.7–4.6 s), PF-Q1-17 (`TrackerOptions.publish_delay`),
  PF-Q1-03 (stage events), PF-Q3-01 (alert service, Aryan), PF-Q4-02 (worker). ADR-004.
- Docs: `docs/11_rt_dataflow.md` (run `slice_comp2`, frames 6 961–12 007 of `zHxIAF2vUGxJ`), `tasks/notes/PF-Q2-13.md`
  (`slice_clean` 64.6 ms vs `slice_comp2` 73.3 ms), `docs/analysis/rt_optimisation_plan.md` (ten levers),
  `docs/analysis/realtime_pipeline_alignment.md`.
- Code: `pf/rt/component.py`, `pf/rt/module_host.py`, `pf/rt/gating.json` (`Gate(spec, enabled=False)`),
  `pf/rt/prod_module.py`, `pf/pipeline/causal_rows.py`, `http_sink(url)`; run with `scripts/rt_watch.py --ingest frames
  --bandwidth-mbps 10 --subscriptions`; slices `scripts/rt_slices.py`.
- Worker: `external/realtime-pipeline` (clone @ 8cd6e62, 30-frame chunks; origin/main @ 7f10615 of 2026-10-06: 1-minute
  chunks from the bucket, exit container, Kafka messages). Hand-off `chain.py` base64 JPEG (q 62, 151 KB per frame).
  Our `pf/gm`, `pf/tracker` vendored as `general_model/`, `trackers/`.
- Faster runtime = TensorRT fp16 heads (`--provider tensorrt`); T4 emulated as heads 3× slower.
