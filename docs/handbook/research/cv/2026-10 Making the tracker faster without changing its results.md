# Making the tracker faster without changing its results

*26–28 October 2026 · Valentyn and Yurii Luchko (task owners); cluster test: Maksym Chernyshev · Status: tested once on
the cluster (the same tracks, 13 % less time in production); the exact comparison with fixed random numbers is still to
do; not in production*

## In short

The tracker follows the aircraft, the vehicles and the people from frame to frame. We made seven changes that cannot
change its output. On our machine, with the debug video the tracker can draw, a full 36-minute turnaround took **33.2
milliseconds per frame instead of 70.7 (−53 %)**, and the tracks and the debug video were byte-identical. But production
starts the tracker with the debug video switched off, and most of that saving was in drawing the video. On the cluster,
on five turnarounds and without the video, as in production, the new version took **346 minutes instead of 399
(−13 %)**. The tracks and every box were the same on every frame. The moments of arrival, departure and belt loaders at
doors moved by up to a few seconds, as they do between any two runs of production itself, which picks some points at
random. The last step before production is an exact comparison with the random numbers fixed in both runs. Expected
effect in production: the tracker job of a typical 87-minute video about 1.3 → 1.13 hours, about 2.5 % off the
processing bill.

## The question

A turnaround is the whole servicing of an aircraft at the gate. Words used on this page: a **frame** is one picture of
the video (the cameras take 8 per second); a **detection** is a box the General Model (the shared detector) draws around
an object; a **track** is the same object followed from frame to frame; **byte-identical** means two files are exact
copies.

After the General Model, the tracker reads its detections and the video. It follows the aircraft, the belt loaders
(vehicles with a conveyor that carries bags to the cargo door), other service vehicles (the General Model's class for
ground support equipment) and the people. Each object gets a track with a stable number; the aircraft and the vehicles
also get a motion state: moving, stopping or stopped. The tracker also marks when the aircraft arrives and departs, and
which cargo door a belt loader serves. 25 of the checks read the aircraft's track.

In production the tracker job takes about 1.3 hours for a typical 87-minute video and 19 % of all machine time of a
video. The job can also draw and upload a debug video: on every frame, the boxes, the outlines of the objects and the
points it follows. Can the tracker run faster with exactly the same output?

## What we did

1. **Measured the production tracker with and without the debug video** on a busy 2.5-minute stretch (1 200 frames).
   The tracks were identical. With the video it took 69.3 milliseconds per frame, without it 42.1 (37.3 in a rerun): the
   debug video is about 40 % of the tracker's time when it is drawn.
2. **Asked whether anyone watches the video.** It is watched (answer of 27 October), so the option stays. The work
   became: draw the same video faster, and save what can be saved without it.
3. **Found where the video's time goes.** Drawing the outlines of the objects was the largest single cost of the whole
   tracker, 38 % of its time. For every object the code built an empty full-size colour picture (1920 × 1080 pixels)
   and ran three pixel operations over all of it, although an outline covers a small part of the frame. Compressing
   (encoding) the video took about 8 %; the boxes and points under 1 %.
4. **Made seven changes**, each chosen so that the result cannot change (table below).
5. **Proved them on our machine.** We ran the production version and the new one on the same detections, with the same
   random numbers and the same colours for the points, on a machine with no other work. We compared the tracks file,
   the debug video file and every decoded frame of the video.
6. **Ran the new version on the cluster** (28 October), on the five turnarounds of the General Model test, and compared
   its files with the ones production had written for the same turnarounds a week earlier.
7. **Read the settings of the production tracker jobs** in their logs. Every production job starts the tracker with the
   debug video switched off, although the program's own default is on. The production saving is therefore the part
   that does not depend on the video.

## What we found

### The seven changes

| | What the tracker did | Change | Why the result cannot change |
|---|---|---|---|
| 1 | Drew each object's outline by building a full-size picture and processing the whole frame (38 % of its time when the video is drawn) | The same three operations, only on the small rectangle around the outline | Outside that rectangle the old way leaves every pixel as it was |
| 2 | Encoded the debug video in the main loop | Encodes it in a background thread, a second line of work that runs at the same time | The same frames in the same order; a frame is not touched after it is handed over |
| 3 | Updated the three object trackers (belt loaders, people, service vehicles) one after another | Updates them at the same time, in three threads | They share nothing; each has its own model |
| 4 | Every 2 seconds measured the image noise on the full frame, computing four layers of detail per colour and keeping one | Computes only the layer it keeps, one thread per colour | The same calculation in the same order; checked bit for bit on real frames |
| 5 | Made two full copies of every frame, plus one for a graphics-card library | No copies | The frames are only read; the reader gives a new picture every frame |
| 6 | Wrote a frame header and the belt loaders' state to the log on every frame | Behind a debug switch | Log only |
| 7 | Rebuilt the lists of ignored object types for every detection; kept confirmed people in a growing list | Built once; a fast lookup set | Only "is it in the list?" is asked |

