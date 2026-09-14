# Analysis (Q1, started 2026-09-14): what GM + Tracker are really responsible for, and what the modules read from them

Phase goal: before rebuilding GM/Tracker (v2) and moving to chunk-wise processing, pin down (a) the current
responsibilities of GM and the tracker, (b) the exact interface consumed by the 27 modules, (c) the observed format
of the prod output on real data, (d) how to measure that module accuracy has not dropped with v2.

| Report | Source | Who | Status |
|---|---|---|---|
| `gm_current.md` | code of `external/general_model` (master @ 13a4ddc = review pin) + `external/db_worker` | gm-tracker-engineer | **done → Yurii's review** (375 lines; note `tasks/notes/PF-Q1-12.md`). Describes master 13a4ddc; the production commit a0157a4 differs — see `gm_prod_delta.md` |
| `gm_prod_delta.md` | bucket object names (`general_modela0157a4`, `trackersbd43c3c`) + `git diff` master→production; worktrees `external/general_model_prod`, `external/cv_trackers_prod` | Valentyn (gm-tracker-engineer) | **done** — production GM/tracker commits ≠ the review pin; BGR→RGB was the decisive difference; GM v2 head parity 99.8 % pairs |
| `module_consumption.md` + `.json` | code of the 27 modules `external/<repo>` (default branches, fresh clones) + `db_worker/ML_worker.py` | module-porter | **done → review** (note `tasks/notes/PF-Q1-14.md`; decision → `decisions/ADR-001`) |
| `contract_observed.md` + `ndjson_observed.json` + `scripts/inspect_ndjson.py` | real prod ndjson `G:\gat_stages\atlc5_inferences` (7 videos, 5.8 GB) | qa-parity | in-progress |
| `tracker_current.md` | code of `cv_trackers` + `cv_common` — **no access** (ssh key not in GitLab, https "not found", local clones are gone) | gm-tracker-engineer | **done → review** (389 lines; production bd43c3c covered in §12; note `tasks/notes/PF-Q1-13.md`) |
| `measurement_plan.md` | baseline: speed (ms/frame per component) + module accuracy (parity of v1↔v2 verdicts on the same videos, fail samples) | Valentyn / qa-parity | draft v1 |

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
