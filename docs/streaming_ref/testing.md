_English translation of `G:/gat-streaming/docs/testing.md` (Ukrainian original), 2026-09-14._

# Testing

## The main caveat: what these numbers mean and what they do not

The monthly-report labelling — 90 videos. Class distribution over the four checks
of the first wave:

| check | fail | pass | fail share |
|---|---|---|---|
| Main gear chocks removed | 30 | 48 | **38.5 %** |
| BL forward chock | 12 | 77 | 13.5 % |
| Pushback pathway | 4 | 82 | 4.7 % |
| Nose wheel chock removed | **1** | 78 | 1.3 % |

**Nose wheel has exactly one fail across all 90 videos.** A module that always
answers "pass" gets 78 out of 79. The question "what is the accuracy" for this
check is ill-defined in principle.

**Pushback pathway** has no fail at all in the working eight — i.e. "7 of 7"
means only the absence of false alarms, and says nothing about the ability
to catch anything.

Hence the rule of this repository:

> **Paired comparison is valid, absolute accuracy is not.**
> The question "did the verdict change on the same video" is correct regardless of
> the balance. The question "what is the accuracy" — only for Main gear chocks.

`tools/pick_balanced.py` builds a balanced sample for a specific check:
it takes **all** fails from the labelling and the same number of passes.

## Three levels of gates

### Level 1 — fast, every PR (`ci.yml`)

No secrets, no GPU, no production data. Under a second.

| gate | what it catches |
|---|---|
| `test_contract.py` | a foreign schema version, field leakage between classes |
| `test_parity.py` | the chunked feed diverging from the batch one |
| `test_session.py` | numbering drifting apart on chunk loss |

A synthetic stream, not production data: what is checked is the **feed mechanics**, not
the detector quality. Real inferences are 500–800 MB per video, they do not belong
in git.

### Level 2 — real modules (`nightly.yml`)

Self-hosted runner with a GPU. Needs the submodules from GitLab, the weights from DVC and
GCP credentials.

```bash
python -m streaming.runner --mod aircraft-chocks --entry main \
    --inf data/inferences --videos-dir data/videos \
    --gt data/gt_by_video.json --out out/batch.json

python -m streaming.runner --mod aircraft-chocks --entry main_stream \
    --inf data/inferences --videos-dir data/videos \
    --gt data/gt_by_video.json --out out/stream.json

python tools/compare_runs.py --batch out/batch.json --stream out/stream.json \
    --gt data/gt_by_video.json
```

`compare_runs.py` exits with code 1 if discrepancies appeared — CI
goes red instead of just writing to the log.

### Level 3 — transport

What happens to the verdict when a chunk does not arrive. Two modes:

```bash
# correct receiver: the gap is filled with placeholder frames, numbering stays intact
python -m streaming.runner --mod beltloader-chocks --no-video \
    --drop-at 0.3 0.6 --drop-mode fill ...

# "as is" behaviour: frames simply vanish, numbering drifts apart
python -m streaming.runner --mod beltloader-chocks --no-video \
    --drop-at 0.3 0.6 --drop-mode shift ...
```

The difference between `fill` and `shift` is literally the price of the absence of `frame_id`
in the contract, expressed in verdicts.

## Running without a video file

`beltloader-chocks` and `pushback-pathway` do not read pixels: `dataset` is never used after
`load_source()`. They need only the number of
frames and the fps, and the number of frames equals the number of lines in the ndjson (verified
on 8 videos, exact match).

Hence — `--no-video`, and they can be tested on any video for which there are
inferences, even if the mp4 is not on disk.

For `aircraft-chocks` this is **not possible**: `dataset.get_im0s(frame_number)`
is called every frame for the frame-difference algorithm. The runner checks this and
refuses to start with `--no-video`.

## Measurement conditions

| | |
|---|---|
| hardware | RTX 5070 Ti 16 GB (sm_120), onnxruntime-gpu 1.29, cuDNN from torch |
| input | production video 1920×1080, 8 fps, H.264, ≈4.0 Mbit/s |
| segmentation | `ffmpeg -c copy -f segment -segment_time 7.5` — stream-copy |
| detectors | GM_yolov8m_best_augmentation_march2024 @1088 + chocks_v4.3 @1280 |
| tracker | parameters from their `global_config`: MAX_AGE 40, MIN_HITS 8 |
| budget | 125 ms per frame at 8 fps |

## Traps we have already stepped on

**Short tests overestimate.** A 60-second test gave 4.72× real-time versus
3.95× on the full video. On an empty apron the detector has nothing to compute.
For planning, take the number from a full turnaround.

**The state of the file cache shifts measurements twofold.** The same 8 videos in batch
mode: 1092 s on a warm cache versus 2228 s on a cold one. Files are
500–800 MB each, the run is bound by the disk, not by compute. Only modes
within a single run can be compared — and even then the second mode has
the advantage of a warm cache.

**Concurrent load ruins everything.** The first streaming measurement had to be
thrown out: during it another module was running and recursive disk scans
were going on. A speed measurement needs an idle machine, period.

**The decoder must be pinned.** See X4 in [architecture.md](architecture.md).
