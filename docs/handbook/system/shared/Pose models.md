# Pose models

A pose model finds a person's joints in a picture. It takes the box the General Model drew around a person (a
detection) and returns 17 points of the body (nose, eyes, ears, shoulders, elbows, wrists, hips, knees and ankles), each
with a confidence score from 0 to 1. A whole-body pose model returns 133 points, including the hands. Several checks use
these points to see what a worker does: raises an arm to signal, bends down at a wheel, holds a handrail, faces away from
the camera. Today seven checks use four different body models and one check uses a whole-body model. The plan is two
shared models: one for the body, one for the whole body including the hands.

## Status

| | |
|---|---|
| In production | Each check runs its own model. The planned shared body model is already the model of one check (motorized service vehicles parked and chocked) |
| Last change | October 2026: the shared body model was tested on 66 of the 90 recordings of the monthly test (the client's validated turnarounds we measure on); summary of 27 October |
| Next step | Re-tune the wing walker hand-signal rule for the shared body model; send every changed verdict (Pass, Fail or Not observed) to Oksana and Ihor before production |
| Who looks after it | Valentyn with Yurii Luchko; Oksana and Ihor approve verdict changes |

## What it does

Each check calls its pose model itself, inside its own job, only for the people and moments it cares about. The model
takes the person's box from the check, usually enlarges it, cuts that part out of the frame (one picture of the video; the
cameras take 8 per second), scales it to its input size, finds each point and scores it. The check then applies simple
geometry to the points: a wrist above an elbow, the angle of a knee, a drop in the person's height, the order of the
shoulders.

## What it finds: the five models in use

| Model | Points | Size | Time per call on the same boxes (test machine) | Notes |
|---|---|---|---|---|
| A, large body model | 17 | 63.6 million parameters, 269 megabytes | 42.2 milliseconds | looks at every person twice, as is and mirrored |
| B, medium body model | 17 | 43.3 million, 178 megabytes | 12.4 milliseconds | also mirrored |
| C, small body model | 17 | 6.3 million, 25 megabytes | 4.9 milliseconds for one person (in its check) | its check reads only the shoulders |
| D, shared body model | 17 | 27.6 million, 110 megabytes | 8.9 milliseconds | |
| E, whole-body model | 133, with the hands | 33.6 million, 134 megabytes | 13.9 milliseconds | |

A call handles all person boxes of a frame. The walk-around and safety vest checks use another pose model, outside
this work.

## Which checks depend on it

| Check | Model | What it looks for |
|---|---|---|
| All GSE guided into aircraft using approved hand signals | A | the worker in front of the door during the 30 to 5 seconds before a belt loader stops there: a wrist at or above the elbow (5 pixels tolerance), both points scoring at least 0.2, on 8 frames (1 second) |
| Lead marshaller and wing walkers in correct position | A | while the aircraft rolls in, every worker: a wrist above the elbow (score at least 0.2) is a signal frame |
| Wing walkers in proper position and using approved wands | A | in the first 60 seconds of the pushback, each walker: a wrist at most 4.8–8 % of the box height below the elbow, both points scoring at least 0.2, on 8 frames (1 second) or 20 % of the walker's frames if fewer |
| Steering by-pass pin installed, or steering otherwise bypassed | A | a worker who stops by the nose wheel within 4 minutes after the arrival: a 25-second clip of their points, from which a second model decides whether they installed the pin or used the bypass switch |
| Pushback operator verifies steering bypass pin installation | B | workers by the nose wheel after the pushback tractor is attached: bending (a wrist below the hip, body angle at most 150°) or crouching (knee angle under 120°) for 1.5 seconds, or standing straight, feet still, with a hand at head height for 2.5 seconds, gives Pass |
| FOD walk completed | C | every person before the aircraft arrives: do they face away from the camera (left shoulder left of the right one)? |
| Motorized GSE parked and properly chocked | D | a worker at the lower part of a service vehicle whose height drops below 65 % of its maximum within 1 second has bent down to chock it; poses scoring under 0.3 are ignored |
| Handrails on GSE being used | E | each worker on a belt loader: one hand within a few pixels of the handrail line for 5 frames in a row (4 in the left-side view) |

## The plan: two shared models

- **Body:** model D for all seven body checks. Five networks become two.
- **Whole body:** model E stays in the handrails check, which needs the hands. Tried on the body checks, it was twice as
  slow as D and lost two correct verdicts (32 → 30 of 38), so it stays there only.
