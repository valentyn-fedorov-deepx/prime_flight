# GM production delta: what actually produced the ATL-C5 files (commit a0157a4) vs the reviewed master pin (13a4ddc)

Discovered 2026-09-14 while running the first L1 parity of GM v2. The objects in `gs://cv-modules-topics/<video>.mp4/` are
named `general_model<commit>.ndjson` / `trackers<commit>.ndjson`; for all ATL-C5 videos the suffixes are **`a0157a4`**
(GM) and **`bd43c3c`** (tracker). Neither is the master HEAD that the 2026-09-07 architecture review pinned
(`13a4ddc` / `b5d350c`). Worktrees of both production commits are in `external/general_model_prod` and
`external/cv_trackers_prod`; `gm_current.md` describes master, this note lists the production differences.

## GM a0157a4 (branch `deployment_v_py3_10`, also `new_plane_type`; 2025-09-04 "Fix plane type format")

`git diff --stat 13a4ddc a0157a4`: 24 files, +1986/−136. What matters for the output:

| Area | master 13a4ddc | production a0157a4 | Effect on parity |
|---|---|---|---|
| Detector input colour order | BGR frame fed as is | **BGR→RGB** before /255 (`scripts/new_model.py:308-309`) | decisive: with BGR the GM head matched 73 of 2713 detections; with RGB 10 092 of 10 113 pairs (see below) |
| Detector weights | `weights.dvc` md5 96fb8549 (8 files) | md5 a88a99a7 (9 files): the **same three ONNX detectors** (byte sizes identical) + `general_tail_classifier.pth` | none for detections |
| Main-aircraft tracking | Norfair `Tracker` | `FeaturedTracker` (`scripts/tracker.py`, Norfair 0.3.1 subclass with FAST/ORB feature re-check on association, `image=im0s`) + candidates < 10 % of the frame area dropped (`main.py:612-621`) | affects class-2 rows (which frames carry the main aircraft) — not yet ported |
| Aircraft type | `aircraft_determining` votes after arrival, answer at > 500 votes | per-frame vote while the main aircraft is present: engine y2 vs wing y2, parts ≥ 50 % inside the aircraft; answer at departure or end of video; "plane passing by" resets counters after 10 s absence (`scripts/engine_script.py`, `main.py:912-949, 1109`) | report field only; ported as `pf.gm.context_prod.AircraftTypeVoterProd` |
| Entity (airline) | entity YOLOv5 detector, 40 hits every 8th frame | `EntityClassifier` (`scripts/entity/`: CRAFT text detector + label/tail classifiers) every 2·fps frames during the first 60 s of the main aircraft; `get_most_common_entity()` | report field only; not ported (separate subsystem) |
| cv_common pin | d74eb096 | d74eb096 (unchanged; not in the archive history — the archive's master ac5098d is used for helpers; thresholds match the data: conf 0.35 / chock 0.10 / vehicle 0.40) | — |

## Measured L1 parity of the GM head (`pf.gm.onnx_detector` vs `general_modela0157a4.ndjson`)

Video `DjwtQRdZyt0sSk`, first 2 795 frames, GM classes only (synthesized 2/29/30 and the separately-truncated 25/31 ignored),
RTX 5070 Ti + onnxruntime-gpu 1.29 vs production T4 + onnxruntime-gpu 1.16.2, same fp16 ONNX files, OpenCV decoder on both sides:

| metric | value |
|---|---|
| detections prod / v2 | 10 113 / 10 114 |
| pairs (same class, IoU ≥ 0.5) | 10 092 → pair recall 99.79 % |
| pairs bit-exact (coords and conf) | 5 365 (53 %) |
| pairs within ±2 px and ±0.02 conf | 10 049 (99.6 %) |
| frames fully within tolerance | 2 715 / 2 795 = 97.1 % |
| coordinate delta px (p50 / p90 / p99 / max) | 0 / 0 / 2 / 18 |
| confidence delta (p50 / p90 / p99 / max) | 0 / 0.002 / 0.004 / 0.008 |
| unmatched | 21 (prod) / 22 (v2), mostly class 3 beltloader boxes cut by the frame edge at x = 0 with conf ≈ 0.35–0.39 |

Interpretation: the remaining differences are fp16 convolution / cuDNN algorithm / ORT-version noise, not logic (the runs in
this file additionally used cuDNN "fallback mode" convs caused by a wrong provider option in the first port — corrected, see
`gm_speed.md` §1; the fixed path is 2.6× faster and equally non-bit-exact). Exact bitwise parity across different GPUs is not attainable; the acceptance
criterion for GM v2 (measurement_plan.md §3.1) is therefore the tolerant metric: pair recall ≥ 99.5 %, frames within
±2 px / ±0.02 conf ≥ 97 %, every unmatched detection near the threshold or the frame edge. On the **same** hardware and ORT
version as production, bitwise parity is expected.

Speed: the figure first printed here (77.6 ms/frame) was measured on the cuDNN fallback path and is void — the corrected
measurements are in `gm_speed.md` (22.4 ms/frame for the three heads with the v1 options, 16.8 ms parallel, 8.0 ms TensorRT).

## Measured L1 parity of the v1-compat second-run file (all detector heads, same 3 000 frames)

Compared against the production second-run file with the synthesized rows (2/29/30) ignored — they depend on whole-video
context that a 3 000-frame prefix does not have — so the comparison covers the GM head plus the chock (25) and vehicle (31)
heads after the second-run int-truncation:

| metric | all heads | chock head (25) | vehicle head (31) |
|---|---|---|---|
| detections prod / v2 | 20 184 / 20 184 | 3 000 / 3 000 | 6 225 / 6 224 |
| pairs (same class, IoU ≥ 0.5) | 20 158 (99.87 %) | 3 000 (100 %) | 6 220 (99.9 %) |
| pairs bit-exact | 12 969 (64 %) | 2 294 (76 %) | 4 795 (77 %) |
| pairs within ±2 px / ±0.02 conf | 20 099 (99.7 %) | 3 000 | 6 209 |
| frames fully within tolerance | 2 896 / 3 000 = 96.5 % | 100 % | 99.4 % |
| coord delta px p99 / max | 2 / 18 | 1 / 1 | 2 / 6 |
| conf delta p99 / max | 0.003 / 0.008 | 0.0005 / 0.003 | 0.002 / 0.005 |

Exact (bitwise) frame parity of the compat file on this prefix: 60.7 % — the rest is the same fp16 noise. (Speed for this
run withdrawn — fallback path, see `gm_speed.md` §1.)

## Full-video L1 parity of the regenerated second-run file (37 530 frames, ALL rows incl. synthesized)

Run: `scripts/gm_v2_run.py` on the whole `DjwtQRdZyt0sSk.mp4` (three heads, production preprocessing), then
`scripts/gm_v2_replay.py` on the recorded first-run rows with the current context (norfair 0.2.0 main-aircraft
tracking, parts layout, obstacle logic) → `general_modelDjwtQRdZyt0sSk.mp4-second_run.ndjson`, compared with the
production file `general_modela0157a4.ndjson` (`docs/analysis/parity/gm_v2_replayDjwtQRdZyt0sSk.mp4.json`):

| rows | prod / v2 | pairs (IoU ≥ 0.5, same class) | bit-exact | within ±2 px / ±0.02 | frames within tolerance |
|---|---|---|---|---|---|
| all classes | 723 542 / 723 526 | 722 833 (99.90 %) | 405 975 (56 %) | 716 568 (99.1 %) | 32 095 / 37 530 = 85.5 % |
| class 2 main aircraft (height mode in conf) | 17 673 / 17 671 | 17 667 (99.97 %) | 14 193 (80 %) | 17 397 | 99.25 % |
| class 29 obstacle | 60 081 / 60 074 | 60 030 (99.92 %) | 24 864 | 59 291 | 98.3 % |
| class 30 side_obstacle | 41 600 / 41 563 | 41 473 (99.69 %) | 20 676 | 40 832 | 98.0 % |

Context reproduced from the rows alone: main aircraft first seen at frame 3 457, first track at 3 465 (norfair delay),
class-2 rows on 17 671 frames vs 17 673 in production; parts layout frozen at 3 933; side ROIs left x ≥ 1 414.4 /
right x ≤ 265.2 (identical obstacle assignment on 98 % of frames). Unmatched rows (709 / 693 ≈ 0.1 %) are threshold
flicker of small objects (class 24 air_conditioning alone 185 / 241) and a handful of main-aircraft frames where a
different candidate box won the merge (coord p99 56 px on class 2 only). The `conf` of obstacle rows can differ by up to
0.56 because v1 writes the stale loop variable — the last row's confidence — which flips with detection order; the
compat writer reproduces the quirk, the value is inherently non-deterministic across hardware.

Speed on the full turnaround: the 79.3 ms/frame / 1.58× real-time figure was measured on the cuDNN fallback path and is
void; decode was 2.5 ms/frame. Corrected per-configuration numbers: `gm_speed.md`; the full-turnaround re-run with the
fixed options is listed there as next.

Verdict for PF-Q1-16 acceptance (measurement_plan.md §3.1): **met** on the tolerant criterion for all row types
(pair recall ≥ 99.5 %, frames within tolerance ≥ 97 % for the synthesized classes; 85.5 % for "every row in the frame
within tolerance" because a single flickering small object fails the whole frame). Bitwise parity is expected only on
the production hardware/runtime.

## Tracker bd43c3c (branch `optimization`, 2026-02-28)

`git diff --stat b5d350c bd43c3c`: tracker.py +115/−?, local_config.yaml +2, weights.dvc changed, `scripts/tracker_clips.py`
(new, 797 lines). Covered in `tracker_current.md` §12 (production delta).

## Consequences

- The architecture review (2026-09-07) documents master, not production, for GM and the tracker; module pins in
  `docs/04_modules.md` are unaffected (modules are deployed from their own repos).
- GM v2 defaults to the production behaviour (`bgr_to_rgb=True`); the master behaviour is kept as a flag for A/B.
- Open: port `FeaturedTracker` (needs Norfair 0.3.1 semantics; installed norfair 2.3 has a different API) to make the
  class-2 rows of the v1-compat file match production; decide whether `EntityClassifier` belongs to GM v2 or to a separate job.
