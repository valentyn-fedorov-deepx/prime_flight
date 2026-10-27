# Making the General Model faster without changing its results

*8–22 October 2026 · Valentyn and Yurii Luchko (task owners); cluster test and production build: Maksym Chernyshev ·
Status: done, the faster version runs in production since October 2026*

## In short

The General Model, the shared detector that runs first on every turnaround video, did a lot of work whose results
nobody used. We removed that work and proved that every output stays byte-identical: the new files are exact copies of
the old ones, so no verdict can change. Production turned out to run an older build than the newest code on its branch,
so we moved the change onto that exact build before the cluster test. On five production videos the General Model jobs
took **589 minutes instead of 799 (−26 %)**, and every General Model file was identical. For a typical 87-minute video,
the time from the merged video to the results falls from 4.8 to about 4.2 hours (**−13 %**), and processing costs
**about 10–13 % less** per hour of video. The job log is about five times shorter.

## The question

A turnaround is the whole servicing of an aircraft at the gate. Two cameras record it: the cone camera (looks towards
the aircraft nose) and the wing camera (looks along the wing). Each camera's video then goes through three jobs in a row
on the cloud computers (the cluster): the General Model, the tracker, then the checks.

Words used on this page: a **frame** is one picture of the video (the cameras take 8 per second); a **detection** is a
box the detector draws around an object; a **verdict** is Pass, Fail or Not observed; **byte-identical** means two files
are exact copies.

The General Model draws detections on every frame (the aircraft and its parts, people, vehicles, cones, chocks) and
decides the camera, the aircraft type and the airline. It reads the video twice. The first pass runs the detectors and
follows the aircraft. The second pass picks the main aircraft, marks vehicles that block the view, writes the file the
tracker and the checks read, and works out the arrival.

A General Model job took about 2.4 hours for a typical 87-minute video, the longest single job. Does it compute things
nobody uses, and can that work go with every output exactly the same, so that no verdict can change?

## What we did

1. **Measured where the time goes**, step by step, on a 6-minute part of a turnaround and on a full 36-minute turnaround
   (17 280 frames).
2. **Followed every result** to see who reads it: the tracker, the checks, the website, or nobody.
3. **Removed the unused work in two changes.** The first skips work whose results are never used. The second makes one
   extra pass over the video optional; it is separate because it switches a computation off.
4. **Proved it on our machine**: old and new side by side, with the same random numbers, comparing the files of both
   passes, the report, the annotated video frame by frame and a video-selection report.
5. **Moved it onto the production build** (below). Maksym tested it on five production videos: the production image on
   21 October, the new image on 22 October, each time with the five jobs started together. The stored files are
   compressed with the file time written into them, so we compared them after unpacking.

### Production runs an older build than the branch head

We first put the changes on the newest code of the production branch (December 2025) and pushed them on 9 October. On
one test video, production's files and our branch's agreed on 99.95 % of the detections but were not exact copies. On
21 October Maksym confirmed why: production runs the image built from the code of 4 September 2025, on an older software
stack (older programming language version, base image and shared library). The newest code is the same General Model
on a newer stack and was never deployed. The 99.95 % compared two stacks, not two versions of our code.

A proof on the branch head would only prove the change on a stack production does not run. So we moved the same two
changes onto the production code; they applied cleanly, and we checked that the code is valid for the older language
version. Maksym built it as the production image with only the changed files swapped, plus three small image fixes (library versions and a font file).
Our own proof had used a newer shared library than production's, which we cannot read, so the cluster run was the real
proof.

## What we found

### What the General Model computed that nobody used

