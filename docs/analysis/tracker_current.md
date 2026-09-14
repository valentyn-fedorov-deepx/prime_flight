# Tracker as-is (`cv_trackers` @ b5d350c + `cv_common` @ ac5098d): responsibilities, output contract, what Tracker v2 must keep

Task PF-Q1-13 (basis for PF-Q1-17 Tracker v2 and PF-Q1-03 stage detector, per ADR-001). Sources: `external/cv_trackers`
(`tracker.py`, `local_utils/bl_utils.py`, `model_starter.py`, `local_config.yaml`, vendored `deep_sort_pytorch/`),
`external/cv_common` (`tracked_object.py`, `transport.py`, `track.py`, `common.py`, `global_config.yaml`, `utils/datasets.py`),
`external/db_worker` (`ML_worker.py`, `model_starter.py`, `send_report.py`). Empirical rules of `contract_observed.md` §3–5 are
confirmed/refuted from code in §4 below. All paths are relative to `G:\prime_flight\external\` unless stated otherwise.
**Production ran `bd43c3c` (branch `optimization`), not master** — §12 lists the delta and which sections apply to both.

**TL;DR.** The tracker is a per-video, pixel-reading batch job: three DeepSORT instances (beltloader, gse, person) on top of the GM
second-pass ndjson, one `Airplane` object fed by the class-2 rows, an optical-flow/MobileSAM motion state machine per object
(`cv_common.TrackedObject`), a door-based beltloader classifier, and a 5-frame output buffer that **rewrites `arrival_frame`
retroactively**. The output contract is the `Track` dataclass envelope + a `state_dict` of exactly 39 keys (airplane) / 34 (beltloader,
gse) / 0 (person); `from_state_dict` on the current `cv_common` family raises on any unknown key. Nothing about chunks, `frame_id`,
`schema_version`, resets, or stage events exists in the code.

## 1. Entry points and job model

- **Live entry** is `db_worker/model_starter.py:147-190` (`start_trackers`), not the stale copy `cv_trackers/model_starter.py:68-87`
  (that copy passes `port=`/`ip=` kwargs that `VideoWorker.__init__` does not accept, `db_worker/ML_worker.py:129-138`, and reports
  `process_status='error'` even on success, `cv_trackers/model_starter.py:81`). The live path: `VideoWorker(model_name='trackers',
  load_from_file=True, testing=True, inferences_dir="")` → `load_inferences_from_cloud_storage('general_model', commit|latest)`
  (`ML_worker.py:323-356`: downloads `gs://cv-modules-topics/<video>/general_model<commit>.ndjson.gz`) → `tracker.detect(...)` →
  `upload_infereces_to_cloud_storage('trackers')` (`ML_worker.py:359-380`: uploads `<video>/trackers<commit>.ndjson.gz`, where
  `commit` = short HEAD of **`./.git` = the cv_trackers repo**, not cv_common — the bucket suffix does not identify the `state_dict` schema).
- **Kafka is legacy**: with `testing=True` no consumer/producer is created (`ML_worker.py:179-185`); `model_pub` writes ndjson rows
  (`:307-309, 282-288`). `__push`/`__pull` (`:395-408`) are dead in this path.
- **Report** (`send_report.py:115-118, 122-131`): `ModuleReport.TRACKERS` = `{video_name, log_filename}` + `process_status`
  (`processing` → `processed` | `error`), `pod_id`, `node_id`, `processing_time`. No anchors, no frame counts — `frame_stopped` is in the GM report only.
- **Inputs**: the video (decoded by OpenCV, `cv_common/utils/datasets.py:205 cap.read()`, `nframes` from `CAP_PROP_FRAME_COUNT`, `:285`)
  **and** the GM ndjson, zipped positionally: `for frame_number, ((path, img, im0s, vid_cap), frame_metadata) in enumerate(zip(dataset, metadata), 1)`
  (`tracker.py:144`); the frame key of the GM line is discarded (`ML_worker.py:250-254`). `zip` truncates to the shorter source.
- **It reads pixels on every frame**: MobileSAM masks, FAST keypoints, PyrLK optical flow, DeepSORT appearance features and TV
  denoising all consume `im0s` (`tracker.py:236, 248, 262, 270-288, 301, 348, 484`). `--no-video` is impossible for this tracker.
  `LoadImages` additionally letterboxes every frame to 1280 (`datasets.py:227`) for an `img` the tracker never uses.
- **Outputs**: one ndjson line per published frame `{"<frame_ii>": [track, ...]}` (`ML_worker.py:286`), key = the writer's call counter
  `frame_ii` (`:223, 309, 321`); the `frame_id` argument of `model_pub` is ignored in testing mode (`:309`). Optional debug video (`--save-video`).
- **Per-video job**: all state lives in `detect()` locals for one video (`tracker.py:93-140`); one process per video/camera; the wing camera
  is signalled by `cone_camera=False` (`:64`, only used by `get_bl_type`). CLI: `tracker.py:577-602`, prod launch `process_videos.sh:87`.

## 2. Tracking algorithm

Three vendored DeepSORT trackers (`deep_sort_pytorch/deep_sort/deep_sort.py`), one class each, created once per video (`tracker.py:93-106`):

| tracker | classes fed | config block (`deep_sort_pytorch/configs/deep_sort.yaml`) | metric / features |
|---|---|---|---|
| `bl_tracker` | `beltloader` (3) after the square filter `min(h,w)/max(h,w) >= 0.9 → skip` (`tracker.py:183-191`) | `DEEPSORT_TRANSPORT`: MAX_DIST 150, MIN_CONFIDENCE 0.3, NMS 0.5, MAX_IOU_DISTANCE 0.75, **MAX_AGE 160, N_INIT 8**, NN_BUDGET 100 | `metric_type` not passed → **cosine** with threshold 150 (`deep_sort.py:15, 28-30`), i.e. appearance never gates; ResNet34 ImageNet logits as features (`resnet=True`, `feature_extractor.py:11-43`) |
| `gse_tracker` | `gse` (4) (`:193-201`) | same block | euclidean, threshold 150 (`:100`), ResNet34 |
| `workers_tracker` | `person` (0) (`:203-208`) | `DEEPSORT_WORKER`: MAX_DIST 0.2, MIN_CONF 0.3, NMS 0.9, MAX_IOU_DISTANCE 0.6, **MAX_AGE 100, N_INIT 6**, NN_BUDGET 100 | cosine; re-id net `torch.jit.load(weights_dir/scripted_ckpt.t7)` (`global_config.yaml:90`, `feature_extractor.py:46-80`) |

