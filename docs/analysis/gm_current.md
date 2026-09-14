# General Model (U02) — що він реально робить сьогодні

Read-only аналіз коду для перебудови GM у по-чанковий (streaming) компонент із побітово-сумісним або явно версіонованим
per-frame виходом. Джерела: `external/general_model` @ `13a4ddc` (master, 2024-06-07 «fix onnx corrupted outputs»),
`external/db_worker` @ `5a4aa83` (master; від піна GM `2fd7325e` відрізняється лише README — `git diff --stat`),
`docs/04_modules.md` §U02, `docs/03_components.md`, `docs/arch_review/REVIEW_DETAILED.md:915-949`, реальні прод-ndjson у
`G:\gat_stages\atlc5_inferences\`. Шляхи нижче — відносно `G:\prime_flight\external\` (`main.py` = `general_model/main.py`,
`ML_worker.py` = `db_worker/ML_worker.py`).

**Важливе обмеження:** `cv_common` (пін GM `d74eb096`) відсутній на диску — submodule-каталоги в усіх клонах порожні,
`G:\deepx_gat` видалено. Усе, що живе там (`global_config.yaml` зі `str2id`, `LoadImages`, `ImagePreprocessor`, `Airplane`,
`BboxStabilizer`, `parse_config`), описано лише за використанням у коді GM і за фактичними даними — див. §11.

---

## 1. Entry points і режими запуску

**Що таке job.** Один GM-job = одне full-turn відео однієї камери (`--source <video>.mp4`) → один per-frame ndjson у бакет +
один звіт (report) у Kafka-топік приймача. Ніякого per-chunk чи per-event режиму немає.

**Прод-запуск (K8s Job, `general_model/test-gm.yaml`).** Образ `us-central1-docker.pkg.dev/rampvision-2/modules/general_model:latest`
(`test-gm.yaml:18`), нода з `nvidia-tesla-t4` (`:14`), 1 GPU / 3.3 CPU / 8 GiB (`:53-58`), env `videoname`, `model_name`, `device`,
`NODE_ID`, `POD_ID`, `service_dns` + ConfigMap `ml-config` + Secret `credentials` (`:26-51`). Команда (`:60-65`): записати
`$GCP_CRED` у `/config/bucket.json`, `mkdir ./weights`, **скопіювати `db_worker/model_starter.py` у корінь** і виконати
`python3.8 model_starter.py --source=<video>.mp4 --model=general_model --device=gpu --report_topic=$receiver_topic`.

**`model_starter.py` (db_worker) — справжній entry point.** CLI (`model_starter.py:337-349`): `--kafka_ip`, `--report_topic`,
`--source`, `--output`, `--model`, `--weights_dir` (default `./weights`), `--device` (default `cpu`), `--camera_type`,
`--airplane_type`, `--restart`, `--write_video` (**default `t` = True**, `:348`). Послідовність у `__main__` (`:350-405`):
1. `prepare_config_for_production()` — `sed` по `./cv_common/global_config.yaml`: `DIVX→avc1`, `mkv→mp4` (`:45-53`).
2. `pull_weights()` — `dvc pull` у `./weights` (`:58-69`).
3. Завантаження відео з GCS `source_bucket` (fallback `old_source_bucket`) у `storage/<video>` (`:372-388`).
4. `start_general_model()` (`:73-143`): `get_video_info()` відкриває відео ще раз заради `nframes`/`fps` (`:36-40`);
   `VideoWorker(model_name='general_model', source, load_tracks=False, load_from_file=True, testing=True,
   auto_download_inference=False)` (`:86-87`); `from main import detect` (`:89`); `detect(...)` під `torch.no_grad()`
   (`:92-100`); збір `description` (`:102-110`); за `write_video` — upload анотованого відео (`:112-121`); Kafka-звіт
   `ModuleReport.GENERAL_MODEL` зі статусом `processed` (`:123-127`); `video_worker.close()`;
   `upload_infereces_to_cloud_storage("general_model")` (`:132`). Будь-який виняток → звіт зі статусом `error` (`:133-140`).
5. Лог `execution_logs.log` → `gs://cv-modules-logs/<video>/general_model-<date>.logs` (`:392, 405`).

**Локальний запуск (`main.py:1077-1100`).** `--source`, `--output-path`, `--device`, `--weights` (README описує `--weights-dir` —
розбіжність, `README.md:66` vs `main.py:1083`), `--testing` (завжди True через `set_defaults`, `:1087`), `--inferences_dir` (не
використовується), `--save-video`. Створює `VideoWorker(source, model_name='general_model', testing=True)` (`:1096`) і викликає
`detect()` (`:1098-1100`).

**Головний цикл — `detect()` (`main.py:444-1074`), три проходи по відео:**

| Прохід | Рядки | Що робить |
|---|---|---|
| Ініціалізація | `444-514` | SAM, 3 ONNX-детектори, **три незалежні readers** `load_source()` (`475-477`), Norfair-трекер літаків (`488-491`), `BboxStabilizer`, `ImagePreprocessor` |
| FIRST RUN | `517-662` | per-frame: препроцесинг → GM + chocks + vehicle детектори → запис сирих рядків (`595`) → злиття/трекінг літаків (`598-646`) → BL-евристика (`649-660`) |
| Між проходами | `664-712` | вибір головного літака (`669-675`), layout частин і ROI бокових перешкод (`678-697`), закриття ndjson і **відкриття його ж на читання** (`710-712`) |
| SECOND RUN | `714-902` | **повторне декодування відео**; читає рядки першого проходу (`765`), збагачує (obstacle/side_obstacle, головний літак), entity, тип літака, класифікатор камери; пише другий ndjson (`871`) |
| Хвіст | `904-1074` | голосування камери, стадії, статистика, `select_video()` (**третє декодування**, `1055`), `return_dict` (`1071-1073`) |

