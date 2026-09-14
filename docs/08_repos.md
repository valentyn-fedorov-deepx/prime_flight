# Repositories, local clones, infrastructure

> **2026-09-14:** `G:\deepx_gat` (all local clones) has vanished from the disk. Fresh clones over https are in `G:\prime_flight\external\`
> (27 modules, `general_model` @13a4ddc master, `db_worker` @5a4aa83 master; the `cv_common`/`db_worker` submodules inside the modules are empty —
> ssh URL). `cv_trackers`, `cv_common`, `camera_software` are unavailable: https "not found", the machine's ssh key is not in GitLab (PF-X-05).

## Main repos (GitLab, group `dxgat`)

| Role | GitLab | Locally | Branch (as of 2026-09-14) | Notes |
|---|---|---|---|---|
| All modules | https://gitlab.com/dxgat/detectors | `external\<repo>` (fresh clones) | default (`master`/`main`) | 27 repos, each with `main.py` + `local_config.yaml`; each has the `cv_common`, `db_worker` subs pinned |
| General Model | https://gitlab.com/dxgat/detectors/general_model | `external\general_model` | `master` @ 13a4ddc | detection generation; `main.py`, `scripts/engine_script.py`, `videos_selection_script.py` |
| Tracker | https://gitlab.com/dxgat/utils/cv_trackers | `external\cv_trackers` (from the lead's archive) | `master` @ b5d350c | aircraft, BL, GSE, people; `tracker.py`, `local_utils/bl_utils.py` |
| db_worker | https://gitlab.com/dxgat/utils/db_worker | `external\db_worker` | `master` @ 5a4aa83 | GM JSON detections, tracks; `ML_worker.py`, `model_starter.py`, `send_report.py` |
| cv_common | https://gitlab.com/dxgat/utils/cv_common | `external\cv_common` (from the lead's archive) | `master` @ ac5098d | helpers: `tracked_object.py`, `transport.py`, `detections.py`, `image_preprocessing.py`, `utils/datasets.py` |
| camera_software | `git@gitlab.com:dxgat/detectors/camera_software` (per the architecture review; https path not found — to be clarified) | — (not available locally) | @ 13ef3fc | merge, chunks_handling, classifier, notification — **Q1 zone (Wi-Fi upload)**; to be cloned |

Access: https + Git Credential Manager works for `general_model`, `db_worker`; `cv_trackers`, `cv_common`, `camera_software`
over https return "not found" (permissions/path) — local clones exist, the SSH key on this machine is not configured (host key).

Module repos (M-ID → repo) and the architecture review's pinned commits are in `04_modules.md`. Locally there is also `seat-belts-used-on-all-gse-equipped-with-seat-belts`
(M25, out of scope) and the working folders `_vest_verifier`, `_pa_scene_decomp`, `_steering_eval`, `onboarding_docs/` (safety_vests.md, walkaround.md).

## Prime Flight repo (GitHub)

https://github.com/valentyn-fedorov-deepx/prime_flight — private, branch `main`, push over https (gh auth, keyring). Commits in English, without Claude trailers; `external/` and large artifacts are outside git.

## The gat-streaming stand (test bench)

`G:\gat-streaming` — **not production**, a test stand (test bench): the contract (`streaming/contract.py`), the session (`session.py`), the runner
of the production modules in stream mode (`runner.py`), workers (`workers/meta_worker.py`, `lossy_worker.py`, `sanitize_tracks.py`),
tools (`tools/compare_runs.py`, `pick_balanced.py`, `fetch_compatible.py`, `parse_gt.py`, `chunk_study.py`), CI (23 tests, <1 s).

```bash
cd G:\gat-streaming && pip install -r requirements-ci.txt && pytest          # level-1 gates
python -m streaming.runner --mod aircraft-chocks --entry main        --inf data/inferences --videos-dir data/videos --gt data/gt_by_video.json --out out/batch.json
python -m streaming.runner --mod aircraft-chocks --entry main_stream --inf data/inferences --videos-dir data/videos --gt data/gt_by_video.json --out out/stream.json
python tools/compare_runs.py --batch out/batch.json --stream out/stream.json --gt data/gt_by_video.json   # exit 1 on mismatch
python -m streaming.runner --mod beltloader-chocks --no-video --drop-at 0.3 0.6 --drop-mode fill ...        # level 3: chunk loss
```

## Infrastructure

| What | Where |
|---|---|
| GCP project | `rampvision-2` |
| Buckets | `CamboxChunks` (chunks), `Videos-to-process` (merged full-turn), `cv-modules-topics` (GM/tracker ndjson per-frame), `modules-inferences` (smart timeline), prod/dev3 |
| Orchestration | GKE Jobs (GM, Trackers, Modules), Cloud Run (ping, logs, pub-sub subscriber), Pub/Sub |
| DB | MongoDB (video docs, event docs, video/event tasks) |
| Portals | RampVision website (prod/dev), MLflow, Google Sheets (monthly reports/labeling) |
| Weights | DVC (not in git) |
| RT measurements | RTX 5070 Ti 16 GB, onnxruntime-gpu 1.29; input 1920×1080 @ 8 fps H.264 ≈4 Mbit/s |

## Code conventions

- Branches: `pf/<PF-ID>-<slug>` (e.g. `pf/q1-03-stage-detector-v0`). Commits in English, short, without Claude trailers.
- Push and MR are done by the human owner. The agent leaves: the diff, the MR description, how to verify.
- Do not change the pinned `cv_common` in a module outside task PF-Q3-05.
- Large artifacts (inferences 500–800 MB/video, weights, videos) — only buckets/DVC.