The "MAX_AGE 40, MIN_HITS 8" of the brief are **GM's norfair** parameters (`global_config.yaml:11-15`, `general_model/main.py:488-491`),
not this tracker's. `pushback`, `vehicle`, `trailer`, cones etc. are never tracked (only in `ignore_dict`, `tracker.py:108-111`).

Association (`deep_sort/sort/tracker.py:98-136`): matching cascade on features with Kalman gating, then IoU on the leftovers; a track is
confirmed after `hits >= n_init` (`sort/track.py:147-148`), a tentative track dies on its first miss, a confirmed one after
`time_since_update > max_age` (`:150-156`). Frames without detections of a class call `increment_ages()` = age + `mark_missed` for all
tracks (`tracker.py:238, 251, 264`, `sort/tracker.py:58-61`). Output = confirmed tracks with `time_since_update <= 1`, box =
**Kalman `to_tlwh()` cast to int and clamped to `width-1/height-1`** (`deep_sort.py:56-62, 104-115`) — hence tracker boxes ≠ GM boxes
(smoothed, IoU 0.9–0.99 in `contract_observed.md` §3). `outputs_beltloaders` are sorted by area before the update (`tracker.py:226-229`).

**Ids.** `tr_id` = DeepSORT `track_id` from a per-tracker counter starting at 1 (`sort/tracker.py:48, 138-143`) → collides across classes.
`_obj_id` = the id the `Vehicle` was created with (`tracker.py:414, 475`); on re-association the *old object* is re-keyed to the new track id
and keeps its `_obj_id`/state: BL — a second-sighting track whose box has `get_relative_intersection(new, old.recent_biggest_bbox) > 0.3`
(literal, `:388-393`; `recent_biggest_bbox` = max-area box of the last `10*fps=80` boxes, `tracked_object.py:326-338`); GSE — IoU with any
existing object > `gse_iou_reinit_thresh` 0.25 (`tracker.py:462-470`). Objects are **never deleted** from `bl_obj_dict`/`gse_obj_dict`
(`:127-130`), so a vehicle parking hours later where an old one stood can inherit that object's `_obj_id`, `_stops_count`, `_bl_type_frames`.
The airplane is `Airplane(obj_id=1)` created once (`:294-299`), so `tr_id = _obj_id = 1`.

**BL lifecycle quirks.** A new BL track first goes to `bl_to_init` (`:413-417`) and is neither updated nor emitted; on its next sighting it is
updated, re-association is tried, and only then added to `bl_obj_dict` (`:370-406`) — still not emitted on that frame (no `Track` append in
that branch). GSE is emitted on its creation frame without `update_params` (`:475-488`). Person tracks are emitted only when confirmed, but the
tentative history is **back-filled** into the previous buffered frames (`:435-441`).

**Envelope** (`cv_common/track.py:5-21`): dataclass `Track(tr_id=0, xyxy=(0,0,0,0), cls_str='Object', conf=0.0, state_dict={}, data=None)`;
`to_json()` returns **`self.__dict__` itself** (`:16-17`), `from_json` is `__dict__.update` (`:19-21`). Construction sites: airplane
`Track(tr_id=obj_id, xyxy, 'airplane', state_dict=to_state_dict())` (`tracker.py:310-311`), BL with `data={'bl_type': ...}` (`:365-366`),
person `Track(worker_id, w_xyxy, 'person')` (`:444`, `:450`), GSE (`:487-488`). **`conf` is never passed → always 0.0** (`track.py:11`);
`data` is `None` for everything but BL. Because `to_json` is the live `__dict__`, `replace_plane_arrival_frame` (`tracker.py:55-58`) adds a
7th envelope key `arrival_frame` to the buffered airplane tracks — the leak observed in `contract_observed.md` §5.4.

**`data.bl_type`** (`tracker.py:350-366`): while a BL is `is_stopped` (`status == STOPPED`) and observed, `get_bl_type` (§5) may return
`front`/`back`, which is stored in `bl_labels_dict[type] = beltloader_id` (keyed by **`tr_id`**); a label is cleared when that BL becomes
`MOVING` (`:354-357`); the emitted value is `front`/`back` if the current `tr_id` holds the label, else `undefined` (`:359-364`). After a
re-association the label is lost until re-derived, and `back` requires a wing camera or `front_type_frames == 0` (`bl_utils.py:79`).

## 3. TrackedObject / Airplane / Vehicle state

`TrackedObject` (`cv_common/tracked_object.py:341-363`) composes `ObjectState` (status/counters, `:20-95`), `FeatureTracker`
(optical flow, `:98-172`), `ObjectSegmenter` (MobileSAM, `:175-200`), `BoxesQueue` (`:326-338`), `MovementAnalyzer` (`:203-301`),
`ParameterManager` (ROI fractions, `:304-323`). `to_state_dict` (`:538-601`) writes exactly these 32 keys in this order:

`to_numpy, to_status, _obj_id, _class_name, _xyxy, _previous_xyxy, _init_xyxy, _status, _color, _prev_status, _prev_color,
_static_frames, _moving_frames, _is_stopped, _prev_stop_point, _stop_point, _stops_count, _p0, _st, _of_dots_lifetime,
_init_dots_lifetime, _mask, _segm_points, _static_points_thres, _stopping_time_thres, _moving_time_thres, _proceeding_time_thres,
_display_proceeding_time_thres, _from_x, _to_x, _from_y, _to_y`

`Airplane.to_state_dict` appends 7 (`transport.py:115-127`): `_moving_counter, _stopped_counter, have_pre_arrival_stage,
have_arrival_stage, arrival_frame, departure_frame, _height_mode` → **39**. `Vehicle` appends 2 (`transport.py:192-198`):
`_bl_type_bbox, _bl_type_frames` → **34** (beltloader and gse). Person → `{}` (default of `Track`). This matches the observed 39/34/0 exactly.

- `to_numpy` lists which keys hold arrays: `_p0` when not None, `_st` when not None (`:569-579`); `to_status` = `['_status']` +
  `'_prev_status'` only when it is set (`:543, 553-559`). `Status` is serialised as `.value` strings `stopped|moving|stopping|unobserved|proceeding`
  (`:11-17`); `status2id` (`global_config.yaml:152-157`) is a separate id map (no id 4) not used by the tracker.
- `_color`/`_prev_color` are norfair `Color` tuples → JSON 3-int lists: MOVING grey, STOPPING/PROCEEDING teal, STOPPED olive,
  UNOBSERVED black, `Vehicle` init olive (`:23, 39, 55, 65, 71, 78`, `transport.py:170`). Values depend on the **unpinned** `norfair>=0.1.7`
  (`cv_trackers/requirements.txt:8`); locally (norfair 2.3.0) grey=(128,128,128), teal=(128,128,0), olive=(0,128,128), black=(0,0,0).
