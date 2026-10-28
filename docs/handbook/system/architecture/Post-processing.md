# Post-processing — how a video becomes a result today

> Today every check runs after the turnaround. The camera box uploads the video in one-minute pieces, the pieces of a
> turnaround are joined into one video per camera, and then three kinds of jobs run one after the other on the whole
> video: the General Model, the tracker, and one job per module. Nothing reaches the client before the whole chain has
> finished — about 16 hours after the recording ended (the median of September 2026).

## The path of a video, step by step

1. **Recording at the gate.** The camera box records the cone camera and the wing camera in one-minute video files
   (full high definition, 8 frames per second, about 4 megabits per second per camera) and uploads them to the bucket of
   raw pieces. A small service checks that the box is alive and writes it to the database; another one
   stores the box's logs.
2. **Collecting the pieces.** A subscriber service notices the uploaded pieces and collects the list of pieces of one
   turnaround.
3. **Merge.** The merge job finds, orders and joins the pieces into one video per camera — the full turnaround — and
   puts it into the bucket of videos to process. It also decides where the turnaround begins and ends.
4. **The message bus.** The new video produces a message. The **receiver** reads every message, updates the database
   (the video, the turnaround and its list of checks) and decides which job comes next; the **job scheduler** starts that
   job on the cluster of graphics cards.
5. **The General Model job** goes through the whole video once and writes, for every frame, the boxes of the objects it
   found; it also finds the camera type, the aircraft type and the airline (*Shared parts / General Model*). Its result
   file goes to the bucket of results.
6. **The tracker job** reads the General Model's file and follows the aircraft, the belt loaders, the service vehicles and
   the people from frame to frame; it finds when the aircraft arrived and when it left, and which belt loader serves
   which door (*Shared parts / Tracker*). Its result file goes to the same bucket. The job can also draw a debug video,
   but production starts it with the video switched off.
7. **The module jobs** — one per module, all at the same time — read both result files, and some also the video, and
   give the verdicts of their checks with one sentence for the client and a timeline (*Modules*).
8. **Results.** The verdicts and timelines go to the database and the bucket of timelines; the website shows them.

## What each job needs and where it runs

| Job | What it does | Runs on | How long, for a median 87-minute video |
|---|---|---|---|
| Merge | joins the one-minute pieces into one video per camera | a pool of machines for merging | 0.8 hours, after 1.7 hours of waiting to start |
| General Model | finds the objects, the camera, the aircraft type and the airline | one graphics card per job | 1.8 hours (2.4 before the October 2026 speed-up) |
| Tracker | follows the objects; arrival and departure | one graphics card per job | 1.3 hours |
| Modules | one job per module: the verdicts | graphics cards or ordinary processors, depending on the module | the slowest about 0.9 hours; they run at the same time |

Every job on a graphics card gets one card of the production type, 3.3 processor cores and 8 gigabytes of memory. The
production cluster is in Google Cloud; a move to Microsoft Azure is in progress.

## Where the files are

| What | Where |
|---|---|
| Raw one-minute pieces | the bucket of raw pieces |
| Merged videos | the bucket of videos to process (production: read-only for engineers) |
| What the General Model and the tracker found | the bucket of results: one folder per video, one file per version; the file is named after the version of the code that wrote it |
| Timelines of the checks | the bucket of module timelines |
| Job logs | the bucket of logs: one file per job and start time |
| Turnarounds, videos, verdicts | the database behind the website |

Three facts that trip people up:

- **Every job writes its file under the name of its code version.** A new version writes a new file next to the old one,
  and the next jobs read the **newest** file of a video, unless a test run names the version it wants.
- **The result files are compressed**, although their names do not say so, and the compressed file contains the time it
  was written. Two runs with identical results therefore give different compressed files: compare them unpacked.
- **The times in the names of the log files** are in UTC for the General Model and hair policy jobs, but in the local
  time of the job for the tracker and the other modules.

## What makes it slow

1. **Waiting for the whole turnaround and the merge.** Nothing starts before every piece is uploaded and merged; the
   upload alone takes 9.5 hours in the median. Uploading while recording and processing the pieces as they come removes
   this wait.
2. **The jobs run one after the other** — General Model, then tracker, then modules — on the whole video, and every module
   is a separate job.
3. **Nine modules compute the arrival of the aircraft themselves,** and two compute the moment the pushback is attached
   in an extra pass over the video. Each copy can differ from the others; the stage detector will be the single owner of
   these moments.
4. **The production system cannot take a live stream:** the job wrapper refuses camera streams, so the real-time branch
   is built next to it.
5. **The result files of the tracker carry no format version,** so an incompatible change shows up only as a crash of a
   module.
6. **The modules use different versions of the shared code,** which makes shared fixes slow.

## What runs where

- **At the gate (camera box):** recording and upload only.
- **Real time (being built):** the video goes to the server as it is recorded; the General Model, the tracker, the stage
  detector and the urgent checks run while the turnaround happens (*Real-time*).
- **After the turnaround:** as today, for the checks that can only be judged on the whole turnaround — the walk-around
  inspections, the conditioned air hose that is checked against the departure, and the reporting checks.

## For developers

| Part | Repository | Main code |
|---|---|---|
| Merge | `dxgat/utils/camera_software` | `merge.py`, `chunks_handling/` |
| Chunk subscriber, bucket checker, ping service, logs | `dxgat/cambox-api/*` (Cloud Run) | — |
| Video subscriber, receiver, orchestrator, Kafka | `dxgat/ml_backend/*` | `ml-backend-api`, `k8s-dockers-orchestrator`, `kafka-in-kubernetes` |
| General Model | `dxgat/detectors/general_model` | `main.py`, `scripts/new_model.py` |
| Tracker | `dxgat/utils/cv_trackers` | `tracker.py`, `local_utils/bl_utils.py` |
| Modules | `dxgat/detectors/<module>` | `main.py` |
| Job wrapper | `dxgat/utils/db_worker` | `ML_worker.py`, `model_starter.py`, `send_report.py` |
| Shared code | `dxgat/utils/cv_common` | `tracked_object.py`, `transport.py`, `detections.py` |

- Buckets: `CamboxChunks`, `prod_videos_to_process_1` (read-only), `cv-modules-topics`
  (`<video>.mp4/general_model<commit>.ndjson`, `trackers<commit>.ndjson`, gzip without a content-encoding header),
  `modules-inferences`, `cv-modules-logs` (`<video>.mp4/<job>-<start time>.logs`). Pin a test run's input with
  `general_model_inferences_version_commit` (with the extension, e.g. `a0157a4.ndjson`).
- Cluster: GKE node pool `gpu-pool`, Tesla T4, 3.3 vCPU, 8 GiB per job; `cpu-pool`, `merge-pool`, `technical-pool`.
- General Model in production: `pf/q4-02-gm-exact-speedups-a0157a4` built as `b6e1a3e` (production code a0157a4 of
  September 2025 with the October 2026 speed-ups); the branch head d4ae8e5 is not deployed. Tracker: bd43c3c with cv_common 58b1b1f; production
  starts it with `write_video=False` (the `--write_video` default in `model_starter.py` is true).
- `db_worker.ML_worker.load_source` raises "Stream is not implemented yet" for rtsp and http sources.
