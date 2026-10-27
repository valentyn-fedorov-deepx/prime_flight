# One pose model instead of five for the checks that read body poses

*13–27 October 2026 · Valentyn and Yurii Luchko (task owners) · Status: in progress; the wing walkers check needs new
settings before anything goes to production*

## In short

Seven checks read people's poses, using four different pose models; the handrails check uses a fifth. We served all
seven with one model, the one the service vehicle chocks check already runs in production, without changing the checks'
code. On 66 of the 90 videos of the monthly test, correct verdicts went from **326 to 318 of 370**. All of the loss is in
one check, wing walkers during pushback (47 → 36 of 55); without it, correct verdicts rose from 279 to 282. The time
spent on poses fell by **55 %**, the seven checks' time by 13 %. In post-processing this saves only **about 1 %** of the
machine time, because pose work is a small part of the bill. It matters for real time: one pose call takes about **9
milliseconds instead of 60**. The wing walkers check is being recalibrated for the new model.

## The question

Words used on this page: a **frame** is one picture of the video (the cameras take 8 per second); a **verdict** is
Pass, Fail or Not observed; a **turnaround** is the whole servicing of an aircraft at the gate; the **monthly test** is
the set of the client's validated turnarounds we measure on, and a **label** is the client's verdict for one of them.

A pose model finds a person's joints in a picture: shoulders, elbows, wrists, hips, knees and ankles, 17 body points,
each with a score of how sure the model is (0 to 1). The checks use them to see, for example, whether a worker raises an
arm to signal or bends down at a wheel. Each check came with its own pose model: four different networks find the same
17 points. Can one model serve all of them, does any verdict change, and what does it
save?

### What runs today

| Check (short name used below) | Pose model today |
|---|---|
| Service vehicles guided to the aircraft with approved hand signals (hand signals) | the large model (63.6 million learned values), run twice per person: as is and mirrored |
| Steering bypass pin installed (steering pin) | the large model |
| Lead marshaller and wing walkers in position (lead marshaller) | the large model |
| Wing walkers in position with approved wands during pushback (wing walkers) | the large model |
| Pushback driver checks the steering bypass pin (pin check) | the pin model (43.3 million), run twice per person |
| Foreign object debris walk completed (debris walk) | the small model (6.3 million), one person at a time; only the order of the shoulders is read |
| Motorized service vehicles parked and chocked (vehicle chocks) | **the shared model** (27.6 million) |
| Handrails on service vehicles being used | the whole-body model (33.6 million; 133 points, with the hands) |

The handrails check needs the hands. The walk-around and safety vests checks use a pose model built into a detector and
were not part of this test.

## What we did

1. **Built one shared pose runner.** It cuts each person out exactly as the original pose library does (0 pixels of
   difference). It sends persons in fixed groups of four, because the graphics-card runtime spends about 30 milliseconds
   preparing again whenever the group size changes; filling the empty places changes no result (checked bit for bit).
2. **Plugged it in without touching the checks' code.** A small adapter, installed before the check starts, answers the
   three ways the checks call a pose model; the check's own model is not loaded.
3. **Compared the models on the same people:** 280 person boxes on 120 frames of one turnaround.
4. **Ran every check twice on the same inputs**, with its own model and with the shared one: first 38 runs on 8 videos,
   then the whole monthly test, which stopped after 66 of the 90 videos. Both runs read the same boxes of people and
   objects, made by the project's own version of the General Model (the shared detector), not production's: the
   comparison is fair, but the absolute numbers are not production's accuracy. The checks' own models, rerun, gave 38 of 38
   identical verdicts, so every change comes from the pose model.

## What we found

### Speed and agreement on the same people

| Model | Milliseconds per call (all persons of a frame) | Milliseconds per person |
|---|---|---|
| The large model, mirrored (today) | 42.2 | 18.1 |
| The pin model, mirrored (today) | 12.4 | 5.3 |
| **The shared model** | **8.9** | **3.8** |
| The whole-body model, body points | 13.9 | 6.0 |