- `_p0`: PyrLK points, float32 `(N,1,2)` → `tolist()` nested lists (`:570`), N ≤ 250 (`_max_num_keypoints`, `:102`); `_st`: PyrLK status
  vector of the last flow step, ints 0/1, set only from the second step after re-initialisation (`:163-164`), None right after a re-init.
  `_prev_p0` does not exist in the tracker (modules create it, `module_consumption.md` §2.3). `_of_dots_lifetime` counts down from
  `_init_dots_lifetime` (airplane 16 / BL 10 / GSE 5, `global_config.yaml:22, 68, 46`) once per flow step (`:165`); at 0 (or when `_p0` is
  empty/None) features are re-detected (`:384-385`).
- `_mask` is always written as `None` (`:585`); the real SAM mask lives only in memory. `_segm_points`: airplane only — 10 uniformly random
  points inside the central ROI (`_from_x.._to_x`, `_from_y.._to_y`) of the airplane-nose box with the largest relative intersection with the
  airplane (`transport.py:55-76`), None if none or intersection ≤ 0.5; used as positive SAM prompts (`tracked_object.py:180-192`).
- `_static_frames`/`_moving_frames`: episode counters of the state machine (§4); `_is_stopped`: raw flag, set to **`None` at the start of
  every `update_params`** (`:402`) and only re-set by a transition, hence the observed nulls; the property `is_stopped` that modules call is
  `status == STOPPED` (`:90-91, 419-420`), independent of the raw field. `_stops_count`: incremented when a new stop point is farther than
  `_dist_between_stops = 5 %` of the box width from the previous one (`:247, 258-262`), reset on PROCEEDING → MOVING (`:51-53`).
- Thresholds (config → `MovementAnalyzer`, `:352-362`): `_stopping_time_thres` 24, `_moving_time_thres` 8, `_proceeding_time_thres` 16,
  `_display_proceeding_time_thres` 5, `_static_points_thres` 0.5, `min_points_number` 2, `real_height` 7/3/2 m (not serialised),
  `movement_anomaly_thres_x/y` 50/5 px (not serialised). The GSE/BL config keys are misspelled `proceeding_time_thes`
  (`global_config.yaml:43, 65`) → the default 16 is used (same value). ROI `_from_x/_to_x/_from_y/_to_y` are per class (`:27-31, 49-53, 71-75`).
- `_height_mode` (airplane): the 5th field of the GM class-2 row (`tracker.py:215-216`, `= int(mode(height))`, `general_model/main.py:854`).
- `from_state_dict` (`tracked_object.py:604-674`): converts `to_numpy`/`to_status` keys, pops every known key with default `None`, re-casts
  `_p0` to float32 and `_st` to **bool** (`:631-636`), tolerates exactly `_recent_bboxes`, `_recent_bboxes_time`, `arrival_frame`
  (`:666-668`) and **raises `ValueError("Unexpected keys in state_dict: ...")` on anything left (`:671-672`)**. `Airplane.from_state_dict`
  pops its 7 keys first (`transport.py:129-144`), `Vehicle` its 2 (`:200-208`); `Airplane.update_inner_state` = `from_state_dict` (`:107-108`).
  Consequences: a 39-key airplane record restored into the base `TrackedObject` or into `Vehicle` raises (6 airplane keys unknown), a
  34-key vehicle record restored into `Airplane` raises (`_bl_type_*`), an empty `{}` restores fine (all defaults None).

## 4. Motion / event semantics

**Per-frame update** (`TrackedObject.update_params`, `:393-403`): skipped entirely while UNOBSERVED; validates the box (`check_bounding_box`,
`common.py:470-495`, raises on zero area / negative / outside the frame → the whole job dies); `_previous_xyxy ← xyxy`; `_is_stopped ← None`;
`_update_moving_status` (`:373-391`): both frames to gray (per object!), **skip the status update if the box area changed by > 1.5× or
< 0.66×** (`:380-382`), re-detect features when needed (`:384-385`: FAST keypoints on the current gray inside the SAM mask of the box, minus
`bboxes_to_remove` of ignored classes, ≤ 250 sampled **with `np.random.choice`**, `:111-138`), PyrLK `prev→cur` (backwards on the first step
after a re-init, `:150-153`, winSize 20, maxLevel 5, 16 it/0.05, `:99-101`), then `analyze_movement`.

**`analyze_movement`** (`:216-301`): inliers = new points inside the box, filtered to |v − median| < 1σ; if fewer than 2 remain → return
unchanged (`:233-234`, leaves `_is_stopped = None`); `stopping_flag` = share of points with |Δ| ≤ `tol = max(0.002·h/real_height, 0.1)` px
> 0.5 (`:236-240`). Transitions:

| state | static frame | non-static frame |
|---|---|---|
| MOVING | → STOPPING (`_static_frames`+1, `_moving_frames`=0; new stop point → `_stops_count`+1); at `_static_frames >= 24` → STOPPED (`:255-265`) | stay MOVING, `_moving_frames`+1 (`:273`) |
| STOPPING | same as above | if `_moving_frames >= 8` → MOVING (`:267-268`), else stay STOPPING with **`_static_frames`+1 and `_moving_frames`+1** (`:269-271`) |
| STOPPED / PROCEEDING | `_static_frames`+1 (capped at 24) and → STOPPED, `stop_point = centre` (`:283-285`) | if `_moving_frames >= 16` → MOVING (`:276-277`), else `_moving_frames`+1 and → PROCEEDING once > 5 (`:279-281`) |

`set_moving` resets `_static_frames`, `set_proceeding`/`set_moving` push `_stop_point` to `_prev_stop_point` (`:50-83`). Movement anomaly =
mean |Δx| > 50 or |Δy| > 5 px while MOVING/PROCEEDING (`:288-294`); `_normal_moving_frames` counts anomaly-free moving frames (`:296-299`,
not serialised). UNOBSERVED (BL only, `tracker.py:339-344`): status/colour saved, `_moving_frames = 0`, restored by `set_observed` (`:35-48`).

**Confirmation of `contract_observed.md` §4 (all values in frames at 8 fps):** stopping→stopped at `_static_frames` = 24 ✓;
stopping→moving at `_moving_frames` = 9 ✓ (`>= 8` then `set_moving` adds one); stopped→proceeding at 6 ✓; proceeding→moving at 17 ✓;
proceeding→stopped at `_static_frames` = 1 ✓ (flicker is structural: every non-static frame in STOPPED bumps `_moving_frames`, every
static one re-enters STOPPED). Quirk: in STOPPING a non-static frame still increments `_static_frames` (`:270`), so it can exceed 24
without a transition (observed max 25).

