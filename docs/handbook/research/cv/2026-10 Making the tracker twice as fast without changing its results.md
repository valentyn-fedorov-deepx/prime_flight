# Making the tracker twice as fast without changing its results

*26–27 October 2026 · Valentyn and Yurii Luchko (task owners); cluster test: Maksym Chernyshev · Status: ready and
proved on our machine; the cluster test is still to do; not in production*

## In short

The tracker follows the aircraft, the vehicles and the people from frame to frame. About 40 % of its time goes into a
debug video that changes no track. The video is watched, so it stays: we draw exactly the same video faster. With seven
changes, a full 36-minute turnaround (17 280 frames) took **33.2 milliseconds per frame instead of 70.7 (−53 %)**, 9.6
minutes instead of 20.4, and **the tracks and the debug video were byte-identical**. Today's production picks some points
at random, so two of its runs are never exactly alike; a new optional setting fixes the random numbers, so that the
cluster test can compare old and new exactly. That test is still to do. If it confirms our measurement, the tracker job
for a typical 87-minute video falls from about 1.3 to about 0.65 hours, and the processing bill by about 9 %.

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
video. It also draws and uploads a debug video: on every frame, the boxes, the outlines of the objects and the points it
follows. What does the tracker compute that nobody reads, and can it run faster with exactly the same output?

## What we did

1. **Measured the production tracker with and without the debug video** on a busy 2.5-minute stretch (1 200 frames).
   The tracks were identical. With the video it took 69.3 milliseconds per frame, without it 42.1 (37.3 in a rerun): the
   debug video is about 40 % of the tracker's time.
2. **Asked whether anyone watches the video.** It is watched (answer of 27 October), so it stays. The work became:
   draw the same video faster.
3. **Found where the video's time goes.** Drawing the outlines of the objects is the largest single cost of the whole
   tracker, 38 % of its time. For every object the code built an empty full-size colour picture (1920 × 1080 pixels)
   and ran three pixel operations over all of it, although an outline covers a small part of the frame. Compressing
   (encoding) the video took about 8 %; the boxes and points under 1 %.
4. **Made seven changes**, each chosen so that the result cannot change (table below). The first alone, drawing each
   outline only on the small rectangle around it, cut the drawing time by 81 % and the whole tracker by 31 % on the busy
   stretch, with tracks and video identical.
5. **Proved them.** We ran the production version and the new one on the same detections, with the same random numbers
   and the same colours for the points, on a machine with no other work. We compared the tracks file, the debug video
   file and every decoded frame of the video.

## What we found

### The seven changes

| | What the tracker did | Change | Why the result cannot change |
|---|---|---|---|
| 1 | Drew each object's outline by building a full-size picture and processing the whole frame (38 % of its time) | The same three operations, only on the small rectangle around the outline | Outside that rectangle the old way leaves every pixel as it was |
| 2 | Encoded the debug video in the main loop | Encodes it in a background thread, a second line of work that runs at the same time | The same frames in the same order; a frame is not touched after it is handed over |
| 3 | Updated the three object trackers (belt loaders, people, service vehicles) one after another | Updates them at the same time, in three threads | They share nothing; each has its own model |
| 4 | Every 2 seconds measured the image noise on the full frame, computing four layers of detail per colour and keeping one | Computes only the layer it keeps, one thread per colour | The same calculation in the same order; checked bit for bit on real frames |
| 5 | Made two full copies of every frame, plus one for a graphics-card library | No copies | The frames are only read; the reader gives a new picture every frame |
| 6 | Wrote a frame header and the belt loaders' state to the log on every frame | Behind a debug switch | Log only |
| 7 | Rebuilt the lists of ignored object types for every detection; kept confirmed people in a growing list | Built once; a fast lookup set | Only "is it in the list?" is asked |

### The proof

| Run | Tracks | Debug video | Time per frame, production → new |
|---|---|---|---|
| Full turnaround, 36 minutes (17 280 frames) | Identical | Identical, 17 280 of 17 280 frames | 70.7 → 33.2 milliseconds (−53 %); 20.4 → 9.6 minutes in total |
| Busy 2.5-minute stretch (1 200 frames), two rounds in turn | Identical in all four runs | Identical in all four runs, 1 200 of 1 200 frames | 83.0 → 42.5 milliseconds (−49 %); the rounds: 83.0 and 83.0 → 42.7 and 42.4 |

The rounds on the busy stretch repeat to within half a millisecond, so the measurement is stable.

### Where the time went on the full turnaround

| Part of the work | Production (milliseconds per frame) | New |
|---|---|---|
| Drawing object outlines on the debug video | 24.9 | 1.1 |
| Measuring the image noise | 5.9 | 1.8 |
| Encoding the debug video | 7.1 | now beside the main work |
| Updating the three object trackers | 7.7 | now beside the main work |
| Updating each object's motion state (unchanged) | 15.2 | 15.2 |
| Following points from frame to frame (unchanged) | 6.8 | 7.0 |
| Finding object outlines (unchanged) | 4.2 | 4.2 |

