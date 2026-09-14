# Prime Flight — борд задач (єдине джерело правди)

Статуси: `todo` · `in-progress` · `review` · `blocked` · `done` · `dropped`. Теги: `trigger-change`, `decision-needed`, `external`.
ID: `PF-Qn-nn`. Нотатка по задачі — `tasks/notes/<ID>.md`. Оновлює власник або `pm-coordinator`.
Стан на 2026-09-14 (оновлено 12:30): **чернетка ліда** — узгодити з Максимом Ч., Юрієм, Аріаном; після рецензії Ігоря/Сергія зняти позначку draft.
Фаза «аналіз GM/Tracker/модулів» стартувала 14.09: задачі PF-Q1-12…17, звіти в `docs/analysis/`. Код збираємо в пакеті `pf/` цього репо (GitHub — PF-X-04).

---

## Q1 — Continuous Upload + Faster Post-Processing (місяці 1–3)

| ID | Задача | Власник | Агент | Статус | Deps | Acceptance |
|---|---|---|---|---|---|---|
| PF-Q1-01 | Wi-Fi/SIM вивантаження чанків з CameraBox **під час запису** (camera_software: chunks_handling, storage_handling); решта пайплайну як є | Максим Ч. | pipeline-architect | todo | PF-Q1-08, зовнішнє: канал/VPN | чанк доступний у бакеті ≤ 30 с після закриття файлу; merge і далі працює без змін; заміряно Time-to-first-chunk на 1 гейті |
| PF-Q1-02 | Приймач чанків + реєстр сесій: порядок, gap-fill заглушками, `frame_id`, `schema_version` (референс `gat-streaming/streaming/session.py`, `contract.py`) | Максим Ч. | pipeline-architect | todo | — | тести паритету чанкова подача = наскрізна побітово; втрата чанка не зсуває нумерацію (`drop-mode fill`) |
| PF-Q1-03 | Stage detector v0: T_arr, T_dep, BL@door, BL leave, `pushback_attached` (нерухома рамка N с) як єдиний власник; `stage/events/anchors` у контракті | Максим Ч. | pipeline-architect | todo | PF-Q1-06 | події на кожному кадрі; латентність 4 с/10 с; на 8 відео стенду якорі збігаються з пакетними ±1 кадр (крім документованого зсуву Nose wheel) |
| PF-Q1-04 | Прибрати merge з раннього етапу: GM v2 + Tracker v2 біжать по чанках у міру надходження через `pf.receiver.Session` (один трекер на подію), модулі отримують кадри «на ходу», merge лише для архіву/пост-модулів | Максим Ч. (+Валентин) | pipeline-architect | todo | PF-Q1-02, PF-Q1-16, PF-Q1-17 | вердикти E0-модулів ідентичні пакетним на збалансованій вибірці; Time to Result заміряно до/після |
| PF-Q1-05 | GM: гігієна під по-чанкову обробку (без залежності від повного відео: класифікація камери/типу літака/entity з перших N кадрів), реєстр моделей, dead models (wing-walkers wand), чужий `model_name` у `__main__` | Юрій + Валентин | gm-tracker-engineer | todo | — | GM працює на потоці чанків без merge; вихід ndjson побітово = пакетному |
| PF-Q1-06 | Tracker: `schema_version` у `state_dict`, тест витікання полів (`VEHICLE_ONLY_KEYS`), один трекер на подію без скидання, події для stage detector (BL@door, BL leave), `pushback_attached` причинно зі стаціонарністю | Юрій + Валентин | gm-tracker-engineer | todo | — | `check_class_leakage` зелений; 5 «літаків» на референс-відео; зсув якоря Nose wheel ≤ 24 с або задокументований (D5) |
| PF-Q1-07 | CI паритету: гейти рівня 1 у пайплайні репо + nightly на GPU-раннері (`compare_runs.py`, exit 1 при розбіжності) | Денис (+ запит Ігорю на раннер) | qa-parity | blocked `external` | раннер | nightly червоніє при розбіжності пакет↔стрім хоча б для 4 перевірок першої черги |
| PF-Q1-08 | Baseline Time to Result: заміряти поточні ≈24 год по етапах (upload, merge, GM, трекер, модулі, доставка) на 10 подіях | Валентин | pm-coordinator | todo | — | таблиця етапів із медіаною/p90; узгоджена з Ігорем як baseline KPI |
| PF-Q1-09 | Fail-розмітка для збалансованих вибірок: Main gear на всіх 30 fail; Nose wheel; BL forward chock; pushback-pathway (вікно 45 с, класи transport) | Денис / Оксана | qa-parity | todo | — | `gt_by_video.json` покриває всі fail-и місячних звітів для 4 перевірок першої черги |
| PF-Q1-10 | Ієрархія GM → група → модуль і спільні компоненти E01–E33 як план рефакторингу (що виносимо з модулів у shared) | Владислав + Юрій | module-porter | todo | — | таблиця «компонент → модулі-споживачі → де живе код зараз → куди йде»; ревʼю Ігоря |
| PF-Q1-11 | Delivery Q1: демо «відео надходить, поки CameraBox пише» + звіт Time to Result до/після | Валентин | pm-coordinator | todo | Q1-01…06 | демо клієнту; звіт у `tasks/notes/PF-Q1-11.md` |
| PF-Q1-12 | **Аналіз GM as-is**: обов'язки, моделі, per-frame схема, per-video рішення (камера/тип/entity), припущення «повне відео», перф-профіль, рекомендації до v2 → `docs/analysis/gm_current.md` | Валентин (+Юрій ревʼю) | gm-tracker-engineer | in-progress | клон `external/general_model` @13a4ddc | звіт з file:line; список «що має лишитись побітово» для модулів |
| PF-Q1-13 | **Аналіз Tracker + cv_common as-is**: state_dict per class, події arrival/departure, BL-семантика, скидання, оптичний потік `_p0/_st` → `docs/analysis/tracker_current.md` | Юрій + Валентин | gm-tracker-engineer | blocked `external` | доступ до `cv_trackers`/`cv_common` (PF-X-05) | звіт + мінімальний контракт `state_dict` |
| PF-Q1-14 | **Матриця споживання**: що кожен із 27 модулів читає з GM (класи/поля) і трекера (`state_dict`, приватні поля), пікселі, проходи, піни → `docs/analysis/module_consumption.{md,json}` | Валентин (+Владислав) | module-porter | in-progress | клони 27 модулів у `external/` | union класів GM і полів трекера = контракт сумісності v2 |
| PF-Q1-15 | **Baseline-замір і harness**: (а) швидкість мс/кадр по компонентах на повному turnaround; (б) точність: паритет per-frame ndjson v1↔v2 (`pf.eval.compare_gm_ndjson`) + паритет вердиктів модулів на тих самих відео + fail-вибірки; дані: ATL-C5 локально (7 відео) + бакети після `gcloud auth login` → `docs/analysis/measurement_plan.md`, `contract_observed.md` | Денис / Оксана / Валентин | qa-parity | in-progress | PF-Q1-09 | методика узгоджена з Ігорем; перший прогін baseline на 7 ATL-C5 відео |
| PF-Q1-16 | **GM v2** у `pf/gm`: чисте ядро кадр→детекції (`FrameDetector`), інкрементний `VideoContext` (камера/тип/entity з подією «вирішено на кадрі X»), I/O-адаптери окремо; побітова сумісність формату `[x1,y1,x2,y2,conf,class_id]` і class-id мапи | Юрій + Валентин | gm-tracker-engineer | todo | PF-Q1-12, PF-Q1-14, PF-Q1-15 | паритет ndjson v1↔v2 на 7 відео (frame_parity ≥ 0.99 при ndigits=1 або кожна розбіжність пояснена); ≤ 28 мс/кадр; вердикти модулів незмінні |
| PF-Q1-17 | **Tracker v2** у `pf/tracker`: причинний, один на подію, `schema_version` у `state_dict`, події для stage detector (BL@door/BL leave/pushback stationarity), без приватних полів у контракті | Юрій + Валентин | gm-tracker-engineer | todo | PF-Q1-13, PF-Q1-14 | паритет `state_dict` по споживаних полях на 7 відео; 5 «літаків» на референс-відео; вердикти модулів незмінні |

