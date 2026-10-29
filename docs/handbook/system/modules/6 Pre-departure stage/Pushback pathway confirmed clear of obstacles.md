# Pushback pathway confirmed clear of obstacles

*In plain words: pushback path clear of obstacles.*

> When the aircraft is pushed back, nothing may stand in its way. In the cone camera's pictures the module builds a
> region behind the aircraft's tail and gives Fail when a small vehicle, a cone, a chock or a ladder lies inside it while
> the aircraft moves.

## Status

| | |
|---|---|
| How accurate it is | 61 of 68 turnarounds correct (90 %) on the monthly test |
| Fail turnarounds it caught | 0 of 3 |
| In production | the version of January 2026 |
| Who looks after it | to assign |
| Biggest open problem | It caught none of the known violations: 0 of the 3 Fail turnarounds of the monthly test and 0 of 4 in our own measurement. |

## What the client wants

*Pushback pathway confirmed clear of obstacles*

| Verdict | When |
|---|---|
| Pass | No service vehicle, trailer, fuel truck, belt loader, person, cone or chock is on the pushback path during the departure stage. |
| Fail | Any of these is on the pushback path during the departure stage. |
| Not observed | There is no departure stage, or no aircraft tail, or no aircraft in the video. |
| Not observed, view blocked | Something blocked the view for more than 30 seconds during the departure stage (and the 60 seconds before it). |

A verdict is the answer of a check: Pass, Fail or Not observed; a stage is a part of the turnaround; a frame is one
picture of the video (8 per second). Service vehicles are ground support equipment: tugs, belt loaders, fuel trucks,
tractors.

## When and where it looks

The check covers the stages before departure and the departure with pushback. The module looks at the frames where the
aircraft moves after its arrival, up to 15 seconds after the tracker's departure moment; a crossing counts only from 15
seconds before to 15 seconds after that moment. The tracker sets its arrival
moment after about 4 seconds of standing still and its departure moment after about 10 seconds of movement. The module
uses the cone camera (which looks towards the aircraft nose), for aircraft and jets; the code does not check the camera.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object on a frame): the
  aircraft tail and nose and pushback tugs; belt loaders, service vehicles, fuel trucks and trailers; cones, chocks and
  ladders.
- **From the tracker:** the aircraft track (the aircraft followed from frame to frame) with its moving or stopped status
  and the tracker's arrival and departure moments.
- **From the video itself:** nothing; pictures are read only to draw an annotated video.
- **Own models:** none (a model that followed the tug was removed in January 2026), so a processor is enough.

## How it decides, step by step

1. **Frames and aircraft.** Frames where the General Model found nothing are skipped. On the others the module follows
   the last aircraft track listed.
2. **Path region.** After arrival it keeps the latest tail and nose boxes and builds the region: as tall as the aircraft
   box, as wide as the tail box, and extended beyond the tail, away from the nose, by half the nose-to-tail distance (at
   most 250 pixels).
3. **Sorting.** Cones, chocks and ladders are path objects only below a size limit (for example a chock under 25 × 5
   pixels). Belt loaders, service vehicles, fuel trucks and trailers bigger than 800 × 600 pixels, or lower in the
   picture than the aircraft, the region and the tug, block the view; smaller ones below their size limit are path
   objects; sizes in between are ignored. A blocking box holding more than 80 % of a tug box is the tug itself and is
   dropped.
4. **Checked frames.** A frame is checked when the aircraft has arrived, the tracker reports it moving, a tug has been
   seen at least once (at any earlier time) and the region exists. The module stops 15 seconds after the departure
   moment.
5. **Crossing.** A blocking box covering more than 10 % of the region makes the frame blocked; it is counted and
   skipped. Otherwise a path object with more than 50 % of its box inside the region makes the result Fail. Only the
   first crossing of the video is kept (object and time).
