# Real time — the branch being built

> The real-time branch gives the urgent checks while the turnaround happens, instead of a day later. One worker runs all
> the time on one graphics card: it takes every minute of video as soon as the camera box has uploaded it, finds where in
> the turnaround we are, runs the checks and writes their verdicts — and a Fail on an urgent check becomes an alert while
> the aircraft is still at the gate. It is being built: the worker runs end to end, with stand-ins for the parts that are
> not ready.

## What runs

One worker stays up all the time; it does not start when an aircraft arrives. It is one deployment whose containers share
one graphics card, each taking a slice of it. In the order they are called:

1. **Ingest.** The camera box uploads every one-minute video file to the cloud bucket while it is still recording. As
   soon as a file arrives, the ingest downloads it and decodes it into frames. It has no model and no graphics card.
2. **Stage detector.** Finds the objects of the turnaround, follows the aircraft, notices belt loaders arriving at and
   leaving the cargo doors, and finds the camera type, the aircraft type, the airline, the arrival and the departure. It
   owns the turnaround: the arrival is its start, the departure its end. See *Shared parts / Stage detector*.
3. **General Model.** Only what the stage detector does not do: chocks, vehicles, and the objects that block the view.
4. **Tracker.** Follows people, the front and back belt loaders and the service vehicles. It takes the aircraft's track
   from the stage detector instead of following the aircraft again.
5. **Checks.** Each check is its own container. It gives a verdict only: the check, Pass / Fail / Not observed, and the
   time of the frame. It does not send alerts or write to the database.
6. **Exit.** Writes everything out: the file of boxes for every minute, the picture of the frame of an alert, and the
   messages to the receiver that updates the turnaround on the website. It is the only container that talks to the rest
   of the system.

## When things run

- The checks of the time before arrival run on every minute; they keep a verdict until the turnaround exists, then the
  exit sends it.
- Every other check stays off until the stage of the turnaround and the aircraft type are known, and stays off on a
  camera that is not in its camera list.
- With no aircraft at the gate the stage detector still finds objects, chocks still run, people are followed when there
  are people; following the aircraft, the vehicles, the belt loaders and the service vehicles waits for an aircraft.
- When the aircraft arrives, the last 10 minutes before the arrival are already processed: their results are kept, and
  the checks do not run on them again.

## The clock and the minutes

- The clock is the camera's own time, not the server's. Times sent to the website are in UTC, to the whole second.
- One minute of video has about 450 to 460 frames; the number may vary.
- If the connection drops, the camera box does not upload the minutes it missed and goes on with the newest one. The
  worker notes the missing minutes on the turnaround, keeps following the objects on the next minute that arrives, and
  never invents the missing minute. A missing minute that arrives later is processed, but does not reopen a turnaround
  that has ended.

## The turnaround

- The stored window is 10 minutes before the arrival to 6 minutes after the departure.
- After the departure the worker processes 6 more minutes, writes them, and reports that the turnaround ended.
- If the departure never comes and the recording stops, the turnaround is closed with the last minute processed.

## What is stored for every minute

1. **The minute of video**, as the camera box uploaded it; nothing is drawn into it.
2. **The file of boxes** of that minute: for every frame the time, what was found, the aircraft track, the stage, the
   camera and aircraft type, the airline, the events, the chocks, the vehicles, the blocking objects, the tracks and the
   verdicts — in the format the website already reads.
3. **The alert picture**, only for an alert: one picture of the frame, with nothing drawn on it.

## Verdicts and alerts

- A verdict is Pass, Fail or Not observed at a moment of the camera's clock.
- **An alert** is a Fail of a check that is marked as alerting in the list of checks, while the turnaround is still open.
  The exit saves the picture of that frame and puts its location on the message; the receiver stores it on the check's
  row of the turnaround. That stored row with its picture is the whole alert.
- Pass and Not observed write the row without a picture; so does a Fail of a check that does not alert, a Fail after the
  turnaround ended, and a second Fail of the same check in the same turnaround.

## The two cameras of a gate

- One gate, one turnaround, one record — the two cameras join it when they belong to the same airport and gate and
  their arrivals are within 15 minutes.
- The aircraft type of the cone camera is the type of the turnaround; a wing camera that disagrees takes the cone's type.
- A second camera of the same kind, or the same camera box again, opens its own turnaround.

## State (October 2026)

| Part | State |
|---|---|
| Worker, ingest, exit | running |
| General Model, tracker | the real ones, scoped as above |
| Stage detector | a stand-in, checked against one labelled turnaround (arrival at 9 minutes 39 seconds, departure at 1 hour 12 minutes 41 seconds); the real one replaces it |
| Checks | stand-ins that log one simulated verdict per check; the first three real checks come as their own containers |
| The backbone is finished when | a recorded full turnaround runs through the real stage detector, General Model, tracker and three checks; one turnaround record exists; the minutes and box files are stored; the verdicts are on that record; an alerting Fail is stored with its frame |

How fast it can be: a prototype of the same chain (one camera: decoding, the General Model, the tracker and three real
checks) needed 73 milliseconds per frame of the 125 available at 8 frames per second. Because the video now arrives in
one-minute files, a frame can wait up to about a minute before it is processed; the upload while recording sets that
delay, not the computing (*Research / CV / A real-time prototype on one graphics card*).

## Rules of this worker

- The worker's architecture file is the contract; it changes only when the architecture owner decides so.
- Every container has its own image and its own packages.
- The production video buckets are read-only; the files of boxes and the alert pictures go to the test bucket.

## For developers

- Repository `dxgat/detectors/realtime-pipeline`, `ARCHITECTURE.md` of 2026-10-06 (commit 7f10615, "real time backbone");
  the local clone in the Prime Flight workspace is at the 2026-10-01 version (8cd6e62, 30-frame pushes from the camera
  box) and is one commit behind.
- Messages to the receiver: `sender_id` `bucket_sub` (turn started and ended), `general_model`, `trackers`, `cv_module`
  (one per decision), all with `metadata.realtime` true so that the receiver does not start the after-the-turnaround jobs.
- Box files: `{eventId}/{camera}/vid_{index:06d}.json`; alert pictures `{eventId}/{camera}/{task}/{capture_t}.jpg`, in
  the test inferences bucket.