## Q2 — Real-Time Architecture Foundation (місяці 4–6)

| ID | Задача | Власник | Агент | Статус | Deps | Acceptance |
|---|---|---|---|---|---|---|
| PF-Q2-01 | RT-гілка: покадрове (не чанкове) приймання на GPU-хост, декод на місці, шина контракту, гейтування модулів за stage detector | Максим Ч. | pipeline-architect | todo | PF-Q1-02, PF-Q1-03 | end-to-end latency кадр → контракт ≤ 125 мс (p95) на 1 камері; 3,95× RT на повному turnaround не деградує |
| PF-Q2-02 | GM/Tracker під RT: RT-GM (≈6 класів), batching/ONNX або TensorRT, рішення 1080p vs 720p (recall −≈3 %), профіль пам'яті на N камер | Юрій + Валентин | gm-tracker-engineer | todo | PF-Q1-05, PF-Q1-06 | GM ≤ 28 мс/кадр збережено або покращено; кількість камер на 1 GPU задокументована |
| PF-Q2-03 | **Перший RT-модуль**: `beltloader-chocks` (E0·I1, NOW, повнота 83 %/влучність 91 %) через гейт BL@door…BL leave | Валентин / Юрій | module-porter | todo | PF-Q2-01 | паритет пакет↔стрім 0 розбіжностей на збалансованій вибірці; вердикт у момент BL leave, до merge |
| PF-Q2-04 | Хедж-кандидати без залежності від змін GM/Tracker: `pushback-does-not-start-until-wing-walkers…` (E0·I1), `bl_rear_cone`, `3-stop-brake-check` | Валентин / Юрій | module-porter | todo | PF-Q2-01 | хоча б один додатковий модуль у RT з паритетом |
| PF-Q2-05 | Гейтування модулів у RT-гілці (open/close за подіями, 4–9 активних на стадію замість 27) | Максим Ч. | pipeline-architect | todo | PF-Q1-03 | ресурс на подію ↓ ≥ 2× vs always-on; lookback-модулі без буфера повтору |
| PF-Q2-06 | Delivery Q2: демо «модуль дає результат до завершення merge» | Валентин | pm-coordinator | todo | PF-Q2-03 | демо клієнту + замір Time to Result для RT-перевірки |

