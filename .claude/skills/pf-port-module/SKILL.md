---
name: pf-port-module
description: Чеклист перенесення одного CV-модуля DXGAT у streaming/real-time — аудит проходів/пікселів/моделей/приватних полів трекера, стадія та події, причинність (шаблон main_stream.py), паритет пакет↔стрім, замір на fail-відео, оновлення module_map.json і борду. Аргумент — назва репо модуля (напр. beltloader-chocks).
---

Модуль: `$ARGUMENTS` (репо в `G:\deepx_gat\<repo>`). Виконує агент `module-porter`; `qa-parity` закриває.

## 0. Картка
- Знайди модуль у `docs/04_modules.md` (stage, opens/closes, decision, verdict, компоненти, attention) і в `docs/05_module_logic.md` (клієнтська Pass/Fail/NO логіка, камери, tier).
- Якщо картки немає або verdict застарів — виправ `docs/streaming_ref/module_map.json`, запусти `python scripts/build_docs.py`.

## 1. Аудит коду (заповни таблицю в `tasks/notes/<ID>.md`)
| питання | як перевірити |
|---|---|
| проходів по метаданих | `grep -n "load_metadata\|enumerate(metadata" main.py` |
| читає пікселі | `grep -n "get_im0s\|imread\|VideoCapture" -r .` |
| власні моделі | `grep -n "onnx\|\.pth\|torch.load\|InferenceSession" -r .` |
| приватні поля трекера / локальний arrival stage | `grep -n "_p0\|_prev_p0\|_st\b\|arrival_frame\|departure_frame\|pushback" main.py` |
| пін cv_common / db_worker | `git -C <repo> submodule status` |
| кількість кадрів/fps без відео | чи використовується `dataset` після `load_source()` |

## 2. Стадія і події
- Замінити локальні розрахунки якорів на `anchors`/`events` з контракту (єдиний власник — stage detector).
- Визначити `opens`/`closes`; для lookback — вікно від `anchors`.

## 3. Причинність
- passes = 2 → знайти «величину з майбутнього»; шаблон `G:\gat-streaming\modules\aircraft-chocks\main_stream.py` (`_STREAM_SKIP`, онлайн-накопичення, медіана в момент звіту; порядок «додати після перевірки на відліт»).
- passes = 1 → без правок логіки; лише гейтування.

## 4. Паритет і заміри (команди в `docs/08_repos.md`)
```
python -m streaming.runner --mod <repo> --entry main        ... --out out/batch.json
python -m streaming.runner --mod <repo> --entry main_stream ... --out out/stream.json   # або --no-video, якщо пікселі не читає
python tools/compare_runs.py --batch out/batch.json --stream out/stream.json --gt data/gt_by_video.json
python tools/pick_balanced.py --check "<назва перевірки>"    # усі fail + стільки ж pass
python -m streaming.runner --mod <repo> --no-video --drop-at 0.3 0.6 --drop-mode fill ...   # втрата чанка
```
- Таблиця: відео × пакет × стрім × зсув; кожна розбіжність — механізм. Зміна покриття Not observed — окремо.
- Декодер закріплений, машина вільна, умови записані.

## 5. Семантика
- Якщо для превенції треба інший момент рішення — **не патчити**: тег `trigger-change`, ADR, погодження Ігоря/Оксани.

## 6. Закриття
- Гілка `pf/<id>-<slug>`, мінімальний diff по хунках, нотатка з таблицями, рядок у `tasks/BOARD.md` → `review`; `qa-parity` → `done`.
