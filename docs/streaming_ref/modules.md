_English translation of `G:/gat-streaming/docs/modules.md` (Ukrainian original), 2026-09-14._

# Modules: classification and what to do with them

## Criterion

Formal, verifiable by reading the code in ten minutes, requires no
arguments about "gut feeling".

**Axis 1 — causality.** How many times the module reads the metadata, and whether the
decision at frame N relies on something that will happen after N.

**Axis 2 — pixels.** Whether the module needs decoded frames, or detections
and tracks are enough.

| module | checks | passes | causal | pixels |
|---|---|---|---|---|
| `aircraft-chocks` | Main gear chocks removed<br>Nose wheel chock removed | **2** | no | **yes** |
| `beltloader-chocks` | BL forward chock | 1 | yes | no |
| `pushback-pathway-confirmed-clear-of-obstacles` | Pushback pathway | 1 | yes | no |

Three of the four checks are structurally causal and stream without edits.
The two problematic ones live in one repository.

---

## aircraft-chocks

### What is wrong

`load_metadata()` is called twice — lines 1222 and 1291. The first pass
walks the whole video to find **a single value**:

```python
if aircraft.departured or frame_number == video_worker.number_of_frames:
    needed = [p for p in list(pushback_window)[:pushback_window.maxlen//2] if p]
    if len(needed) > config['fps']:
        median_pushback = np.median(needed, axis=0)
    break
```

`median_pushback` — where the pushback stood at the moment the aircraft departed. Then the stream
is rewound, and the second pass already knows this answer in advance:

```python
if not pushback_attached_frame:
    if median_pushback is not None:
        if p_box is not None and bboxes_iou(p_box, median_pushback) > 0.8:
            pushback_frames += 1
    elif nose_xyxy:                      # ← causal branch, never executed
        ...
```

That is, the decision "pushback attached" at frame N is made with knowledge of what
will happen half an hour later.

### The good news

All of the non-causality boils down to **a single variable**, and for it their own
code **already has a causal branch** — `elif nose_xyxy` checks the geometry relative
to the aircraft nose in the current frame. It simply never fires, because the first
branch always has a value.

### The streaming variant

`main_stream.py` — three hunks:

1. The first pass is not executed (`_STREAM_SKIP`), `median_pushback` stays
   `None`, the module takes the causal branch.
2. The same accumulation of the pushback series, but online, in a single pass.
3. The median is computed at report time — by then the future has already become the past.

The third change is deliberately pedantic: in the first pass the record is appended **after**
the departure check, so at the stop frame the series contains frames up to `T−1`. If this were
not reproduced, the window would shift by one frame, and the difference between the modes would
no longer be clean.

### What it cost

| check | discrepancies on 8 videos |
|---|---|
| Main gear chocks removed | **0** |
| Nose wheel chock removed | 2 |

Both Nose wheel discrepancies are the consequence of one mechanism: **the causal branch
catches the attachment earlier**, because the non-causal one waits until the pushback settles in its
final place (IoU > 0.8 with the median), while the causal one fires as soon as it
has approached the nose.

| video | batch | stream | shift |
|---|---|---|---|
| 0wW3jgdtn1d1 | 01:16:42 | 01:16:42 | match |
| LFaccZVJAl6G | 00:48:21 | 00:48:21 | match |
| 1WBBTx2wApOn | 00:27:46 | 00:27:39 | −7 s |
| F9jIwLEhmU7E | 00:36:34 | 00:36:10 | −24 s |
| sAHYpFpM01Dg | 00:44:05 | 00:42:17 | −108 s |
| e0w9l4LmMDI7 | 01:01:50 | 00:54:26 | −444 s |

**All shifts go in one direction.** This is systematic, not noise, so it can be removed:
the causal branch should additionally require that the pushback **has stopped moving** —
a stationary box for a few seconds. This brings "attached" closer to "parked"
without knowledge of the future.

### Why pixels are needed

```python
diff_result = rear_wheels[wheel_name].update_difference(
    img_to_draw, dataset.get_im0s(frame_number), diff_classifier, device, ...)
```

The call is unconditional. The frame-difference algorithm with the effnetb0 classifier reads
the image every frame for each rear wheel. So these two checks must
live where decoded frames exist — the metadata bus alone is not enough for them.

---

## beltloader-chocks and pushback-pathway

One pass, state accumulated frame by frame, verdict at the end:

```python
for frame_number, frame_metadata in enumerate(metadata, 1):
    ...                                   # accumulation
status, report, smart = make_inference(beltloaders_dict)
```

This is a causal structure — the verdict simply appears when the event has finished.
Needs no edits.

`dataset` is never used after `load_source()`, so they
can be run without an mp4 (`--no-video`) and tested on the entire labelled set, not only
on the videos that are on disk.

### Results on the working eight

| check | match | "Not observed" |
|---|---|---|
| BL forward chock | 4 / 4 defined | 4 of 8 |
| Pushback pathway | 7 / 7 defined | 1 of 8 |

Read with the caveat from [testing.md](testing.md): in this eight, Pushback
pathway has no fail at all, so "7 of 7" means only the absence of false
alarms.

---

## "Not observed" — the third state

Occurs in a third of the cases, and on different videos for different checks. It is neither
an error nor a verdict: the module did not see enough to judge.

For streaming this has a practical consequence: **switching to the causal branch
turns part of the silence into verdicts** — both correct and wrong. On
`sAHYpFpM01Dg` the batch mode stayed silent, the streaming mode said `Pass` against a
`fail` label. This is not a degradation of accuracy in the usual sense, it is a change
of coverage, and it has to be measured separately.
