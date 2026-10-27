# Edge onboarding

> Welcome to Edge. We make every gate record and upload its video, and we find out what can run on the device itself.

## 1. What you will work on

The CameraBox software (recording, chunks, upload), device health and the CamBox Pro rollout with the PrimeFlight IT team,
and what the device can run besides recording (battery, compute, Hair Policy on the device). Owners: the *Edge team*
page.

## 2. How it works, for Edge

- A CameraBox records two cameras (cone and wing) in 1-minute chunks: 1080p, 8 frames per second, H.264, about 4 Mbit/s
  per camera.
- The chunks go to the `CamboxChunks` bucket; `cambox-bucket-checker` starts the merge after the turnaround. A ping service
  keeps every box's connection data in MongoDB, a log service stores the box logs.
- Today the median wait from the last chunk filmed to the bucket is 9.5 hours — more than half of the time to result.
  Uploading during recording (Q1) needs at least 8 Mbit/s of uplink for two cameras.
- Real time, being built: the real-time worker takes every one-minute file from the bucket as soon as it is uploaded,
  so the upload while recording is what makes real time possible.

Details: *2 System / Architecture / Edge*.

## 3. Read, in this order

1. *2 System / System overview* (20 min).
2. *2 System / Architecture / Edge*.
3. *2 System / Architecture / Real-time* — the ingest part.
4. *2 System / Architecture / Post-processing* — the upload and merge part.
5. *2 System / Modules / HP Hair policy* — the module meant to run on the device.

## 4. Where things are

| What | Where |
|---|---|
| CameraBox software, merge | GitLab `dxgat/utils/camera_software` |
| Services around the box | `dxgat/cambox-api/*` (log handler, ping service, bucket checker) |
| Chunks and logs | the `CamboxChunks` bucket, GCP log storage |
| Box status | MongoDB (ping records); the availability chart on the website |

## 5. Rules for Edge

The rules everyone follows are in *Start here*. In Edge in particular:

- Changes that affect cameras, upload or accounts: a heads-up to the PrimeFlight IT team first.
- The state of every box is kept in the deployment tracking.

## 6. Your first two weeks

Week 1:

- [ ] Accounts: GitLab, GCP `rampvision-2` (buckets and logs), access to a test CameraBox, Jira, Slack.
- [ ] Read the list above.
- [ ] Find one box's chunks for one turnaround in the bucket, its logs and its ping record.

Week 2:

- [ ] The first task from Jira with Vladyslav.
- [ ] Meet the PrimeFlight IT contact; read the CamBox Pro rollout states.

## 7. Whom to ask

| About | Ask |
|---|---|
| The device and its software | Vladyslav Ivashchuk |
| Devices and network at the stations | the hardware engineer; the PrimeFlight IT team |
| Upload into the buckets, real-time ingest | Maksym Chernyshev (MLOps) |
| Priorities | Valentyn Fedorov |