**Airplane stage counters** (`transport.py:78-105`, called after the base update, `:110-113`), constants `_departure_thresh = 10·fps = 80`,
`_movement_before_arrival = 3·fps = 24`, `_arrival_thresh = 4·fps = 32`, `_minimal_pre_arrival_time = 60·fps = 480` (`:37-40`):
- before arrival: `_moving_counter` += 1 on MOVING (never reset except at arrival); `_stopped_counter` = consecutive STOPPED frames (any
  other status resets it, `:86`); **`arrival_frame = frame_id` when `_stopped_counter > 32` and the box height > 0.95·`_height_mode`**
  (`:87-89`; the height gate was `>=` before ac5098d "fix plane arrival timing"); then `_moving_counter = 0` and
  `have_pre_arrival_stage = arrival_frame >= 480` (`:92`) — i.e. "at least 60 s of footage before the arrival", **not** a stop-duration flag;
  `have_arrival_stage = True` once `normal_moving_frames > 24` (`:94-95`) — evaluated only while `arrival_frame is None`, so frozen after arrival.
- after arrival: `_moving_counter = min(+1, 80)` on MOVING, `max(−10, 0)` otherwise; `departure_frame = frame_id` when the counter first
  equals 80 (`:99-103`) — 80 moving frames with at most a 10-frame penalty per interruption ("motion start + 79" in §4 ✓, causal, written once).
- `print("Stopped counter ...")` every frame (`:105`).

**The `arrival_frame` rewrite** (`tracker.py:305-308, 493-527`): `accumulate_airplane_data` is True while the airplane exists, has no
`arrival_frame` and is STOPPING/STOPPED (`:305-306`) — note it is only re-evaluated on frames with an airplane row. Every frame goes through
`tracked_data_buffer`; the frame popped 5 frames later (`len >= N_INIT = 6`, `:499-500`) is either appended to `airplane_data_buffer`
(while accumulating) or triggers the flush: if the popped frame already carries `arrival_frame` (set at frame A = 24 stopping + 33 stopped
frames after the stop start S), `real_arrival_frame = airplane_data_buffer[0][1]` = **S**, and `arrival_frame` is overwritten with S in
`main_airplane` itself, in all buffered/accumulated frames' `state_dict` and in their envelopes (`:507-518`, `replace_plane_arrival_frame`
`:55-58`). If the episode ended without arrival (back to MOVING, or the height gate failed), the buffer is flushed unchanged (`:520-523`).
This confirms §4: `arrival_frame` = start of the first stopping episode that reaches the arrival criterion, written into that very frame;
"fake stops" = episodes that returned to MOVING before 24 static + 33 stopped frames, or that failed the 0.95·height gate; the 61–63
envelope-leak frames = 5 buffered + 1 current + ~57 accumulated. **Correction to §4's latency estimate**: a causal detector can know S only
at A = S + 57 frames (≈ 7.1 s) plus the publication delay, not "24 frames later"; the glossary's "4 s stop" is `_arrival_thresh` alone.
`have_pre_arrival_stage` is computed from A, not S (`transport.py:92` runs before the rewrite). GM computes `frame_stopped` from its own
`Plane(Airplane)` without this rewrite (`general_model/main.py:62, 874-875`) → two owners of T_arr today, differing by ≈ 57 frames.

**SAM and optical flow roles**: SAM only produces the keypoint mask at (re-)initialisation (`tracked_object.py:114, 365-367`); optical flow
drives every status decision; the box itself never influences the status except through the area-shift guard and the inlier ROI.

## 5. Beltloader semantics (`local_utils/bl_utils.py`)

- `get_bl_type` (`:4-133`) is called only for a **stopped, observed** BL (`tracker.py:350-351, 398-399`) with the per-frame biggest
  `front_door`/`back_door` boxes (`:317-322`), engine and back-wheel boxes. `check_door` (`:18-82`): front — BL overlaps the front door and
  extends past 60 % of its width (`:36-38`); back — any overlap with the back door (`:61`); a closed door is bridged by IoU > 0.8 with the
  previously classified `bl_type_bbox` (`:49, 71`); counters `bl_type_frames['front'|'back']` (the serialised `_bl_type_frames`) reset to 0 when
  the condition fails, and the type is returned at **≥ `1·fps` = 8 frames** (`:57, 79`), `back` only if `front == 0 or not cone_camera`. Wing
  extra (`:85-113`): BL below the closest back wheel, overlapping the biggest engine, engine's left edge inside the BL → `back`. On success
  `bl_type_bbox` is stored (`:129-131`). Config keys `door_offset`, `min_iou_bl_type`, `bl_rel_inter_thresh` (`local_config.yaml:8, 11-12`) are
  **never read**; `bl_range`, `bl_min_height` are used by the obstacle rule (`tracker.py:47-49`).
- "BL near aircraft": the tracker never computes IoU(BL, aircraft); `bl_type` is door-relative. Obstacle/unobserved: a `gse` or `trailer`
  box (offset 10 %) covering > 80 % of a non-moving BL that is centred within 10–90 % of the width and ≥ 30 px tall → `set_unobserved`
  (`tracker.py:33-52, 333-344`), the BL's box freezes while unobserved (`tracked_object.py:396`).
- Stops: only `_stops_count`, `_stop_point`, `_prev_stop_point`, `_dist_between_stops` (§3); the 3-stop rule, "BL@door = intersection > 0.2",
  BL speed, and "left the aircraft" are re-derived by modules (`module_consumption.md` §2.4). What the tracker already provides: per-BL
  status, stop count/points, door type with frame counters, obstacle status, `_init_xyxy`, `recent_biggest_bbox` (in memory only).
- Stage-detector events derivable **today** from tracker state: **T_arr** (`arrival_frame`, or causally STOPPED@S+24 / `_stopped_counter > 32`@S+57),
  **T_dep** (`departure_frame`), **BL@door** (BL `_status == stopped` ∧ `data.bl_type ∈ {front, back}`; a door-based, not aircraft-IoU-based,
  definition), **BL leave** (labelled BL → MOVING, `tracker.py:354-357`, or track end). **Missing**: `pushback_attached` — pushback is not tracked
  and no nose/pushback geometry exists; BL↔aircraft IoU; any explicit event/edge output (all of the above are levels, not transitions).

