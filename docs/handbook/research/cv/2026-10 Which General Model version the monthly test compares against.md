# Which General Model version the monthly test compares against

*20–22 October 2026 · Computer-vision team (analysis); production runs: Maksym Chernyshev; scoring: Oksana · Status: in
progress; the production baseline on all 90 videos and its scores are still to do*

## In short

The monthly test compares every change against General Model files made in **April 2024**. Production has run a
different General Model since June 2024: it feeds the colours to its detectors in a different order, and its aircraft
tracking, aircraft-type rule, airline classifier and weights changed too. On the one test video that has files from
both, **not a single frame agrees** within tolerance and 60 % of the detections moved. When we looked on 20 October,
production had General Model files for **only 1 of the 90 test videos**. So the "score drops" reported for the faster
General Model compared production with a model it stopped running in 2024, not with the speed-up, which is
byte-identical to production. The fix: run the production General Model on the 90 videos, score it, and make it the
baseline from now on, so that the baseline moves with production.

## The question

Words used on this page: a **frame** is one picture of the video (the cameras take 8 per second); a **detection** is a
box the General Model, the shared detector, draws around an object on a frame; a **verdict** is Pass, Fail or Not
observed; a **turnaround** is the whole servicing of an aircraft at the gate; the **monthly test** is the set of the
client's validated turnarounds we measure on (90 videos); **byte-identical** means two files are exact copies.

Every change to the General Model is judged by the monthly test: the checks run on the new detections, and their
verdicts are compared with the client's labels and with those from the baseline, the General Model files the test treats
as "production". In October 2026 a score table showed the faster General Model losing accuracy on 56 of the 90 videos.
Was that the speed-up, or something else? And which General Model is the baseline?

## What we did

1. **Listed the General Model files in cloud storage** for the 90 test videos (20 October). Each file is named after
   the code version of the job that wrote it.
2. **Compared the versions pair by pair** on the one video that has files from all of them (25 800 frames, about 54
   minutes, about 850 000 detections). Two detections are paired when their boxes overlap by at least half; "within
   tolerance" means within 2 pixels and 0.02 in confidence.
3. **Asked which build production runs.** On 21 October Maksym confirmed: the image built from the code of 4 September
   2025, not the newest code of the production branch.
4. **Ran the production image on five test videos** on 21 October, the five with the largest drops in the score table,
   and compared its files with our branch's.
5. **Ran the speed-up on production's own build** on the same five videos on 22 October.

## What we found

### What storage holds for the 90 test videos

A colour picture is stored as three layers: red, green and blue. A detector learns with the layers in one order and
should be fed them in that order. In June 2024 production switched the order in which it feeds them.

| General Model version | Date | Colour order fed to the detectors | Test videos with a file |
|---|---|---|---|
| **The monthly baseline**: what production wrote when these videos were first processed | April 2024 | blue-green-red | 90 |
| The change "add colour conversion" | June 2024 | red-green-blue | 1 |
| Five older production versions | July 2023 – March 2024 | blue-green-red | 69–90 each |
| Two versions of a research branch for airline recognition, branched off before the colour change | August and September 2026 | blue-green-red | 90 each |
| **Production** | code of 4 September 2025 | red-green-blue | **1** (written 13 October 2026) |
| The newest code of the production branch, the same General Model on a newer software stack, never deployed | December 2025 | red-green-blue | 0 |
| Our speed-up on that undeployed code (the "optimised" column of the score table) | October 2026 | red-green-blue | 90 |

Besides the colour order, production also changed the tracking of the main aircraft, the rule that sorts aircraft into
"aircraft" and "jet", the airline classifier and the pinned weights.

### The one video that has all of them

| Comparison | Detections paired | Within tolerance | Identical to the last digit | Frames entirely within tolerance |
|---|---|---|---|---|
| Production against our speed-up branch (both on the cluster) | 850 119 of 850 586 (99.95 %) | 846 565 (99.5 %) | 555 839 | 22 257 of 25 800 |
| April-2024 baseline against production | 794 314 (93 %) | 340 672 (40 %) | 1 273 | **0** |
| Airline research branch against production | 794 334 (93 %) | 340 664 (40 %) | 1 270 | 0 |

- **Our branch and production give the same detections** up to tiny differences in the last digits. These come from
  the two software stacks: the production file was written by the production image, our branch's by the image of the
  newest, undeployed code. On one machine and one stack the speed-up is byte-identical (three full runs of a 36-minute
  turnaround).
- **The April-2024 baseline and production behave differently.** No frame agrees within tolerance; 60 % of the
  detections move by more than 2 pixels or 0.02 in confidence, and 6–7 % have no counterpart at all.

### The production image on five test videos (21 October)

