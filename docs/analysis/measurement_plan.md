# Measurement plan: baseline and proof that "module accuracy has not dropped" for GM v2 / Tracker v2

Status: lead's draft 2026-09-14 (PF-Q1-15). To be refined after `gm_current.md`, `module_consumption.md`,
`contract_observed.md`. Rule from CLAUDE.md: a paired comparison on the same videos is always valid; absolute accuracy —
only where fail labels exist.

## 1. What exactly we measure (three levels, from cheap to expensive)

| Level | Question | Method | Tool | Data |
|---|---|---|---|---|
| L1 · GM per-frame output | Does v2 produce the same detections as v1 on the same frames? | exact: per-frame multiset matching with rounding (ndigits=1), matched by `frame_id`; tolerant: same-class IoU pairing with ±px / ±conf tolerances and delta percentiles (cross-hardware) | `pf.eval.compare_gm_ndjson`, `compare_gm_ndjson_tolerant` (tests) | ATL-C5: `general_model<ID>.mp4.ndjson` (v1) vs the v2 output on `atlc5_videos/<ID>.mp4` |
| L1 · tracker per-frame output | Does v2 produce the same `state_dict` on the consumed fields? | per-frame comparison of only the fields **consumed by the modules** (list from `module_consumption.json`), the private `_p0/_st` separately (expected not bitwise-identical) | `pf.eval` (add `compare_tracker_ndjson`, after the `state_dict` contract) | ATL-C5: `trackers<ID>.mp4.ndjson` (v1) vs v2 |
| L2 · module verdicts | Does the Pass/Fail/NO of any module change if the input is swapped v1 → v2? | run the prod module (as is, without code changes) on the v1 ndjson and on the v2 ndjson of the same video; compare the status + the key time anchors in the report | `gat-streaming/streaming/runner.py` (+ `tools/compare_runs.py`, exit 1 on mismatch) — port into `pf/eval/run_module.py` with a path to `external/<repo>` | ATL-C5 7 videos (both cameras?) → then a balanced sample with fails from the monthly reports (`tools/pick_balanced.py`) |
| L3 · accuracy against labels | Is v2 no worse than v1 against GT where GT exists? | recall/precision on the checks with enough fails (Main gear chocks 30 fail; BL forward chock 12) | `compare_runs.py --gt` | `gt_by_video.json` from the monthly reports (`tools/parse_gt.py`), needs inferences from the bucket |
| Speed | ms/frame per component (decode, GM, tracker, logic), full turnaround | timing in the `pf.gm`/`pf.tracker` core; stand (test bench) reference: decode 2.90 / GM 28.29 / tracker 0.11 ms on RTX 5070 Ti @1088 | new `pf/eval/bench.py` | `atlc5_videos` (full events, not 60-s excerpts) |

## 2. Measurement conditions (without these the numbers are not accepted)

- The decoder is pinned on both sides (X4): one and the same (OpenCV; ffmpeg drops frames on non-monotonic DTS).
- Full turnaround, not an excerpt (short tests overstate speed: 4.72× vs 3.95×).
- Idle machine; the file-cache state is identical for both modes (cold/warm shifts it twofold).
- Weights, resolution (1088 GM / 1280 chocks), thresholds and tracker parameters (MAX_AGE 40, MIN_HITS 8) are pinned and
  recorded in the report; any change is a separate table row, not an "improvement".
- Frame numbering 1-based by `frame_id`; number of frames = number of ndjson lines (verified on the stand: exact match, down to the single frame).

## 3. Acceptance criteria for GM v2 / Tracker v2 (proposal, to be agreed with Ihor/Oksana)

1. L1 GM (measured 14.09 on `DjwtQRdZyt0sSk`, `gm_prod_delta.md`): cross-hardware runs cannot be bitwise-equal, so the
   criterion is the tolerant metric of `pf.eval.compare_gm_ndjson_tolerant` — pair recall ≥ 99.5 % (same class, IoU ≥ 0.5),
   ≥ 97 % of frames fully within ±2 px / ±0.02 conf, every unmatched detection near the conf threshold or the frame edge;
   on the production hardware/runtime bitwise parity (`compare_gm_ndjson`, ndigits=1) is expected and must be reported too.