Per-frame цикл — `for frame_id, (path, img, im0s, vid_cap) in enumerate(dataset, 1)` (`517`, `745`): нумерація 1-based, від
першого декодованого кадру.

---

## 2. Моделі

| # | Модель / призначення | Ваги (ключ конфігу) | Framework | Вхід | Batch | Device | Пороги | Де завантажується |
|---|---|---|---|---|---|---|---|---|
| 1 | **GM YOLOv8** — усі класи перону (за docs: `GM_yolov8m_best_augmentation_march2024`) | `config['general_model_weights']` (cv_common) | onnxruntime-gpu 1.16.2, CUDA EP, fp16 IO-binding (`scripts/new_model.py:231-439`) | 1088×1088 static; 1920×1080 → letterbox 1088×640 + pad 224 px зверху/знизу (`:330-352`) | 1 | `cuda:0` | conf 0.35 (`local_config.yaml:3`), NMS IoU 0.7 **class-agnostic** (`new_model.py:426`) | `main.py:463-464` |
| 2 | **Chocks YOLOv8** (docstring: `chocks_v4.3_200ep_yolov8` export imgsz=1280 half, `new_model.py:244`) | `config['chocks_model_weights']` | те саме | 1280×1280; контент 1280×736 + pad 272 | 1 | cuda | `config['chock_conf_thres']` (за даними ≈0.10, §3) | `main.py:467-468` |
| 3 | **Vehicle YOLOv8** — широкий детектор транспорту | `config['vehicle_model_weights']` | те саме | 1088 (default `new_model.py:233`) | 1 | cuda | `config['vehicle_conf_thres']` (за даними ≈0.40) | `main.py:471-472` |
| 4 | **MobileSAM vit_t** — маска літака для стану руху (всередині `cv_common.transport.Airplane.update_params`) | `weights_dir/mobile_sam.pt` (hard-coded, `main.py:454`) | torch (`mobile_sam` з GitHub-коміту `01ea8d0f`) | image per call (усередині cv_common) | – | device | – | `main.py:452-459` |
| 5 | **Entity detector** — авіакомпанія (6 класів: JetBlue/Allegiant/UnitedExpress/Breeze/American/Spirit) | `./weights/{config['entity_detector_weights']}` — **шлях відносно cwd**, не `weights_dir` (`main.py:716`) | torch `torch.load(...)['model']` (YOLOv5-стиль, `UModel`, `new_model.py:152-209`), fp16 | resize 1280×1280 **без letterbox** (`:191`) | 1 | cuda if available | conf 0.7, IoU 0.7, YOLOv5 NMS (`:153, 197`) | `main.py:716` (початок SECOND RUN) |
| 6 | **Камера cone/wing** — бінарний класифікатор | `config['camera_classifier_weights']` | timm `efficientnet_b0(pretrained=True, num_classes=1)` — **`pretrained=True` тягне ImageNet-ваги з мережі при старті** (`main.py:719`), потім `load_state_dict` (`:720`) | crop рядків `150:930` → 224×224, ImageNet norm (`classifier_utils.py:9-13, 36-39`) | 1 | device | sigmoid ≥ 0.5 → cone (`classifier_utils.py:44`, TODO «threshold has to be finetuned») | `main.py:719-723` |

Ваги: DVC (`weights.dvc`: каталог `weights`, 8 файлів, 210 865 680 байт, md5 `96fb8549…`), remote `gs://cv_weights/DVC`
(`.dvc/config:1-4`); останнє оновлення 2024-03-29 (`git log -- weights.dvc`). Імена файлів визначає `cv_common/global_config.yaml`
(нема на диску, §11). ONNX-сесія: `ORT_ENABLE_ALL`, CUDA EP з `cudnn_conv_use_max_workspace=1`, `cudnn_conv_algo_search=DEFAULT`
(`main.py:34-39`). Клас `YOLO8` (ultralytics) у `new_model.py:212-228` не використовується в `main.py`.

---

## 3. Per-frame схема виходу

**Формат файлу.** ndjson, один рядок на кадр: `{"<frame_id>": [row, row, ...]}` — ключ рядок, значення список рядків
(`ML_worker.py:286` `writerow({str(frame_id): frame_metadata})`). `frame_id` — **внутрішній лічильник `frame_ii`** VideoWorker,
що стартує з 1 в `init_writer` (`ML_worker.py:223`) та інкрементується на кожен виклик `model_pub` (`:321`); аргумент
`frame_id`, який передає GM, **ігнорується** (`:309`). GM викликає `model_pub` рівно раз на кадр у кожному проході
(`main.py:595`, `871`), тому ключ = 1-based індекс `enumerate(dataset, 1)`. Порожній кадр — `{"1": []}`. Жодного
`schema_version`, `frame_id`-поля, fps чи заголовка у файлі немає.

**Два файли.** Перший прохід пише `<inferences_dir>/general_model<video>.mp4.ndjson` (`ML_worker.py:192-193`) — сирі рядки.
Другий прохід після `init_writer(file_prefix="second_run")` пише `general_model<video>.mp4-second_run.ndjson` **у cwd**
(`ML_worker.py:213`, без `inferences_dir`). У бакет вивантажується `self.ndjson_path['general_model']` (`ML_worker.py:374-380`),
тобто **файл другого проходу** — саме його читають трекер і 27 модулів.

**Рядок детекції:** `[x1, y1, x2, y2, conf, cls_id]` (довжина завжди 6 — перевірено на 930 527 рядках реального файлу).
- `xyxy` абсолютні пікселі кадру 1920×1080, `int` → `float` (`main.py:543, 551`), обрізані `correct_coords` до
  `[0..1920]×[0..1080]` (`main.py:202-217`); у реальних даних усі координати цілочисельні, min/max = 0/1920, 0/1080.