## Q3 — Real-Time Expansion + Alerting (місяці 7–9)

| ID | Задача | Власник | Агент | Статус | Deps | Acceptance |
|---|---|---|---|---|---|---|
| PF-Q3-01 | Шина алертів: дедуплікація, вікна тиші, життєвий цикл тривоги, MongoDB-схема, endpoint, рендеринг на RampVision (кейс: 357 алертів на одному відео без дедуплікації) | Аріан | alerting-engineer | todo | PF-Q2-03 | ≤ 1 алерт на подію-порушення; латентність вердикт → алерт ≤ 5 с; список відкритих питань до Ігоря закритий |
| PF-Q3-02 | Хвиля E0 (12 модулів «як є»): за вагою I1 → I2 → I3 | Валентин / Юрій / Владислав | module-porter | todo | PF-Q2-05 | кожен — паритет + замір на fail-відео; статус done лише після qa-parity |
| PF-Q3-03 | Хвиля E1 (кадри без власних моделей, 4 модулі) | module-porter (розподіл на старті Q3) | module-porter | todo | PF-Q3-02 | те саме + вартість на кадр заміряна |
| PF-Q3-04 | PATCH-модулі через подію детектора: `aircraft-chocks` (main_stream, 0 розбіжностей Main gear), `pin-verification` | Юрій | module-porter | todo | PF-Q1-03 | обидва однопрохідні; `pushback_attached` лише з детектора |
| PF-Q3-05 | Техборг архітектури: уніфікація пінів `cv_common` у модулях, gzip ndjson, реєстр (crew-present full_name, aircraft/jet), прибирання дублів arrival-stage з 9 модулів | Максим Ч. | pipeline-architect | todo | PF-Q1-10 | один пін cv_common для E0/E1-модулів; жодного локального розрахунку arrival stage |
| PF-Q3-06 | Трек `trigger-change` для S1: safety zone (причинна зона по траєкторії заїзду), pushback pathway (безперервно під час руху), walkers (алерт на pushback_attached ∧ walkers відсутні), hand signals (двопрохідний → подія) | Валентин + Юрій | module-porter | todo `decision-needed` | Ігор/Оксана | ADR на кожну зміну тригера; клієнтська логіка в `05_module_logic.md` оновлена після погодження |
| PF-Q3-07 | Delivery Q3: більше RT-модулів + алерти менеджерам станцій | Валентин | pm-coordinator | todo | Q3-01…04 | демо + звіт |

