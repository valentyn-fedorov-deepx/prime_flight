# M21 · Pushback pathway confirmed clear of obstacles

> Checks that nothing stands in the aircraft's path while it is pushed back. In the cone camera view it builds a region behind the aircraft tail and fails when a small vehicle, cone, chock or ladder lies inside it while the aircraft moves.

## At a glance

| | |
|---|---|
| Checks | M21 · Pushback pathway confirmed clear of obstacles |
| Stage | Pre-departure, Departure |
| Looks at | moving-aircraft frames after arrival, up to 15 s after the tracker's departure moment; a crossing counts only from 15 s before to 15 s after that moment |
| Cameras | cone camera, for aircraft and jets (the code does not check the camera type) |
| Uses | General Model (GM) classes: airplane_tail, airplane_nose, pushback, belt loader, GSE (ground support equipment), fuel truck, trailer, cone, chock, ladder. Tracks: aircraft (with the tracker's arrival and departure moments). Video frames: no |
| Own models | none (the MobileSAM pushback tracker was removed in January 2026) |
| Runs on | CPU (no model; the Docker image uses the GPU base) |
| Real time | ready as is — one pass, no video frames, decides 15 s after the tracker's departure moment |
| Production version | master @ 104db85 (2026-01-22) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | There is no GSE, trailer, fuel truck, belt loader, person, cone or chock on the pushback pathway during departure. |
| Fail | Any of the listed items is on the pushback pathway during departure. |
| Not observed | There is no departure, no aircraft tail or no aircraft in the video. |
| Not observed — view blocked | Obstacles were present for more than 30 s during departure (and the 60 s before it). |

## How it decides

1. Frames without any GM detection are skipped. On the other frames it follows the last aircraft track in the list. Arrival and departure come from the tracker (arrival after about **4 s** stopped, departure after about **10 s** of movement).
2. After arrival it keeps the latest tail and nose boxes and builds the pathway region: as tall as the aircraft box, as wide as the tail box, widened beyond the tail by half the nose-to-tail distance, at most **250 px**.
3. It sorts the detections. Cones, chocks and ladders are path objects only below a size limit (e.g. chock **25 × 5 px**). Belt loaders, GSE, fuel trucks and trailers larger than **800 × 600 px**, or lower in the image than the aircraft and the pushback, are view blockers; the others below their size limit are path objects. A blocker holding more than **80 %** of a pushback box is the pushback itself and is dropped.
4. A frame is checked when the aircraft has arrived, the tracker reports it as moving, a pushback was seen at least once and the region exists. The module stops **120 frames** (15 s) after the departure moment.
5. If a blocker covers more than **10 %** of the region, the frame is counted as blocked and skipped. Otherwise it counts as a checked frame; a path object with more than **50 %** of its box inside the region makes the result Fail. Only the first crossing of the video is stored (class and time).
6. No aircraft → Not observed. Fewer than **56 checked frames** (7 s) → Not observed ("no departure stage" or "not enough frames").
7. A Fail is kept only if the stored crossing lies in the last **30 s** of the check; otherwise the verdict becomes Pass.
8. If the verdict is not Fail and more than **240** blocked frames (30 s) fall in the last **60 s** of the check, the verdict is Not observed — view blocked.

## Settings

All values are hard-coded in `main.py`; `local_config.yaml` holds only the task name.

| Setting | Value | What it does |
|---|---|---|
| `Plane._check_after_departure` | 120 frames (15 s, written as `15 * 8`) | checking time after the departure moment |
| region widening | half the nose-to-tail distance, at most 250 px | extends the region beyond the tail |
| `filter_dict` (width × height) | chock 25×5, cone 15×40, ladder 70×200, belt loader 200×70, GSE 150×100, fuel truck 250×150, trailer 150×130 px | only smaller boxes are path objects |
| big vehicle | > 800 × 600 px | vehicle treated as a view blocker |
| blocker overlap | > 10 % of the region | frame blocked, not checked |
| object overlap | > 50 % of the object box | object on the path → Fail |
| minimum checked frames | 56 frames (7 s) | fewer → Not observed |
| Fail window | last 30 s of the check | earlier crossings are dropped |
| blocked limit | > 240 frames (30 s) in the last 60 s | → Not observed |

## What it reports

- **Verdict:** Pass, Fail or Not observed.
- **Report:** one line. Pass: "There is no transport on the pushback pathway on the departure stage. (HH:MM:SS - HH:MM:SS)" (the window starts at most 45 s before the end of the check). Fail: "<class> crossed the pushback pathway. (HH:MM:SS)". Not observed: no plane, no departure stage, not enough frames, or "There was an obstacle on the video".
- **Smart timeline:** one entry with the status, start and end frame for Pass and Fail; empty for Not observed.
- **Files:** a per-frame JSON log; an annotated video with `--write-video`.

## Known issues and limits

- Measured: 0 of 4 known violations caught (recall 0 %); the 85 % accuracy comes from passing clean videos. The repository's monthly labels agree (3 true Fail videos, all reported Pass); `scripts/problems.txt` names a too-thin region, missed departures and an ignored big obstacle.
- Only the first crossing of the video is stored (`main.py:479-482`). If it lies more than 15 s before the departure moment (e.g. a false "moving" status), it is dropped at the end and the verdict flips to Pass, even if objects crossed later. Likely part of the low recall; to confirm.
- People are not checked although the client rule lists them; ladders are checked although the rule does not list them.
- The size limits are very small (a chock must be under 25 × 5 px), so chocks practically never count. To confirm on data.
- "Pushback moving" is the aircraft's tracker status; a pushback seen once at any earlier time is enough (architecture review).
- The region needs a tail detection. When the tail appears right of the nose, the code narrows the region instead of widening it.
- It follows the last aircraft track in each frame, not the largest, so another aircraft can be mixed in.
- Without a tracker departure moment nothing is trimmed: crossings and blocked frames from the whole video count.
- The README still describes the removed MobileSAM pushback tracker; `mobile-sam` and the DVC weights (one 40.7 MB file) are no longer used.

## For developers

- **Repository:** `dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles`; production line `master` @ `104db85`; default branch `master` @ `104db85` (the same).
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, weights_dir, json_logger, cone_camera)`; all logic is in `main.py` (`Plane` keeps tail, nose and the region; `smallEnough` is the size filter). `scripts/` holds the monthly evaluation notebook, labels and problem notes.
- **Dependencies:** `cv_common` dd5b554, `db_worker` 5a4aa83 (`git ls-tree HEAD`; dd5b554 is not in the local archive, the local folder carries ac5098d); norfair 0.3.1, OpenCV; DVC remote `gs://cv_weights/DVC`.
- **Run locally:** `python main.py --source <video>.mp4 --inferences-dir <GM and tracker files> [--write-video] [--json-fn <name>]`; `run_module.py` runs a test list.
- **Code references:** step 1 `main.py:294-295`, `:319-332`; 2 `:117-150`, `:344-346`; 3 `:196-198`, `:252-260`, `:297-317`, `:348-368`, `:415-420`; 4 `:81`, `:168-187`, `:427-429`, `:504-505`; 5 `:432-482`; 6 `:513-524`; 7 `:526-532`; 8 `:550-557`.