- `conf` — `float` з fp16-виходу ONNX (усі 905 247 значень ≤1 у файлі точно представимі у float16).
- `cls_id` — `int` з `config['str2id']`.

**Джерела рядків у файлі другого проходу (`main.py:767-871`):**
1. Усі рядки першого проходу **крім класу `airplane`** (`:773-774`): GM-класи з conf > 0.35; chocks як `str2id['chock']`
   (`:583-586`), vehicle-детектор як `str2id['vehicle']` (`:589-592`).
2. Копії боксів транспорту/vehicle, що пройшли фільтр «наш гейт», з класом `obstacle` або `side_obstacle` (`:810-832`).
   **Дефект:** `conf` у цих рядках — залишкова змінна циклу (`:768`/`:798` → `:823`/`:829`), не впевненість самого
   об'єкта; у реальному файлі conf збігається з conf вихідного боксу лише у 5 687 з 72 512 рядків класу 29.
3. Рівно один рядок головного літака на кадр у діапазоні його треку: `[x1,y1,x2,y2, int(mode_plane_height), str2id['airplane']]`
   (`:851-854`) — **п'яте поле = мода висоти bbox у пікселях (напр. 680), не ймовірність** (attention-нотатка U02).

**Реальний запис** (`G:\gat_stages\atlc5_inferences\general_modelAIjEAz70OfWCYG.mp4.ndjson`, 39 360 рядків, ключі 1…39360
монотонні без дірок), рядок 5000, перші елементи:
```
{"5000": [[698.0, 505.0, 828.0, 617.0, 0.9150390625, 7], [1433.0, 362.0, 1920.0, 536.0, 0.888671875, 6],
          [577.0, 583.0, 642.0, 635.0, 0.85302734375, 20], [255.0, 476.0, 371.0, 781.0, 0.85205078125, 0], ...]}
```
рядок 11150 містить головний літак: `[508.0, 44.0, 1608.0, 752.0, 680, 2]` (рядки класу 2 лише у кадрах 11150…38233).

**Список класів.** Дослівний `str2id` живе у `cv_common/global_config.yaml` і **недоступний** (§11). Імена, на які посилається
код GM (27): `person, cone, engine_cone, wing_cone, tail_cone, beltloader_cone, airplane_tail, airplane_wing,
airplane_engine, airplane_nose, front_door, back_door, front_wheel, back_wheel, air_conditioning, beltloader, pushback, gse,
airplane` (`main.py:480-483`), `trailer, fuel_truck` (`:575-576`), `tow_bar, ladder` (`:789-790`), `chock` (`:586`),
`vehicle` (`:592`), `side_obstacle` (`:823`), `obstacle` (`:829`). Ідентифікатори, підтверджені даними/кодом стенду:

| id | клас | доказ |
|---|---|---|
| 0 | person | IoU-збіг з `cls_str` трекера (1306/1306) |
| 2 | airplane | збіг з трекером + рядки з висотою в conf-слоті |
| 3 | beltloader | збіг з трекером (959) |
| 4 | gse | збіг з трекером (761) |
| 5 | pushback | `gat-streaming/streaming/simulate.py:33` («str2id з global_config») |
| 9 | airplane_nose | там само |
| 25 | chock | мін. conf у файлі 0.1002 (≠ 0.35 GM) → окремий поріг `chock_conf_thres`; медіанний бокс 21×22 px; є у 38 916/39 360 кадрів |
| 29 | obstacle | 100 % рядків — точні копії боксів класів 12/3/31/15 у тому ж кадрі; медіанний центр x=1410 |
| 30 | side_obstacle | 100 % копії боксів 4/14/31/3; медіанний центр x=66 px (краєвий ROI) |
| 31 | vehicle | мін. conf 0.4004 → окремий поріг `vehicle_conf_thres`; присутній у 39 329/39 360 кадрів |

Решта GM-класів має id 0…24 (мін. conf 0.3503 = поріг GM); id 22, 26, 27, 28 у трьох перевірених файлах не зустрічаються.
За боксами-дублікатами id 12, 13, 14, 15 — транспортні класи (`tow_bar/fuel_truck/trailer/ladder` у невідомому порядку).
Тобто `str2id` має ≥ 32 записи, GM-детектор — ≈25 класів (0…24), а `chock`, `obstacle`, `side_obstacle`, `vehicle` —
синтетичні id, що додає сам `main.py`.

**Як читають споживачі.** `VideoWorker.__metadata_generator` бере `list(record.values())[0]` і зіпує GM та trackers **за
позицією** (`ML_worker.py:244-254`); ключ кадру ігнорується. Стенд робить так само (`simulate.py:47-53`). Трекер видає файл з
тією ж кількістю рядків (39 360 = 39 360 для того ж відео).

---

## 4. Per-video рішення (критично для чанків)

