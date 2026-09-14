# Прод-архітектура DXGAT сьогодні (as-is, вересень 2026)

Джерела: діаграми «Dataflow diagram of DXGAT video processing» і «Cambox flow diagram» (Confluence), код `db_worker`,
`general_model`, `cv_trackers`, `camera_software`. Усе нижче — пост-обробка: жоден результат не з'являється, поки
подія (turnaround) не завершена і чанки не злиті у full-turn відео.

## 1. Cambox flow (на гейті)

```
камера (cone / wing) ──1-хв mp4──► CamboxChunks bucket (GCS)
   │                                     │
   ├─ logs ──► logs bucket ◄── logs handling (Cloud Run)
   ◄─ ping ── ping service (Cloud Run) ──DB record──► MongoDB
                                         │
                       pub-sub-camboxes-subscriber (Cloud Run):
                       збирає чанки у список для merge script
                                         │  pub-sub cam. sub. logic
                                         ▼
                                    Merge script ──full turns──► ML processing pipeline
```

- CameraBox записує **1-хвилинні відео** (1080p, 8 к/с, H.264, ≈4 Мбіт/с на камеру) і виливає чанки в бакет
  після/під час події — саме тут Q1 додає вивантаження по Wi-Fi/SIM **під час запису**.
- `ping service` стежить за живістю камери й пише запис у MongoDB; `logs handling` складає логи.
- `pub-sub-camboxes-subscriber` формує список чанків події для merge.

## 2. Dataflow обробки (сервер, GKE)

```
Cambox ──chunks──► CamboxChunks (GCS) ──Cambox bucket checker──► Merge Script (GKE Job) ──video merged──► Videos-to-process (GCS)
                                                                                                             │ subscriber
        ┌────────────────────────────────────────────────────────────────────────────────────────────────────┘
        ▼                              Receiver                            Receiver
  General Model (GKE Job) ─────────────────────► Trackers (GKE Job) ─────────────────────► Modules (GKE Jobs)
  · детекція об'єктів                            · трекінг літака, BL, GSE, людей          · CV module inference
  · класифікація камери (cone / wing)                                                       · smart timeline
  · тип літака (aircraft / jet)                                                             │
  · entity (авіакомпанія)                                                                   │
        │ per-frame inferences .ndjson             │ per-frame tracks .ndjson               │ smart-timeline data
        ▼                                          ▼                                        ▼
  cv-modules-topics (GCS bucket: GM / tracker inference storage) ◄── modules читають GM+tracker ndjson
                                                                                     modules-inferences (GCS) ──► RampVision Website
  GM / Trackers / Modules ──update video doc, create/update event doc, video/event tasks──► MongoDB ──video & event data──► RampVision
```

Raw full-turn відео йде і в GM, і в трекери, і в модулі (частина модулів читає пікселі — див. вісь 2 у `04_modules.md`).

## 3. Що саме робить кожен вузол

| Вузол | Репо | Роль | Вихід |
|---|---|---|---|
| Merge Script | `camera_software` (`merge.py`, `chunks_handling/`) | знайти, впорядкувати, злити чанки в full-turn відео; класифікатор межі події | mp4 у Videos-to-process, повідомлення |
| General Model | `detectors/general_model` (`main.py`, `scripts/engine_script.py`) | YOLO-детекції (GM_yolov8m @1088 + chocks_v4.3 @1280 тощо), камера cone/wing, тип літака, entity | `.ndjson` per-frame у cv-modules-topics |
| Trackers | `utils/cv_trackers` (`tracker.py`, `local_utils/bl_utils.py`) | ідентичність і рух: літак (arrival/departure по 4 с/10 с зупинки/руху), BL, GSE, люди; семантика BL biля дверей | `.ndjson` per-frame треки зі `state_dict` |
| Modules | `detectors/<27 repos>` (`main.py` кожен) | логіка перевірки; читає GM+tracker ndjson (і пікселі, якщо треба) | Pass/Fail/NO + report + smart timeline |
| db_worker | `utils/db_worker` (`ML_worker.py`, `model_starter.py`, `send_report.py`) | завантаження медіа/метаданих, запуск моделей, звіти в MongoDB | video/event docs, tasks |
| cv_common | `utils/cv_common` | спільна бібліотека: `tracked_object.py`, `transport.py`, `detections.py`, `image_preprocessing.py` | — |

## 4. Відомі вузькі місця (чому Time to Result ≈ 24 год)

1. **Чекання на завершення події і merge**: нічого не запускається, поки всі чанки не залиті й не злиті. Q1 прибирає це
   (upload під час запису + обробка по чанках без раннього merge).
2. **Послідовні GKE-джоби** GM → трекери → модулі на повному відео; 27 модулів = 27 always-on воркерів на відео.
3. **9 модулів самі перераховують arrival stage** з приватних полів трекера, 2 — `pushback_attached` другим проходом
   (aircraft-chocks, pin-verification). Кожна копія дрейфує → stage detector як єдиний власник (Q1).
4. `db_worker.ML_worker.load_source` для rtsp/http кидає `Exception("Stream is not implemented yet")` — приймання
   потоку в проді відсутнє, RT-гілка будується з нуля (Q2).
5. Схеми `state_dict` трекера без версії: у бакеті по 15–16 версій інференсів на відео, несумісність видно лише падінням.
6. Модулі запінені на **різних** версіях `cv_common` (ac5098d, dd5b554, 86731e4 …) — спільні компоненти потребують уніфікації.

## 5. Що обчислюється де (для тирингу)

- **Edge (CameraBox)**: тільки запис і вивантаження. Бюджет і залізо на камері не передбачають інференсу.
- **Streaming (сервер, live)**: RT-гілка — потік на сервер, GM+трекер+stage detector+RT-модулі, бюджет 125 мс/кадр @ 8 к/с.
- **Post (сервер, після події)**: як зараз, на full-turn — walk-around-и, conditioned air lookback, і все, що «за суттю POST».