- The debris walk check may keep model C: cheaper for its one-person calls, and no verdict change either way.
- **Without touching the checks' code.** One shared runner cuts out the person exactly as the checks' own library does
  (0 pixel difference) and answers the three ways the checks call pose; the check's own weights are not loaded. Every
  run gets the same input shape (batches of 4, padded), because the graphics-card runtime spends about 30 milliseconds
  whenever the shape changes (5 with a fixed batch). Padding changes no output.
- **Real time**: one pose step per frame could serve all pose checks at once, but only after they agree on how much to
  enlarge the box (by 10 to 25 % or not at all) and how to prepare the picture (contrast enhancement in three checks,
  brightness equalisation in the steering check). That is a separate test.

## How it works, step by step (the shared runner)

1. Take the person's box from the check; enlarge it by 25 % and widen it to the model's shape.
2. Cut and scale the crop out of the full frame in one step; convert and normalise the colours.
3. Pad the batch to 4 persons and run model D.
4. Hand each point's position and score back in the format the check expects.

## How fast it is and what it costs

- **First test** (38 runs on 8 recordings, same machine and load): pose time 599 → 251 seconds (−58 %), check jobs
  2,733 → 2,137 seconds (−22 %). The four checks on model A: −28 to −39 % per job (60 → 9 milliseconds per pose call).
  Pin check −10 %. Debris walk +12 %: model C is lighter on one person per call, and the check calls pose 21,297 times
  on 6 recordings (every person on every frame before the aircraft arrives).
- **Large test** (66 recordings): pose time 12,477 → 5,614 seconds (−55 %; −78 % if the debris walk keeps model C); the
  seven checks' time −13 %.
- **In production** pose runs inside the check jobs, so the General Model job does not change. On five recordings with
  production job times, the five checks whose model would change take 105 of 2,181 job minutes (5 %). The change saves
  about 21 minutes, about 1 % of the job time (0.5 to 7 minutes per recording), up to about 2–3 % if model A is
  relatively slower on the production graphics card. Time to result does not move: the checks run side by side and none
  of these is the slowest (hand signals 6–9 minutes; handrails on service vehicles 47–74, safety zone up to 51, safety
  vests up to 35).
- **The value is elsewhere**: two models instead of five; one 110-megabyte file instead of 269 megabytes in four checks
  plus 178 and 25; and real time, where a pose call drops from 60 to 9 milliseconds against a budget of 125 milliseconds
  per frame for everything.

## How good it is

- On the same boxes, D's points lie a median 1.5 % of the box height from A's; 92.9 % are within 10 % of the box height
  (arms 90.2 %). B differs from A about as much. Mirroring buys nothing measurable; the colour order makes no difference.
- Debris walk: C and D agree on the shoulder order for 74 % of 209 crops; front or back is the hard part for any pose
  model. Service vehicles chocked: the shared runner moves the points a median 1.1 % of the box height against the
  check's own runner and keeps its low-confidence decision on 95 %.
- First test: 36 of 38 verdicts unchanged, one moved towards the label and one away; correct 32 → 32. The checks' own
  models rerun gave 38 of 38 identical, so both changes come from the model.
- **Large test**, 66 of 90 recordings, verdicts merged over both cameras, truth from the monthly test:

| Check | Correct, own model → D | Changed (towards / away from the label) | Check time |
|---|---|---|---|
| Hand signals for service vehicles | 53 → 53 of 55 | 0 | −16 % |
| Lead marshaller and wing walkers | 53 → 53 of 55 | 0 | −32 % |
| Steering bypass pin | 38 → 41 of 46 | 7 (5 / 2) | −57 % (partly earlier exits) |
| Pushback driver's pin check | 35 → 36 of 46 | 4 (2 / 1, 1 neither) | +4 % |
| Service vehicles chocked (same model, shared runner) | 47 → 47 of 56 | 2 (1 / 1) | unchanged |
| Foreign object debris walk | 53 → 52 of 57 | 1 (0 / 1) | +15 % |
| Wing walkers during pushback | 47 → 36 of 55 | 13 (1 / 12) | −24 % |
| **Total** | 326 → 318 of 370 (without wing walkers 279 → 282) | 27 | −13 % |

With the debris walk left on model C, every check except wing walkers keeps or gains correct verdicts.

## Known problems

**The wing walker check loses with model D.**