| Рішення | Де | Коли/на якій підставі | Куди пишеться | Вердикт для потоку |
|---|---|---|---|---|
| **Головний літак** | `main.py:669-675` | після EOF першого проходу: трек Norfair з найбільшою кількістю кадрів; кандидати — бокси `airplane` висотою ≥150 px (`:547-548`), злиття перекриттів >0.7 (`:598-609`), пере-асоціація нового id з історією при overlay >0.5 (`:633-645`); немає жодного → `NoPlaneException` (`:675`) | рядки класу 2 у другому файлі лише для кадрів треку (`:851-854`) | **needs whole video** (argmax по всіх треках) |
| **Висота-мода літака** | `:701-702` | мода округлених до десятків висот по всьому треку | 5-те поле рядка літака | **needs whole video** |
| **Layout частин** (main front wheel, nose, ліве/праве крило) | `:555-562, 367-375, 378-415, 678-689` | після EOF: бакети боксів з IoU >0.8, частина «головна», якщо з'явилась > max(10-те за частотою, 30·fps) кадрів | не пишеться напряму; визначає obstacle-ROI | **recomputable incrementally** з правилом заморозки (≥240 стабільних кадрів); правило «10-те за частотою» — whole-video |
| **ROI бокових перешкод** | `:691-697` | від крил: `[x0_left + 0.8·w, 0, 1920, 1080]`, `[0, 0, x0_right + 0.2·w, 1080]` | впливає на клас 29/30 у кожному кадрі другого проходу (`:810-832`) | після заморозки layout — per-frame |
| **Тип камери cone/wing** | `:879-897, 904-908` | класифікатор на **кожному** кадрі, де `plane_available and main_plane.arrived`; більшість голосів після EOF; `confidence_camera` = частка (`:1062-1063`). Змінна `n_frames_for_classification = 20 хв` оголошена і **не використана** (`:734`) | `gm_report({"camera_type", "frame_stopped"})` (`:911`, у testing лише print) і фінальний звіт `camera_type: bool` (`model_starter.py:102`) | **recomputable incrementally** (біжуча більшість), але фінал — після EOF; для потоку потрібне правило «фіксуємо після N кадрів після зупинки» (ADR) |
| **`frame_stopped`** | `:874-875` | `main_plane.arrival_frame` зі стану `cv_common.Airplane` (`arrived`), перезаписується щокадру | звіт `frame_stopped` | причинний після зупинки, **але залежить від вибору головного літака** (другий прохід) |
| **Тип літака JET/AIRCRAFT** | `:881-886`; `scripts/engine_script.py:7-108` | після `arrived`: щокадру голос за 4 геометричними перевірками (двигун∩хвіст, двигун∩заднє колесо, двигун над/під крилом, позиція двигуна на крилі, `:66-91`), `answer` коли лічильник типу > 500 кадрів (`:103-106`); `airplane_type` присвоюється лише на наступному кадрі після `answer` (`main.py:883-886`) | звіт `airplane_type: str|None` | **decidable from first N frames** після зупинки (~62 с голосів) |
| **Entity / авіакомпанія** | `:835-848` | з кадру 8 кожен 8-й кадр (1/с @8fps) до 40 детекцій, незалежно від літака; рішення: сума class_id ∈ {0:JetBlue, 40:Allegiant, 80:UnitedExpress, 120:'Breze', 160:American, 200:Spirit} інакше `Undefined` (`:844-848`) — усі 40 мають збігтись | звіт `entity: str|None` | **decidable from first N frames** |
| **Стадії** | `:921-951` | `pre_arrival=(1, first_plane_frame)` якщо ≥241 кадр; BL-стадії (`:930-943`) **завжди False**: `front_door`/`back_door` ініціалізуються `[]` щокадру (`:522`) і ніде не наповнюються → `check_if_bl_came` повертає одразу (`:112-120`) [INPUT-GAP U02.19]; `from_arrival_till_departure=(first, last plane frame)`; `departure` лише якщо після треку ≥720 кадрів (`:947-950`); `fullturn=(1, last_frame)` | звіт: усередині `detection_statistics` (`model_starter.py:107`); ключ `stages` звіту = `None`, бо `results.get('stages')` читає відсутній ключ (`model_starter.py:109` vs `main.py:1071-1073`) | **needs whole video** (кінець треку, останній кадр) |
| **Статистика видимості класів** | `:171-199, 959-1051` | частка кадрів зі класом у стадії; `None` якщо стадія < 480 кадрів (`:182`) | звіт `detection_statistics` | **needs whole video**; за `render_dependencies.py:177` жоден модуль це не читає (тільки сайт) |
| **Video selection** | `:1053-1055`; `videos_selection_script.py:24-113` | пороги тривалості стадій і часток детекцій (`local_config.yaml:7-25`) + третє декодування з frame-diff (`:60-88`) | лише `report_video_selection_module.txt` (append, `:90-111`); у `return_dict` не входить (U02.22) | whole video; **нікому не потрібна** |
| **Шум / broken** | `:526-535, 753-755, 1073` | `ImagePreprocessor` (cv_common) щокадру | `video_type_by_noise`, `noise_mean`, `noise_std`, `is_broken` у `return_dict`, **не потрапляють у звіт** (`model_starter.py:102-110`; `send_report.py:92-104` не має таких ключів, `validation` кинула б `KeyError`) | per-frame; губиться на межі job |
| Obstacle/side_obstacle per frame | `:810-832` | транспорт з `bbox_area > 7000` і поза боксом переднього колеса; vehicle-бокси дедуплікуються з транспортом при IoU >0.7 (`:797-805`) | рядки 29/30 | per-frame, після layout |

Ланцюжок залежностей: **сирі рядки → головний літак (EOF) → layout/ROI (EOF) → другий прохід (obstacles, `arrived`,
камера, тип літака, `frame_stopped`) → стадії/статистика (EOF)**. Лише entity незалежний від нього.

---

## 5. Побічні ефекти та I/O

