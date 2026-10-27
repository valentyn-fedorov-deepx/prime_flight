# How to run a check on one turnaround on your computer

**For:** a CV engineer who wants to see how a check decides on a real turnaround, debug it or try a change.

**You need:** access to GitLab (group `dxgat`), to the Google Cloud project `rampvision-2` (read access to the buckets)
and an SSH key added to GitLab (the shared code inside every module is downloaded over SSH). A graphics card helps but is
not required: most checks also run on the processor, only slower.

A check does not look at the video alone. It reads what the General Model and the tracker found in that video, so for
one run you need three things: the module's code with its model weights, the video, and the two result files of the
General Model and the tracker for that video.

## Steps

1. **Find the production branch.** Open the page of the check in *System / Modules*; the section *For developers* names
   the repository and the branch that runs in production.

2. **Get the code with its shared parts.** Every module carries two shared folders (`cv_common` — code shared by all
   checks, `db_worker` — how a job reads its inputs and writes its results) as git submodules:

   ```bash
   git clone -b <branch> https://gitlab.com/dxgat/detectors/<module>.git
   cd <module>
   git submodule update --init
   ```

3. **Create a Python environment** with the module's packages. The `Dockerfile` of the module shows which Python version
   production uses; use the same one.

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Download the model weights.** They are kept with DVC (a tool that stores large files in a cloud bucket):

   ```bash
   gcloud auth application-default login
   dvc pull
   ```

5. **Choose a turnaround** — for example one from the monthly test that the client labelled Fail for this check (ask
   Oksana or look at the monthly report).

6. **Download the video.** The merged videos are in the video buckets of `rampvision-2`. Production buckets are
   read-only: copy from them, never upload into them.

   ```bash
   gcloud storage cp gs://<video bucket>/<video>.mp4 data/
   ```

7. **Download what the General Model and the tracker found.** Each video has a folder in the bucket `cv-modules-topics`
   with one file per version; the newest is the one production uses.

   ```bash
   gcloud storage ls gs://cv-modules-topics/<video>.mp4/
   gcloud storage cp gs://cv-modules-topics/<video>.mp4/general_model<version>.ndjson inferences/gm.gz
   gcloud storage cp gs://cv-modules-topics/<video>.mp4/trackers<version>.ndjson inferences/tr.gz
   ```

   The files are compressed although their names do not say so. Unpack them under the names the module expects:

   ```bash
   gzip -dc inferences/gm.gz > inferences/general_model<video>.mp4.ndjson
   gzip -dc inferences/tr.gz > inferences/trackers<video>.mp4.ndjson
   ```

8. **Run the check.** The exact arguments are on the check's page (*For developers*, "how to run"); most checks take:

   ```bash
   python main.py --source data/<video>.mp4 --inferences-dir inferences --weights-dir weights
   ```

   Add `--device cpu` without a graphics card and `--write-video` to get a video with everything the check drew.

## How to see that it worked

The module prints its verdict and the sentence the client would see. Compare them with the verdict on the RampVision
website for the same turnaround (or with the monthly report). The `output` folder of the module holds its logs and, with
`--write-video`, the annotated video.

## Common problems

| What you see | Why | What to do |
|---|---|---|
| `git submodule update` asks for a password or fails | the submodules use SSH addresses | add your SSH key to GitLab |
| an error converting an array to a number | the production images use an older NumPy (version 1); NumPy 2 refuses some conversions | install `numpy<2` in the environment |
| the verdict differs from the website | the website may have used an older version of the General Model or tracker file, or another branch of the check | use the file versions and the branch named on the check's page |
| the hair policy check does not start | its production code is a protected build that runs only on Python 3.8 | use a Python 3.8 environment (on Windows: inside WSL) |

## For developers

In the Prime Flight workspace the same run is two commands, with the inputs placed and named automatically:

```bash
python scripts/testset/fetch.py --videos <video>.mp4 --what video,gm,trackers
python scripts/run_module.py --module <module> --video <video>.mp4 --videos-dir out/testset/videos \
    --inferences-dir out/testset/prod/<video>.mp4 --out out/<module>_<video>.json
```

`scripts/run_module.py` calls the module's `detect()` the way the production job does and records the verdict, report,
timeline and errors in one JSON file; `--numpy1-scalars`, `--module-dir`, `--no-video` and the pose options are described
in its help.