The other models place the points within a median 1.3–1.5 % of the box height of the large model's, with 93–95 % of the
points (90–92 % of the arm points) within 10 %. Mirroring buys nothing measurable. On the debris walk's crops the small
and the shared model agree on the order of the shoulders (which tells whether a person faces the camera) in 74 % of 209
cases; front and back are the hard part for any pose model.

### First test: 38 runs on 8 videos

36 verdicts stayed the same and correct verdicts stayed at 32: one change towards the label (wing walkers, Fail → Pass)
and one away (pin check, Not observed → Pass). The whole-body model also kept 36, but both of its changes went against
the label (32 → 30), and its pose time was almost twice the shared model's (482 against 251 seconds). It stays in
handrails only.

### The whole monthly test: 66 of 90 videos

| Check | Correct verdicts, own → shared | Changed (towards / away from the label) | Check's time, own → shared (seconds) | Pose time (seconds) |
|---|---|---|---|---|
| Hand signals | 53 → 53 of 55 | 0 | 15 033 → 12 647 (−16 %) | 2 392 → 367 |
| Lead marshaller | 53 → 53 of 55 | 0 | 6 187 → 4 187 (−32 %) | 2 219 → 385 |
| Steering pin | 38 → 41 of 46 | 7 (5 / 2) | 3 439 → 1 489 (−57 %, partly because it finished earlier on some videos) | 1 889 → 171 |
| Pin check | 35 → 36 of 46 | 4 (2 / 1, 1 neither) | 4 730 → 4 901 (+4 %) | 284 → 167 |
| Vehicle chocks (same model, shared runner) | 47 → 47 of 56 | 2 (1 / 1) | 14 946 → 14 937 | 718 → 701 |
| Debris walk | 53 → 52 of 57 | 1 (0 / 1) | 5 004 → 5 769 (+15 %) | 2 781 → 3 473 |
| **Wing walkers** | **47 → 36 of 55** | **13 (1 / 12)** | 7 258 → 5 483 (−24 %) | 2 194 → 351 |
| **Total** | **326 → 318 of 370** (without wing walkers 279 → 282) | 27 | 56 597 → 49 414 (−13 %) | 12 477 → 5 614 (−55 %) |

The debris walk is the only check that gets slower: its small model is cheaper for one person at a time, and it calls
the pose model for every person in every frame before the aircraft arrives. If it keeps its own model, the pose time
falls by 78 % (9 696 → 2 141 seconds), the checks' time by 14 %, and every check except wing walkers keeps or gains
correct verdicts.

### Why only about 1 % in production, and why it still matters

The pose model runs inside the check jobs, so the General Model job does not change. On five production videos (21–22
October 2026) the five checks whose model would change take 105 of 2 181 machine minutes (5 %). With the share of each
job that faster pose calls saved here, the change saves about 21 minutes in total: **about 1 % of the machine time**,
0.5–7 minutes per video; up to about 2–3 % if the large model is relatively slower on production's graphics card than on
ours. The time to result does not move: the checks run in parallel and none of these is the slowest (hand signals 6–9
minutes per video; handrails 47–74 minutes, safety zone up to 51, safety vests up to 35).

The value lies elsewhere:
- **Real time.** While the turnaround happens, each frame has 125 milliseconds for everything: decoding, detection,
  tracking and all checks. One call of the large model took about 60 milliseconds, and four checks use it; the shared
  model takes about 9. One pose step per frame could serve all pose checks at once, after they agree on how to cut out a
  person and how to prepare the picture (today each check does both its own way).
- **Five networks become two.** One 110-megabyte file replaces the 269-megabyte file each of four checks loads, plus a
  178- and a 25-megabyte file. Two checks also carry an unused 255-megabyte copy of the large model.

### Wing walkers: why the check loses with the shared model

Wing walkers walk at the wing tips while the aircraft is pushed back, to keep the wings clear.

