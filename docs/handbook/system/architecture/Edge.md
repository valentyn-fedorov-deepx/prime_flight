# Edge — the camera box at the gate

> At the gate a CameraBox records two cameras and uploads the video. Today the upload is the largest part of the time to
> result; the real-time branch will take the video straight from the box.

## Recording

- Two cameras per gate: the **cone camera** (towards the nose) and the **wing camera** (along the wing).
- 1-minute chunks, 1080p, 8 frames per second, H.264, about 4 Mbit/s per camera.
- A ping service checks that every CameraBox is alive and writes it to MongoDB; a log service keeps the box logs.

## Upload today

The chunks go to the `CamboxChunks` bucket. After the turnaround a subscriber collects the chunk list and the merge job
builds one video per camera. In September 2026 the median wait from the last chunk filmed to its arrival in the bucket was
**9.5 hours** — more than half of the time to result.

## Upload during recording (Q1)

Uploading over Wi-Fi or SIM while the CameraBox is still recording removes most of that wait. Two cameras need at least
8 Mbit/s of uplink to keep up.

## Video for the real-time branch

The real-time worker takes the same one-minute files from the bucket as soon as each one is uploaded; the camera box
does not connect to the worker. Uploading every minute while recording is therefore what makes real time possible: a
frame waits at most about a minute plus the upload. If the connection drops, the box does not upload the minutes it
missed and goes on with the newest one; the worker notes the gap. See *Real-time*.

## Services around the CameraBox

| Service | What it does |
|---|---|
| cambox-log-handler | writes the CameraBox logs to GCP log storage |
| cambox-ping-service | keeps the connection data of every CameraBox current in the database |
| cambox-bucket-checker | checks the uploaded chunks and starts the merge jobs |
| cambox-chart-updater | the data behind the CameraBox availability chart on the website |
| weekly-stats-updater | weekly statistics per CameraBox, sent by e-mail |

## The device itself

What the CameraBox can run besides recording (battery, compute, Hair Policy on the device) is being measured; the battery
test moved to November 2026.

## CamBox Pro rollout

New CamBox Pro units are received, checked and shipped to the stations by the PrimeFlight IT team. The deployment
tracking uses these states: on portal · functional · online but no turnaround data · needs monitoring or diagnostics ·
not yet on portal (merged manually) · needs repair · no raw video · under maintenance · lost.
