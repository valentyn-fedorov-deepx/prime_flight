# System overview

> RampVision checks the safety checklist of every aircraft turnaround from two cameras at the gate and gives Pass, Fail
> or Not observed for 30 checks of the client. This page says what the system does, how it works, and the state of every
> part. The numbers marked as coming from the monthly test are filled in automatically.

## What the system does

At the gate two cameras film every turnaround — the time an aircraft spends at the gate between arrival and departure.
The **cone camera** looks towards the nose of the aircraft, the **wing camera** along the wing. The ground crew has a
safety checklist: chocks at the wheels, cones around the aircraft, a lead marshaller and wing walkers when the aircraft
moves, handrails on the vehicles, fastened safety vests, a clear path for the pushback, and more. RampVision watches the
videos and gives every check of the client one of three verdicts:

- **Pass** — the rule was followed;
- **Fail** — the rule was broken;
- **Not observed** — the moment did not happen in the video, or the view was blocked by a vehicle or an object.

The client sees the verdicts with the video timeline on the RampVision website.

## How it works today

Everything runs after the turnaround:

1. **At the gate.** A camera box records both cameras in one-minute pieces (8 pictures — frames — per second) and uploads
   them.
2. **Merge.** After the turnaround the pieces are joined into one video per camera.
3. **The General Model** — the shared detector — goes through every frame and draws a box around every object it knows:
   the aircraft and its parts, people, belt loaders, service vehicles, cones, chocks. It also tells which camera this is,
   whether the aircraft is a regular aircraft or a small jet, and the airline.
4. **The tracker** follows the objects from frame to frame, gives each one a number that stays the same, says whether it
   is moving or standing, and finds when the aircraft arrived and left.
5. **The modules** — the code of the checks, one job each — read what the General Model and the tracker found (some also
   look at the pictures and run their own small models) and apply each check's rule.
6. **Results.** The verdicts go to the database and to the website.

## The parts and their state (October 2026)

| Part | What runs in production | State and next step | Who | Read |
|---|---|---|---|---|
| Camera box and upload | one-minute pieces of video, uploaded after the turnaround | upload while recording | Edge, MLOps | Architecture / Edge |
| Merge and jobs | Google Cloud, one graphics card per job: merge, then the General Model, the tracker and one job per module | moving to Microsoft Azure | MLOps | Architecture / Post-processing |
| General Model | the version of October 2026 | 26 % faster since October with the same results; next: fold the separate vehicle detector into it | CV | Shared parts / General Model |
| Tracker | the version of February 2026 | a faster version with the same tracks took 13 % less time in its first cluster run; the exact comparison is next | CV | Shared parts / Tracker |
| Checks | the client's 31 checks: 27 modules give 29 of them, one job each (one module gives three); one check is combined from two others; one (seat belts) gets no verdict | {{ACCURACY_RANGE}} correct by check on the monthly test; the differences from the client's rules are on each page | CV | Modules index |
| Stage detector | — | being built for the real-time branch | CV | Shared parts / Stage detector |
| Real-time branch | — | the worker runs; the stage detector and the checks inside it are still placeholders | MLOps, CV | Architecture / Real-time |
| Results, alerts, website | the database and the RampVision website | alerts being built | Backend | Teams / Backend |

## Time from filming to the result

The median of 148 videos of 10–22 September 2026 (about 87 minutes long), with the October version of the General Model:

| Step | Hours |
|---|---|
| From the last piece filmed until it is in the cloud | 9.5 |
| Merge: waiting and running | 2.5 |
| General Model | 1.8 |
| Tracker | 1.3 |
| Checks (they run at the same time; the slowest) | 0.9 |
| Waiting between the jobs | 0.2 |
| **From recording to the result** | **16.2** |

Computing costs 1.6 to 4.05 dollars per hour of video, depending on one or two cameras and on the aircraft type. The
General Model takes about a quarter of the computing time of a turnaround, the tracker a fifth, the checks together about
half.

## Accuracy

{{ACCURACY_TEXT}}

## Where it is going

The video will be uploaded while it is recorded. A stage detector will know where in the turnaround we are. With it, a
real-time branch will run the urgent checks while the turnaround happens, so that a violation can become an alert within
seconds; the other checks will still run after the turnaround, in about 5–6 hours instead of a day.

## The parts of the production system

| Part | What it does |
|---|---|
| Camera box | records the two cameras in one-minute pieces and uploads them |
| Upload checker | checks the uploaded pieces and starts the merge |
| Merge | joins the pieces of a turnaround into one video per camera |
| Message bus | carries the messages between the parts |
| Receiver | reacts to every message, writes the database and decides the next job |
| Job scheduler | starts the jobs on the cluster of graphics cards |
| General Model | finds the objects, the camera, the aircraft type and the airline |
| Tracker | follows the objects and finds the arrival and departure of the aircraft |
| Modules | one job per module: the verdicts of its checks |
| Results streamer | sends the timelines of the checks to the website |
| Website | the RampVision website: turnarounds, verdicts, videos |

## Words you will hear

| Word | Meaning |
|---|---|
| Turnaround | the time an aircraft is at the gate, from arrival to departure |
| Cone camera, wing camera | the two cameras at a gate: towards the nose, and along the wing |
| Frame | one picture of the video; the cameras take 8 per second |
| Stage | a part of the turnaround: before arrival, arrival, after the aircraft stops, unloading and loading, before departure, departure |
| Belt loader | the vehicle with a conveyor belt that loads bags into the hold |
| Service vehicle | any vehicle working at the aircraft: tugs, belt loaders, fuel trucks, tractors, air conditioning units |
| Chock, cone | a wedge at a wheel so that it cannot roll; a safety cone around the aircraft |
| Lead marshaller, wing walker | the person who guides the arriving aircraft; the person who walks at the wing tip when the aircraft moves |
| Pushback | the tug that pushes the aircraft back from the gate |
| Verdict | Pass, Fail or Not observed |
| General Model | the shared detector |
| Tracker | the part that follows objects from frame to frame |
| Module | the code of one or more checks |
| Stage detector | the part that knows where in the turnaround we are (being built) |
| After the turnaround, real time | how everything runs today; while it happens (being built) |
| Monthly test | the turnarounds the client checked by hand; every change is measured on them |
