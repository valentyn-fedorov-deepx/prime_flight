# Why the wing walker check lost accuracy with the shared pose model, and how new thresholds bring it back

*27 October 2026 · Valentyn Fedorov · Status: the cause is found and new thresholds are measured; to be confirmed on more
turnarounds before production*

## In short

When all checks that read body poses were switched to one shared, faster pose model, the check *Wing walkers in proper position and using approved wands* fell from 47 to 36 correct verdicts out of 55 turnarounds of the monthly test. Every
loss came from one rule: "the wing walker raises an arm" (a wrist at or above the elbow). The people in these videos are
tiny — about 57 pixels tall — and the two pose models place the wrist and the elbow differently at that size; the rule's
thresholds had been tuned on the old model. We recorded both models on the same people in 40 turnarounds and replayed
the rule with other thresholds. With a confidence limit of 0.15 instead of 0.2, a 1.5 times wider wrist–elbow tolerance
and 12 frames (1.5 seconds) of raised arm instead of 8 frames (1 second), the shared model gets **47 of 55 right — as many
as the old model** — and no turnaround the client labelled Fail becomes a Pass. The best setting is narrow, and only one
labelled Fail in the set depends on the arm rule, so it has to be confirmed on more turnarounds.

## The question

The shared pose model (it finds a person's joints: shoulders, elbows, wrists, knees) is six to seven times faster than the
model this check uses today, which matters for running it in real time. Six of the seven checks that read poses kept
their accuracy with it. This one did not. Why — and can it be fixed without changing what the check means?

## How the check decides (the part that matters here)

During the first 60 seconds of the pushback the check looks for a wing walker on each side of the aircraft: a person
whose path follows the aircraft. Who is a wing walker comes from the paths of the people, not from the pose model. Then,
for every frame, it asks the pose model where each wing walker's elbows and wrists are. A frame counts as "signalling"
when a wrist is not lower than its elbow by more than a small tolerance (8 % of the person's height on the left side,
4.8 % on the right side for a regular aircraft, 7 % for a small jet), and both points are found with a confidence of at
least 0.2. A wing walker who signals on 8 frames (1 second) — or on a fifth of the frames they are seen, if that is fewer —
passes. The check passes only if both sides have a signalling wing walker.

## What we did

1. **Looked at the 13 turnarounds whose verdict changed** with the shared model. In all of them the wing walkers were
   found on both sides (the paths did not change); the verdict changed only because one wing walker "did not signal" (11
   times Pass became Fail; once Fail became Not observed) or now did (once Fail became Pass).
2. **Measured the people.** On a typical turnaround the median wing walker box is 57 pixels tall; an arm is about 10
   pixels. Both models are unsure about arms that small: half of the confidence values are below the 0.2 limit. The old
   model puts a wrist at elbow height about twice as often as the shared one (19 % against 10 % of the frames on the same
   people).
3. **Tried the simple fixes first:** the shared model with mirrored second look ("flip test"), the shared model on the
   picture without the contrast enhancement the check applies, and the larger whole-body model. None of them brought the
   accuracy back with the check's current thresholds (35 to 37 of 55).
4. **Recorded both models on the same people.** For the 40 turnarounds where the verdict depends on the pose (in the
   other 15 there is no wing walker on a side or no departure, whatever the pose), we ran the check as it is in
   production and, for every person it looked at, also asked the shared model — on the same picture, the same box. Then we
   replayed the check's arm rule offline with any model and any thresholds. The replay gives exactly the recorded verdicts
   of both models on all 40 turnarounds, so it can be trusted.
5. **Tried 150 combinations** of the three thresholds (confidence 0 to 0.25, tolerance 0.5 to 3 times, 2 to 12 frames) for
   every variant of the shared model, and compared each with the client's labels and with the old model.

## What we found

| Pose model and thresholds | Correct of 55 | Same verdict as the old model | Labelled Fail that became Pass |
|---|---|---|---|
| Old model, today's thresholds | 47 | 55 | 0 |
| Shared model, today's thresholds | 36 | 42 | 0 |
| Shared model with flip test, today's thresholds | 37 | 43 | 0 |
| Shared model without contrast enhancement, today's thresholds | 35 | 43 | 0 |
| Whole-body model, today's thresholds | 35 | 43 | 0 |
| **Shared model: confidence 0.15, tolerance × 1.5, 12 frames** | **47** | **53** | **0** |
| Shared model: confidence 0.10–0.15, tolerance × 1.5–2, 6–12 frames | 46 | 52 | 1 |

At the best setting the shared model differs from the old one on two turnarounds: on one it is now right (the client said
Pass, the old model said Fail), on the other it says Not observed where the client and the old model said Fail.

How stable it is: around the best setting the result is 46 of 55 almost everywhere, but those settings let one labelled
Fail turnaround pass — the only Fail in the whole set that is decided by the arm rule. Ten of the 11 labelled Fails of
this check come from a missing wing walker or a blocked side, which the pose model does not touch.

## What it means

- The shared pose model can replace the old one in this check, if the check gets new thresholds for it: confidence 0.15,
  wrist–elbow tolerance 1.5 times today's, 12 frames (1.5 seconds) of raised arm. The meaning of the rule does not change —
  "a wing walker raises an arm" — only how strict the measurement is with the new model.
- With one labelled Fail that depends on the arm rule, the test set cannot show whether the new thresholds catch real
  violations. The best setting is the one that kept that Fail; a slightly looser one would have let it pass.
- The arm rule itself is weak on people this small, with any model. The check also never looks at the wands, although its
  report says "approved wands" (see the check's page).

## What is next

1. Confirm on more turnarounds: the 24 videos of the monthly set that were not run yet, and turnarounds with labelled
   wing walker violations from the Data team.
2. If confirmed: switch the check to the shared model with the new thresholds, show the verdict table to Oksana and the
   client's safety team, then production.
3. For real time: the shared model costs about 9 milliseconds per call instead of about 60.

## For developers

- Recorder: `scripts/ww_pose_record.py` (the module decides with its own HRNet-W48; on every pose call inside the departure
  window the same boxes also go through RTMPose-l on the CLAHE frame, on the raw frame, with flip test, and DWPose-l;
  the decision inputs — window, airplane type, walkers per side with `frames_observed`, blocked share — are captured).
  Batch: `scripts/ww_pose_batch.py` over `out/pose/ww_videos.json` (40 pose-dependent videos). Replay and sweep:
  `scripts/ww_pose_replay.py --sweep` → `out/pose/ww_replay.json`; replay = recorded verdicts on 40 of 40 for both runs.
- Thresholds in the module's `local_config.yaml`: `handsignals.conf_thr` 0.2 → 0.15; `handsignals.<type>.<side>.margin_of_error_*`
  × 1.5 (left 0.08 → 0.12; right 0.048 → 0.072 for aircraft, 0.07 → 0.105 for jets); `handsignals.min_frames` 8 → 12.
  Module: `wing-walkers-in-proper-position-and-using-approved-wands`, branch `obstruction_hand_signals` @ 3460afc.
- The two turnarounds that differ from HRNet at the best setting: KB04bkqBI7ms (label pass: HRNet fail → pass) and
  KOlRIvK7wCq1 (label fail: HRNet fail → not observed). The one hand-signal Fail label: HwGR6Wvf7mE2K3.
- Background: `docs/analysis/pose_unification.md` §8; task PF-Q4-02.
