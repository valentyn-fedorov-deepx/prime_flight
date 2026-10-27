# MLOps onboarding

> Welcome to MLOps. We make the video get from the camera to the result reliably, quickly and at a sensible cost: the
> running pipeline, the clusters, the images, and the real-time worker.

## 1. What you will work on

The running pipeline (receiver, orchestrator, subscribers, merge), Google Kubernetes Engine clusters and node pools,
Kafka, images and CI/CD, the move to Azure, and the architecture of the real-time worker. Owners: the *MLOps team* page.

## 2. How it works, for MLOps

Post-processing, today:

1. The CameraBox uploads 1-minute chunks to `CamboxChunks`; `cambox-bucket-checker` checks them and starts the merge job
   (`merge-pool`), which writes one video per camera to `Videos-to-process`.
2. The upload event goes through Pub/Sub and the video subscriber to **Kafka**. The **receiver** (`ml-backend-api`) reacts
   to every message, writes MongoDB and decides the next job; the **orchestrator** queues it on the cluster.
3. Jobs on `gpu-pool` (one Tesla T4, 3.3 vCPU, 8 GiB per job): General Model → trackers → one job per module. Outputs go
   to `cv-modules-topics` and `modules-inferences`, logs to `cv-modules-logs`; results to MongoDB and the website.

Real time, being built: one worker that stays up, its containers sharing one time-sliced GPU — ingest → stage detector →
General Model → trackers → modules → exit. The ingest takes every one-minute file from the bucket as soon as the camera
box has uploaded it; the exit writes the box files, the alert pictures and the messages to the receiver.

Details: *2 System / Architecture* (all three pages).

## 3. Read, in this order

1. *2 System / System overview* (20 min).
2. *2 System / Architecture / Post-processing* — including *Production jobs, versions and files*.
3. *2 System / Architecture / Real-time* and the worker's `ARCHITECTURE.md`.
4. *2 System / Architecture / Edge*.
5. The *At a glance* tables of *General Model* and *Tracker* (what each job needs and produces).

## 4. Where things are

| What | Where |
|---|---|
| Receiver, orchestrator, subscribers, Kafka | GitLab `dxgat/ml_backend/*` |
| Merge | `dxgat/utils/camera_software` |
| Real-time worker | `dxgat/detectors/realtime-pipeline` |
| CI | `dxgat/detectors/ci_configuration` |
| Cloud | GCP project `rampvision-2`: GKE (`gpu-pool`, `cpu-pool`, `merge-pool`, `technical-pool`), Pub/Sub, buckets; Azure (move in progress) |
| Base images | `us-central1-docker.pkg.dev/rampvision-2/new-base/gpu_base` |
| Processing time and cost | *System overview*; the cost workbook (archive package) |

## 5. Rules for MLOps

The rules everyone follows are in *Start here*. In MLOps in particular:

- `prod_videos_to_process_1` and `camboxes_raw_videos` are read-only. Never upload there.
- An output file is named after the commit inside the image (`general_model<commit>.ndjson`, `trackers<commit>.ndjson`):
  a test image must carry its own commit, or it overwrites production's files. For test runs set
  `general_model_inferences_version_commit`.
- Compare outputs after gunzip, not by the bucket checksum (the gzip header holds the file time).
- Job log names: UTC for the General Model and Hair Policy, the container's local time for the others.
- The real-time worker changes only as its `ARCHITECTURE.md` says.

## 6. Your first two weeks

Week 1:

- [ ] Accounts: GCP `rampvision-2` with GKE access, GitLab, Jira, Slack; Azure when it is ready.
- [ ] Read the list above.
- [ ] Follow one turnaround through the pipeline: its chunks, the merged video, the job logs, the outputs, its MongoDB
  documents.

Week 2:

- [ ] The first task from Jira with Maksym.
- [ ] Run one job (General Model or a module) on one video in the dev environment with a test commit.

## 7. Whom to ask

| About | Ask |
|---|---|
| Clusters, jobs, images, the real-time worker | Maksym Chernyshev |
| General Model and tracker images | Yurii Luchko (CV) |
| MongoDB and the website side | Aryan Singh (Backend) |
| The CameraBox and upload | Vladyslav Ivashchuk (Edge) |
| Priorities | Valentyn Fedorov |