The encoder and the three object trackers now run beside the main work, so their time overlaps it and no longer adds to
the total. About three quarters of the saving is less work (outlines and noise), and that part carries over to the
production machine even with fewer processor cores. The rest comes from doing things at the same time, which needs spare
processor cores: our machine has 8, a production tracker job has 3.3 virtual cores. That should be enough for the parallel
parts (three tracker threads and the encoder); the cluster test will tell.

### Production is not repeatable run to run

When an object has more than 250 candidate points to follow, the shared library the tracker uses picks 250 of them at
random, without a fixed starting value for the random numbers (a "seed"). It also picks the colours of the points in the
debug video at random when the program starts. So two runs of today's production give slightly different tracks and
never the same video. In an earlier check, two production runs differed in 6 of 3 186 records (a record is one object
on one frame). Our comparison fixed the random numbers and the colours in both runs.

The change therefore adds an optional seed setting. Without it nothing changes. With it, runs are repeatable, so the
cluster test can compare old and new exactly. Seeding every run by default would make production repeatable too, but it
would change which points production picks, so it is left as a separate decision.

## What it means

- **The client will see the same verdicts, earlier.** The tracks are exact copies, so no check can decide differently.
- **Expected production effect (an estimate, to confirm on the cluster):** the tracker job falls from about 1.3 to about
  0.65 hours for a typical 87-minute video. The computing part of the time to result, already about 4.2 hours after the
  faster General Model, falls to about 3.5 hours. The tracker is 19 % of the machine time of a video, so the processing
  bill falls by about 9 %.
- **The debug video stays.** The saving comes from drawing it differently, not from dropping it.
- **The same approach as for the General Model:** prove that the outputs are exact copies, so that no accuracy test is
  needed (see *Making the General Model faster without changing its results*).
- **Real time.** Several of these changes were first proved in our real-time version of the tracker (50.6 → 39.2
  milliseconds per frame, results identical). In real time every frame has 125 milliseconds for everything; production's
  tracker takes about 112 milliseconds per frame on its graphics card machine, so halving it matters there too.

## What is next

1. **The cluster test (Maksym).** Build two images: production plus the seed option, and the new version. Run both with
   the same seed on the same five videos as the General Model test. Expected: identical tracks files (compared after
   unpacking, because the stored files are compressed) and identical debug videos, and the job taking about half the time.
   We cannot reach the tracker's repository ourselves, so the changes go to Maksym as patch files.
2. **Production**, if the test confirms.
3. **More exact savings in the shared library** (a separate change there): turning a frame grey once per frame instead of
   twice per object, a faster test of which points lie inside a box (both proved exact in the real-time version), and
   drawing outlines on the small rectangle inside the shared library's own drawing function.
4. **Decide on seeding by default.**

## For developers

- Repository `dxgat/utils/cv_trackers`, production `optimization` @ `bd43c3c` with cv_common `tracker_optimization`
  (≈ `2759daf`; the image's commit to confirm). No access to the repository (https "not found"): local branch
  `pf/q4-02-tracker-exact-speedups` as patches `tasks/patches/cv_trackers/` (`git am` on `bd43c3c`).
- Commits: `7e1b867` optional `TRACKER_SEED`; `f1add44` speed-ups. Changed `tracker.py`, new `local_utils/speedups.py`
  (`draw_obj_mask_roi`, `AsyncVideoWriter`, `estimate_sigma_rgb`); no new packages. `TRACKER_VERBOSE=1` restores the
  per-frame logs. Three DeepSORT instances in threads; `confirmed_workers_ids` as a set.
- Unseeded `np.random` in cv_common: key-point sampling `tracked_object.py:132` (> 250 key points), point colours at
  import `:103`. Mask drawing: `TrackedObject.draw_obj_mask` (`tracked_object.py:564-573`); the tracker calls its own copy.
- Harness `scripts/tracker_exact_ab.py` via `scripts/tracker_v1_profile.py` (`--pin prod`, `--save-video`,
  `--fast-mask-draw`); seeded, fixed palette, production `--write_video t` path. Results `out/tracker_ab/full_zHxI.json`
  (`zHxIAF2vUGxJ`; tracks sha256 `853e6c89…`, video `685c1754…`) and `busy_clean.json` (`DjwtQRdZyt0sSk` frames
  9 000–10 200; tracks `2ce18845…`, video `55c0306e…`). Machine RTX 5070 Ti, 8 cores; production pod T4, 3.3 vCPU.
- Not in this change: grey frame and vectorised in-box test (cv_common `tracked_object.py:421-422`, `:262`), mask drawing
  on the box in cv_common, seeding by default. Real-time port figure (v2 stream port, 50.6 → 39.2 ms) in
  `tasks/notes/PF-Q4-02.md`.
- Notes `tasks/notes/PF-Q4-02.md` (section "Production tracker"), `PF-Q4-02-tracker-mr.md`; page
  `docs/models/trackers.md`. Task PF-Q4-02.
