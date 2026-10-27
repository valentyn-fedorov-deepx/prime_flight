# Can the General Model and the tracker process the video in pieces and give the same results?

*September 2026 · Yurii Luchko and Valentyn · Status: in progress. The rebuilt parts match production; a whole
turnaround on pieces, with the verdicts on its outputs, is next*

## In short

Today nothing starts until the camera's one-minute files are merged into one video of the whole turnaround, and the
General Model and the tracker both need that whole video: for example, the main aircraft is the one with the longest
track in the entire recording. We rebuilt both to work step by step while keeping four conditions: one tracker per
turnaround, absolute frame numbers, a version in every record, and the same video decoder on both sides of every
comparison. The rebuilt tracker writes **the same file as production's, line for line,** when the random choice of
points is fixed; the rebuilt General Model pairs **99.9 % of production's rows**, with differences only in the last
digits. On
the monthly test **851 of 858 verdicts** stayed the same (accuracy 86.7 % against 86.6 %). A first run on pieces kept up
at 1.9 times real time and set the arrival on production's frame.

## The question

A **frame** is one picture of the video (the cameras take 8 per second); a **detection** is a box the General Model
draws around an object; a **track** is the same object followed from frame to frame; a **verdict** is Pass, Fail or Not
observed.

Today the turnaround's files are merged first; then the General Model, the tracker and the checks run one after another,
and the answer arrives about 24 hours later. If the work starts on each piece as it arrives, nobody waits for the merge,
and the same code can later run live. A piece is only a way to carry the video: a check never knows about pieces. Can
the General Model and the tracker run piece by piece and still give production's results?

### Four conditions for doing it correctly

The team measured them on its test bench for video in pieces (a test set-up, not production):

1. **One tracker per turnaround, never restarted.** The tracker learns each object's identity over time. On the same
   video, one tracker from start to end found 5 aircraft; restarted every 60 seconds it found 42; every 7.5 seconds, 297.
2. **Absolute frame numbers, gaps filled.** Modules count frames by their position. If one 7.5-second piece is lost,
   every later frame is off by 60 frames (7.5 seconds), and a module waiting for "this is the departure frame" misses
   it. So every frame keeps its absolute number, and a lost piece is filled with placeholder frames.
3. **A version in every record.** Cloud storage holds 15 to 16 incompatible versions of results per video with no
   marker; today an incompatibility shows only when a module crashes.
4. **The same video decoder on both sides of a comparison.** Two common decoders read 22,791 and 22,800 frames from the
   same file when its timestamps are irregular.

The video stores a full picture every 3.75 seconds and only changes in between, so a piece is cut at full pictures: 7.5
seconds, copied without re-encoding (the last piece can be up to 11.25 seconds). A frame therefore has no fixed number
"inside its piece", only its absolute number. With 7.5-second pieces the delay from the camera to processing was 10.5
seconds, against 84 seconds with 60-second pieces. On the test bench, feeding pieces gave bit-identical results to the
whole video.

## What we did

- **General Model.** The same detectors and the same arithmetic, split into a core (one frame in, boxes out), a part
  that makes the turnaround-level decisions step by step and records the frame at which each was decided (main aircraft,
  aircraft type, camera, airline), and two outputs: the old file format, exactly, for the 27 modules, and a new frame
  record with a version number. Along the way we found that production runs a different version from the one the
  architecture review read. The decisive difference is the order of the colour channels fed to the detector: with the
  wrong order only 73 of 2,713 detections matched.
- **Tracker.** Production's tracker loop rebuilt as a step-by-step process, one per turnaround, around production's own
  code copied unchanged. Speed-ups that keep the output identical: one grey picture per frame, no full-picture copies, a
  faster noise estimate, grouped point-following, identity updates side by side. A new, lighter output without the
  tracker's internal point data, about 10 times smaller (57 megabytes instead of 597 for a 78-minute video). The stage
  moments (a stage is a part of the turnaround: arrival, departure, belt loader at the door and leaving, pushback
  attached) are worked out from its output.
- **Comparisons**, from cheap to expensive: boxes, the tracker file, stage moments, verdicts, the monthly test.
- **A first run on pieces**: both parts on 7.5-second pieces cut from a recorded video and fed one after another, with
  the aircraft and "view is blocked" rows worked out from past frames only.

## What we found

### The same results as production

| Level | What was compared | Result |
|---|---|---|
| Boxes | rebuilt against production General Model, one full production video (78 minutes) | 99.90 % of all rows paired (same class, boxes overlapping by at least half); 99.1 % within 2 pixels and 0.02 of score; 56 % identical to the last digit |
| Tracker file | rebuilt against production tracker on the same boxes, random choice of points fixed | identical: 1,200 of 1,200 lines on a busy 2.5-minute stretch; two whole videos of 36 and 38 minutes, every line |
| Stage moments | full video through both rebuilt parts, against production | the arrival, the belt loader arriving at and leaving the front cargo door, and the moment the tracker re-identified it: every frame identical |
| Verdicts | the 12 modules that never read pictures, on the rebuilt General Model's file with production's tracker file | 11 of 11 comparable: same verdict; 9 of 11 also identical timelines and reports |
| Monthly test | all modules, rebuilt inputs against production files, 69 turnarounds | 851 of 858 identical; accuracy 86.7 % against 86.6 % |

- The box differences are rounding noise of half-precision arithmetic on a different graphics card and software
  version, not logic; equality to the last digit across cards is not possible. The agreed criterion (at least 99.5 % of
  boxes paired, at least 97 % of frames within tolerance for each kind of row) was met. Only 85.5 % of frames have every
  row within tolerance, because one flickering small object fails a whole frame.
