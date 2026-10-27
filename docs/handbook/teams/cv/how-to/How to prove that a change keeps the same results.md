# How to prove that a change keeps the same results

**For:** a CV engineer who made the General Model, the tracker or a check faster or cleaner and must show that nothing
the client sees can change.

**The rule:** a change that is meant to keep the results must give **exactly the same output files** — byte for byte —
and, if there is a video, the same picture in every frame. "Almost the same" is not enough: then the change is a change
of results and has to be measured on the monthly test instead (*How to measure a change on the monthly test*).

## Why this needs care

- **Randomness.** The shared code picks some points on objects at random (for following their movement), and draws the
  colours of the debug video at random. Two runs of the same production code therefore differ. Both runs of a comparison
  must start the random number generator from the same value.
- **The video decoder.** Two decoders can return a slightly different number of frames from the same file. Both sides
  must use the same one.
- **Compressed files.** The result files in the buckets are compressed, and the compressed file contains the time it was
  written. Compare the unpacked content, never the compressed files.
- **A busy machine.** Speed numbers mean something only on a quiet machine, with the old and new version running one
  after the other, several times.

## Steps

1. **Pick the input.** A part of a busy turnaround (for example 1 200 frames — two and a half minutes — with many
   objects) for a first check, then at least one full turnaround.
2. **Run the old version and the new version** on the same input, with the same random seed and the same decoder.
3. **Compare every output:** the result files, the report, the debug video file, and every decoded frame of the video.
4. **Measure the time**, alternating: old, new, old, new.
5. **Write down** what was changed and why it cannot change the result, the files compared with their checksums, and the
   times — in a research report and in the description of the merge request.
6. **The test on the cluster.** The MLOps team builds an image of the new version. Both images run on the same five
   videos; the unpacked result files must be identical; the job times show the real gain.

## How to see that it worked

Every checksum of the new version equals the old one, and the number of identical decoded frames equals the number of
frames. One different byte means the change is not exact: find the cause before going on.

## Common problems

| What you see | Why | What to do |
|---|---|---|
| the outputs differ between two runs of the **same** version | randomness is not seeded | seed it at the same point in both runs |
| the debug video differs but the result files are equal | the colours of the drawn points are random | fix the colours in both runs |
| the compressed bucket files differ but the content is equal | the compressed file carries its write time | compare after unpacking |
| a few frames more or less | different video decoders | use the same decoder on both sides |

## For developers

- General Model: `scripts/gm_prod_profile.py run --gm-root <checkout> --video <video> --out <dir>` for each checkout,
  then `scripts/gm_prod_profile.py compare <dir old> <dir new>`; it seeds `np.random` before each pass, as the proof of
  the October 2026 speed-up did.
- Tracker: `scripts/tracker_exact_ab.py --label <name> --video <video> --gm-ndjson <General Model file> --start <frame>
  --frames <count> --rounds 2` runs production and the branch alternately through `scripts/tracker_v1_profile.py`
  (seeded, fixed point colours) and compares tracks, video files and decoded frames; the tracker branch also has the
  `TRACKER_SEED` setting for the cluster test.
- A check: run `scripts/run_module.py` on both checkouts with the same inputs and compare the JSON fields `status`,
  `report` and `smart_timeline`.