6. **Enough frames.** No aircraft: **Not observed**. Fewer than 56 checked frames (7 seconds): **Not observed** ("no
   departure stage" or "not enough frames").
7. **Fail window.** A Fail stays only if the kept crossing lies in the last 30 seconds of the check (15 seconds before
   to 15 seconds after the departure moment); otherwise the verdict becomes **Pass**.
8. **Blocked view.** If the verdict is not Fail and more than 240 blocked frames (30 seconds) fall in the last 60
   seconds of the check: **Not observed** (view blocked).

## Settings that change the result

All values are fixed in the code; the settings file holds only the check's name.

| Setting | Value | What it changes |
|---|---|---|
| Check after the departure moment | 15 seconds | End of the check |
| Region extension | half the nose-to-tail distance, at most 250 pixels | Width of the path |
| Size limits (width × height, pixels) | chock 25 × 5, cone 15 × 40, ladder 70 × 200, belt loader 200 × 70, service vehicle 150 × 100, fuel truck 250 × 150, trailer 150 × 130 | Only smaller boxes are path objects |
| Big vehicle | over 800 × 600 pixels | View blocker |
| Blocker overlap | over 10 % of the region | Frame blocked |
| Object overlap | over 50 % of the object's box | Fail |
| Minimum checked frames | 7 seconds | Fewer: Not observed |
| Fail window | last 30 seconds of the check | Earlier crossings dropped |
| Blocked limit | over 30 seconds within the last 60 seconds | Not observed |

## What it reports

- **Sentence.** Pass: "There is no transport on the pushback pathway on the departure stage. (<time> - <time>)", the
  window starting at most 45 seconds before the end of the check. Fail: "<object> crossed the pushback pathway.
  (<time>)". Not observed: "There is no plane on the video", "There is no departure stage on the video", "There are not
  enough inference frames were captured during departure stage." or "There was an obstacle on the video". A "tail not
  detected" sentence exists in the code but is never reached: without a tail no frame is checked.
- **Timeline entry:** one block with the verdict, start and end for Pass and Fail; none for Not observed.
- **Files:** per-frame drawings, and an annotated video if switched on.

## How accurate it is

The monthly test (the client's validated turnarounds we measure on) has 69 turnarounds; 68 were labelled for this check
and the module matched 61 (90 %). It caught none of the 3 labelled Fail: the high number comes from passing clean
turnarounds and says nothing about catching obstacles. Our own earlier measurement agrees: 0 of 4 known violations
caught, its 85 % "accuracy" coming from clean videos only. The module's own notes on the missed cases name a region that
is too narrow, missed departures and an ignored big obstacle.

## Known problems

- **Only the first crossing is kept.** If it lies more than 15 seconds before the departure moment (for example after a
  false "moving" status), it is dropped at the end and the verdict flips to Pass, even if objects crossed later. Likely
  part of the low catch rate (to confirm).
- **People are not checked**, although the client lists them; ladders are checked, although the client does not.
- **Size limits too small (to confirm on data).** A chock must be under 25 × 5 pixels, so chocks practically never count.
- **"Moving" is the aircraft's status.** The tug's own movement is not checked; a tug seen once at any earlier time is
  enough.
- **Tail needed.** Without a tail there is no region. When the tail appears right of the nose, the code narrows the
  region instead of widening it.
- **Last aircraft, not largest.** It follows the last aircraft track listed on each frame, so another aircraft can be
  mixed in.
- **No departure moment, no trimming.** Without the tracker's departure moment, crossings and blocked frames from the
  whole video count.
- **Old description.** The module's description still explains the removed tug model, whose files are no longer used.

## In real time

The client puts this check in the "real-time" group: the result is wanted within seconds. It can run as it is: one pass,
no pictures, deciding 15 seconds after the tracker's departure moment; the stage detector (the part that knows where in
the turnaround we are) would start it when the last belt loader leaves. In the real-time test setup it gave the
post-processing (after the turnaround) verdict 20 seconds after the departure moment; the report's time window moved
slightly because that test's tracker followed only this module's objects (with the full tracker it was identical). On 68
test turnarounds the reduced real-time inputs gave the same verdicts. Cost with the General Model and the tracker: 23.1
of the 125 milliseconds a frame may take (18 %); own work 0.48 milliseconds alone, 1.6 with all checks; as a
post-processing job, 16 seconds per turnaround. In live runs, on 2 turnarounds where another aircraft was in view first,
its Pass became Not observed: a problem of the shared live feed.

By its type it suits real time well, as any crossing gives Fail at once; but its crossing detection does not work yet,
and, like the other checks where seconds matter, it decides after the fact. Warning before the aircraft meets an
obstacle needs a change of when the check decides, to agree with the client.

## For developers

- **Module code:** M21. **Repository:** `dxgat/detectors/pushback-pathway-confirmed-clear-of-obstacles`; production
  `master` @ `104db85` (2026-01-22), the default branch.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, weights_dir, json_logger,
  cone_camera)`; `Plane` (tail, nose, region), `smallEnough` (size filter); `scripts/` holds the monthly evaluation
  notebook, labels and `problems.txt`.
- **Run:** `python main.py --source <video>.mp4 --inferences-dir <dir> [--write-video] [--json-fn <name>]`;
  `run_module.py` runs a test list.
- **Keys:** none (`local_config.yaml` holds only `task`). In code: `Plane._check_after_departure` `15 * 8`,
  `filter_dict`, `min(x_diff, 250)`, 800 × 600, 0.1, 0.5, `7 * fps`, `30 * fps`, `45 * fps`, `60 * fps`; unreachable
  tail reason `:522-524`.
- **Code places:** step 1 `main.py:294-295, 319-332`; 2 `:117-150, 344-346`; 3 `:196-198, 252-260, 297-317, 348-368,
  415-420`; 4 `:81, 168-187, 427-429, 504-505`; 5 `:432-482` (first crossing `:479-482`); 6 `:513-524`; 7 `:526-532`; 8
  `:550-557`.
- **Dependencies:** `cv_common` dd5b554 (local folder: ac5098d), `db_worker` 5a4aa83; norfair 0.3.1, OpenCV; GPU base
  image; DVC `gs://cv_weights/DVC` holds one unused 40.7 MB MobileSAM file (`mobile-sam` unused too).