- All 12 losses come from the hand-signal rule. The walkers on both sides are found (from the paths they walk, without
  the pose), but with the shared model one of them "does not signal": 11 videos went Pass → Fail (label Pass), one Fail →
  Not observed (label Fail). In the one gain, the large model had missed a walker's signal.
- The rule: a frame counts as signalling when a wrist is less than 4.8–8 % of the person's box height below its elbow and
  both points score at least 0.2. Eight such frames (1 second) within the 60-second window are enough.
- The walkers are small: the median box is 57 pixels high, an arm about 10 pixels. Both models are unsure about the arms
  (median of the lower of the wrist and elbow scores: 0.21 for the large model, 0.19 for the shared one). The rule really
  asks whether the model ever puts a wrist at elbow height with some confidence for eight frames; the large model does so
  about twice as often (on one video, 19 % of the frames against 10 %), and the thresholds were set on it.
- Mirroring and the whole-body model do not help.
- The hand-signal part decides only one of the 11 videos labelled Fail; the other Fails come from a missing walker or a
  blocked side. 15 of the 55 videos do not depend on the pose at all.

**Fix in progress.** We record both models' arm points on the same walkers over the 40 videos that depend on the pose,
then replay the rule offline for any model and thresholds; on one video the replay already reproduces both recorded
verdicts. The target: the three settings (the score limit, the wrist-to-elbow margins, the minimum number of frames) that
make the shared model give the large model's verdicts on the 40 videos, win back the 11 Passes and keep the one
hand-signal Fail a Fail.

## What it means

- Every check except wing walkers keeps or gains correct verdicts (the debris walk if it keeps its own small model).
- A model change must not silently change what a verdict means, so every changed verdict goes to Oksana (accuracy
  validation) and Ihor (technical reviewer) before production. Nothing is in production yet.

## What is next

1. Finish the wing walkers recalibration; the new thresholds go to Oksana and Ihor with the table of verdicts. If none
   work, the wing walkers check keeps the large model.
2. Run the remaining 24 videos.
3. Roll out check by check: each check keeps its code and installs the adapter at its start.
4. Real time: one pose step per frame for all pose checks, once the cut-out and picture rules are common.

## For developers

- Models: large = HRNet-W48 COCO-17 (mmpose 1.3.1, flip test); pin = SimCC ResNet-50 (flip); small = MoveNet Thunder;
  shared = RTMPose-l body7 (the gse-chocks file); whole body = DWPose-l; walk-arounds, safety-vests: YOLOv8-pose. Crop
  offsets 0.1/0.1, 0.2/0.1, 0.25/0.1 or the raw box; CLAHE in hand-signals, lead-marshaller, wing-walkers; histogram
  equalisation in steering. Production estimate: per-job shares −13 / −47 / −31 / −26 / −3 % (§8).
- Modules: hand-signals; steering-by-pass-pin…; lead-marshaller… (`pre_arrival_departure`); wing-walkers…
  (`obstruction_hand_signals`); pin-verification; fod-walk-completed (`dev`); gse-chocks (`per_component_improvement`).
- Code: `pf/pose/topdown_onnx.py`, `pf/pose/shims.py`, `scripts/run_module.py --pose-override rtmpose-l` (control
  `--pose-timing`), `scripts/pose_bench.py`, `scripts/testset/pose_full_run.py`; summaries
  `out/pose/interim_summary3.json`, `out/testset/compare_pose_rtm_vs_pose_ctl_interim.json`. Inputs: v2 GM / tracker.
- Wing walkers rule `main.py:314-323`, `:494-505`; settings `handsignals.conf_thr`, margins, `min_frames`; recorder
  `scripts/ww_pose_record.py`, `ww_pose_batch.py`, replay `ww_pose_replay.py`. Videos `KB04bkqBI7ms` (gain),
  `wMk1umBGpV8f` (19 % / 10 %), `HwGR6Wvf7mE2K3` (hand-signal Fail), `MwCSLbQ7QvXQ` (pin change).
- Report `docs/analysis/pose_unification.md`; task PF-Q4-02.