## Q4 — Maximum Real-Time Coverage + Optimization (місяці 10–12)

| ID | Задача | Власник | Агент | Статус | Deps | Acceptance |
|---|---|---|---|---|---|---|
| PF-Q4-01 | Хвиля E2 (кадри + моделі, 5; vests останні) і RETHINK/E4 (hand-signals, safety-zone геометрія з буфера); POST-модулі лишаються в пост-гілці свідомо | module-porter | module-porter | todo | PF-Q3-03 | бюджет 125 мс дотримано з усіма RT-модулями на 1 камері; список «свідомо POST» затверджений |
| PF-Q4-02 | Оптимізація GM/Tracker: TensorRT/fp16, роздільна здатність, спільний детектор на дві гілки без повторного інференсу | Юрій + Валентин | gm-tracker-engineer | todo | PF-Q2-02 | камер на GPU ↑ ≥ 1,5×; recall не гірше −1 % vs baseline |
| PF-Q4-03 | Stage detector v1 + архітектурна оптимізація (receiver, ресурси, стабільність, autoscaling GKE) | Максим Ч. | pipeline-architect | todo | PF-Q3-05 | compute/подію ↓, SLO стабільності задокументовано |
| PF-Q4-04 | Стрімінг гейтів на RampVision (live-вигляд гейта зі stage/events/вердиктами) | Аріан + Максим Ч. | alerting-engineer | todo | PF-Q3-01 | live-сторінка гейта на dev-порталі; затримка ≤ 10 с |
| PF-Q4-05 | Пост-гілка тільки для POST-за-суттю (walk-around-и, conditioned air lookback) на оптимізованому пайплайні | Максим Ч. | pipeline-architect | todo | PF-Q1-04 | Time to Result пост-частини ≤ 5–6 год (замір на 10 подіях) |
| PF-Q4-06 | Фінальний замір KPI vs baseline + звіт року | Валентин | pm-coordinator | todo | усе | звіт з методикою PF-Q1-08 |

---

## Наскрізні / підтримка

| ID | Задача | Власник | Агент | Статус |
|---|---|---|---|---|
| PF-X-01 | Тримати `docs/` актуальними: після кожного ADR або зміни xlsx → `python scripts/build_docs.py`; нові документи через `docs/inbox/` | Валентин | pm-coordinator | ongoing |
| PF-X-02 | Список відкритих питань до Ігоря в каналі (транспорт, VPN, GPU-раннер, інтерфейс до шини алертів, MongoDB-схема) | Аріан | alerting-engineer | ongoing |
| PF-X-03 | Клонувати `camera_software` локально: по https «not found», ssh — ключ не зареєстрований (див. PF-X-05) | Максим Ч. | pipeline-architect | blocked `external` |
| PF-X-04 | **GitHub-проєкт**: репо `prime_flight` (цей воркспейс + пакет `pf/`), private; локально git init + перший коміт зроблено; remote — після `gh auth login` (gh 2.100 встановлено) | Валентин | pm-coordinator | in-progress |
| PF-X-05 | **Відновити доступ до коду**: `G:\deepx_gat` (усі локальні клони) зник з диска 14.09 ~11:00 — з'ясувати, куди; зареєструвати ssh-ключ `~/.ssh/id_ed25519.pub` у GitLab або дати https-права на `utils/cv_trackers`, `utils/cv_common`, `detectors/camera_software`; клони модулів/GM/db_worker тепер у `G:\prime_flight\external\` (gitignored) | Валентин | pm-coordinator | blocked `external` |