| Канал | Що | Де |
|---|---|---|
| GCS читання | відео `gs://<source_bucket>/<video>` → `storage/<video>` (fallback `old_source_bucket`) | `model_starter.py:372-388`; `ML_worker.py:102-125` |
| Декодування | `cv_common.utils.datasets.LoadImages(source, img_size=cv_config["img_size"])` (cv2.VideoCapture; `.nframes`, `.cap`) — **4 екземпляри** на job: `get_video_info` + три readers у `detect` | `ML_worker.py:225-238`; `model_starter.py:36-40`; `main.py:475-477`; rtsp/http → `Exception("Stream is not implemented yet")` (`ML_worker.py:229-233`) |
| Локальні файли | `../inferences_dir/general_model<video>.mp4.ndjson` (перший прохід), `./general_model<video>.mp4-second_run.ndjson` (другий), `.gz` після `gzip -f`, `report_video_selection_module.txt`, `execution_logs.log`, `gm-output-<date>-<video>` (mp4) | `ML_worker.py:192-193, 213, 378`; `videos_selection_script.py:91`; `custom_logging.py:8`; `model_starter.py:91` |
| GCS запис | `gs://cv-modules-topics/<video>.mp4/general_model<short-commit>.ndjson` (**вміст gzip під іменем .ndjson**); commit = `Repo('./.git').rev_parse HEAD` репо GM — єдина «версія» схеми (X3), потребує `.git` в образі (`.gcloudignore: !.git`) | `ML_worker.py:359-380` |
| GCS запис | анотоване відео → `gs://<output_bucket>/gm-output-…` (за `--write_video`, default True) | `model_starter.py:112-121` |
| GCS запис | лог → `gs://cv-modules-logs/<video>/general_model-<date>.logs` | `model_starter.py:405` |
| Kafka | звіт `send_to_receiver(report_topic, 'general_model', report)` — новий `KafkaProducer` на виклик, `bootstrap=<kafka_ip>:9092`; `Report{sender_id, contents{pod_id, node_id, processing_time, process_status, description}}`; `description` для GM: `camera_type, frame_stopped, fps, entity, number_of_frames, video_name, detection_statistics, log_filename, airplane_type, stages, confidence_camera` | `send_report.py:10-23, 53-55, 74-131`; `model_starter.py:75-79, 102-110, 123-127` |
| Kafka per-video топіки | `general_model<video>` створюються **лише при `testing=False`** — прод-шлях використовує `testing=True`, тож ця гілка мертва; `gm_report()` у testing лише друкує | `ML_worker.py:179-185, 439-453` |
| MongoDB | **жодного звернення** ні в `general_model`, ні в `db_worker` (grep `mongo` порожній, `pymongo` немає у requirements). Video/event doc оновлює приймач `receiver_topic` (orchestrator поза цими репо, §11) | — |
| stdout | ≈8 рядків на кадр у першому проході (`main.py:533, 535, 652-654`; `new_model.py:435-438` ×3 моделі) при `PYTHONUNBUFFERED=1` | — |
| logging | `set_logging` визначено, не викликається (`main.py:87-90`); `logging.info` (`:1064`) іде в root-логер без handler-а | — |
| Мережа при старті | `dvc pull` (`gs://cv_weights/DVC`), `timm.create_model(pretrained=True)` (`main.py:719`) | — |

Env, які читає db_worker: `kafka_ip`, `receiver_topic`, `source_bucket`, `old_source_bucket`, `output_bucket`,
`module_inferece_bucket` (модулі), `event_id` (модулі), `general_model_inferences_version_commit` (у GM-гілці читається і не
використовується, `model_starter.py:82-84`), `trackers_inferences_version_commit`, `POD_ID`, `NODE_ID`, `STAGE`,
`GOOGLE_APPLICATION_CREDENTIALS` (через `test-gm.yaml:61-62`).

Як GM використовує db_worker: `VideoWorker.load_source` (три рази), `model_pub` (щокадру, обидва проходи + `end=True`
`main.py:710, 1066`), `load_metadata` (`:711`), `init_writer("second_run")` (`:712`), `gm_report` (`:911`); model_starter — ще
`upload_infereces_to_cloud_storage`, `close`, `upload_to_bucket`, `download_from_bucket`, `send_to_receiver`, `ModuleReport`.

---

## 6. Припущення, що ламаються на потоці чанків

1. **Три full-file readers відкриваються до початку обробки** (`main.py:475-477`) + `load_source` кидає виняток на будь-який
   stream URL (`ML_worker.py:229-233`). Чанковий вхід неможливий без заміни `LoadImages`.
2. **Двопрохідність за побудовою:** другий прохід читає відео з кадру 1 і ndjson першого проходу (`main.py:710-712, 745, 765`).
   Усі збагачені рядки (obstacles, головний літак) і всі per-video рішення другого проходу існують лише після EOF першого.
3. **Головний літак = argmax після EOF** (`:669-675`), висота-мода по всьому треку (`:701-702`); рядки класу 2 у вихідному файлі
   з'являються лише у другому проході. На потоці «найдовший трек» невідомий до кінця події.
4. **Layout частин після EOF** із правилом «10-те за частотою або 240 кадрів» (`:392-395`) → ROI перешкод (`:684-697`).
5. **Стадії ключовані EOF:** `last_frame` (`:664`), `frame_of_ending` (`:704`), `departure` вимагає ≥720 кадрів після треку
   (`:947-950`), `fullturn=(1, last_frame)` (`:951`); статистика по стадіях (`:959-1000`) і `find_the_percent` (`:171-199`).
6. **Голосування камери після EOF** (`:904-908`); тип літака — лічильник до 500 (`engine_script.py:105`); entity — 40 хітів
   (`main.py:841`) — ці три інкрементальні, але без явного моменту «вирішено».
7. **`NoPlaneException` лише після EOF** (`:675`) — на потоці вердикт «літака не було» не виникає вчасно.
8. **Третє декодування** у `select_video` (`videos_selection_script.py:66-88`) та `dataset.nframes` для оцінки fps (`main.py:1070`).
9. **Нумерація кадрів = лічильник викликів writer-а** (`ML_worker.py:223, 309, 321`), без абсолютного `frame_id` (X2);
   споживачі зіпують GM/trackers позиційно (`ML_worker.py:244-254`). Пропущений чанк зсуває все.
10. **Стан препроцесора і гейти залежать від межі проходу:** `ImagePreprocessor.update` накопичує історію (`:526, 753`);
    у першому проході препроцесинг увімкнено з кадру 1 (`airplane_detected=True`, `:514`), у другому — лише після появи
    головного літака (`:743, 754-755, 864`); `YOLOv8_onnx` кешує геометрію letterbox з першого кадру (`new_model.py:330-356`).
