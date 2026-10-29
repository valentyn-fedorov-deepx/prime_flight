# Safety huddle conducted at huddle cone

*In plain words: safety huddle at the huddle cone.*

> Before the aircraft arrives, the crew must gather for a short safety briefing (a huddle) at the green huddle cone. The
> module finds green cones by their colour in the cone camera's pictures and counts the people standing next to each
> one until the aircraft stops.

## Status

| | |
|---|---|
| How accurate it is | 63 of 68 turnarounds correct (93 %) on the monthly test |
| Fail turnarounds it caught | 51 of 52 |
| In production | the version of August 2026 |
| Who looks after it | to assign |
| Biggest open problem | The green test is not the client's colour-and-size check, and Pass and Not observed judge the pre-arrival stage by different rules. |

## What the client wants

*Safety huddle conducted at huddle cone*

| Verdict | When |
|---|---|
| Pass | No aircraft is seen, and at least 3 people are seen near one green cone for 15 seconds. |
| Fail | No huddle is seen. |
| Not observed | The video has no pre-arrival stage, or the aircraft has not arrived. |
| Not observed, view blocked | The view is blocked during more than 50 % of the pre-arrival stage. |

The client adds that the cone is confirmed by its colour, checked in the Lab colour space (a standard way to describe a
colour as lightness plus a green–red and a blue–yellow value), and by its size. A verdict is the answer of a check:
Pass, Fail or Not observed. The pre-arrival stage is the part (stage) of the turnaround before the aircraft arrives.

## When and where it looks

The module reads from the first frame of the video (one picture; the cameras take 8 per second) to the frame on which
the tracker (the part that follows objects from frame to frame) reports that the aircraft has stopped, once it has stood
still for more than 4 seconds. It looks for the huddle up to that frame, then runs 60 seconds more only to count blocked
frames. It runs on the cone camera (which looks towards the aircraft nose), for aircraft and jets, without checking which
camera filmed the video.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object): cones, to find the
  huddle cone; belt loaders, pushback tugs, trailers, fuel trucks and other service vehicles (ground support equipment:
  tugs, belt loaders, fuel trucks, tractors), to tell when the view is blocked.
- **From the tracker:** the aircraft track (a track is the same object followed from frame to frame), the one with the
  largest box, and its stop; the person tracks, to see who stands near a cone.
- **From the video itself:** yes, the colours inside every cone box.
- **Own models:** none; the green test is a colour rule, and a small tracker of its own follows the cones. It runs on
  an ordinary processor.

## How it decides, step by step

1. Reads the boxes, the person tracks and the aircraft track frame by frame; follows the aircraft with the largest box.
2. Counts a frame as blocked when a belt loader, service vehicle, pushback tug, trailer or fuel truck box is larger than
   600 × 400 pixels (the picture is 1,920 × 1,080) with its centre in the left 75 % of the picture. The frame is still
   used.
3. For every cone it reads the picture and keeps the cone only if its box is more than 1.2 times taller than wide and
   its lower middle part is greenish: for each pixel there it computes (green − red) ÷ (red + green + blue), and the
   middle value (median) must be above 0, so green outweighs red.
4. Follows the green cones from frame to frame. A cone counts after more than about 2.5 seconds of detections, and is
   dropped when it is not seen for 15 seconds while no person hides it.
5. Around each cone it builds a huddle area: 3 cone heights to each side, and about 5 metres in front of and behind the
   cone, worked out from the cone's height in the picture (assuming a 1-metre cone and a camera 1.5 metres high). A
   person is in the area when the bottom edge of their box touches it.
6. A frame with at least 3 people in the area (or 2, when a third seems hidden behind another person) adds to that
   cone's huddle counter; 10 seconds without that resets it. More than 15 seconds: huddle found at that cone.
7. The huddle search stops when the tracker reports the stop; 60 seconds later the module ends.
8. **Pass** if a huddle was found and the stop came more than 60 seconds into the video. Otherwise **Not observed** if
   blocked frames are more than 50 % of all frames read, if the shared arrival check saw no pre-arrival stage (the
   aircraft box grew 18 % or less, or the aircraft first appeared within 11.25 seconds), or if the aircraft did not
   stop; otherwise **Fail**.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Huddle length | more than 15 seconds (3 people, or 2 plus 1 hidden) | Shorter: no huddle |
| Gap reset | 10 seconds | A longer gap restarts the count |
| Cone confirmed | more than about 2.5 seconds of detections | Drops brief false cones |
| Cone lost | unseen for 15 seconds, not hidden by a person | The cone is dropped |
| Cone shape | height more than 1.2 × width | Drops square or lying boxes |
| Green test | median (green − red) ÷ (red + green + blue) above 0; top 50 %, bottom 5 % and 30 % per side left out | Which cones are green |
| Huddle area | 3 cone heights to each side; 5 metres in front and behind; 1-metre cone, camera 1.5 metres high | Who stands at the cone |
| Blocking box | larger than 600 × 400 pixels, centre in the left 75 % | Which frames are blocked |
| Blocked share | 50 % of all frames read | More: Not observed |
| Earliest stop for Pass | 60 seconds into the video | Earlier: no Pass |
| Arrival check | box growth more than 18 %; first sighting 11.25 seconds or later | Pre-arrival filmed |

All values are written in the code; the settings file holds only the task name.

## What it reports

