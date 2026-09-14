# Репозиторії, локальні клони, інфраструктура

> **2026-09-14:** `G:\deepx_gat` (усі локальні клони) зник з диска. Свіжі клони по https — у `G:\prime_flight\external\`
> (27 модулів, `general_model` @13a4ddc master, `db_worker` @5a4aa83 master; сабмодулі `cv_common`/`db_worker` у модулях порожні —
> ssh-URL). `cv_trackers`, `cv_common`, `camera_software` недоступні: https «not found», ssh-ключ машини не в GitLab (PF-X-05).

## Основні репо (GitLab, група `dxgat`)

| Роль | GitLab | Локально | Гілка (на 2026-09-14) | Примітки |
|---|---|---|---|---|
| Усі модулі | https://gitlab.com/dxgat/detectors | `external\<repo>` (свіжі клони) | default (`master`/`main`) | 27 репо, кожен `main.py` + `local_config.yaml`; у кожному запінені саби `cv_common`, `db_worker` |
| General Model | https://gitlab.com/dxgat/detectors/general_model | `external\general_model` | `master` @ 13a4ddc | генерація детекцій; `main.py`, `scripts/engine_script.py`, `videos_selection_script.py` |
| Трекер | https://gitlab.com/dxgat/utils/cv_trackers | — (зник; недоступний) | було `master` @ b5d350c | літак, BL, GSE, люди; `tracker.py`, `local_utils/bl_utils.py` |
| db_worker | https://gitlab.com/dxgat/utils/db_worker | `external\db_worker` | `master` @ 5a4aa83 | JSON-детекти GM, треки; `ML_worker.py`, `model_starter.py`, `send_report.py` |
| cv_common | https://gitlab.com/dxgat/utils/cv_common | — (зник; недоступний) | було `tracker_optimization` @ 29def48 | helper-и: `tracked_object.py`, `transport.py`, `detections.py`, `image_preprocessing.py`, `utils/datasets.py` |
| camera_software | `git@gitlab.com:dxgat/detectors/camera_software` (за ревʼю; https-шлях не знайдено — уточнити) | — (немає локально) | @ 13ef3fc | merge, chunks_handling, classifier, notification — **зона Q1 (Wi-Fi upload)**; клонувати |

Доступ: https + Git Credential Manager працює для `general_model`, `db_worker`; `cv_trackers`, `cv_common`, `camera_software`
по https повертають «not found» (права/шлях) — локальні клони є, SSH-ключ на цій машині не налаштований (host key).

Модульні репо (M-ID → repo) і pinned-коміти ревʼю — у `04_modules.md`. Локально є також `seat-belts-used-on-all-gse-equipped-with-seat-belts`
(M25, поза скоупом) та робочі папки `_vest_verifier`, `_pa_scene_decomp`, `_steering_eval`, `onboarding_docs/` (safety_vests.md, walkaround.md).

## Репо Prime Flight (GitHub)

https://github.com/valentyn-fedorov-deepx/prime_flight — private, гілка `main`, push через https (gh auth, keyring). Коміти англійською, без Claude-трейлерів; `external/` і великі артефакти — поза git.

## Стенд стрімінгу

`G:\gat-streaming` — **не прод**, тестовий стенд: контракт (`streaming/contract.py`), сесія (`session.py`), раннер
прод-модулів у стрім-режимі (`runner.py`), воркери (`workers/meta_worker.py`, `lossy_worker.py`, `sanitize_tracks.py`),
інструменти (`tools/compare_runs.py`, `pick_balanced.py`, `fetch_compatible.py`, `parse_gt.py`, `chunk_study.py`), CI (23 тести, <1 с).

```bash
cd G:\gat-streaming && pip install -r requirements-ci.txt && pytest          # гейти рівня 1
python -m streaming.runner --mod aircraft-chocks --entry main        --inf data/inferences --videos-dir data/videos --gt data/gt_by_video.json --out out/batch.json
python -m streaming.runner --mod aircraft-chocks --entry main_stream --inf data/inferences --videos-dir data/videos --gt data/gt_by_video.json --out out/stream.json
python tools/compare_runs.py --batch out/batch.json --stream out/stream.json --gt data/gt_by_video.json   # exit 1 при розбіжності
python -m streaming.runner --mod beltloader-chocks --no-video --drop-at 0.3 0.6 --drop-mode fill ...        # рівень 3: втрата чанка
```

## Інфраструктура

| Що | Де |
|---|---|
| GCP проєкт | `rampvision-2` |
| Бакети | `CamboxChunks` (чанки), `Videos-to-process` (злиті full-turn), `cv-modules-topics` (GM/tracker ndjson per-frame), `modules-inferences` (smart timeline), prod/dev3 |
| Оркестрація | GKE Jobs (GM, Trackers, Modules), Cloud Run (ping, logs, pub-sub subscriber), Pub/Sub |
| БД | MongoDB (video docs, event docs, video/event tasks) |
| Портали | RampVision website (prod/dev), MLflow, Google Sheets (місячні звіти/розмітка) |
| Ваги | DVC (не в git) |
| Заміри RT | RTX 5070 Ti 16 ГБ, onnxruntime-gpu 1.29; вхід 1920×1080 @ 8 к/с H.264 ≈4 Мбіт/с |

## Конвенції роботи з кодом

- Гілки: `pf/<PF-ID>-<slug>` (напр. `pf/q1-03-stage-detector-v0`). Коміти англійською, короткі, без Claude-трейлерів.
- Push і MR робить людина-власник. Агент лишає: diff, опис MR, як перевіряти.
- Не міняти pinned `cv_common` у модулі поза задачею PF-Q3-05.
- Великі артефакти (інференси 500–800 МБ/відео, ваги, відео) — тільки бакети/DVC.