11. **Один Norfair-трекер на відео** (`:488-491`) — сумісно з X1 лише якщо GM-процес живе всю подію, не перезапускається на чанк.
12. **Версія схеми — лише суфікс імені файлу** (`ML_worker.py:367-369`): у стрімі потрібен `schema_version` у записі (X3).

---

## 7. Профіль продуктивності (з коду, без виконання)

Референс стенду (`docs/02_target_architecture.md:69-80`, RTX 5070 Ti, профіль core): декод 2,90 мс/кадр, **детекція GM
28,29 мс/кадр @1088**, трекер 0,11; бюджет 125 мс @ 8 к/с; 3,95× real-time на повному turnaround. Це **лише один детектор**;
прод-GM робить на кадр набагато більше, до того ж на T4 (`test-gm.yaml:14`).

**FIRST RUN, на кожен кадр (`main.py:517-662`):**
- декод cv2 (+ невикористаний letterbox `img` усередині `LoadImages`, `img_size` з cv_common — не верифіковано);
- `ImagePreprocessor.update` (cv_common; `cucim`/`cupy` у requirements натякають на GPU-оцінку шуму — не верифіковано);
- H2D: `torch.from_numpy(im0s).float().cuda().half()` — 1920×1080×3 float32 (≈24 МБ) на GPU, потім у fp16 (`:529-532`);
- **три ONNX-детектори** (GM@1088, chocks@1280, vehicle@1088): GPU-препроцесинг permute/÷255/bilinear/pad (`new_model.py:305-314`),
  `run_with_iobinding` fp16 (`:393`), GPU-постпроцесинг + `torchvision.nms` (`:409-426`), далі **Python-цикл по індексах з
  GPU-скалярами** `detections.append([*boxes[i], scores[i], classes[i]])` → `torch.tensor(detections).cpu()` (`:427-432`) —
  ≈6·N_det неявних синхронізацій на модель на кадр (у реальному файлі ≈24 рядки/кадр); 2 `print` на модель (`:435-438`);
- Python-цикли по детекціях (`main.py:541-580`), `count_bbox_frames` з IoU по словнику (`:367-375`) — O(N_buckets) на бокс;
- Norfair `update` (`:613`) + **MobileSAM через `Airplane.update_params` для кожного трекованого літака щокадру**
  (`:629-642`; вартість у cv_common, невідома — потенційно домінує);
- `ndjson.writerow` (JSON-серіалізація щокадру, `ML_worker.py:286`), `prev_im0s = im0s.copy()` (`:662`, 6 МБ/кадр).
- Статичні квадратні входи: у 1088×1088 корисних 1088×640 → **≈41 % обчислень GM/vehicle на паддінгу**; у 1280×1280 корисних
  1280×736 → ≈42,5 % для chocks.

**SECOND RUN, на кожен кадр (`:745-902`):** повторний декод; H2D-копія `image_tensor` створюється і **не використовується**
(`:757`); JSON-парсинг рядка (`:765`); IoU-цикли obstacles (`:797-832`); entity YOLOv5 `.pt` @1280 кожен 8-й кадр до 40 хітів
(PIL resize + python NMS, `new_model.py:186-209`); SAM для головного літака щокадру (`:861`); EfficientNet-B0 на CPU-трансформах
PIL щокадру після зупинки (`:889`); `aircraft_determining` щокадру (`:884`); за `save_video` — `cv2.VideoWriter` 1080p +
малювання всіх боксів (`:759-762, 793-832, 899-902`) — **у прод-шляху `write_video` default True** (`model_starter.py:348`), якщо
маніфест не перевизначає (§11).

**Третій прохід** (умовно, коли відео пройшло фільтри): декод + `absdiff/GaussianBlur/threshold/findContours` на CPU
(`videos_selection_script.py:66-88`).

**Старт:** `dvc pull`, завантаження відео, 3 ONNX-сесії + SAM + `torch.load` entity + timm з мережі; `get_video_info` відкриває
відео окремо (`model_starter.py:36-40`).

**Batching:** відсутній скрізь (batch=1, один кадр на `predict`). **Очевидні неефективності:** три повні декодування;
невикористаний тензор у другому проході; per-row GPU→CPU синхронізації; паддінг квадратних входів; per-frame print/JSON;
SAM щокадру; encoder анотованого відео в проді; `prev_im0s.copy()`; entity-детектор без letterbox (спотворення пропорцій).

---

## 8. Конфігураційна поверхня

**`general_model/local_config.yaml` (мерджиться `parse_config()` з cv_common):** `task: general_model`; `conf_thres: 0.35`
(поріг GM-детектора); `airplane_min_height: 150` (мін. висота bbox літака для трекінгу, `main.py:547`); `video_selection.stages`
(мін. тривалість стадій: pre_arrival/from_arrival_till_departure/departure = 300 с) і `video_selection.detections` (мін. частки:
prearrival.cone 0.2; from_arrival_till_departure: airplane_tail 0.5, airplane_engine 0.7, airplane_wing 0.5, airplane_nose 0.7,
airplane 0.9, front_wheel 0.8, pushback 0.1; fullturn: airplane 0.4, pushback 0.01) — усе лише для `select_video`.

**Ключі з `cv_common/global_config.yaml` (файл недоступний; за використанням):** `fps` (`main.py:446, 734; engine/select`),
`width`, `height`, `fourcc`, `save_format` (`:446-447, 694-697, 1092`), `img_size` (`ML_worker.py:235`), `str2id`, `colors`,
`general_model_weights`, `chocks_model_weights`, `vehicle_model_weights`, `entity_detector_weights`, `camera_classifier_weights`,
`chock_conf_thres`, `vehicle_conf_thres`, `tracking.airplane.norfair` (kwargs Norfair `Tracker`, `:490`),
`tracking.airplane.tracked_object` (`:230, 857`); `status2id` (модулі). `prepare_config_for_production` править його `sed`-ом.

