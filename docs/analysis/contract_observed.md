# Observed GM + Tracker contract (production ndjson ATL-C5, 7 videos)

Source: `G:\gat_stages\atlc5_inferences\` (14 files, 5.8 GB), `G:\gat_stages\atlc5_videos\` (ffprobe, no decoding).
Script: `scripts/inspect_ndjson.py` (streaming line by line, 7 processes, ≈35 s), the full dump —
`docs/analysis/ndjson_observed.json` (5.8 MB). The GM code (`external/general_model` @13a4ddc) is described in `gm_current.md`;
here — only what is visible **from the data**, plus references to the code where it explains what is seen. The tracker code (`cv_trackers`,
`cv_common`) is unavailable, so all tracker rules below are empirical.

```
python scripts/inspect_ndjson.py --dir G:\gat_stages\atlc5_inferences --videos-dir G:\gat_stages\atlc5_videos ^
    --workers 7 --out docs/analysis/ndjson_observed.json          # --max-frames N for a quick trial
```

## 1. Files, naming, frame numbering

| video id | mp4 (GB) | nb_frames (ffprobe) | GM lines | Tracker lines | GM empty | Tracker empty | first non-empty tracker |
|---|---|---|---|---|---|---|---|
| AIjEAz70OfWCYG | 2.46 | 39 360 | 39 360 | 39 360 | 12 | 2 728 | 142 |
| DjwtQRdZyt0sSk | 2.35 | 37 530 | 37 530 | 37 530 | 3 420 | 5 788 | 37 |
| EjMS44IMRSHs4i | — | — | 57 000 | 57 000 | 4 925 | 7 386 | 4 627 |
| OKK5AlUiZnACMm | 4.31 | 69 030 | 69 030 | 69 030 | 4 381 | 8 571 | 4 872 |
| iE9pRtOwlwj9XY | 2.11 | 33 780 | 33 780 | 33 780 | 4 | 554 | 48 |
| vwksGNQQwqjT0I | — | — | 44 160 | 44 160 | 0 | 2 247 | 1 |
| xMFpSi7ZM6pQFa | 2.66 | 42 540 | 42 540 | 42 540 | 3 771 | 4 436 | 4 394 |

- Names: `general_model<ID>.mp4.ndjson`, `trackers<ID>.mp4.ndjson`; in the bucket a commit suffix is appended to the name
  (`gm_current.md` §5) — the local copies have lost it, so **the code version the files were produced with cannot be recovered from the data**.
- Videos: all 8 mp4 are h264 1920×1080, `r_frame_rate` 8/1. Three mp4 without inferences (7ci1uyF9Uz6PAg, ZFaAB6pxGcpYwx,
  sPTqv4GlCXi9Mz), two inference pairs without an mp4 (EjMS44IMRSHs4i, vwksGNQQwqjT0I).
- One JSON object per line, `\n`, exactly one key: **a string with the 1-based frame number** (`"1"`, `"2"`, …). In all 14 files
  the keys are contiguous 1..N, with no gaps, duplicates or non-monotonicity (`keys.contiguous_1_to_N = true`); N = `nb_frames` for all
  5 videos with an mp4. An empty frame is `{"<n>": []}` (10 bytes).
- The frame key is the writer's counter, not a timestamp (`gm_current.md` §3); consumers zip GM and trackers **positionally**.
  For the v2 contract this is exactly argument X2 (explicit `frame_id`).
- Serialization: `json.dumps` with default separators (`", "`, `": "`), without `sort_keys`. Re-serializing every
  25th line gave **byte-for-byte the same line** in all 14 files (GM 1352–2762 lines/video, tracker 1271–2427) — bitwise
  parity via Python `json.dumps` is achievable.

## 2. General Model: record format and class_id inventory

Record: `[x1, y1, x2, y2, conf, class_id]`, always length 6 (6 756 839 records, 0 other lengths). Types:
`[float, float, float, float, float, int]` — 6 553 040 records; `[float, float, float, float, **int**, int]` — 203 799 (all of class 2, §5).

- Coordinates are absolute pixels, clipped to `[0..1920]×[0..1080]` (min 0.0, max 1920.0/1080.0; 0 records outside the frame);
  always `x2 > x1`, `y2 > y1`. Integer-valued floats (`255.0`) in **all** classes except class 2 in 3 videos (§5).
- `conf` ∈ [0,1] for all classes except 2; **100 % of the values are exactly representable in float16** (e.g. `0.83349609375`) — the output
  of an fp16 engine, float64 repr (`gm_current.md` §2).
- Detections per frame: mean 19.2–23.6, p90 26–33, maximum 38–53 (OKK5AlUiZnACMm frame 52746). Line 930–1150 B, max 2 553 B.
- **Order within a frame** is not a single sorted list but a concatenation of groups (see `main.py:767-871`): (1) the GM detector,
  `conf` descending, threshold 0.35 (classes 0–24, min 0.350341796875); (2) the chocks model → class 25, threshold 0.10 (min 0.10015869);
  (3) the vehicle model → class 31, threshold 0.40 (min 0.400390625); (4) copies of vehicle boxes with classes 29/30 (`obstacle`/`side_obstacle`);
  (5) one record of the main airplane, class 2 — **always last**. Frames where the whole list is sorted: only 38–3 340 out of ≈40 000.

Inventory (sum over 7 videos; `w×h` — mean box size, px; name — only where there is evidence):

| id | name (evidence) | records | conf min | w×h | id | name | records | conf min | w×h |
|---|---|---|---|---|---|---|---|---|---|
| 0 | person (IoU match with the tracker 319 989) | 335 351 | 0.350 | 121×302 | 16 | ? | 14 998 | 0.350 | 42×94 |
| 1 | ? | 537 786 | 0.350 | 70×156 | 17 | ? | 1 880 | 0.350 | 30×68 |
| 2 | airplane (match 203 799; `main.py:854`) | 203 799 | **int 580–680** | 1568×636 | 18 | ? | 3 609 | 0.350 | 22×45 |
| 3 | beltloader (match 207 642) | 216 713 | 0.350 | 835×272 | 19 | ? | 222 656 | 0.350 | 103×96 |
| 4 | gse (match 129 445) | 148 943 | 0.350 | 241×194 | 20 | ? | 218 349 | 0.350 | 93×67 |
| 5 | pushback (`gat-streaming/streaming/simulate.py:33`) | 30 869 | 0.350 | 226×248 | 21 | ? | 98 549 | 0.350 | 241×141 |
| 6 | ? | 283 460 | 0.350 | 841×177 | 22 | ? | 18 | 0.370 | 88×65 |
| 7 | ? | 475 604 | 0.350 | 207×123 | 23 | ? | 33 315 | 0.350 | 44×95 |
| 8 | ? | 273 506 | 0.350 | 77×248 | 24 | ? | 111 041 | 0.350 | 668×251 |
| 9 | airplane_nose (`simulate.py:33`) | 158 162 | 0.350 | 236×283 | 25 | chock (`main.py:586`, threshold 0.10) | 914 303 | 0.100 | 54×29 |
| 10 | ? | 325 887 | 0.350 | 90×130 | 29 | obstacle or side_obstacle (`main.py:829`) | 471 281 | 0.105* | 595×281 |
| 11 | ? | 19 | 0.363 | 39×92 | 30 | side_obstacle or obstacle (`main.py:823`) | 345 050 | 0.105* | 180×203 |
| 12 | ? | 106 709 | 0.350 | 303×96 | 31 | vehicle (`main.py:592`, threshold 0.40) | 1 004 512 | 0.400 | 354×202 |
| 13 | ? | 7 757 | 0.350 | 376×207 | 26–28 | — do not occur in any of the 7 videos | | | |
| 14 | ? | 152 679 | 0.350 | 246×267 | | | | | |
| 15 | ? | 60 034 | 0.350 | 145×315 | | | | | |

\* The `conf` of records 29/30 is a "leaked" loop variable (`gm_current.md` §3), so it can be below the GM threshold.
The `?` names live in `cv_common/global_config.yaml` → `str2id` (unavailable); by size, 6/24 look like airplane parts
(wing/tail), 12–15 — vehicles. **The table gets filled in as soon as `global_config.yaml` appears**; until then v2 must reproduce
ids, not names. The share of a class's detections accompanied by a track (IoU ≥ 0.5 in the same frame, 7 videos): 0 → 95.0 %, 2 → 100 %,
3 → 95.8 %, 4 → 86.8 %, 31 → 0.5 %, 5 (pushback) → 0.04 %, the rest 0 — the tracker tracks only person/airplane/beltloader/gse.

## 3. Tracker: envelope, `state_dict`, sizes

The frame value is a list of objects. The envelope (key order is constant):
`{"tr_id": int, "xyxy": [int×4], "cls_str": str, "conf": float, "state_dict": {...}, "data": null | {"bl_type": str}}`.
In 61–63 frames per video (the first airplane object-frames after arrival, e.g. AIjEAz70OfWCYG 11151–11212) the airplane envelope has
**a seventh key `arrival_frame`** (§5).

| cls_str | keys in `state_dict` | object-frames (7 videos) | distinct `tr_id` / `_obj_id` per video | `data` | max per frame |
|---|---|---|---|---|---|
| airplane | 39 | 203 799 | 1 / 1 (`tr_id = _obj_id = 1`) | null | 1 |
| beltloader | 34 (+`_bl_type_bbox`, `_bl_type_frames`) | 209 498 | 9–26 / 5–8 | `{"bl_type": "front" | "undefined"}` — "back" does not occur | 3 |
| gse | 34 (the same as BL) | 132 923 | 49–193 / 20–39 | null | 3 |
| person | **0** (`{}`) | 326 145 | 157–232 / — | null | 8 |

- `conf` in the envelope is **always 0.0** (all classes); `xyxy == state_dict._xyxy` always (0 mismatches); `cls_str == _class_name`
  wherever a state exists. `tr_id` **is not equal** to `_obj_id` for BL/GSE (BL: 24 051 of 24 318 frames in AIjEAz70OfWCYG): `tr_id` is the track id,
  `_obj_id` is a stable object id that survives re-association (up to 9 tracks per BL, up to 55 per GSE in iE9pRtOwlwj9XY).
  `tr_id` is not unique across classes (person and gse share numbers; 0–377 frames per video with a collision); the pair
  `(cls_str, tr_id)` is unique within a frame (0 duplicates).
- Tracker boxes ≠ GM boxes: an exact match only in 0.2–4.6 % of BL/GSE/person frames (best-IoU mostly 0.9–0.99, person 0.7–0.99);
  the airplane — an exact match in 5 videos, IoU ∈ [0.99,1) in 3 (float GM boxes, §5). I.e. the tracker smooths/predicts boxes.
- The schema is **the same in all 7 videos** (0 differences in key sets, key order constant), `_bl_type_*` is **absent** from the airplane —
  this is the "correct" hierarchy per `streaming_ref/contract.md`, but 39 keys instead of 38: `_height_mode` was added. Hence ATL-C5 was produced
  by a third tracker version, different from both described on the test bench.

`state_dict` (order as in the file); constants are unchanged for an object throughout the whole track in all 7 videos:

| group | fields | observed |
|---|---|---|
| service | `to_numpy` (list of numpy field names: `[]`, `["_p0"]`, `["_p0","_st"]`), `to_status` (`["_status"]`, occasionally `["_status","_prev_status"]`) | change over time |
| identity (const) | `_obj_id`, `_class_name`, `_init_xyxy` | |
| geometry | `_xyxy`, `_previous_xyxy` (int×4), `_stop_point`, `_prev_stop_point` ([x,y] or null; = box centre, jitters ±2 px in "stopped") | every frame |
| status | `_status` ∈ {moving, stopping, stopped, proceeding} (+ `unobserved` in BL, 1–23 frames/video), `_prev_status` (almost always null), `_color` (derived from the status), `_is_stopped` (true/false/**null** in 7–16 % of frames), `_stops_count` | |
| counters | `_static_frames` 0..25, `_moving_frames` up to ≈380, `_of_dots_lifetime` 0..16; airplane: `_moving_counter` 0..137, `_stopped_counter` 0..33 | every frame |
| optical flow (private, large) | `_p0` — a list of ≤250 points `[[x,y]]` float; `_st` — a list of ≤250 int 0/1; `_mask` always null; `_segm_points` — 10 points `[x,y]` int, airplane only (25 212/25 280 frames) | depend on OpenCV |
| parameters (const, = class config) | `_init_dots_lifetime` airplane 16 / BL 10 / gse 5; `_static_points_thres` 0.5; `_stopping_time_thres` 24; `_moving_time_thres` 8; `_proceeding_time_thres` 16; `_display_proceeding_time_thres` 5; ROI `_from_x,_to_x,_from_y,_to_y` airplane 0.35/0.9/0.25/0.8, BL 0.1/0.7/0.4/0.9, gse 0.1/0.9/0.2/0.9 | |
| Vehicle-only | `_bl_type_bbox` (int×4 or null), `_bl_type_frames` `{"front": n, "back": n}` | every frame |
| Airplane-only | `have_pre_arrival_stage`, `have_arrival_stage` (bool), `arrival_frame`, `departure_frame` (int or null), `_height_mode` (float, = the 5th field of the class-2 GM record) | §4 |

Sizes: a tracker line is on average **15.3–21.6 KB** (non-empty 17.1–23.4 KB), maximum 36.9–60.6 KB (iE9pRtOwlwj9XY frame
13623) — at 2.2–3.6 objects per frame. An airplane object ≈ 11.2–12.2 KB, beltloader ≈ 9.7–11.8 KB, gse ≈ 5.7–10.0 KB, person
≈ 110 B. `_p0` dominates: **80–87 % of the bytes** of an object with state, `_st` another 4–6 %, envelope + scalars ≈ 0.9 KB. The tracker file is
14–22 times larger than the GM one precisely because of the optical-flow arrays; without `_p0`/`_st` it would be ≈ 1.5–2 KB per frame.

## 4. Airplane events (anchors T_arr / T_dep) — what the stage detector has to reproduce

Observed state machine (all 7 videos, values in `state_at_set` in the JSON):
`stopping` → `stopped` at `_static_frames` = 24 (`_stopping_time_thres`, 3 s); `stopping` → `moving` at `_moving_frames` = 9
(> 8); `stopped` → `proceeding` at `_moving_frames` = 6 (> 5); `proceeding` → `moving` at 17 (> 16); `proceeding` → `stopped`
at `_static_frames` = 1 (hence the proceeding↔stopped "flicker" of 1–7 frames, up to 56 status transitions per video).
- **`arrival_frame`** is written **in the frame where `stopping` begins** (`_static_frames` = 1) and does not change afterwards — but not on the first
  `stopping`: in DjwtQRdZyt0sSk two earlier stops (3466, 3514) without arrival, in EjMS44IMRSHs4i (4972) and OKK5AlUiZnACMm (4892)
  one each. In all 7 videos arrival = the start of **the first `stopping` episode that reaches `stopped`**; the criterion the tracker
  applies causally (stop point/ROI/counters do not explain it — see `ndjson_observed.json`) remains unknown without `cv_common`.
  In practice: a causal detector can confirm T_arr only 24 frames (3 s) later — the value will match, the availability will be delayed.
- **`have_arrival_stage`** → true on the 25th consecutive frame with `_status = moving` before arrival (3 videos); in 4 the airplane appeared already
  on the stand — the flag stays false forever. **`have_pre_arrival_stage`** → true when `_stopped_counter` = 33 (≈4.1 s after
  `stopped`; this is exactly the glossary's "4 s stop"), after which `_moving_counter` is reset to 0.
- **`departure_frame`** = the frame in which `_moving_counter` reached 80 (10 s of motion; motion start + 79, e.g. 36075 → 36154), and does not change
  afterwards; after it `_stops_count` is reset, subsequent stops do not change arrival.

| video | airplane track: frames (object-frames, presence episodes) | T_arr = `arrival_frame` | stops before it | `stopped` from | `have_arrival_stage` | `have_pre_arrival_stage` | T_dep = `departure_frame` | `_height_mode` |
|---|---|---|---|---|---|---|---|---|
| AIjEAz70OfWCYG | 11150–38233 (25 280; 12) | 11151 | — | 11175 | — | 11207 | 36154 (motion from 36075) | 680 |
| DjwtQRdZyt0sSk | 3465–21962 (17 673; 52) | 3669 | 3466, 3514 | 3692 | 3502 | 3724 | — (track breaks off at 21962 of 37530) | 660 |
| EjMS44IMRSHs4i | 4627–45792 (40 585; 36) | 5067 | 4972 | 5090 | 5025 | 5122 | — (45792 of 57000) | 610 |
| OKK5AlUiZnACMm | 4872–52820 (44 144; 39) | 4902 | 4892 | 4925 | — | 4957 | — (52820 of 69030) | 610 |
| iE9pRtOwlwj9XY | 1647–33610 (20 138; 31; absent for 11 826 frames) | 1653 | — | 4524 | — | 12001 | 31776 | 660 |
| vwksGNQQwqjT0I | 10246–42917 (25 930; 15; absent for 6 742) | 10309 | — | 15712 | 10271 | 15744 | 41169 | 580 |
| xMFpSi7ZM6pQFa | 4394–36398 (30 049; 186) | 4420 | — | 4443 | — | 4475 | — (36398 of 42540) | 680 |

The airplane object in the tracker exists **exactly in those frames where GM has a class-2 record** (203 799 = 203 799), i.e. its "presence"
is inherited from the main-airplane selection in GM after EOF (`gm_current.md` §4) — in 4 of 7 videos the track breaks off long before the end of the
recording and T_dep never occurs at all; in iE9pRtOwlwj9XY between 1653 and 4524 the airplane is "stopping" for 2 871 frames because it is present in only 53 of them.

## 5. Anomalies and traps

1. **The class-2 record**: the 5th field is `int(mode(bbox height/10)·10)` (580–680), not a probability (`main.py:854`); always last in the
   frame; in 3 videos the coordinates are **non-integer** (EjMS44IMRSHs4i 40 487 of 40 585 records, OKK5AlUiZnACMm 33 670 of 44 144, xMFpSi7ZM6pQFa
   14 782 of 30 049; e.g. `[130.5, 138.78125, 1745.1875, 974.46875, 610, 2]`) — `BboxStabilizer` on "heavy" noise; the tracker
   writes the same boxes as int (`xyxy`, `_xyxy`), hence IoU 0.99–1 there instead of an exact match.
2. Records 29/30 are copies of vehicle boxes with the `conf` of the frame's last detection (min 0.105 < GM threshold 0.35).
3. `conf` in the tracker envelope is always 0.0; `person` has no state (`state_dict: {}`), the class is visible only from `cls_str`.
4. The envelope key `arrival_frame` in 61–63 airplane object-frames after arrival (in iE9pRtOwlwj9XY stretched over 1653–12006 due to
   sparse presence) — a leak of a state field into the envelope; modules must not read it.
5. `tr_id` ≠ `_obj_id` and `tr_id` collisions across classes (§3) — the identity for parity must be taken as `(cls_str, _obj_id)`
   for classes with state and `(cls_str, tr_id)` for person.
6. `_bl_type_*` **does not leak** into the airplane in any of the 7 videos (`check_class_leakage` = 0), but the schema has 39 keys (`_height_mode`)
   versus the 38/40 known to the test bench; there is no versioning in the files (X3). `data.bl_type` — only `front`/`undefined`.
7. `_is_stopped` can be `null` (1–10 % of frames), `_prev_status`/`to_status` change shape in isolated BL frames
   (`unobserved`), `_p0` can be `null` when `to_numpy = []`.
8. Empty GM frames: 0–4 925 per video (DjwtQRdZyt0sSk 3 420, EjMS44IMRSHs4i 4 925, OKK5AlUiZnACMm 4 381, xMFpSi7ZM6pQFa 3 771) —
   long stretches without a single detection, in trackers even more (554–8 571).
9. Numbering, duplicates, order — clean in all files; no schema differences between videos; `nb_frames` = lines. Gaps will appear
   only on chunk-wise transport (test-bench level 3), not in batch production.

## 6. What to compare between old ↔ new GM/Tracker, and with what tolerance

Principle: first **field-level** parity (by `frame_id`, not by position), then **bitwise** (`json.dumps` of the line) — only for
the v1-compat adapter that reproduces the legacy file (`gm_current.md` §10.3). X4 conditions: the same decoder on both sides, a full turnaround,
identical weights/thresholds (0.35/0.10/0.40), a warmed-up cache, an idle machine.

| what | how to compare | tolerance |
|---|---|---|
| numbering | line count, keys 1..N, `[]` on an empty frame | exact (N = `nb_frames` of the same decoder) |
| GM records of classes 0–25, 31 | multiset of `[x1,y1,x2,y2,cls]` per frame + `conf` after matching | coordinates exact (int-valued float, clamp 0..1920/1080); `conf` exact with the same fp16 engine, otherwise ≤ 1/2048 (1 ulp fp16); group order (GM↓, chock↓, vehicle↓) — for the bitwise level |
| per-video summary | record count per class, min conf per class, detections/frame histogram | count ±0.5 %, min conf exact (catches a threshold/model shift), presence of all ids 0–25, 29–31 |
| class-2 records | set of presence frames; box; 5th field | frames exact; box exact where v1 is integer, ±1 px where the stabilizer is (3 videos); 5th field — the int mode exact (needs the whole video → v1-compat post mode only, in the v2 bus replace with a real `conf`) |
| records 29/30 | set of boxes per frame | boxes exact; do not compare `conf` (a defect), for the bitwise level — reproduce as is |
| tracker: objects per frame | matching by `(cls_str, _obj_id)` (person — by `tr_id`) and IoU ≥ 0.9 | object count per frame exact; distinct `_obj_id` per class per video ±0; airplane exactly 1 (X1) |
| `state_dict` constants | all "const" fields from §3 (thresholds, ROI, `_init_dots_lifetime`, `_class_name`, `_init_xyxy`, `_height_mode`) | exact; the set and **order** of keys per class exact (39/34/0) |
| `_status` | per-frame sequence per object | match ≥ 99 % of frames; each transition ±1 frame; number of `stopping`/`stopped` episodes exact |
| `arrival_frame`, `departure_frame`, `have_*` | value and the frame it is set at | value **exact** (these are the stage detector anchors); the set-at frame exact in batch mode, in causal mode — ≤ +24 frames for arrival, a documented delay |
| `_xyxy`, `_stop_point`, `_bl_type_bbox` | per object and frame | IoU ≥ 0.99 or ±1 px; stop point ±2 px; `_bl_type_frames` counters exact |
| counters (`_static_frames`, `_moving_frames`, `_moving_counter`, `_stopped_counter`, `_stops_count`) | per frame | exact given an identical `_status` sequence |
| `_p0`, `_st`, `_segm_points`, `to_numpy` | not bitwise: list length, share of `null`, `to_numpy` | length ±10 %, `null` pattern ±1 % of frames (depend on OpenCV/SAM) |
| `data`, envelope | `data.bl_type` per frame; set and order of envelope keys; `conf` = 0.0 | exact; the extra `arrival_frame` in the envelope — reproduce only in v1-compat |
| size | mean bytes per line | ±5 % (a proxy for lost/added fields) |
| bitwise level | `json.dumps(obj) + "\n"` == the v1 line | 100 % of lines for the v1-compat writer; any difference → field-level diff first |

The minimal data set for this is these 7 videos (all have T_arr, 3 have T_dep, 3 have "fake stops", 3 have float airplane
boxes), then a balanced sample with fail labelling (`tools/pick_balanced.py`), because parity here only shows "the same as v1".