| What the old version did | Who used the result | What changed |
|---|---|---|
| First pass, every frame: analysed the motion of every aircraft it followed (up to 250 points followed from frame to frame, the aircraft's outline cut out about once a second by a small model, moves and stops counted) | Nobody: afterwards only each aircraft's box was read; the second pass works out the main aircraft's motion again from scratch | Only the box check is kept |
| First pass: computed visual features of every followed object | Nobody: the comparison that would use them never runs | Not computed |
| Second pass: copied every frame onto the graphics card in high-precision numbers | Nobody: the second pass reads the first pass's detections | Removed |
| Loaded the retired airline detector | Nobody: its calls were switched off when the airline classifier replaced it | Not loaded |
| Downloaded generic starting weights for the camera classifier from the internet | Nobody: our trained weights replace every value | Not downloaded |
| Converted every frame to high-precision numbers on the processor and sent 24 megabytes to the graphics card | — | Sends the original 6 megabytes and converts on the graphics card: the same values |
| Copied the full frame before each detector; prepared the same frame twice for two detectors of the same input size | — | No copy; one prepared frame per input size |
| Moved detection values from the graphics card one at a time, waiting for each | — | One copy per detector |
| Wrote about eleven log lines per frame | Log storage only | Behind a debug switch; per-video summaries stay |
| When some filters passed, decoded the whole video a third time to look for camera movement | Nobody: the result went only to a text file on the job's temporary machine | Optional, off by default |

### The proof

| Test | Where | Result |
|---|---|---|
| 6-minute part (approach, arrival, aircraft standing) | Our machine | Every output byte-identical |
| Full 36-minute turnaround, three times (once as old, new, old, new in turn) | Our machine | Every output byte-identical, the same fingerprints in every run |
| Five production videos, production image against the new image | Cluster, 22 October | Every General Model file byte-identical |

### Speed

On our machine the full turnaround took 1 494 seconds with the old version and 1 210 with the new one (−19 %). A second
pair gave −28 %, but the machine had less other work during that new run, so we quote 17–19 %: about −30 % in the first
pass and −5 % in the second. The third pass did not run on this video.

On the cluster:

| Video | Before (minutes) | After (minutes) | Change |
|---|---|---|---|
| 1 | 92.8 | 75.6 | −18.5 % |
| 2 | 131.7 | 99.6 | −24.4 % |
| 3 | 170.9 | 114.8 | −32.8 % |
| 4 | 196.0 | 143.7 | −26.7 % |
| 5 | 208.0 | 155.1 | −25.4 % |
| **Total** | **799.3** | **588.7** | **−26.3 %** |

The same machines now process 1.36 times as many videos. We had estimated −18 to −21 % on videos without the third pass
and about −32 % where it would have run; the results fall in that range. Whether the third pass would have run on each
of the five videos is not known.

### Effect on the whole processing and on the cost

For the median of 148 production videos (10–22 September 2026, about 87 minutes long):

| | Before | After |
|---|---|---|
| General Model job | 2.4 hours | 1.76 hours |
| From the merged video to the results | 4.8 hours | 4.16 hours (−13 %) |
| From the end of recording to the results | 16.8 hours | 16.16 hours (−4 %) |

Most of the wait comes before any processing (the video upload and the merge), so the whole wait shrinks less (see *How
long a turnaround takes to process and what it costs*). On four of the five test videos (those with the logs of all
checks), the time from the start of the General Model to the end of the slowest check fell by 15 % (5.3 to 4.5 hours per
video), and the machine time of all jobs by 9 %.

Cost per hour of video, at list prices:

| Turnaround | Before (dollars) | After (dollars) | Cheaper by |
|---|---|---|---|
| Jet, cone camera only | 1.84 | 1.60 | 12.9 % |
| Jet, both cameras | 3.86 | 3.40 | 12.0 % |
| Aircraft, cone camera only | 2.66 | 2.40 | 10.0 % |
| Aircraft, both cameras | 4.59 | 4.05 | 11.7 % |

The General Model sorts each aircraft into "aircraft" or "jet" by where its engines sit against the wing; fewer checks
run for jets. The cost falls more than the machine time because the General Model runs on machines with a graphics
card, which cost about four times as much per hour as machines with a processor only.

### The job log

The General Model's own log lines went from 212 145 per 36-minute video to 55, but the whole log is not 55 lines: the
shared library's video reader still writes one line per frame in each pass, and the code that follows the main
aircraft's motion still writes on every frame. The log is about five times shorter: about 444 000 lines before and
89 000 after on one 53-minute video.

## What it means

- **The client sees the same verdicts, sooner and cheaper**: about 40 minutes earlier for the median video and 10–13 %
  less per hour of video.
- **Two report fields still vary, as before.** The arrival moment and the confidence of the camera type in the General
  Model's report already differ between two runs of production itself, because the shared library picks motion points
  at random. To compare versions, compare the detection files, not these fields.
- **A byte-identical change needs no accuracy test.** This matters because the monthly test (the client's validated
  turnarounds we measure on) still compares against an old General Model version (see *Which General Model version the
  monthly test compares against*).

## What is next

These change the numbers slightly, so each needs the verdict test on the monthly test before production:

- A graphics-card setting that made the detectors 2.6 times slower on our newer card: check it before any change of card
  or base image (for example the move to Azure).
- A faster runtime that prepares the three detectors for the graphics card; classifying the camera on several frames at
  once.
- Teaching the main detector the vehicle class, so that the separate vehicle detector (the largest network, about half
  of the detection time) can go: the largest single saving left. It needs a training run and the verdict test on the six
  checks that read vehicles.

Two more savings would keep the outputs exact: reusing the first pass's noise measurements (about 2 %) and skipping an
unused resizing step in the video reader (about 3.5 %, in the shared library). The annotated video, written by default,
costs about 12 milliseconds per frame of the second pass plus its upload; whether anyone watches it is to confirm.

## For developers

- Repository `dxgat/detectors/general_model`. Production: `pf/q4-02-gm-exact-speedups-a0157a4` built as `b6e1a3e` (code
  `8d8c9a4` + image commits `727a474`, `bb9c0f2`, `b6e1a3e`: onnxruntime-gpu 1.16.3, pins, font). Code commits on
  `a0157a4` (`deployment_v_py3_10`, 2025-09-04; Python 3.8, `gpu_base:legacy_base`, cv_common `d74eb09`, not readable
  to us): `2259608` (skip unused work), `8d8c9a4` (camera-motion pass opt-in). The same diff on the undeployed head `d4ae8e5` (Python 3.10, cv_common `ac5098d`):
  `pf/q4-02-gm-exact-speedups` (`fe243c1`, `3bd356e`, head `afaebf1`). Patches `tasks/patches/gm-exact-speedups/`.
- Switches `GM_VERBOSE=1`, `video_selection.check_camera_motion: true` (in `local_config.yaml`).
- Harness `scripts/gm_prod_profile.py`; logs `out/gm_prod/`. Full event `zHxIAF2vUGxJ`. Cluster videos in table order:
  `fAkpu3dj2NIj`, `ytQDROiCyhBh`, `b8ijKDWsLlQi8W`, `n96M7fASlhGn`, `7PytHarRNqmT` (sha256 after gunzip). Fields that
  vary run to run: `frame_stopped`, `confidence_camera`. Costs: `G:\fullturn_processing_cost.xlsx`.
- Not in the change: `cudnn_conv_algo_search=DEFAULT` (`main.py:41`, RTX 5070 Ti, cuDNN 9.19), TensorRT heads (ADR-003),
  camera-classifier batching, the `vehicle` head (YOLOv8m) folded into the GM head.
- Notes `tasks/notes/PF-Q4-02.md`, `PF-Q4-02-gm-mr.md`, `PF-Q2-16.md`; page `docs/models/general_model.md`. Tasks
  PF-Q4-02, PF-Q2-16.
