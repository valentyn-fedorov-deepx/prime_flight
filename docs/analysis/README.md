# Analysis (Q1, started 2026-09-14): what GM + Tracker are really responsible for, and what the modules read from them

Phase goal: before rebuilding GM/Tracker (v2) and moving to chunk-wise processing, pin down (a) the current
responsibilities of GM and the tracker, (b) the exact interface consumed by the 27 modules, (c) the observed format
of the prod output on real data, (d) how to measure that module accuracy has not dropped with v2.

| Report | Source | Who | Status |
|---|---|---|---|
| `gm_current.md` | code of `external/general_model` (master @ 13a4ddc = review pin) + `external/db_worker` | gm-tracker-engineer | **done → Yurii's review** (375 lines; note `tasks/notes/PF-Q1-12.md`) |
| `module_consumption.md` + `.json` | code of the 27 modules `external/<repo>` (default branches, fresh clones) + `db_worker/ML_worker.py` | module-porter | **done → review** (note `tasks/notes/PF-Q1-14.md`; decision → `decisions/ADR-001`) |
| `contract_observed.md` + `ndjson_observed.json` + `scripts/inspect_ndjson.py` | real prod ndjson `G:\gat_stages\atlc5_inferences` (7 videos, 5.8 GB) | qa-parity | in-progress |
| `tracker_current.md` | code of `cv_trackers` + `cv_common` — **no access** (ssh key not in GitLab, https "not found", local clones are gone) | gm-tracker-engineer | blocked |
| `measurement_plan.md` | baseline: speed (ms/frame per component) + module accuracy (parity of v1↔v2 verdicts on the same videos, fail samples) | Valentyn / qa-parity | draft v1 |

## Data for measurements available locally

- `G:\gat_stages\atlc5_inferences\` — `general_model<ID>.mp4.ndjson` + `trackers<ID>.mp4.ndjson` for 7 ATL-C5 events
  (format: `{"<frame_no>": [[x1,y1,x2,y2,conf,class_id], ...]}`, 1-based keys, absolute pixels 1920×1080).
- `G:\gat_stages\atlc5_videos\` — 8 mp4 (20 GB) of the same events (+1 without inferences).
- `G:\gat-streaming\data` — empty (the stand's inferences were in `G:\deepx_gat`, which is gone).
- Buckets `cv-modules-topics` / `modules-inferences`: gcloud is authenticated, but `Reauthentication required` → `gcloud auth login`.

## How to use

- The reports are the source for ADRs and for `pf/gm`, `pf/tracker` (the interfaces are already pinned to the observed format).
- Updates: each agent overwrites its own file; the index and statuses here are maintained by `pm-coordinator`.