## 6. Reset / lifetime

- No reset inside a video: trackers (`tracker.py:93-106`), `main_airplane` (`:132, 294-299`), object dicts and `bl_labels_dict` (`:126-130`) live
  for the whole `detect()` call; nothing prunes them. X1 "one tracker per event" maps onto **one `detect()` call per merged video**; running
  it per chunk would recreate all of this (the stand's 297-"aircraft" case is GM's norfair main-plane selection, but the same applies here:
  `Airplane` counters, `bl_to_init`, DeepSORT ids restart).
- Frame numbering: `frame_number` = position in `zip(dataset, GM lines)` (`:144`), used for `arrival_frame`/`departure_frame` (`:302`); the file
  key = `frame_ii` call counter (`ML_worker.py:223, 309, 321`). They coincide only because frames are published exactly once in order. **EOF
  ordering hazard**: the final flush writes the 5 buffered frames *before* any still-accumulated pre-arrival frames (`tracker.py:561-568`), so
  a video ending while the airplane is STOPPING/STOPPED-before-arrival (or after the airplane vanished in that state — `accumulate_airplane_data`
  is not re-evaluated without an airplane row, `:305-308`) gets its last frames' contents assigned to the wrong keys.
- Video-length dependencies: none (no `nframes` use) except the EOF flush; `have_pre_arrival_stage` depends on the recording start (≥ 480).
- Non-causal elements: (1) the `arrival_frame` rewrite — unbounded look-ahead, one scalar (§4); (2) person back-fill of ≤ 5 tentative frames
  (`:435-441`); (3) a fixed 5-frame publication delay (`:499`); (4) `accumulate` episodes delay publication until the episode resolves — in
  iE9pRtOwlwj9XY ("stopping" for 2 871 frames, `contract_observed.md` §4) the tracker held ≈ 6 min of output in memory.
- Object order inside a frame (matters for a bitwise v1-compat writer): airplane, beltloaders (DeepSORT order), confirmed persons, GSE, then
  back-filled persons appended later (`:310, 365, 444, 487, 440`).
- Determinism: `np.random.choice` for keypoint subsampling (`tracked_object.py:132`) and `np.random.randint` for SAM prompts
  (`transport.py:76`) are **unseeded**; the TV-denoise gate (`tracker.py:268-282`) and the ImageNet ResNet download (`feature_extractor.py:13`)
  are environment-dependent. Two runs of v1 on the same file are not guaranteed bit-identical.

## 7. Version drift across `cv_common` pins

Both clones are grafted shallow tips (every commit in `.git/shallow`); of the 11 pins only **`ac5098d2` exists** locally (master HEAD; used by
`aircraft-chocks`, `beltloader-chocks`, `fod-walk-completed`, and `cv_trackers`' own submodule, `.gitmodules`/`ls-tree`). `dd5b5547`,
`33c188d0`, `86731e4c`, `8e3a7bf6`, `bb0b1746`, `acfc0808`, `d7f907cd`, `4291b0d9`, `238e1ef7`, `d74eb096` are absent (`git cat-file` fails), and
the modules' `cv_common/` submodule directories are empty. What the 24 reachable tips (branch heads + tags v1.1–v1.7.2) show:

| family | tips (date) | serialisation | unknown keys | airplane / vehicle keys |
|---|---|---|---|---|
| A "flat" | v1.3–v1.7.2 (2021–22), `3fc2ff6` (2024-01-05), `9f7223c` (2024-03), `1bbe772` (2024-04), `c11573b`/`beb229f` (2025-01), `984beef` (2025-04) | `state_dict = self.__dict__.copy()` minus `_mask` + `to_numpy`/`to_status` (`3fc2ff6:438-456`) | `from_state_dict = self.__dict__.update` → **accepts anything** (`:458-472`) | key set = instance attributes: `3fc2ff6` **40 / 34** (`_recent_bboxes`, `_recent_bboxes_time` and `_bl_type_*` in the base `__init__`, `:85-90`, no `_st`, no `have_arrival_stage`); `9f7223c`, `c11573b` 36 / 30; `1bbe772` 38 / 32 (adds `_real_height`, `_st`); `984beef` 36 / 31 (adds `_mask_full_size`, drops `_height_mode`) |
| B "explicit" | `8810e59` (2025-03-05), `9029e13`, `e397525`, **`ac5098d` (2025-08-08)**, `a9bf32d` (2026-04), `2759daf` (2026-05) | explicit key list (§3) | **`ValueError`** (`tracked_object.py:671-672`), tolerates `_recent_bboxes*`, `arrival_frame` | 39 / 34 in all six tips (identical key sets; `2759daf` only adds a `model_type` kwarg and `frame_number/invoker` plumbing) |

The stand's "correct 38 / 34" and "broken 40 / 34" (`docs/streaming_ref/contract.md:62-65`) are family A: 38 = the 36-key flat airplane +
`_recent_bboxes` + `_recent_bboxes_time` (exactly the two keys family B was taught to discard, `:666-667`), with `_bl_type_*` living in
`Vehicle`; 40 = the same plus `_bl_type_bbox`/`_bl_type_frames` in the base class — `3fc2ff6` reproduces 40/34 exactly. This is a reconstruction
(no 38/40-key file is available locally). ATL-C5 (39/34) was produced by family B — `ac5098d` or any sibling.

Crash matrix: producer B → consumer B: fine; producer B → consumer A: fine (extra `_st`, `have_arrival_stage` become inert attributes);
producer A(38) → B: fine; producer A(40), `1bbe772` (`_real_height`), `984beef` (`_mask_full_size`) → B: `ValueError` when restored into
`Airplane`. Any producer B airplane → a module that restores into the base class (`post-arrival:139`, `pre-departure:30`, `seat-belts:114`)
crashes on family B pins → since prod runs, those pins (`bb0b1746`, `d7f907cd`, `238e1ef7`) are presumably family A (unverified). Adding **any**
key to `state_dict` breaks every family-B consumer; removing a key breaks nobody (all pops default to None) but changes the modules' values.

## 8. Performance profile — measured 14.09 (RTX 5070 Ti, 1080p, `DjwtQRdZyt0sSk`, `scripts/tracker_v1_profile.py`)

The stand's `tracker = 0.11 ms` (`gat-streaming/streaming/simulate.py:305`) was a placeholder. Two 1 200-frame slices
("arrival" 3 400–4 600, "busy" 9 000–10 200, up to 8 tracks/frame), the unmodified `tracker.detect()` of each pin with
timing wrappers; raw reports `docs/analysis/speed/tracker_v1_profile_*.json`, discussion `tasks/notes/PF-Q1-17.md`:

| pin | slice | total ms/frame | `update_params` | PyrLK | DeepSORT ×3 | `estimate_sigma` | masks | `model_pub` |
|---|---|---|---|---|---|---|---|---|
| master b5d350c + ac5098d (MobileSAM) | arrival | **137.4** | 14.4 | 5.7 | 5.9 | **100.1** | SAM 4.4 | 0.5 |
| master | busy | **148.7** | 25.4 | 9.7 | 9.1 | **102.5** | SAM 8.0 | 0.8 |
| production bd43c3c + 2759daf (YOLO-seg) | arrival | **35.8** | 12.1 | 6.9 | 6.0 | 6.7 | YOLO-seg 2.2 | 0.5 |
| production | busy | **48.7** | 20.2 | 10.9 | 9.6 | 7.0 | YOLO-seg 3.8 | 0.8 |

Master runs **below real time** (7.3 fps for 8 fps input) because `estimate_sigma` on the full frame costs 161 ms per call on
this CPU and runs on every frame with any object (item 2 below); production throttles it to every 16th frame but still on
the full frame (the crop is commented out, `cv_trackers_prod/tracker.py:300-304`). Production's remaining cost is the
per-object state machine (optical flow + masks + DeepSORT ≈ 20–30 ms/frame) plus ≈ 10 ms of decode and loop overhead.
Master vs production on the same busy slice: same 4 identities, all 3 186 object-frames matched, but `_status` differs on
88 object-frames (2.8 %), `_is_stopped` 106, `_stops_count` 20 — the segmentation backend changes stop timing, and the
keypoint sampling is unseeded — yet the production pin's own run-to-run floor is small (two runs of the same slice:
identities and `_status` identical, 6 of 3 186 object-frames differ on `_moving_frames`/`_is_stopped`), so the status
gap between the backends is behavioural (PF-Q1-17).