- Production's tracker picks points at random on every run, so even two production runs differ (in the internal point
  data on most lines, in movement counters on 0.2 % of objects). Fixing the same random choice on both sides is what
  makes a line-by-line comparison possible; only the line endings of the two files differ. Since the tracker's output is
  then identical, the rebuilt tracker cannot change a verdict on those videos.
- The three small differences at verdict level are one frame of a timeline's end, one second of a reported interval and
  one frame of a visibility count. The twelfth module failed on both sides because of a maths library version.
- On the first 4 complete turnarounds of the monthly test, 116 of 116 verdicts matched, with accuracy 88.8 % on both.

### Speed on the test machine

| Part | Milliseconds per frame |
|---|---|
| General Model, three detector parts one after another as production runs them · side by side, identical rows · faster runtime, tiny differences | 22.4 · 16.8 · 8.0 |
| General Model, whole turnaround including decoding | 28.3 (4.4 times faster than real time) |
| Tracker, the reviewed version · production's version (two 2.5-minute stretches) | 137 to 149 · 36 to 49 |
| Rebuilt tracker, plain · with the speed-ups (both measured under load) | 50.6 · 39.2 (−23 %) |

The reviewed tracker is slower than real time because it estimates the picture's noise over the full picture on every
frame (about 100 milliseconds); production does it every 2 seconds. The target for the rebuilt tracker, 15 milliseconds
per frame, is not reached yet.

### The first run on pieces

- 8 minutes 45 seconds of video in 7.5-second pieces, on a graphics card shared with other work: 65.2 milliseconds per
  frame, 1.9 times faster than real time.
- The arrival fired on production's frame (7 minutes 39 seconds into the video) and was published 7.5 seconds later,
  because the tracker holds the aircraft's records until the arrival is final.
- All 695 main-aircraft rows were there; on 6 % of them only the aircraft height written into the row differed (680
  pixels while running, 670 at the end).
- The "view is blocked" rows were identical from the moment the nose wheel was first known (8 minutes 13 seconds in).
  Before that the old file holds 2,563 such rows only because it applies the final wheel position to the whole video,
  from the fourth frame on. No live system can produce those.
- Pushback attached, on 7 production videos: on the 5 where production used the same rule, the same frame; on the 2
  where production looked ahead, about 23 and 2 seconds earlier.

## What it means

- The rebuilt parts can stand in for production without changing verdicts: proven line for line for the tracker,
  within rounding noise for the General Model, and confirmed by the monthly test.
- Working in pieces keeps up and finds the same moments. The one real difference is that the main aircraft must be
  chosen from the past only; on about one turnaround in six an earlier aircraft keeps that title too long and verdicts
  change (see the report *Which checks can run in real time, and what does each one cost?*). Deciding which aircraft
  belongs to the turnaround is the stage detector's job.
- *Later note (October 2026):* the files the monthly test calls production were written by a side branch of the General
  Model that still feeds the old colour order, like the April 2024 model; the deployed version feeds the other order.
  The rebuilt General Model ran in the matching set-up, so each pair is like for like, but the accuracy figures describe
  that older line and will be measured again (see the report *Which General Model version the monthly test compares
  against*). The comparison on the production videos of one gate was against the deployed version.

## What is next

1. A whole turnaround on pieces, with lost pieces simulated, and the verdicts on its outputs against post-processing.
2. Camera type and the arrival frame for the live path, and what fills a lost piece (empty frames or the last aircraft
   track): both need a decision.
3. The tracker under 15 milliseconds per frame; the remaining changes alter numbers slightly and must be judged by the
   verdicts.
4. Time to Result measured before and after.

## For developers

- Tasks PF-Q1-16 (GM v2, `pf/gm`), PF-Q1-17 (Tracker v2, `pf/tracker`), PF-Q1-18 (test set), PF-Q1-15 (measurement plan,
  levels L1–L3), PF-Q1-04 (`scripts/stream_pipeline.py`, `pf/pipeline/causal_rows.py`, `pf/tracker/events.py`,
  `pf/stage/pushback.py`); ADR-001 (one inference, v1-compat + v2 sinks), ADR-002 (camera type, `frame_stopped` in RT).
- Docs: `docs/analysis/gm_prod_delta.md` (production GM a0157a4, BGR→RGB, `DjwtQRdZyt0sSk` 37 530 frames),
  `l2_gate.md`, `streaming_v0.md`, `measurement_plan.md`, `gm_speed.md`, `gm_baseline_lineage.md` (test set "production"
  = GM 8576299, BGR lineage; v2 variant `entity_clip`), `docs/02_target_architecture.md` (X1–X4, stand `G:\gat-streaming`).
- Tracker proof: `scripts/tracker_v2_run.py --seed 0 --exact-fast` vs `scripts/tracker_v1_profile.py --pin prod --seed 0`
  (bd43c3c + cv_common 2759daf); `scripts/testset/tracker_exact_check.py` (`zHxIAF2vUGxJ`, `MwCSLbQ7QvXQ`; only CRLF / LF
  differ). Monthly result: `docs/analysis/rt_module_cost.md` section 6.
- GM parity `pf.eval.compare_gm_ndjson_tolerant` (IoU 0.5, ±2 px, ±0.02); verdicts `scripts/run_module.py --no-video`;
  lead-marshaller failed on NumPy 2 (`float()` of a one-element array).
