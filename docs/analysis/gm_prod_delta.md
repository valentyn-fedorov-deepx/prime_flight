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

Interpretation: the remaining differences are fp16 convolution / cuDNN algorithm / ORT-version noise (this GPU runs several
fp16 convs in ORT "fallback mode"), not logic. Exact bitwise parity across different GPUs is not attainable; the acceptance
criterion for GM v2 (measurement_plan.md §3.1) is therefore the tolerant metric: pair recall ≥ 99.5 %, frames within
±2 px / ±0.02 conf ≥ 97 %, every unmatched detection near the threshold or the frame edge. On the **same** hardware and ORT
version as production, bitwise parity is expected.

Speed on the RTX 5070 Ti (3 000 frames, batch 1, fp16, three detectors sequential): decode 3.7 ms, GM 10.3 ms, chocks 17.5 ms,
vehicle 32.1 ms inference; end-to-end 77.6 ms/frame = 1.6× real-time at 8 fps. The vehicle head (yolov8m @1088) is the
largest cost; batching across the three heads / cameras and removing the padding are the first optimizations (ADR-001 §6).

## Tracker bd43c3c (branch `optimization`, 2026-02-28)

`git diff --stat b5d350c bd43c3c`: tracker.py +115/−?, local_config.yaml +2, weights.dvc changed, `scripts/tracker_clips.py`
(new, 797 lines). Covered in `tracker_current.md` §12 (production delta).

## Consequences

- The architecture review (2026-09-07) documents master, not production, for GM and the tracker; module pins in
  `docs/04_modules.md` are unaffected (modules are deployed from their own repos).
- GM v2 defaults to the production behaviour (`bgr_to_rgb=True`); the master behaviour is kept as a flag for A/B.
- Open: port `FeaturedTracker` (needs Norfair 0.3.1 semantics; installed norfair 2.3 has a different API) to make the
  class-2 rows of the v1-compat file match production; decide whether `EntityClassifier` belongs to GM v2 or to a separate job.
