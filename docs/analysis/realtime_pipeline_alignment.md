# The realtime-pipeline worker and our measurements: what matches, what re-partitions, what is new

`gitlab.com/dxgat/detectors/realtime-pipeline` (main @ 8cd6e62, "initial realtime pipeline") is the architecture the real-time
branch is built on from now on. This is what it contains, what of it is already ours, how the numbers of
`rt_module_cost.md` / `rt_environment.md` / `rt_optimisation_plan.md` map onto it, and the one cost in it that nobody has
measured yet. Read `ARCHITECTURE.md` in that repo first: it is the contract, not a description.

## The worker

One deployment that stays up (not started per arrival), its containers sharing localhost and **one** time-sliced GPU. In call
order: **ingest** (30-frame chunks, decode, no GPU) → **stage detector** (the general detections, the plane track, belt-loader
arrival and leave, camera type, airplane type, entity) → **general model** (only what the stage detector does not do: chocks,
vehicle, obstacle, side obstacle) → **trackers** (person, belt loader, GSE; the plane track is *copied*, never tracked again)
→ **modules** (a verdict only: task, pass / fail / not observed, time).

Each container is its own image. The hand-off is a JSON POST to the next container's `/frames` (`chain.py`), the frame record
is `frame_record.py` (`frame_id`, `capture_t`, `detections`, `plane_track`, `stage`, `airplane_type`, `camera_type`,
`entity`, `events`, `chocks`, `vehicles`, `obstacles`, `tracks`, `verdict`), and the clock is the camera's:
`capture_t = videoStartTime + (pts - first_pts)`. A chunk is 30 frames = one GOP = 3.75 s, pushed by the cambox straight to
the ingest, no bucket. Modules are dummy today; the stage detector is a dummy with the checked ground truth of one turn; the
general model and the trackers are real.

## What of it is already ours

Verified file by file (only the import paths differ, `pf.gm` → `general_model`, `pf.tracker` → `trackers`):

| their file | ours | difference |
|---|---|---|
| `general_model/heads.py`, `geometry.py` | `pf/gm/…` | none |
| `general_model/onnx_detector.py`, `rows.py`, `compat_writer.py` | `pf/gm/…` | the import lines only |
| `trackers/stream.py`, `fast_paths.py`, `fast_grouped_lk.py`, `fast_sigma.py`, `_v1/*` | `pf/tracker/…` | the import lines only |

So **every measurement of the campaign applies to that worker directly**, and anything we land in `pf/gm` or `pf/tracker`
(TensorRT, the segmentors, the DeepSORT batching) is the same change there. The copy is also the risk: two trees of the same
code drift. Worth agreeing with Maksym whether the worker consumes `pf/gm` + `pf/tracker` as a package (pip or submodule)
instead of carrying a copy.

## How our budget re-partitions across their containers

Our 125 ms per frame are the same work, cut differently. From the measured tables (this card, card kept busy):

| their container | what it runs | from our measurements |
|---|---|---|
| ingest | decode | 2.9 ms |
| stage detector | the `gm` head + the plane track + camera / type / entity | head 8.5 ms (TensorRT ≈ 4–5); the aircraft path of the tracker 4.0 ms |
| general model | chocks + vehicle heads, obstacle labelling | 19.2 − 8.5 = **10.7 ms** for the two heads (a difference of measured head sets, not a direct measurement); the labelling itself 0.1 ms |
| trackers | person + belt loader + GSE, no plane | **22.8 ms** measured for exactly that class set (26.2 with the plane) |
| modules | the verdict | under 3.3 ms each for 17 of the 20 that run live; the three pixel modules are 5–19 ms |

Sum of the shared part: ≈ 45 ms of the 125, which is our 52 ms minus the aircraft tracking the trackers no longer repeat.

## What their split fixes, and it is the important one

Dropping the plane from the trackers and copying the stage detector's track removes the double aircraft tracking — and with
it the blocker of `rt_module_cost.md` section 7: today the branch decides *which aircraft is ours* from the causal rows
("the longest track so far"), and that costs **2.9 points of accuracy** on about one event in six (36 module verdicts
changed, T_arr moved by up to 23 minutes). No box rule fixed it; the fix belongs to whoever owns the turnaround, which in
this architecture is the stage detector. The worker puts it exactly there. What the stage detector then has to carry is what
my measurements say the problem needs: anchors that can be re-armed when a new aircraft arrives after a departure, and the
stand geometry to tell our aircraft from a neighbour.

