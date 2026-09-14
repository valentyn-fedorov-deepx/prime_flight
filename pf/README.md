# `pf` — Prime Flight core package

Збираємо тут, по частинах, стрімінгову версію CV-пайплайну DXGAT. Порядок — той, що в roadmap: контракт і приймач
(є), потім GM v2 і Tracker v2 (після аналізу в `docs/analysis/`), потім stage detector, потім адаптери модулів.

| Пакет | Стан | Що це |
|---|---|---|
| `pf.contract` | **готово, тести** | Контракт кадру schema 1.0: `schema_version`, `frame_id`, `general_model`, `trackers` + опційні `stage`/`events`/`anchors`; гігієна витікання полів між класами трекера. Портовано зі стенду `gat-streaming`. |
| `pf.receiver` | **готово, тести** | `Session`: один event = один неперервний потік = один трекер (X1); заповнення дірок заглушками (X2); `stream_from_chunks` для тестів транспорту. |
| `pf.eval` | **готово, тести** | Паритет: digest потоків, `diff_streams`, `compare_gm_ndjson` (старий vs новий GM по кадрах, з допуском, матчинг по `frame_id`, а не по позиції). |
| `pf.gm` | інтерфейс | `FrameDetector` (кадр → детекції `[x1,y1,x2,y2,conf,class_id]`), `VideoContext` (інкрементні per-video рішення з подією «вирішено на кадрі X»). Реалізація — після `docs/analysis/gm_current.md`. |
| `pf.tracker` | інтерфейс | `Tracker.update(frame_id, detections)` причинний, один на подію; `state_dict` per class = контракт. Реалізація — після аналізу трекера (потрібен доступ до `cv_trackers`/`cv_common`). |
| `pf.stage` | словник | `STAGES`, `EVENTS` (у `pf.contract.frame`). Автомат — задача PF-Q1-03. |

## Правила для коду в `pf`

- Ядро інференсу не знає про відео-файли, чанки, MongoDB і бакети — тільки кадр → детекції / детекції → треки.
- Усе, що модулі споживають сьогодні (формат детекції, `class_id`-мапа, ключі `state_dict`, нумерація кадрів з 1),
  лишається побітово сумісним, або змінюється через ADR + `schema_version`.
- Кожна зміна доводиться паритетом на реальних ndjson (`pf.eval`) і замірами на fail-відео, не «на око».
- Швидкі гейти (`pytest`) не потребують torch/onnx/opencv і мають бігти < 1 с.

```bash
pip install -e ".[ci]"   # або просто: pip install pytest
pytest
```