- **Sentence.** Pass: "Huddle detected at cone <number> by workers [<numbers>]" with the time span. Fail: the cones
  where a group broke up too early ("Not enough workers were present near the huddle cone …"), or "Safety huddle is not
  detected near any cones during pre-arrival!". Not observed: "There is an obstacle!", "No pre-arrival stage is detected
  on video!" or "Airplane has not arrived on video!".
- **Timeline entry:** one Pass or Fail block from the start of the video to the stop; none for Not observed.
- **Files:** a drawing file with person tracks, green cones, huddle areas, blocking objects and status texts; an
  annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 68 labelled for this check. The
module matched the client on 63 (93 %). The client labelled 52 of them Fail and the module caught 51, so 1 of its 5
errors is a missed violation; the other 4 are turnarounds labelled Pass or Not observed where it said something else.
Most labelled turnarounds are Fails, so the test does show that it catches missing huddles; our sources do not say which
turnarounds it got wrong.

## Known problems

- **Not the client's cone test.** The client asks for a Lab colour check and a size check. Since August 2026 the code
  uses the green-minus-red middle value and a shape test, with no minimum size, so any greenish cone box passes, however
  small. What this changes in the verdicts: to confirm.
- **Two pre-arrival rules.** Pass uses the old rule (stop more than 60 seconds into the video); Not observed uses the
  shared arrival check. They can disagree: a huddle with a stop in the first 60 seconds can end as Fail.
- **A fragile stop test.** The 60-second test is made only on the exact frame number of the stop, which breaks if frame
  numbers and positions in the video differ; then a real huddle gets no Pass.
- **Aircraft in view.** The rule asks for the huddle while no aircraft is seen; the module also counts huddles while the
  aircraft approaches, until the stop, so such a huddle still gives Pass.
- **Blocked count.** The blocked share includes the 60 seconds after the stop, so it is not the rule's share of the
  pre-arrival stage; blocked frames still count for the huddle.
- **Assumed sizes.** The huddle area relies on assumed heights, not camera calibration. The shared arrival check is
  meant to need 90 seconds before the aircraft appears but waits 11.25.
- **Untidy branch (to confirm).** Old build files that name missing files, an unused tracking folder and an outdated
  description; how production builds it is to confirm. It uses a part of the shared library its pinned version lacks.

## In real time

It can run as it is: one pass, in order, with the pictures read for the colour test. It decides 60 seconds after the
stop, which the tracker gives today and the stage detector (the part that knows where in the turnaround we are) will give
in real time.

On a 36-minute test turnaround in the real-time test setup, it matched post-processing (after the turnaround) in verdict
and sentence; the verdict came 60 seconds after the stop. Own work: 0.87 milliseconds per frame; with the shared General
Model (main detector plus vehicle part) and tracker, 22.9 of the 125 milliseconds each frame may take (18 %). As a
post-processing job: about 22 seconds. A planned saving with identical results: no picture reading after the stop. In
the live test runs its verdict never changed. The client's split puts this check in the post-processing group.

## For developers

- **Module code:** M18. **Repository:** `dxgat/detectors/pre-arrival-safety-huddle`; production `green_cone_median` @
  `a1210c5` (2026-08-04). `master` @ `9b61d2e` (2025-06-19) split from it in 2023: HSV hue test for green, own arrival
  block, no arrival detector.
- **Entry point:** `main.py` → `detect(source, output_path, device, video_worker, write_video, weights_dir, cone_camera,
  json_logger)`; class `Cone` (per-cone huddle state); `is_valid()` / `rg_chromaticity_median()` (green test);
  `calculate_vertical_roi_size()` (area depth); cones tracked with norfair.
- **Run:** `python main.py --source <video>.mp4 --inferences-dir <dir> [--write-video] [--json-fn <name>]`; reads
  `general_model<video>.ndjson`, `trackers<video>.ndjson`. Production: `db_worker/model_starter.py` calls `detect()`.
- **Keys:** `local_config.yaml` holds only `task: huddle`. Code: `Cone.huddle_threshold` 15 s (> 120 frames), gap reset
  > 80 frames, `Cone.missing_threshold` 15 s, cone `hit_counter > 20`, shape > 1.2, `crop_bbox(0.5, 0.05, 0.3)`, area
  ±3 h and `calculate_vertical_roi_size(Hc_m=1.5, Ho_m=1, L_m=5.0)`, blocker 600 × 400 px with centre < 0.75 W, blocked
  share 0.5, Pass pre-arrival `arrival_frame > 60 * fps`. Arrival detector: `area_change_thr` 0.18,
  `prearrival_min_frames` 90 (frames).
- **Code places:** step 1 `main.py:345-355, 393-406`; 2 `:365-382`; 3 `:202-241, 384-390`; 4 `:450-474, 77-91, 506`;
  5 `:251-272, 476-500`; 6 `:93-140, 509-514`; 7 `:436-448`; 8 `:408-412, 545-585`.
- **Dependencies:** pins `cv_common` ac5098d, `db_worker` 5a4aa83 (`master`: acfc080, 6efc0b0); export adds
  `cv_common/modules` 2759daf; no weights. Branch: `python:3.7` Dockerfile, entry `huddle_deepsort.py` (absent), no
  `requirements_docker_developpment.txt`, unused `deep_sort_pytorch/`, old `README.md`. Logic diagram: `.doc/Safety
  Huddle.svg`; Confluence, 2023-07-10.
