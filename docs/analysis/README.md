# Аналітика (Q1, старт 2026-09-14): за що реально відповідають GM + Tracker, і що з них читають модулі

Мета фази: перед тим як перезбирати GM/Tracker (v2) і робити по-чанкову обробку, зафіксувати (а) поточні
обов'язки GM і трекера, (б) точний інтерфейс, який споживають 27 модулів, (в) спостережуваний формат
прод-виходу на реальних даних, (г) як міряти, що з v2 точність модулів не впала.

| Звіт | Джерело | Хто | Стан |
|---|---|---|---|
| `gm_current.md` | код `external/general_model` (master @ 13a4ddc = пін ревʼю) + `external/db_worker` | gm-tracker-engineer | in-progress |
| `module_consumption.md` + `.json` | код 27 модулів `external/<repo>` (default-гілки, свіжі клони) + `db_worker/ML_worker.py` | module-porter | in-progress |
| `contract_observed.md` + `ndjson_observed.json` + `scripts/inspect_ndjson.py` | реальні прод-ndjson `G:\gat_stages\atlc5_inferences` (7 відео, 5.8 ГБ) | qa-parity | in-progress |
| `tracker_current.md` | код `cv_trackers` + `cv_common` — **немає доступу** (ssh-ключ не в GitLab, https «not found», локальні клони зникли) | gm-tracker-engineer | blocked |
| `measurement_plan.md` | baseline: швидкість (мс/кадр по компонентах) + точність модулів (паритет вердиктів v1↔v2 на тих самих відео, fail-вибірки) | qa-parity | todo |

## Дані для замірів, що є локально

- `G:\gat_stages\atlc5_inferences\` — `general_model<ID>.mp4.ndjson` + `trackers<ID>.mp4.ndjson` для 7 ATL-C5 подій
  (формат: `{"<frame_no>": [[x1,y1,x2,y2,conf,class_id], ...]}`, 1-based ключі, абсолютні пікселі 1920×1080).
- `G:\gat_stages\atlc5_videos\` — 8 mp4 (20 ГБ) тих самих подій (+1 без інференсів).
- `G:\gat-streaming\data` — порожньо (інференси стенду були в `G:\deepx_gat`, який зник).
- Бакети `cv-modules-topics` / `modules-inferences`: gcloud автентифікований, але `Reauthentication required` → `gcloud auth login`.

## Як користуватись

- Звіти — джерело для ADR і для `pf/gm`, `pf/tracker` (інтерфейси вже зафіксовані під спостережуваний формат).
- Оновлення: агент перезаписує свій файл; індекс і статуси тут веде `pm-coordinator`.
