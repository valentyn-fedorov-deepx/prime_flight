# CV onboarding

> Welcome to the computer-vision team. This page tells you what we build, how it works, what to read first, where
> everything is, the rules we keep, and what to do in your first two weeks.

## 1. What we build

At an airport gate two cameras film every turnaround — the time an aircraft spends at the gate between arrival and
departure. The **cone camera** looks towards the nose of the aircraft; the **wing camera** looks along the wing.
RampVision watches these videos and checks the ground crew's safety checklist: are the wheels chocked, are the cones in
place, do the wing walkers walk along the wings during the pushback, do people use the handrails, are the safety vests
fastened, and more — **30 checks of the client**, written as 27 modules (a module is the code of one or more checks).

For every check and every turnaround the result — the **verdict** — is one of:

- **Pass** — the rule was followed;
- **Fail** — the rule was broken;
- **Not observed** — the moment did not happen in the video, or the view was blocked by a vehicle or an object.

The client, PrimeFlight, sees the verdicts on the RampVision website. The rule of every check is written and agreed with
the client: *System / Requirements / Client rules*. That rule is our contract.

## 2. How it works

Today everything runs **after the turnaround**:

1. **Recording.** A camera box at the gate records both cameras in one-minute pieces (8 pictures — frames — per second)
   and uploads them.
2. **Merge.** After the turnaround the pieces are joined into one video per camera.
3. **The General Model** — our shared detector — goes through every frame and draws a box around every object it knows:
   the aircraft and its parts (nose, wings, engines, doors, wheels), people, belt loaders, service vehicles (tugs,
   fuel trucks, tractors), cones, chocks. It also tells which camera this is, whether the aircraft is a regular aircraft
   or a small jet, and which airline it belongs to.
4. **The tracker** follows these objects from frame to frame and gives each one a number that stays the same. It also
   says whether each object is moving or standing still, and when the aircraft arrived and when it left.
5. **The modules** — one job per module — read what the General Model and the tracker found. Some also look at the
   pictures themselves and run their own small models (for example a pose model, which finds a person's shoulders,
   elbows and wrists). Each module applies its check's rule to the right part of the turnaround and gives the verdict,
   one sentence for the client, and a timeline.
6. **Results.** The verdicts are stored in the database and appear on the website.

From filming to the result takes about 16 hours today (half of it is the upload). The computing part takes about
4 hours: the General Model about 1.8 hours, the tracker 1.3 hours, the slowest module about 1 hour (the modules run at
the same time).

**What is changing.** The video will be uploaded while it is being recorded. A **stage detector** will know where in the
turnaround we are (the aircraft stopped, a belt loader reached a cargo door, the pushback was attached). With it, a
**real-time branch** will run the urgent checks while the turnaround happens, on one graphics card, so that a Fail can
become an alert within seconds.

## 3. Read, in this order

1. *System / System overview* — the whole system, its state, the words you will hear (20 minutes).
2. *System / Requirements / Client rules* — the rules of the checks you will work on.
3. *System / Shared parts / General Model*, then *Tracker*, then *Stage detector* and *Pose models*.
4. *System / Modules* — first the *Modules index* (all checks with their accuracy), then the pages of your checks.
5. *System / Architecture / Post-processing* and *Real-time* — how the jobs run.
6. *Research / CV* — what we measured recently; start with the reports about your area.
7. *Teams / CV / How-to* — the everyday tasks, step by step.

## 4. Where things are

| What | Where |
|---|---|
| Code of the General Model | GitLab, group `dxgat`, repository `detectors/general_model` |
| Code of the checks | GitLab `dxgat/detectors/<module>` — one repository per module; the page of each check says which branch runs in production |
| Code of the tracker and the shared code | `dxgat/utils/cv_trackers`, `dxgat/utils/cv_common` |
| How a job reads its inputs and writes its results | `dxgat/utils/db_worker` |
| The real-time worker | `dxgat/detectors/realtime-pipeline` — its file `ARCHITECTURE.md` is the contract of the worker |
| Model weights | DVC — a tool that keeps large files in a cloud bucket: `dvc pull` inside a repository downloads them |
| What the General Model and the tracker found in a video | the bucket `cv-modules-topics`, one compressed file per video and version |
| Logs of the jobs | the bucket `cv-modules-logs` |
| The videos | the video buckets of the Google Cloud project `rampvision-2` — production buckets are **read-only** |
| Accuracy of every check | *Modules index* (from the monthly test report) |

## 5. Rules we keep

The rules of the whole team are in *Start here*. In the CV team in particular:

1. **The client's rule is the contract.** What Pass, Fail and Not observed mean for a check changes only with the
   client's agreement, through the lead.
2. **A speed-up must give exactly the same results** — the same output files, byte for byte, and the same debug video
   frame for frame. We prove it before we ask for an image (*How-to / How to prove that a change keeps the same results*).
3. **A change of logic or of a model is measured** on the monthly test, including the turnarounds labelled Fail, before
   it goes to production (*How-to / How to measure a change on the monthly test*).
4. **Production changes go through a merge request**, an image built by the MLOps team, and a run on a few videos next
   to production.
5. **No weights, videos or output files in git.** Videos show people at work: they stay inside the project's buckets.
6. **Code, commits and documents are written in English.**
7. **When you change something that is documented, update its page in the same task.**

## 6. Your first two weeks

Week 1:

- [ ] Ask the team lead for access: GitLab (group `dxgat`), the Google Cloud project `rampvision-2` (read access to the
  buckets), DVC, Jira, Slack.
- [ ] Read the list in section 3.
- [ ] Run one check on one turnaround on your computer (*How-to / How to run a check on one turnaround on your
  computer*).
- [ ] Meet the owner of the part you will work on (*CV team*).

Week 2:

- [ ] Take your first task from Jira with the team lead.
- [ ] Open the monthly test results of your checks in the *Modules index* and watch one turnaround the client labelled
  Fail for each of them.
- [ ] Take part in the monthly review: update the *Status* block of one page.

## 7. Words you will hear

| Word | Meaning |
|---|---|
| Turnaround | the time an aircraft is at the gate, from arrival to departure |
| Frame | one picture of the video; the cameras take 8 per second |
| Detection | a box the General Model draws around an object, with its type and how sure it is |
| Track | the same object followed from frame to frame, with a number that stays the same |
| Stage | a part of the turnaround: before arrival, arrival, after the aircraft stops, unloading and loading, before departure, departure |
| Verdict | Pass, Fail or Not observed |
| Belt loader | the vehicle with a conveyor belt that loads bags into the aircraft hold |
| Service vehicle | any vehicle working at the aircraft: tugs, belt loaders, fuel trucks, tractors, air conditioning units |
| Chock | a wedge put against a wheel so that it cannot roll |
| Wing walker | a person who walks next to the wing tip when the aircraft moves, to watch for obstacles |
| Pushback | the tug that pushes the aircraft back from the gate |
| Lead marshaller | the person who guides the arriving aircraft to its stop |
| Monthly test | the turnarounds the client checked by hand; every change is measured on them |
| Post-processing, real time | after the turnaround (today); while it happens (being built) |

## 8. Whom to ask

| About | Ask |
|---|---|
| Priorities, speed and cost, this documentation | Valentyn Fedorov |
| The General Model, the tracker, the stage detector | Yurii Luchko |
| Hair policy, the structure of the checks | Vladyslav Ivashchuk |
| Images, tests on the cluster, the real-time worker | Maksym Chernyshev (MLOps) |
| Accuracy, the client's labels | Oksana |
| Datasets | Denys Filimonov (Data) |