**Hard-coded у коді (не в конфігу):**

| Константа | Значення | Місце |
|---|---|---|
| Вхід GM/vehicle · chocks | 1088 · 1280 | `new_model.py:233`; `main.py:467` |
| NMS IoU (ONNX, class-agnostic) | 0.7 | `new_model.py:233, 426` |
| Entity: розмір/conf/IoU; крок; кількість хітів; мапа сум | 1280 / 0.7 / 0.7; кожен 8-й кадр; 40; `{0,40,…,200}` | `new_model.py:153`; `main.py:835, 841, 844` |
| Камера: crop, поріг | рядки 150:930, sigmoid ≥ 0.5 | `classifier_utils.py:36, 44` |
| Злиття літаків / пере-асоціація / бакети частин | overlay >0.7 (видаляє **більший** бокс, `:606`) / >0.5 / IoU >0.8 | `main.py:605-606, 637, 371` |
| Мін. кадрів для «головної» частини | max(10-те за частотою, 30·fps) | `main.py:392-395` |
| ROI бокових перешкод | 0.8·w лівого крила, 0.2·w правого | `main.py:694, 697` |
| Гейт-транспорт: площа; side-ROI перетин; vehicle-дедуп | >7000 px²; >0.7; IoU >0.7 | `main.py:814, 821-822, 803` |
| Тип літака: голосів до відповіді | >500 кадрів | `engine_script.py:105` |
| BL-евристика (мертва) | 130 px до дверей, 16 кадрів | `main.py:129, 135, 142-160` |
| Стадії: pre-arrival / BL-зсув / departure / мін. стадія | 240 / 480 / 720 / 480 кадрів | `main.py:922, 931, 947, 182` |
| Розмір кадру для clamp | 1080×1920 | `main.py:202` |
| SAM тип/файл; timm-модель | `vit_t`, `mobile_sam.pt`; `efficientnet_b0` | `main.py:453-454, 719` |
| Шлях entity-ваг | `./weights/…` (cwd) | `main.py:716` |
| Device | `'cuda:0'` якщо не `cpu`; але `.cuda()` без умови (`:529, 757`) — CPU-режим фактично непрацездатний | `main.py:450` |
| Kafka | `<kafka_ip>:9092`, timeout 30 с, batch 32768 | `send_report.py:13-23` |
| Бакети | `cv-modules-topics`, `cv-modules-logs`, `gs://cv_weights/DVC` | `ML_worker.py:325, 362`; `model_starter.py:405`; `.dvc/config` |

Мертві/невикористані: `xyxy2xywh`, `set_logging`, `stabilize_obj_bbox`/`stabilize_aiplane_bbox`, `n_frames_for_classification`,
`temp_camera_type_cone`, `--inferences_dir`, закоментовані k-mean/EMA блоки (`main.py:237-270, 303-357`),
`scripts/videos_selection_script_from_json.py`, клас `YOLO8`, `frame_temp` (`ML_worker.py:43-48`).

---

## 9. Залежності

**`general_model/requirements.txt`:** Cython, matplotlib≥3.2.2, numpy≥1.18.5, pillow≥8.0.1, PyYAML≥5.3, scipy≥1.4.1,
tqdm≥4.41.0, pandas≥1.2.2, seaborn==0.11.1, cucim, cupy-cuda110==12.3.0, easydict, dvc[gs]==3.4.0, timm==0.6.12,
mobile-sam @ git+…MobileSAM@01ea8d0f, onnxruntime-gpu==1.16.2, scikit-image==0.18.3, ndjson==0.3.1, kafka-python==2.0.2,
pydantic==1.8.2. **`no_deps_req.txt`** (`--no-deps`): ultralytics==8.0.175, norfair==0.3.1. **torch/torchvision не запінені** —
з базового образу `us-central1-docker.pkg.dev/rampvision-2/new-base/gpu_base:latest`, python3.8, `libcudnn8=8.2.4.15-1+cuda11.4`
(`Dockerfile:1-11`). **`db_worker/requirements.txt`:** google-cloud-storage, kafka-python, pydantic==1.9.1 (ставиться після
1.8.2 і перемагає), requests, ndjson, GitPython.

**Імпорти з cv_common** (пін `d74eb096`, `git ls-tree`): `image_preprocessing.ImagePreprocessor` (`main.py:14, 505`);
`utils.plots.plot_one_box` (`:17`); `common.{bbox_area, bboxes_iou, get_hw, get_relative_intersection, parse_config,
check_output_path, xyxy_to_det_arr, iou_distance, get_center}` (`:18-19`) + `is_overlap` (`engine_script.py:1`);
`transport.Airplane` (`:20`); `detections.BboxStabilizer` (`:21`); `utils.datasets.LoadImages` (`ML_worker.py:36`;
`model_starter.py:16`); `log_utils.JsonLogger` (модулі). **З db_worker** (пін `2fd7325e`): `ML_worker.VideoWorker` (`main.py:31`);
`model_starter` тягне `upload_to_bucket`, `download_from_bucket`, `send_to_receiver`, `ModuleReport`, `get_logger`.
db_worker сам має submodule `ml_setting` (`dxgat/ml_backend/ml_setting`), де `ml_global_config.json` описує модулі
(`cameras`, `device`, `seq_number`) — саме тут `camera_type` від GM перетворюється на набір модулів (`parser.py:96-108`).

---

## 10. Рекомендації для перебудови (пріоритезовано)