Changes 1 and 2 matter only when the debug video is drawn; 3 to 7 always.

### The proof on our machine

| Run | Tracks | Debug video | Time per frame, production → new |
|---|---|---|---|
| Full turnaround, 36 minutes (17 280 frames) | Identical | Identical, 17 280 of 17 280 frames | 70.7 → 33.2 milliseconds (−53 %); 20.4 → 9.6 minutes in total |
| Busy 2.5-minute stretch (1 200 frames), two rounds in turn | Identical in all four runs | Identical in all four runs, 1 200 of 1 200 frames | 83.0 → 42.5 milliseconds (−49 %); the rounds: 83.0 and 83.0 → 42.7 and 42.4 |
| The first 17 minutes (8 000 frames) of turnaround 1 of the cluster test, without the debug video | Identical | not drawn | 31.5 → 21.1 milliseconds (−33 %) |

Where the time went on the full turnaround (milliseconds per frame, production → new): drawing object outlines on the
debug video 24.9 → 1.1; encoding the debug video 7.1 → beside the main work; measuring the image noise 5.9 → 1.8;
updating the three object trackers 7.7 → beside the main work; unchanged: updating each object's motion state 15.2,
following points from frame to frame 6.8, finding object outlines 4.2. The first two items are the debug video.

### The cluster test, without the debug video as in production

The new version on five turnarounds, against the files production wrote for them a week earlier. Time is the tracking
itself, from the job's start of tracking to its end; the five jobs started together both times.

| Turnaround | Tracker time, production → new | What differed in the results |
|---|---|---|
| 1 (53 minutes of video) | 30.0 → 26.3 minutes (−12 %) | the arrival 0.6 seconds earlier |
| 2 (67 minutes) | 59.8 → 48.5 minutes (−19 %) | the arrival 1.1 seconds earlier; the belt loader at the front door left 2.1 seconds earlier, and once "left" and came back within 6.5 seconds |
| 3 (83 minutes) | 100.7 → 91.6 minutes (−9 %) | the departure 0.9 seconds later; the belt loader reached the front door 4.3 seconds earlier |
| 4 (100 minutes) | 119.0 → 107.6 minutes (−10 %) | the departure 0.6 seconds earlier; three belt loader moments within 2.6 seconds |
| 5 (110 minutes) | 89.8 → 72.2 minutes (−20 %) | the departure 0.1 seconds earlier |
| **All five** | **399 → 346 minutes (−13 %)** | |

Without the video, the new version saves about the same time per frame on the cluster as on our machine (about 9
against 10 milliseconds on turnaround 1), but a cluster frame costs more than twice as much, so the share is smaller:
13 % against 33 %.

On every frame of all five turnarounds the tracks were the same — the same objects under the same numbers — and every
box was the same to the pixel. What differed are the points the tracker picks at random, and what is computed from how
those points move: the counters of stopped and moving frames, and with them the moments above.

### Production is not repeatable run to run

The shared library the tracker uses picks some things at random, without a fixed starting value for the random numbers
(a "seed"): 250 of an object's points to follow when it has more than 250 candidates; 10 points on the aircraft's nose
that tell the outline model where the aircraft is; and the colours of the points in the debug video. Two runs of
today's production therefore never give the same file. We checked it on our machine on the first 17 minutes of
turnaround 1. Two runs of the production version that differ only in their random numbers were identical for the first
8 minutes 40 seconds, and parted at the moment the tracker first uses the aircraft's nose to find its outline; then the
tracks and boxes stayed the same and the arrival came 0.25 seconds apart. The cluster's two files parted at the very
same moment, in the same fields. With the same random numbers, the production version and the new one gave
byte-identical files over all 17 minutes. The cluster test compared the new version with a file production had written
without a seed, so the two files could not be equal, and the differences above are of exactly this kind.

The change therefore adds an optional seed setting. Without it nothing changes. With it, runs are repeatable, so the old
and the new version can be compared exactly. Seeding every run by default would make production repeatable too, but it
would change which points production picks, so it is left as a separate decision.

## What it means

- **The client sees the same tracks; the moments that depend on random points move as much as they already do between
  two runs of production.** With the random numbers fixed, the new version must give identical files; that is the last
  check.