The five jobs, started together, took 92.8, 131.7, 170.9, 196.0 and 208.0 minutes. Against our branch's files for the
same videos (198 450 frames, 5.33 million detections): 99.95 % of the detections paired, 99.38 % within tolerance,
63.4 % identical to the last digit. That is the same level as on the first video, so the difference is the software
stack, not our code. Our branch's jobs had taken about 0.70 of these times, but that mixes our code, the other stack and
the load on the cluster, so it was only a hint of the speed-up.

### The speed-up on production's own build (22 October)

On the same five videos, every General Model file of the speed-up was byte-identical to production's, and the jobs took
26 % less time (see *Making the General Model faster without changing its results*).

## What it means

- **Production's accuracy on the monthly test has never been measured.** Production had General Model files for 1 of
  the 90 videos (6 after the run of 21 October). The score table suggests production may be less accurate than the
  April-2024 model on 56 of 90 videos. The worst checks were the safety huddle, the walk-around inspection before
  departure, the pushback driver's pin check, handrails on service vehicles, cones removed after the service vehicles,
  the steering bypass pin, hand signals and the safety zone. Whether that comes from the colour change or from checks
  tuned on the April-2024 outputs is the next question, check by check.
- **Every General Model change has been judged against the wrong model.** The "drops" of the faster General Model
  measure production against 2024, not the speed-up. The speed-up is byte-identical to production, so it cannot change
  a verdict.
- **The project's own measurements come from the old line too.** The test set the project measured real time with, and
  the General Model variant it runs, belong to the blue-green-red line of the baseline, not to production. The real-time
  accuracy figures (86.7 % after the turnaround, 83.8 % live) describe that line; they will be measured again once a
  production baseline exists.

## What is next

1. **Production baseline:** run the deployed production image on all 90 videos (Maksym).
2. **The speed-up on production's build:** done on five videos, byte-identical.
3. **Scores:** Oksana scores the production files check by check, next to the April-2024 scores. It is the first
   measurement of production's accuracy on the monthly test.
4. **From then on the baseline is the deployed production image**, so it moves when production does.
5. **Our branch's files on the 90 videos** stay useful for one question: should production ever move to the newer
   software stack, they measure that stack against step 1.

Pitfalls for whoever runs this:
- The tracker and the checks read the newest General Model file of a video unless a version is pinned; pin it when
  scoring.
- The tracker's files are named after the tracker's version, so two tracker runs on two General Model files of the same
  video overwrite each other.
- The stored files are compressed, with the time written into them, so stored checksums differ even for identical
  content: compare after unpacking.
- The arrival moment and the camera confidence in the General Model's report vary between two runs of production itself
  (random sampling in the shared library): compare the detection files instead.

## For developers

- Versions: `087dfa9` (2024-04-24, BGR heads; monthly baseline), `342fd00` (2024-06-21, "add rgb conversion"),
  `4083ada`, `b205449`, `9f0f021`, `63d68c9`, `777aa8c` (2023-07 … 2024-03), `b8dd37a`, `8576299`
  (`entity_clip_integration`), `a0157a4` (`deployment_v_py3_10`, 2025-09-04; Python 3.8, `gpu_base:legacy_base`,
  cv_common `d74eb09`), `d4ae8e5` (2025-12-09; Python 3.10, torch 1.13.1, onnxruntime-gpu 1.15.0, cv_common `ac5098d`;
  not deployed), `afaebf1` (`pf/q4-02-gm-exact-speedups`, 2026-10-12), `b6e1a3e` (speed-ups on `a0157a4`, built
  2026-10-22, now production).
- Files `gs://cv-modules-topics/<video>/general_model<commit>.ndjson`, named by `git rev-parse --short HEAD`
  (db_worker `ML_worker.py`, `upload_infereces_to_cloud_storage`). Pin with
  `general_model_inferences_version_commit=a0157a4.ndjson` (the loader does not add the extension).
- Comparison `pf.eval.parity.compare_gm_ndjson_tolerant` (IoU 0.5, ±2 px, ±0.02). Video `Bdx1iGrXPEfe` (local copy of the
  13.10 production file in `out/testset/gm_prod/`); the five: `fAkpu3dj2NIj`, `ytQDROiCyhBh`, `b8ijKDWsLlQi8W`,
  `n96M7fASlhGn`, `7PytHarRNqmT`. Score table `gm-files-for-score-drop.csv` (2026-10-17).
- Project test set `scripts/testset/fetch.py` ("production" = `8576299`), GM v2 `entity_clip`; real-time figures
  `docs/analysis/rt_module_cost.md`.
- Docs `docs/analysis/gm_baseline_lineage.md`, `tasks/notes/PF-Q2-16.md`; task PF-Q2-16 (board: todo).
