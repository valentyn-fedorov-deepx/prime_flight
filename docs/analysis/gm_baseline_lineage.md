# Which General Model the monthly test compares against (2026-10-20)

**The monthly test's baseline is not the production GM.** Its baseline files come from GM 087dfa9 (April 2024), whose
detector heads are fed **BGR** frames. Production is the `deployment_v_py3_10` branch (a0157a4; its head d4ae8e5 runs the same GM code on a new image), which
feeds **RGB** since 342fd00 (June 2024) and also changed the main-aircraft tracking, the aircraft-type logic, the airline
classifier and the weights pin. Production has GM files for **1 of the 90** test videos. So the "score drops" of the
optimised GM (afaebf1, our branch = production code) in `gm-files-for-score-drop.csv` measure production against a model
production stopped running in 2024 — not the optimisation.

## What the bucket holds for the 90 test videos

Files are named by the GM commit that wrote them (`gs://cv-modules-topics/<video>/general_model<commit>.ndjson`, the
second-run rows the modules read). Listed 2026-10-20:

| GM commit | date, branch | heads fed | videos with a file |
|---|---|---|---|
| 087dfa9 | 2024-04-24, master lineage — the files production wrote when these videos were processed | BGR | 90 (the monthly baseline) |
| 342fd00 | 2024-06-21 "add rgb conversion" | RGB | 1 |
| 4083ada, b205449, 9f0f021, 63d68c9, 777aa8c | 2023-07 … 2024-03, older production | BGR | 69–90 each |
| b8dd37a, 8576299 | 2026-08 / 09, `entity_clip_integration` (branches off before the RGB fix) | BGR | 90 each |
| **a0157a4** | 2025-09-04, **production** (`deployment_v_py3_10`) | RGB | **1** (Bdx1iGrXPEfe, written 2026-10-13) |
| d4ae8e5 | 2025-12-09, production image update | RGB | 0 |
| afaebf1 | 2026-10-12, `pf/q4-02-gm-exact-speedups` (production code + the exact speedups + font / dvc pin) | RGB | 90 (the "optimised" column) |

## Measured on the one video that has all of them (Bdx1iGrXPEfe, 25 800 frames, ~850 000 detections)

`pf.eval.parity.compare_gm_ndjson_tolerant` (match IoU 0.5, ±2 px, ±0.02 confidence):

| comparison | pairs | within tolerance | bit-exact pairs | unmatched a / b | frames fully within tolerance |
|---|---|---|---|---|---|
| production a0157a4 vs our branch afaebf1 (both on the cluster) | 850 119 of 850 586 (**99.95 %**) | 846 565 (99.5 %) | 555 839 | 467 / 486 | 22 257 of 25 800 |
| April-2024 baseline 087dfa9 vs production a0157a4 | 794 314 (93 %) | **340 672 (40 %)** | 1 273 | 52 842 / 56 272 | **0** |
| entity_clip 8576299 vs production a0157a4 | 794 334 (93 %) | 340 664 (40 %) | 1 270 | 52 826 / 56 252 | 0 |

- Our branch and production produce the same detections up to last-bit kernel differences, and the two cluster runs
  used two stacks: the bucket file name is the commit the image was built from (`db_worker/ML_worker.py`), so the a0157a4
  file came from the a0157a4 image (python 3.8, `gpu_base:legacy_base`, cv_common d74eb09), while afaebf1 is on
  d4ae8e5's (python 3.10, `gpu_base:python_3_10_cudnn8`, torch 1.13.1, onnxruntime-gpu 1.15.0, cv_common ac5098d). On
  one machine and one image the MR is byte-identical (`tasks/notes/PF-Q4-02.md`, three full-event A/B runs).
- The April-2024 baseline and production are different detector behaviours: no frame agrees within tolerance, 60 % of the
  detections move by more than 2 px or 0.02 confidence, 6–7 % have no counterpart at all.

## What follows

1. **Check the MR against production on one stack**: d4ae8e5 plus the two image commits of the afaebf1 build (font, dvc
   pin), without the MR, on 3–5 of the 90 videos. Byte-identical → the afaebf1 files of the 90 videos are the production
   code's output and serve as the baseline (`tasks/notes/PF-Q2-16.md`).
2. **Score the production code's files against the labels.** It is the first measurement of the production GM's module accuracy on the
   monthly set; the CSV suggests it is lower than the April-2024 model's on 56 of 90 videos (worst: safety huddle,
   pre-departure walk-around, pin verification, handrails on GSE, cones removed, steering, hand signals, safety zone).
   Whether that is the RGB detector or modules tuned on BGR-era outputs is the next question, per task.
3. **Point the monthly test at the production branch head** from now on, so the baseline moves when production does.
4. **For Prime Flight**: the test set this project measured with (`scripts/testset/fetch.py`, "production" = 8576299) and
   the GM v2 variant it runs (`entity_clip`) are the BGR lineage — the same behaviour as the monthly baseline, not
   production. The real-time accuracy figures (86.7 % batch, 83.8 % live, `rt_module_cost.md`) describe that lineage; they
   are re-anchored on production once its baseline exists.
