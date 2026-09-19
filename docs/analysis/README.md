# Analysis (Q1, started 2026-09-14): what GM + Tracker are really responsible for, and what the modules read from them

Phase goal: before rebuilding GM/Tracker (v2) and moving to chunk-wise processing, pin down (a) the current
responsibilities of GM and the tracker, (b) the exact interface consumed by the 27 modules, (c) the observed format
of the prod output on real data, (d) how to measure that module accuracy has not dropped with v2.

| Report | Source | Who | Status |
|---|---|---|---|
| `gm_current.md` | code of `external/general_model` (master @ 13a4ddc = review pin) + `external/db_worker` | gm-tracker-engineer | **done → Yurii's review** (375 lines; note `tasks/notes/PF-Q1-12.md`). Describes master 13a4ddc; the production commit a0157a4 differs — see `gm_prod_delta.md` |
| `gm_prod_delta.md` | bucket object names (`general_modela0157a4`, `trackersbd43c3c`) + `git diff` master→production; worktrees `external/general_model_prod`, `external/cv_trackers_prod` | Valentyn (gm-tracker-engineer) | **done** — production GM/tracker commits ≠ the review pin; BGR→RGB was the decisive difference; GM v2 head parity 99.8 % pairs |
| `tracker_current.md` §8 + `speed/tracker_v1_profile_*.json` | `scripts/tracker_v1_profile.py` on two 1 200-frame slices, both pins (weights via DVC, `scripts/win_shims` for cupy/cuCIM on Windows) | Valentyn (gm-tracker-engineer) | **done 14.09** — master 137–149 ms/frame (full-frame `estimate_sigma` 100 ms), production 36–49 ms/frame; v2 target ≤ 15 ms (`tasks/notes/PF-Q1-17.md`) |
| `streaming_v0.md` + `stage/*.json` | `scripts/stream_pipeline.py`, `pf/pipeline/causal_rows.py`, `pf/tracker/events.py`, `pf/stage/pushback.py` | Valentyn (pipeline-architect / gm-tracker-engineer) | **in progress 14.09** — streaming data flow, what is causal and what differs from batch; tracker events identical to production on DjwtQRdZyt0sSk; pushback rule identical on 5 of 7 videos; full streaming validation running |
| `l2_gate.md` + `l2/*.json` | `scripts/run_module.py` on the 12 pixel-free modules, production vs GM v2 inputs (`DjwtQRdZyt0sSk`) | Valentyn (qa-parity) | **done 14.09** — 11 of 11 comparable modules same verdict; lead-marshaller not runnable on numpy 2.x |
| `gm_speed.md` | `scripts/gm_bench.py`, `scripts/gm_ep_probe.py` on 600 frames of `DjwtQRdZyt0sSk`; raw reports in `speed/` | Valentyn (gm-tracker-engineer) | **done 14.09** — corrected GM speed (the first port had a wrong ORT option → cuDNN fallback): three heads 22.4 ms (v1 options) / 16.8 ms parallel (rows byte-identical) / 8.0 ms TensorRT (tolerant parity; L2 gate pending) |
| `module_consumption.md` + `.json` | code of the 27 modules `external/<repo>` (default branches, fresh clones) + `db_worker/ML_worker.py` | module-porter | **done → review** (note `tasks/notes/PF-Q1-14.md`; decision → `decisions/ADR-001`) |
| `contract_observed.md` + `ndjson_observed.json` + `scripts/inspect_ndjson.py` | real prod ndjson `G:\gat_stages\atlc5_inferences` (7 videos, 5.8 GB) | qa-parity | in-progress |
| `tracker_current.md` | code of `cv_trackers` + `cv_common` — **no access** (ssh key not in GitLab, https "not found", local clones are gone) | gm-tracker-engineer | **done → review** (389 lines; production bd43c3c covered in §12; note `tasks/notes/PF-Q1-13.md`) |
| `measurement_plan.md` | baseline: speed (ms/frame per component) + module accuracy (parity of v1↔v2 verdicts on the same videos, fail samples) | Valentyn / qa-parity | draft v1 |
| `module_compute/` (`pose_person`, `scene_gse`) | read-only audit of the 27 modules' test-set checkouts: models with sha256, calls per frame, pixel work and buffers, passes, lightening candidates with risk class and file:line | module-porter | **done 15.09** — input for PF-Q2-11 |
| `rt_module_selection.md` | which modules run in real time (groups A / B / C / not in real time) and what that fixes for GM, the tracker, the stage detector and the event context | Valentyn (module-porter) | **done 15.09** — PF-Q2-07, ADR-004 |
| `alert_label_queue.json` | wave-1 fails of the monthly report to be labelled with violation moments | Valentyn (qa-parity) | **done 15.09** — input for PF-Q2-09 |
| `rt_module_cost.md` + `.json` | `scripts/rt_module_cost.py` (every module alone behind its pseudo-GM: decisive minutes at 1x, whole event live vs batch), `scripts/rt_shared_cost.py`, `scripts/rt_joint_run.py` (the ready modules together), the `mod:sub` pass of the test set; assembled by `scripts/rt_module_report.py` | Valentyn (qa-parity) | **done 19.09**: 20 of 27 modules run in real time as they are with the batch verdict; load per module, shared GM / tracker cost, cost of sets, comparison with post-processing (PF-Q2-15) |

## Data for measurements available locally

- `G:\gat_stages\atlc5_inferences\` — `general_model<ID>.mp4.ndjson` + `trackers<ID>.mp4.ndjson` for 7 ATL-C5 events
  (format: `{"<frame_no>": [[x1,y1,x2,y2,conf,class_id], ...]}`, 1-based keys, absolute pixels 1920×1080).
- `G:\gat_stages\atlc5_videos\` — 8 mp4 (20 GB) of the same events (+1 without inferences).
- `G:\gat-streaming\data` — empty (the stand's inferences were in `G:\deepx_gat`, which is gone).
- Buckets `cv-modules-topics` / `modules-inferences`: gcloud re-authenticated 14.09 (12:40); GM v1 weights pulled via DVC into `external/general_model/weights/` (8 files, 211 MB: GM_yolov8m_best_augmentation_march2024.onnx, chocks_v4.3_200ep_yolov8.onnx, VM_yolov8m_last_september2023.onnx, camera_cls_effnet_b0_october_v1.8.1.pt, entity_det_aug_expnd.pt, mobile_sam.pt, …).
- Inference environment on this machine: torch 2.11 cu128 + RTX 5070 Ti, onnxruntime-gpu 1.29 (the CPU `onnxruntime` package that shadowed it was removed on 14.09), OpenCV 4.13, norfair 2.3 (v1 pins norfair 0.3.1 — API differs).

## How to use

- The reports are the source for ADRs and for `pf/gm`, `pf/tracker` (the interfaces are already pinned to the observed format).
- Updates: each agent overwrites its own file; the index and statuses here are maintained by `pm-coordinator`.