### 8.1 Where the time goes (from code; confirmed by the profile)

Per frame, in decreasing expected cost (RTX-class GPU, 1080p):
1. **MobileSAM `set_image`** on the full frame (`tracked_object.py:185`) — once per object per re-initialisation (every 16/10/5 frames for
   airplane/BL/GSE, sooner when the point set dies), **not shared between objects in the same frame**; plus `predict` and `getLargestCC`
   (`common.py:522-538`, skimage `label`). The `is_stopped` short-circuit (`:376`) is dead because `:402` sets the flag to None first → SAM/OF
   also run while stopped.
2. **Noise gate + TV denoising** (`tracker.py:268-288`): skimage `estimate_sigma` on the full RGB frame 1–3× per frame on CPU whenever any
   object is present; `cucim.denoise_tv_chambolle` (50 iterations, float64 upload of a 6 MB frame) when σ > 0.5.
3. **DeepSORT features**: one ResNet34 forward per class per frame for BL and GSE crops (two separate ResNet34 instances), one re-id forward for
   persons (`deep_sort.py:39, 129-139`); Kalman/cascade cost negligible.
4. **Per object**: 2× `cv2.cvtColor` of the full frame (`tracked_object.py:377-378`, could be once per frame), FAST on the full gray (`:112, 129`),
   PyrLK on ≤ 250 points (`:151-153`), 3 full-frame copies per frame (`tracker.py:147, 288, 529`) — `img_to_draw` is copied even without `--save-video`.
5. **JSON**: `_p0.tolist()` (float32 → 17-digit doubles) + `_st` every frame per object = the observed 80–87 % + 4–6 % of bytes; `ndjson.writerow`
   per frame; `print`/`logging.info` per frame (`tracker.py:145-146`, `transport.py:105`); `confirmed_workers_ids` is a list appended every frame
   per worker with O(n) membership tests (`tracker.py:435, 442`).
6. Batching: none (one frame, one object at a time); GPU↔CPU round trips per object (SAM, features, cupy).
Nothing above depends on chunking; everything depends on decoded pixels, so the RT budget of 125 ms/frame is not demonstrably met by this code.

## 9. Configuration surface

- `global_config.yaml` (via `parse_config`, `common.py:307-325`, cwd-relative paths `local_config.yaml` + `cv_common/global_config.yaml`;
  local keys override global): `width` 1920, `height` 1080, `fps` 8, `fourcc` (save-video only; `model_starter.py:175-176` seds DIVX→avc1),
  `img_size` 1280 (`LoadImages`, `ML_worker.py:235`), `str2id` (person 0, airplane 2, beltloader 3, gse 4, pushback 5, airplane_engine 7,
  airplane_nose 9, tow_bar 12, fuel_truck 13, trailer 14, ladder 15, back_wheel 20, front_door 21, back_door 22, `:112-144`),
  `tracking.{airplane,beltloader,gse}.tracked_object.*` (§3; `min_points_number`, `real_height`, `movement_anomaly_thres_*` read via
  `tracking_params.get`, `tracked_object.py:349-363`), `deepsort_weights` scripted_ckpt.t7 (`:90`), `colors` (save-video). Not read:
  `tracking.*.norfair`, `conf_thres`, `status2id`.
- `local_config.yaml`: `bl_range` [0.1, 0.9], `bl_min_height` 30, `gse_iou_reinit_thresh` 0.25 (read); `bl_rel_inter_thresh` 0.3 (literal 0.3 at
  `tracker.py:389` instead), `door_offset` 0.5, `min_iou_bl_type` 0.05, `task` (unused).
- `deep_sort_pytorch/configs/deep_sort.yaml`: the two blocks of §2; `REID_CKPT` unused (path comes from `deepsort_weights`).
- Weights: `weights.dvc` (2 files, 86.8 MB: `mobile_sam.pt` + `scripted_ckpt.t7`; the checkpoint dir in git is empty), ResNet34 from
  torchvision `pretrained=True` (network/cache dependency, `feature_extractor.py:13`).
- Hard-coded: `ignore_dict` (`tracker.py:108-111`), BL square filter 0.9 (`:185`), obstacle rule 0.1/0.8 (`:45-49`), σ 0.5 / weight 5 / eps 5e-5 /
  50 it (`:270-282`), SAM `vit_t` + `mobile_sam.pt` (`:114-115`), BL re-init 0.3 (`:389`), buffer depth = `DEEPSORT_WORKER.N_INIT` (`:499`),
  LK params and 250 keypoints (`tracked_object.py:99-102`), area-shift 0.66–1.5 (`:381`), `tol` formula (`:236-237`), 1σ inlier filter (`:225`),
  5 % stop distance (`:247`), `10·fps` box history (`:329`), door 60 % / IoU 0.8 / `1·fps` (`bl_utils.py:37-38, 42, 49, 57, 65, 71, 79, 110`),
  airplane thresholds 10/3/4/60 s and 0.95 height gate, −10 decay, 10 prompt points (`transport.py:37-40, 76, 88, 100`).