- All 12 losses come from the hand-signal rule. The walkers on both sides are still found (from their paths, without
  pose), but with D one of them "does not signal": 11 times Pass becomes Fail where the label says Pass, once Fail becomes
  Not observed where the label says Fail. The one gain is a recording where A missed the right walker's signal.
- The people are small: the median box is 57 pixels high, an arm about 10 pixels. Arm scores sit at the 0.2 threshold
  for both models (median of the weaker of wrist and elbow: A 0.21, D 0.19; half of the boxes are below 0.2). The rule
  really asks whether the model ever puts a wrist at elbow height with some confidence for 1 second, and A does so about
  twice as often (19 % against 10 % of the frames on one recording). The thresholds were set on A.
- Mirroring and the whole-body model do not help: both still give Fail there, and E scores lower still (median 0.12).
- The hand-signal part decides only one of the 11 Fail labels (both models agree there); the other Fails come from a
  missing walker or a blocked side. 15 of the 55 recordings do not depend on the pose at all.
- **Fix found (27 October 2026):** we recorded the arm points of both models on the same walkers over the 40 recordings
  that depend on the pose and replayed the rule offline with other thresholds (the replay gives exactly the recorded
  verdicts of both models on all 40). With a minimum score of 0.15 instead of 0.2, a wrist–elbow tolerance 1.5 times
  wider and 12 frames (1.5 seconds) instead of 8, model D gets 47 of 55 right — as many as A — with the same verdict as A
  on 53 of 55 and no Fail label turned into Pass. Mirroring, the raw frame and model E do not help with today's
  thresholds (35–37 of 55). The best setting is narrow and only one labelled Fail depends on the arm rule: to confirm on
  more recordings before production; the fallback is to keep A in this check only.

**Other problems**

- Four networks for the same 17 points; four checks each load their own 269-megabyte copy of A, and an unused
  255-megabyte file of another version also sits in their folders.
- Each check prepares the picture differently, so one pose result per person cannot yet be shared.
- The service vehicle and handrails checks mix two colour orders (effect to confirm; for D it made no difference).
- The hand-signal rules are coarse: a raised wrist stands for a signal; there is no list of approved signals and no wand
  detection (the wing walker check's wand detector is not loaded).
- Samples are small: 4–6 runs per check in the first test; the large test stopped after 66 of 90 recordings (24
  recordings, 185 runs left).

## What changes next

1. Confirm the wing walker thresholds on more recordings (above).
2. Run the remaining 24 recordings.
3. Send the changed verdicts to Oksana and Ihor: a model change must not change what a verdict means without approval.
4. Roll out model D check by check (each installs the runner at its start; the weights file is the one the service
   vehicle check already uses); model E stays in handrails; decide whether the debris walk keeps model C.
5. Real time: one shared pose step per frame once the crop and picture rules are common, as a separate test.

## For developers

- Models: A HRNet-W48 COCO-17 (mmpose 1.3.1, 192×256, flip test,
  `td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth`); B SimCC ResNet-50 (288×384, flip,
  `simcc_res50_8xb32-140e_coco-384x288-45c3ba34_20220913.pth`); C MoveNet SinglePose Thunder v4 ONNX (CPU onnxruntime
  1.14.1 in production); D RTMPose-l body7 ONNX (`rtmpose-l-4dba18fc.onnx`); E DWPose-l whole body ONNX (288×384);
  walk-arounds and safety vests: YOLOv8m-pose. Unused: `hrnet_w48_coco_384x288_dark-741844ba_20200812.pth`.
- Modules: hand-signals (M13), lead-marshaller (M15), wing-walkers (M27, `obstruction_hand_signals`), steering (M26),
  pin-verification (M16), fod-walk-completed (M11), gse-chocks (M12), handrails-on-gse-being-used (M14).
- Code: `pf/pose/topdown_onnx.py`, `pf/pose/shims.py`; `scripts/run_module.py --pose-override rtmpose-l` (control
  `--pose-timing`); `scripts/pose_bench.py`, `scripts/testset/pose_full_run.py`.
- Wing walkers: rule `main.py:314-323`, `:494-505`; keys `handsignals.conf_thr`, margins, `handsignals.min_frames`;
  `scripts/ww_pose_record.py`, `ww_pose_batch.py`, `ww_pose_replay.py`.
- Results: `docs/analysis/pose_unification.md` (§8), `docs/analysis/module_compute/pose_person.md`,
  `out/pose/interim_summary3.json`. Task PF-Q4-02.