2. L1 Tracker: 100 % match on the consumed non-private fields (`arrival_frame`, `departure_frame`, statuses, `_class_name`,
   `_obj_id` identity by IoU) with a tolerance of ±1 frame on events; the number of unique aircraft per video = as in v1 (X1).
   Measured 14.09: with NumPy seeded identically the v2 tracker file is byte-identical to the production pin (the strongest
   form; `tracker_v2_run.py --seed` vs `tracker_v1_profile.py --pin prod --seed`); two unseeded production runs differ from
   each other on 0.2 % of object-frames, movement counters only. Changes that alter numerics are judged against that floor.
3. L2: 0 verdict changes on ATL-C5 and on the balanced sample; a change "Not observed → verdict" is counted separately and
   explained.
4. L3: recall/precision no worse than v1 on Main gear chocks (30 fail) — the only check with sufficient labels.
5. Speed: GM v2 ≤ 28 ms/frame on the reference hardware; tracker ≤ 1 ms; end-to-end ≥ 3.95× real-time on a full turnaround.
   Measured 14.09 (`gm_speed.md`): the three GM heads 22.4 ms (v1 options) / 16.8 ms (parallel, rows byte-identical) /
   8.0 ms (TensorRT, tolerant parity) on the RTX 5070 Ti; the "tracker 0.11 ms" of the stand was a placeholder — the real
   v1 tracker measured 14.09 (`tracker_current.md` §8): master pin 137–149 ms/frame, production pin 36–49 ms/frame on
   1 200-frame slices. Restated criterion: **Tracker v2 ≤ 15 ms/frame on the reference GPU** (3× vs production) with the
   L1-tracker / L2 criteria above; the tracker comparison target is the **production** pin (bd43c3c), not master.

## 4. Data

| Source | Available now | Needed |
|---|---|---|
| `G:\gat_stages\atlc5_inferences` + `atlc5_videos` | 7 videos with GM+tracker ndjson (v1, prod) + mp4 | the GM/tracker version they were produced with (from `contract_observed.md` / MongoDB) |
| `gs://cv-modules-topics` | access exists, needs `gcloud auth login` | inferences for the balanced samples (fail videos) — `tools/fetch_inferences.py`, `fetch_compatible.py` |
| Monthly reports (Google Sheets) | labels for 90 videos (Main gear 30/48, BL chock 12/77, pathway 4/82, nose 1/78) | `tools/parse_gt.py` → `gt_by_video.json` |
| GM v1 weights (DVC) | not on disk after `deepx_gat` disappeared | `dvc pull` in `external/general_model` (needs access to the DVC remote) |

## 5. Order of work

1. ~~`contract_observed.md` → pin the fields for L1-tracker and the class-id inventory for L1-GM.~~ done (`pf/tracker/contract.py`, str2id from cv_common). L1-GM measured on 1 full video — `gm_prod_delta.md`.
2. ~~Port `runner.py`~~ done: `scripts/run_module.py` (path `external/<repo>`, `--no-video` meta worker). First L2 result
   (14.09, `DjwtQRdZyt0sSk`, `beltloader-chocks` unchanged, cv_common pin ac5098d2): production inferences → **Pass**,
   v2-GM second-run file + production tracker file → **Pass**; smart timeline identical `[9888–22775]`; report text shifts
   by one second (00:32:13 → 00:32:14). Next: the other pixel-free modules (pushback-pathway, bl_rear_cone), then the
   pixel modules with weights (aircraft-chocks needs effnetb0).
3. ~~v1 speed baseline~~ GM: done through the v2 core with the v1 op sequence and options (`gm_speed.md` "baseline");
   tracker: done for both pins on two slices (`tracker_current.md` §8, `tasks/notes/PF-Q1-17.md`); full-turnaround runs
   remain (≈ 1 h per video for the master pin).
4. Then — as v2 appears: L1 → L2 → L3 in this order; report in `tasks/notes/PF-Q1-15.md`.

## 6. Open

- Were the ATL-C5 ndjson produced by the current prod version of GM/tracker (the bucket holds 15–16 versions each, without `schema_version`)?
- Where to get fail videos for the ATL-C5 checks (do the monthly reports cover other gates?).
- GPU runner for nightly (PF-Q1-07) — until it appears, all runs are manual on the test machine.