## 10. Recommendations for Tracker v2 (ADR-001 §3)

1. **Freeze byte-for-byte in the v1-compat file**: the envelope key order `tr_id, xyxy, cls_str, conf(=0.0), state_dict, data`, the 7th key
   `arrival_frame` on the rewrite frames; the 39/34/0 key sets **and order** of §3; `Status.value` strings; `_color` tuples; `_obj_id`
   semantics (first track id of the object, survives re-association, airplane = 1); `tr_id` = per-class DeepSORT ids; `xyxy` = int Kalman box for
   BL/GSE/person and the int GM box for the airplane; `data.bl_type` ∈ {front, back, undefined}; object order inside the frame (§6); one line
   per frame, `[]` when empty. Keep the arrival rewrite *in the compat writer only* (it needs the 57-frame look-ahead anyway).
2. **Do not add keys to `state_dict`** (family B raises). New primitives go to `data{}` (read only via `.data['bl_type']`) or to frame-level
   `events/anchors`: `_movement_anomaly`, `_normal_moving_frames`, `have_arrival_stage` as an event, door counters, obstacle state, stop
   episodes with start/end frames, `bl_near_aircraft` (IoU with the airplane box), and per-object `first_seen`/`last_seen`.
3. **Events for the stage detector** (levels the tracker already has, to be edge-triggered by the detector, one owner): `AIRPLANE_STOPPED`
   (S+24), `T_ARR` = `arrival_frame` at S+57 with `value = S`, `T_DEP` = `departure_frame`, `BL_AT_DOOR` (stopped ∧ bl_type ≠ undefined, or a
   new IoU(BL, aircraft) > 0.2 primitive if the glossary definition is kept — decision needed), `BL_LEAVE` (labelled BL → MOVING or track end),
   `BL_UNOBSERVED`. `pushback_attached` needs a pushback track (class 5) + stationarity + nose geometry — new work, not in v1.
4. **Drop `_p0`/`_st` from the bus** (`schema_version` 2.0): the bus carries the 9 consumed scalars + `data{}`; the v1-compat sink writes
   `_p0`/`_st`/`_segm_points` from the in-memory objects. The 9 arrival-stage copies in modules consume `_p0/_st` only to recompute
   `have_arrival_stage`, which family B already exports (§4) — the porting step is "replace the block with `anchors`", per ADR-001 §4.
5. **Causality**: v2 emits every frame immediately (no 5-frame buffer, no person back-fill); document that the v1 file for frames S..A carries
   `arrival_frame = S` while the bus gets `T_arr` at A — the value matches, the availability differs by 57 frames (+ buffer).
6. **Parity plan** (`pf.eval.compare_tracker_ndjson`, identity `(cls_str, _obj_id)`, person by `(cls_str, tr_id)`): (a) same decoder (X4) and the
   same GM second-pass file as input; (b) seed numpy and pin norfair/torchvision or accept tolerance on `_p0`/`_st` (length ±10 %) and on
   `_segm_points`; (c) compare the consumed fields exactly (`_status` sequence, counters, `arrival_frame`/`departure_frame`/`have_*`, `_xyxy`
   ±1 px, `_stop_point` ±2 px, `_bl_type_frames`, `data.bl_type`); (d) then the bitwise line check for the v1-compat writer on the 7 ATL-C5
   videos; (e) measure the real per-frame cost of v1 first (§8) — the 0.11 ms line in `02_target_architecture.md` §6 is not this tracker.
7. Fix on the way (behaviour-preserving): grayscale once per frame, cache SAM `set_image` per frame, `confirmed_workers_ids` → set, drop
   the unconditional frame copies, remove per-frame prints; behaviour-changing fixes (EOF ordering, `_static_frames` in STOPPING, stale objects)
   only under a versioned schema with a parity report.

## 11. Open questions

1. Which family (A or B) the 9 absent pins are; in particular whether `bb0b1746`/`d7f907cd`/`238e1ef7` (base-class restore) are family A.
   Needs the full `cv_common` history (PF-X-05).
2. Exact composition of the stand's 38/40-key files (reconstructed in §7, not observed).
3. `norfair.Color` values in the production image (unpinned dependency) — needed for a bitwise `_color`.
4. Whether prod runs with any seed / fixed `torch.hub` cache for ResNet34; whether two prod runs of the same video are identical.
5. Which of BL@door definitions the stage detector should own: door-based `bl_type` (tracker) or IoU(BL, aircraft) > 0.2 (glossary, 3-stop).
6. Real per-frame cost of v1 on the reference videos (never measured; §8 ranks by code inspection only).
7. Whether the EOF ordering hazard (§6) has ever fired in prod (needs a video ending in a pre-arrival stop).
8. `cv_trackers` branches `loaders_track_fix` (`bcfa684`: tentative BL accumulation, square filter removed) and `loader_stops_fix`
   (`8c237c7`: MOVING as BL initial status) change BL semantics relative to master — which one prod actually deploys.
9. The exact `cv_common` commit inside the production image: `bd43c3c` still pins `ac5098d` but cannot run on it (§12) — the
   `tracker_optimization` commit it was built with (before `2759daf`, 2026-05-15) is absent from the archive.

## 12. Production delta (b5d350c → bd43c3c)

Production commit `bd43c3c` (2026-02-28, "Edit requirements.txt", `origin/optimization`; worktree `external/cv_trackers_prod`, read-only)
vs the review pin `b5d350c` (2025-08-08, master). `git diff --numstat b5d350c bd43c3c`: `.gitignore` +4/−0, `local_config.yaml` +2/−0,
`requirements.txt` +6/−1, `scripts/tracker_clips.py` +797/−0 (new), `tracker.py` **+79/−36**, `weights.dvc` +3/−3 — 6 files, 891/40.
`local_utils/bl_utils.py`, `deep_sort_pytorch/`, `model_starter.py`, `process_videos.sh`, `Dockerfile`, `.gitmodules` are byte-identical;
`ls-tree bd43c3c` still pins `cv_common ac5098d` and `db_worker 5a4aa83`. Production lines below cite `cv_trackers_prod/...`.

