# Глосарій Prime Flight / DXGAT

| Термін | Значення |
|---|---|
| **DXGAT** | DeepX Ground Aircraft Turnaround — CV-система перевірки безпеки обслуговування літака на гейті. |
| **Prime Flight (PF)** | 12-місячний roadmap переходу на continuous upload → real-time; головний KPI — Time to Result. |
| **Time to Result** | Час від завершення події до результату на RampVision. Зараз ≈24 год. |
| **Turnaround / turn / full turn / подія (event)** | Одне обслуговування літака від pre-arrival до departure; одне full-turn відео на камеру. |
| **CameraBox / cambox** | Пристрій на гейті з камерою, пише 1-хвилинні mp4-чанки і виливає їх у бакет. |
| **Cone camera / wing camera** | Дві камери гейта: cone дивиться на ніс/передню зону (конуси, колодки), wing — на крило/BL/двері. Розподіл задач по камерах — `05_module_logic.md`. |
| **Aircraft / Jet** | Два типи літака (класифікує GM); частина задач біжить на різних камерах залежно від типу. |
| **Чанк (chunk)** | Одиниця транспорту відео. Зараз 1 хв; ціль 7,5 с (2 GOP по 3,75 с), stream-copy. |
| **Merge script** | Скрипт `camera_software`, що з чанків збирає full-turn відео. У PF відсувається з критичного шляху. |
| **GM (General Model)** | YOLO-детектор об'єктів + класифікація камери, типу літака, entity (авіакомпанії). Per-frame `.ndjson`. |
| **Tracker / cv_trackers** | Трекінг літака, beltloader-ів, GSE, людей; дає `state_dict` (arrival/departure, стопи, BL біля дверей). |
| **Модуль / перевірка (check)** | Репо в `dxgat/detectors/*`, що з GM+tracker ndjson (і пікселів) дає вердикт по одному чеклист-пункту. 27 модулів, деякі з кількома перевірками (aircraft-chocks: M02A/B/C). |
| **Pass / Fail / Not observed / NO with obstacles** | Чотири вердикти; семантику визначає клієнт (`05_module_logic.md`). NO = не побачили достатньо; NO with obstacles = перекрито перешкодою. |
| **Merge logic** | Об'єднання вердиктів двох камер: Fail → Pass → Not observed. |
| **ProdReady** | Позначка з клієнтського xlsx: задача в проді (True/False). |
| **Tier (real-time / streaming / post)** | Клієнтський поділ, де має рахуватись перевірка. Real-time = секунди, streaming = live-потік на сервер, post = після події. |
| **Smart timeline** | Вихід модуля для візуалізації на RampVision (бакет `modules-inferences`). |
| **RampVision** | Клієнтський вебсайт з результатами по подіях і гейтах. |
| **T_arr / T_dep** | Якорі прильоту/відльоту з трекера: зупинка 4 с / рух 10 с (латентність 4 с / 10 с). |
| **BL** | Beltloader (стрічковий навантажувач). **BL@door** — BL зупинився біля літака (iou > 0.2); **BL leave** — відʼїхав. |
| **GSE** | Ground Support Equipment — наземна техніка (BL, fuel truck, trailer, pushback…). |
| **pushback_attached** | Подія «пушбек причепився до носа»; сьогодні рахується двома модулями непричинно; у PF — подія stage detector. |
| **Stage detector** | Причинний автомат після трекера: PRE_ARRIVAL → ARRIVAL/POST-ARRIVAL → DOWNLOAD/UPLOAD → PRE_DEPARTURE → DEPARTURE; єдиний власник якорів; гейтує модулі. |
| **Контракт кадру** | Схема запису на шині: `schema_version`, `frame_id`, `stage`, `events`, `anchors`, `general_model`, `trackers`. |
| **X1–X4** | Чотири умови коректності стрімінгу (`02_target_architecture.md`). |
| **Гаряча / холодна гілка** | Real-time-гілка (гейтовані модулі, алерти) / пост-гілка (merge + пост-аналітика). |
| **E0…E4, POST** | Effort переносу модуля: E0 як є; E1 кадри без моделей; E2 кадри + моделі; E3 подія детектора; E4 переписати перший прохід; POST — пост-обробка за суттю. |
| **I1/I2/I3** | Вага для алертів: критично / важливо / звітність. |
| **S1…S4** | Тир миттєвої реакції: секунди вирішують / хвилини, стан оборотний / нагадування / неможливо за змістом. |
| **NOW / NOW_PX / PATCH / RETHINK / POST** | Verdict готовності модуля до стрімінгу (`module_map.json`). |
| **Lookback / live / instant / deadline / event / whole** | Тип рішення модуля: оцінка вікна перед T / накопичення від події / одна детекція → Fail / Fail якщо X не побачено до T / вердикт у момент події / потрібна вся подія. |
| **Паритет (parity)** | Порівняння вердиктів пакет ↔ стрім на тому самому відео; валідне при будь-якому балансі класів. |
| **Збалансована вибірка** | Усі fail-и з розмітки + стільки ж pass-ів (`tools/pick_balanced.py`). |
| **Витікання полів (class leakage)** | Поля `Vehicle` (`_bl_type_*`) у стані літака → `ValueError` у модулі; ловить `check_class_leakage()`. |
| **cv-modules-topics** | GCS-бакет з per-frame GM/tracker ndjson (по 15–16 версій на відео без `schema_version`). |
| **DVC** | Сховище ваг моделей поза git. |
| **ADR** | Architecture Decision Record — `docs/decisions/`. |
| **trigger-change** | Тег задачі, що змінює момент/умову рішення перевірки (потрібне погодження з Ігорем/Оксаною). |
