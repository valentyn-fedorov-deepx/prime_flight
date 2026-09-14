_English translation of `G:/gat-streaming/docs/contract.md` (Ukrainian original), 2026-09-14._

# Frame contract

The cheapest part of the system, and at the same time the one whose absence has already cost
a day of work.

## Schema

```python
{
  "schema_version": "1.0",     # without this, incompatibility is visible only as a crash
  "frame_id": 1234,            # absolute number, NOT the position in the stream
  "general_model": [...],      # detections
  "trackers": [...]            # tracks with state
}
```

Implementation and checks — [streaming/contract.py](../streaming/contract.py),
tests — [tests/test_contract.py](../tests/test_contract.py).

## Why `schema_version`

The bucket `gs://cv-modules-topics` holds **15–16 versions** of tracker
inferences per video — from April to August 2026, with different code hashes
and incompatible `state_dict` schemas. There is no version marker.

The only way to tell them apart was: download, try feeding it to the module,
see whether it crashes with `ValueError: Unexpected keys in state_dict`. For three
videos out of eight **none** of the 15–16 versions was compatible.

## Why `frame_id`

Modules take the frame number from `enumerate(metadata, 1)` — i.e. **from the position in
the stream**. As long as the stream is intact, the position equals the absolute id. As soon as a chunk
is lost they diverge, and comparisons like

```python
elif frame_number == aircraft.departure_frame:
```

start pointing at the wrong frame. `aircraft.departure_frame` comes from the
tracker as an absolute id; `frame_number` is a position. After the loss of one
7.5-second chunk they diverge by exactly 60.

The receiver must fill the gaps with placeholder frames rather than skip frames.
`Session` does this; the `test_session.py` test "without fill, the numbering drifts apart"
(the stand's test names are Ukrainian identifiers) pins down the size of the divergence if it is not done.

There is a second reason too. A chunk **has no fixed length**: at a nominal 7.5 s the
maximum measured duration is 11.25 s, exactly one GOP more, because the
last chunk picks up the remainder. Relying on "frame number within the chunk" is not possible
in principle. See [chunking.svg](chunking.svg).

## Field leakage between classes

`VEHICLE_ONLY_KEYS = {"_bl_type_bbox", "_bl_type_frames"}` — fields that the class
`Vehicle` is allowed to write into its state and which **must not** be in the aircraft's state.

A real bug: in a newer version of the tracker these fields moved up the hierarchy.

| class | correct version | broken |
|---|---|---|
| `airplane` | 38 keys, no `bl_type` | **40 keys, `bl_type` present** |
| `beltloader` | 34 keys, `bl_type` present | 34 keys, `bl_type` present |

The module restores only the aircraft from state (`main.py:1262`), its class does not know
these fields — and the base `tracked_object.py:672` raises `ValueError`. The pinned
`cv_common@ac5098d` has nothing to do with it: it handles these fields correctly in the class
`Vehicle` (`transport.py:203`).

`check_class_leakage()` catches this before deployment. `strip_class_leakage()` heals
data that already exists — by the same mechanism their own code uses to discard obsolete
fields (`state_dict.pop('_recent_bboxes', None)`). This is not a logic change: the module
never reads `bl_type` for the aircraft.

## What is NOT part of the contract

**Alerts.** The verdict is the value the module returns. Deduplication, silence
windows, alert lifecycle, delivery — a separate layer and a separate backend task.

For reference, why the layer is needed: without deduplication one module produced **357
alerts on a single video**. But we will not solve that here.