1. **Ядро інференсу `gm_core` (P0).** Чиста функція `frame → rows` для трьох детекторів з тими самими порогами, letterbox,
   fp16 IO-binding і class-agnostic NMS — це умова побітового паритету сирих рядків. Одразу: векторизувати витяг рядків
   (один `.cpu()` замість циклу, `new_model.py:427-432`), прибрати per-frame print, кешувати pinned-буфер H2D, batching по
   камерах (N потоків × 1 кадр). Прямокутний ONNX-експорт (1088×640 / 1280×736) економить ≈40 % FLOPs, але змінює вихід —
   тільки як версіонована зміна з переміром recall на збалансованій вибірці, не як «оптимізація без ADR».
2. **Компонент контексту `gm_context` (P0), інкрементальний, з подіями `decided_at`:** entity (40 хітів), тип літака (500
   голосів після T_arr), тип камери (зафіксувати після N кадрів після зупинки — природний кандидат невикористане 20-хв
   вікно, `main.py:734`; ADR, бо змінює семантику «більшість по всьому відео»), layout частин (заморозка після ≥240 стабільних
   кадрів), головний літак (біжучий найдовший трек + фінал на кінці події). `frame_stopped`/T_arr — власник stage detector,
   GM його не дублює. Кожне рішення — окремий запис `{"frame_id": N, "decision": "...", "value": ...}` у сесію, щоб модулі
   відкривались із правильним `cone_camera` до кінця відео (`render_dependencies.py:162`).
3. **Два вихідні адаптери (P0).** (a) Шинний запис v2: `{"schema_version": "2.0", "frame_id": N, "general_model": rows}` із
   **сирими** рядками `airplane` (справжній conf) і без obstacle-копій; (b) **post-branch v1-compat writer**, що по закінченню
   події з тих самих сирих рядків і фінального контексту відтворює легасі-файл другого проходу (рядки класу 2 з висотою-модою,
   рядки 29/30, нумерація 1..N) — тоді 27 модулів і трекер не міняються, а паритет з batch перевіряється побітово на 8
   референс-відео. Стале `conf` у рядках 29/30 (`main.py:823, 829`) у v1 відтворювати як є (паритет), у v2 — не переносити.
4. **I/O-адаптери (P1):** джерело (файл / чанк-сесія за `gat-streaming/streaming/session.py`, gap-fill заглушками), sink
   (ndjson v1, шина v2), звіт (Kafka зараз; додати поля шуму/`is_broken`, які нині губляться, і полагодити `stages=None`),
   реєстр ваг (явний список файлів з хешами замість ключів cv_common; прибрати cwd-шлях `./weights/` і `pretrained=True`).
5. **Винести/вимкнути (P1):** третій прохід `select_video` (результат ніким не читається), BL-евристику стадій (мертва —
   двері ніколи не наповнюються), стадії/статистику (жоден модуль не читає; місце — stage detector або окремий post-job),
   анотоване відео — off за замовчуванням.
6. **Що має лишитись ідентичним для сумісності:** формат рядка `[x1,y1,x2,y2,conf,cls]` з float-цілими координатами і
   clamp 0..1920/1080; id класів (зокрема синтетичні 25/29/30/31); 1-based послідовна нумерація без дірок; поля звіту
   `camera_type: bool`, `frame_stopped: int`, `entity: str`, `airplane_type: str`, `fps`, `number_of_frames`; ім'я об'єкта
   `<video>.mp4/general_model<commit>.ndjson` (gzip) у `cv-modules-topics`.
7. **Що міряти для паритету:** (i) сирі рядки — точна рівність множин 6-кортежів на кожному кадрі; (ii) гістограма
   кількостей по класах на відео + мін. conf по класу (ловить зсув порогів/моделей); (iii) діапазон кадрів і висота рядків
   класу 2; (iv) рядки 29/30 (кількість, бокси); (v) поля звіту; (vi) `decided_at` контексту vs batch-значення. Умови X4: той
   самий декодер з обох боків, повний turnaround, прогрітий кеш, вільна машина; T4 vs 5070 Ti — окремі колонки.

---

## 11. Відкриті питання

1. **`cv_common@d74eb096` нема на диску:** дослівний `str2id` (§3 покриває 10 id з ≥32), імена файлів ваг (8 у DVC),
   `fps`/`img_size`/`width`/`height`, параметри Norfair і `tracked_object`, `chock_conf_thres`/`vehicle_conf_thres` (за даними
   ≈0.10/≈0.40), реалізація `LoadImages` (cv2? letterbox щокадру?), `ImagePreprocessor` (що робить `is_heavy`/`is_broken`,
   вартість), `Airplane.update_params` (як часто викликає SAM, поріг `arrived`), `BboxStabilizer`.
2. Чи прод-маніфест оркестратора передає `--write_video false` (інакше GM кодує 1080p-відео щокадру); чи справді `dvc pull`
   тягне всі 8 файлів; чи є мережа для `timm(pretrained=True)` у кластері.
3. Хто пише MongoDB з GM-звіту і які саме поля video/event doc (приймач `receiver_topic` поза цими репо); чи досі Kafka, чи
   Pub/Sub.
4. Чи будь-який модуль читає перший (сирий) файл, `detection_statistics`/`stages` (стенд каже — ні), `confidence_camera`.
5. Реальний час GM-job на T4 на full-turn (для baseline PF-Q1-08) і чи 28,29 мс стенду включає постпроцесинг/NMS.
6. Id 22, 26, 27, 28 та імена для GM-класів 1, 6, 7, 8, 10…24 (потрібен `global_config.yaml`); чи є клас `wand`.
7. Чи entity-детектор (6 авіакомпаній, `Breze` з одруком) досі актуальний з огляду на редизайн entity-класифікатора.
8. Чи головний літак у трекері (`cv_trackers`) береться саме з рядків класу 2 другого проходу — від цього залежить, чи
   можна перенести вибір головного літака з GM у трекер без зміни семантики.