## The one cost nobody has measured: the hand-off

`chain.py` moves pixels as **base64 JPEG inside the JSON body**, and every consumer decodes them again
(`images_from_jpeg`). Measured here on a 1080p frame of a real event:

| step | per frame | per 30-frame chunk |
|---|---|---|
| JPEG encode (q=62) + base64 at the ingest | 2.7 ms | 0.08 s |
| base64 + JPEG decode in a consumer | 3.6 ms | 0.11 s |
| `json.dumps` / `json.loads` of the body | — | 5 ms / 4 ms |
| the body itself | 151 KB | **4.5 MB** |

Three consumers decode the pixels (stage detector, general model, trackers), so the pixel hand-off costs about
**13.5 ms per frame on this machine** — and a pod core is roughly 0.6 of one of these, so **about 22 ms per frame on the
production CPU**, 11–18 % of the whole budget, all of it on the four slow threads the pod has. For comparison, our own
hand-off to twenty module processes through shared memory measured 5–7 ms per frame.

The containers of one pod share the node and can share a memory-backed volume (`emptyDir: medium: Memory`) or a POSIX shared
memory segment, so the raw frame could be written once and read by reference, which is what `pf/rt/module_host.py` does
inside one process tree. This is the first thing I would measure and change in the worker: it is pure overhead, it is on the
scarcest resource, and it needs no model work.

## The latency floor

A 30-frame chunk means a frame waits up to 3.75 s before its chunk is even complete. Our verdict latencies (0.75–1.7 s after
the frame the verdict refers to) were measured with **per-frame** ingest. In the worker the floor is the chunk: 3.75 s +
processing. That is still "minutes" by the roadmap's own definition, but an alert on a safety-zone breach is a different
promise at 4 s than at 1 s. If the cambox can push frames as they are encoded instead of per GOP, the floor drops; that is a
cambox question, not a worker one.

## What we bring to it next

1. **The real modules instead of the dummies.** `pf/rt/prod_module.py` runs an unchanged production module against live
   metadata (its `detect()` in its own thread, a video worker that blocks until the frame arrives, the session-end marker).
   Their modules container is the natural home for it: one module per container, as `ARCHITECTURE.md` already says.
2. **The declarations** (`pf/rt/declarations.json`): which GM classes and tracked classes each module actually reads,
   corrected against the checkouts the test set runs. That is what lets the worker hand a module only its rows — and what
   `module_rules.json` would otherwise have to re-derive by hand.
3. **TensorRT for the heads.** Their `general_model/load.py` builds the heads through the CUDA provider. The same heads
   through TensorRT measured 19.2 → 11.1 ms for three (`rt_optimisation_plan.md`); for their two heads the saving is
   proportional, and on a T4 it is the difference between keeping up and not.
4. **The measurement harness.** Cost per module, verdict parity against batch, the test set with scoped inputs, live
   accuracy: all of it reads GM rows and tracker records, which the worker produces in the same format.

## Questions for Maksym

1. Does the worker consume `pf/gm` + `pf/tracker` as a package, or keep the copy? (Two trees of one tracker will drift, and
   the optimisation work is about to touch both.)
2. The pixel hand-off: is the JPEG-in-JSON deliberate for the first version, or open to a shared memory volume? The number
   above is the cost.
3. Which three modules are "the three real modules" of `ARCHITECTURE.md`? If they are the trio we already run live
   (3-stop, pushback pathway, pushback wing walkers), we can bring them with their declarations and their parity results.
4. The stage detector is the dummy today. When it becomes real, does it own the re-armable anchors and the stand geometry
   (the accuracy blocker above), or should that be a separate component?
5. Chunk size: 30 frames is the alert-latency floor. Is per-frame push from the cambox on the table?

## First steps from our side

1. Run their chain locally (five processes on localhost, our weights, one of our events) and measure each container's
   milliseconds and the hop — the same way `scripts/rt_resource_fit.py` measures ours. One day.
2. Replace a dummy module with a real one through `pf/rt/prod_module.py` and compare the verdict with the batch run of the
   same event. That is the first end-to-end proof on their architecture.
3. Close the TensorRT gate (`rt_optimisation_plan.md` step 1) and hand the result over: it applies to their general model
   container unchanged.