- **Expected production effect, measured on the cluster:** the tracker job about 13 % shorter, about 1.3 → 1.13 hours
  for a typical 87-minute video; the computing part of the time to result about 4.2 → 4.0 hours; about 2.5 % off the
  processing bill (the tracker is 19 % of the machine time of a video).
- **The "twice as fast" holds only where the debug video is drawn** — on our machines and in tests. Our first estimate
  for production (−50 %, about 9 % of the bill) assumed that production draws it, because that is the program's default.
  Lesson: read the settings of the production jobs before estimating a production effect.
- **The same approach as for the General Model:** prove that the outputs are exact copies, so that no accuracy test is
  needed (see *Making the General Model faster without changing its results*).
- **Real time.** Several of these changes were first proved in our real-time version of the tracker (50.6 → 39.2
  milliseconds per frame, results identical).

## What is next

1. **The exact comparison on the cluster (Maksym).** Two images on the production shared library: production plus the
   seed option, and the new version. Both with the same seed, on one or two turnarounds, on the same kind of machine.
   Expected: identical tracks files, compared after unpacking. A comparison across different machines is not exact
   either: on our machine one vehicle got 71 points to follow instead of the cluster's 72.
2. **Production**, if identical.
3. **More exact savings without the video.** The rest of the time is in following points and updating each object's
   state. Two savings proved exact in the real-time version — turning a frame grey once per frame instead of twice per
   object, and a faster test of which points lie inside a box — live in the shared library. They need its production
   version, which we cannot read yet: a copy taken from the production image would do.
4. **Decide on seeding by default.**

## For developers

- Repository `dxgat/utils/cv_trackers`, production `optimization` @ `bd43c3c`; cv_common in the production image
  **`58b1b1f`** (Maksym, 2026-10-28; not readable for us — local proofs ran on `tracker_optimization` `2759daf`). No
  access to the repository (https "not found"): local branch `pf/q4-02-tracker-exact-speedups` as patches
  `tasks/patches/cv_trackers/` (`git am` on `bd43c3c`) and a bundle.
- Commits: `7e1b867` optional `TRACKER_SEED`; `f1add44` speed-ups. Changed `tracker.py`, new `local_utils/speedups.py`
  (`draw_obj_mask_roi`, `AsyncVideoWriter`, `estimate_sigma_rgb`); no new packages. `TRACKER_VERBOSE=1` restores the
  per-frame logs. Three DeepSORT instances in threads; `confirmed_workers_ids` as a set.
- Production jobs run with `write_video=False` (Namespace line in `gs://cv-modules-logs/<video>.mp4/trackers-*.logs`:
  6 of 6 production jobs of 27–28.10 and both test runs); the argparse default in `db_worker/model_starter.py` is true.
- Cluster run: image `a6d6c53` (the branch + a font fix), files `trackersa6d6c53.ndjson` against `trackersbd43c3c.ndjson`
  (21.10) for fAkpu3dj2NIj, ytQDROiCyhBh, b8ijKDWsLlQi8W, n96M7fASlhGn, 7PytHarRNqmT; `scripts/tracker_ndjson_diff.py`,
  results `out/tracker_cluster/<video>_diff.json`. Times from "start tracker" to "tracker processed" in the job logs.
- Unseeded `np.random` in cv_common: key-point sampling `tracked_object.py:132` (> 250 key points), the airplane's
  segmenter prompt points `transport.py:79` (`_update_segm_points`), point colours at import `tracked_object.py:103`.
  Mask drawing: `TrackedObject.draw_obj_mask` (`tracked_object.py:564-573`); the tracker calls its own copy.
- Harness `scripts/tracker_exact_ab.py` via `scripts/tracker_v1_profile.py` (`--pin prod`, `--save-video`,
  `--no-video`); seeded, fixed palette. Results `out/tracker_ab/full_zHxI.json` (`zHxIAF2vUGxJ`; tracks sha256
  `853e6c89…`, video `685c1754…`), `busy_clean.json` (`DjwtQRdZyt0sSk` frames 9 000–10 200; tracks `2ce18845…`, video
  `55c0306e…`). Machine RTX 5070 Ti, 8 cores; production pod T4, 3.3 vCPU.
- Not in this change: grey frame and vectorised in-box test (cv_common `tracked_object.py:421-422`, `:262`), mask drawing
  on the box in cv_common, seeding by default. Real-time port figure (v2 stream port, 50.6 → 39.2 ms) in
  `tasks/notes/PF-Q4-02.md`.
- Notes `tasks/notes/PF-Q4-02.md` (section "Production tracker"), `PF-Q4-02-tracker-mr.md`; page
  `docs/models/trackers.md`. Task PF-Q4-02.