1. **Segmentation backend: MobileSAM → two Ultralytics YOLO-seg models.** `mobile_sam` import and predictor commented out
   (`cv_trackers_prod/tracker.py:27, 120-130`), `from ultralytics import YOLO` (`:30`), `plane_segmentor = YOLO("weights/yolo11s-seg_plane.pt")`
   and `bl_gse_segmentor = YOLO("weights/yolo26s_seg_bl_gse_tr10_noalb.pt")` (`:133-134`, **cwd-relative, not `weights_dir`**),
   `yolo_class_mapping = {'beltloader': [0], 'gse': [1]}` (`:136`). Every `update_params` call now passes `frame_number`, the segmentor and
   (vehicles) `yolo_idx=` (`:339-341, 386-387, 420-421, 522-523`). **This signature does not exist in `cv_common@ac5098d`** — there `Vehicle`
   inherits `update_params(xyxy, prev_im0s, im0s, predictor, bboxes_to_remove=None, is_noised=False)` (`cv_common/tracked_object.py:393`), so
   `cv_trackers_prod/tracker.py:386-387` would raise `TypeError` (two values for `bboxes_to_remove`). The matching code is the
   `tracker_optimization` tip `2759daf`: `Vehicle.update_params(..., frame_id, predictor, ..., yolo_idx=None)` (`transport.py@2759daf:198-199`),
   `Airplane.update_params(..., invoker=None)` (`:113-115`), `tracking_params['model_type'] = 'yolo_seg'` forced in both constructors (`:45, 173`),
   `ObjectSegmenter.segment_object(image, predictor, xyxy, frame_number, invoker, yolo_idx)` (`tracked_object.py@2759daf:183-238`). Hence the
   production image contained a `tracker_optimization`-line `cv_common` newer than the pin (`Dockerfile:11 COPY . .` ships the checked-out
   submodule; `cv_common/README.md:6` recommends `git submodule update --remote`). Consequences visible in code:
   - `to_state_dict`/`from_state_dict` bodies are **byte-identical** between `ac5098d` and `2759daf` (diffed) → 39/34/0 keys, same order; the
     coordinator's "ac5098d is the right cv_common" holds for the **contract**, not for the runtime path.
   - YOLO-seg path (`tracked_object.py@2759daf:200-238`): one inference per class name per frame, cached in the class-level
     `Classwise_buffer_mask[invoker.__class__.__name__] = [frame_number, results]` (`:176, 206-213`); conf 0.01 for `Vehicle`, 0.1 for `Airplane`
     (`:204`); mask = the instance whose box has the best IoU with the track box, resized to the frame and clipped to the box (`:218-236`), no
     `getLargestCC`, `_segm_points` no longer used as prompts (still generated and serialised, `transport.py@2759daf:58-79`). **Cache-key
     collision**: BL and GSE share the key `'Vehicle'` but request different `classes=yolo_idx` (`[0]` vs `[1]`); when a BL and a GSE
     (re-)initialise keypoints on the same frame, the GSE reuses the beltloader-class results → no matching instance → zero mask → no FAST
     keypoints → its status is frozen until the next re-init (BL is processed first, `tracker.py` order).
   - A bad box no longer kills the job: `fix_incorrect_bbox` repairs it (`common.py@2759daf:497-515`, `tracked_object.py@2759daf:441-444`).
2. **Noise gate throttled.** `estimate_sigma_interval: 2` (`cv_trackers_prod/local_config.yaml:14`) → `EST_SGM_DELAY = 2·fps = 16`
   (`tracker.py:155`); sigma is estimated on frames with `(frame_number − 1) % 16 == 0` when any object is present (`:299-304`) and the cached
   value gates TV denoising for the next 16 frames (`:306-323`); the post-denoise estimate is removed (`:320`). Master evaluated the gate on
   every frame (1–3 full-frame estimates), so denoising decisions differ in the 16-frame granularity — a behavioural, not schema, change.
3. **Weights.** `weights.dvc`: dir `e30ba4ea…` (2 files, 86 835 124 B) → `1a3e876f…` (4 files, 130 795 072 B): +2 files = the two YOLO-seg
   checkpoints named at `tracker.py:133-134` (+44 MB); the previous two (`scripted_ckpt.t7`, `mobile_sam.pt`) are presumably kept —
   `mobile_sam.pt` is dead weight since `mobile-sam` is commented out of `requirements.txt:9`. `.gitignore` adds `*venv*`, `runs*`,
   `yolo*.pt` (`.gitignore:6-8`). `requirements.txt` adds `torch==2.5.1`, `torchvision==0.20.1`, `ultralytics==8.4.9`, `opencv-python`,
   `pathspec==0.11.1` (`:3-4, 12, 18-19`).
4. **`scripts/tracker_clips.py` (797 lines, new)** — a copy of `detect()` for developer experiments on selected clips: `--timestamps`
   `'[["00:01:30","00:02:45"], ...]'` parsed with `ast.literal_eval` into frame intervals (`scripts/tracker_clips.py:236-254`), frames outside
   the intervals are skipped and processing stops after the last one (`:280-290`), FPS is reported over processed frames (`:758`), optional
   scalene profiling (`:12, 790, 797`). It imports both MobileSAM and YOLO (`:28, 31`) and hard-codes an absolute weight path
   (`/home/oleksii.shabo/repositories/cv_trackers/weights/…`, `:221`). Not a production entry point (`db_worker/model_starter.py:161` imports
   `tracker`), cannot run in the prod image (no `mobile_sam`), and skipping frames deliberately breaks X1/X2 — its outputs are not comparable
   to full runs.
5. **What of §§2–6 applies to both master and production.** §1 (job model, I/O, report), §2 (DeepSORT configs, ids, re-association,
   envelope, `data.bl_type`), §3 (key sets, order, types, `from_state_dict` rules), §5 (BL semantics) and §6 (buffers, EOF hazard, frame
   numbering, non-causal elements) describe both — the diff touches none of that code. §4 applies to both for the state machine
   (`analyze_movement` unchanged) and the airplane counters (`_update_stage_status` unchanged at `transport.py@2759daf:81`), so **arrival /
   departure / stop semantics and the `arrival_frame` rewrite are unchanged in production**; master-only in §4: the `ValueError` on a bad
   box and the SAM-prompt role of `_segm_points`. §8 item 1 (SAM) is master-only — production runs at most one YOLO-seg inference per class
   name per frame; §8 item 2 is 16× cheaper in production. §9: production additionally reads `estimate_sigma_interval` and the two
   cwd-relative weight paths. **The `state_dict` key set did not change** (ATL-C5's 39/34/0 is consistent with either build); `_p0`/`_st`
   values differ (different masks → different keypoints), so parity against ATL-C5 must be run with the production segmentation backend.
