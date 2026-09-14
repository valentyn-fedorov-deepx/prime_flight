"""Fetch test-set inputs from the production buckets: videos and production GM / tracker inference files.

Layout under --root (default out/testset):
  videos/<video>                                   the mp4 from gs://dev3_videos_to_process_1 (or the bucket in the inventory)
  prod/<video>/general_model<video>.ndjson         production GM second-run rows, commit given by --gm-commit
  prod/<video>/trackers<video>.ndjson              production tracker file, commit given by --tracker-commit

The inference objects in gs://cv-modules-topics are gzip-compressed without a Content-Encoding header; they are
decompressed on download and written with the file names db_worker's VideoWorker expects, so the module runner can point
`--inferences-dir` at `prod/<video>`.

    python scripts/testset/fetch.py --videos zHxIAF2vUGxJ.mp4 --what video,gm,trackers
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore", message="Your application has authenticated using end user credentials")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_GM_COMMIT = "8576299"
DEFAULT_TRACKER_COMMIT = "bd43c3c"
_CLIENT = None


def client():
    global _CLIENT
    if _CLIENT is None:
        from google.cloud import storage

        _CLIENT = storage.Client(project="rampvision-2")
    return _CLIENT


def fetch_inference(video: str, kind: str, commit: str, out_dir: str, force: bool = False) -> dict:
    """Download `<video>/<kind><commit>.ndjson`, gunzip if needed, write `<out_dir>/<kind><video>.ndjson`."""
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, f"{kind}{video}.ndjson")
    if os.path.exists(dst) and os.path.getsize(dst) > 0 and not force:
        return {"video": video, "kind": kind, "path": dst, "cached": True}
    t0 = time.time()
    blob = client().bucket("cv-modules-topics").blob(f"{video}/{kind}{commit}.ndjson")
    raw = blob.download_as_bytes(raw_download=True)
    data = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    with io.open(dst + ".part", "wb") as fh:
        fh.write(data)
    os.replace(dst + ".part", dst)
    return {"video": video, "kind": kind, "path": dst, "compressed_mb": round(len(raw) / 1e6, 1),
            "mb": round(len(data) / 1e6, 1), "lines": data.count(b"\n"), "seconds": round(time.time() - t0, 1)}


def fetch_video(video: str, out_dir: str, bucket: str = "dev3_videos_to_process_1", force: bool = False) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, video)
    blob = client().bucket(bucket).get_blob(video)
    if blob is None:
        raise FileNotFoundError(f"gs://{bucket}/{video}")
    if os.path.exists(dst) and os.path.getsize(dst) == blob.size and not force:
        return {"video": video, "path": dst, "cached": True, "gb": round(blob.size / 1e9, 2)}
    t0 = time.time()
    blob.chunk_size = 64 * 1024 * 1024
    blob.download_to_filename(dst + ".part", raw_download=True)
    if os.path.getsize(dst + ".part") != blob.size:
        raise IOError(f"size mismatch for {video}: {os.path.getsize(dst + '.part')} != {blob.size}")
    os.replace(dst + ".part", dst)
    dt = time.time() - t0
    return {"video": video, "path": dst, "gb": round(blob.size / 1e9, 2), "seconds": round(dt, 1),
            "mb_per_s": round(blob.size / 1e6 / max(dt, 1e-6), 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", required=True, help="comma-separated video names, or @file with one per line, or 'all'")
    ap.add_argument("--what", default="video,gm,trackers")
    ap.add_argument("--root", default=os.path.join(ROOT, "out", "testset"))
    ap.add_argument("--gm-commit", default=DEFAULT_GM_COMMIT)
    ap.add_argument("--tracker-commit", default=DEFAULT_TRACKER_COMMIT)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if a.videos == "all":
        inv = json.load(io.open(os.path.join(a.root, "videos_inventory.json"), encoding="utf-8"))
        videos = [r["video"] for r in inv]
    elif a.videos.startswith("@"):
        videos = [l.strip() for l in io.open(a.videos[1:], encoding="utf-8") if l.strip()]
    else:
        videos = [v.strip() for v in a.videos.split(",") if v.strip()]
    what = {w.strip() for w in a.what.split(",")}

    jobs = []
    for v in videos:
        if "gm" in what:
            jobs.append(lambda v=v: fetch_inference(v, "general_model", a.gm_commit, os.path.join(a.root, "prod", v), a.force))
        if "trackers" in what:
            jobs.append(lambda v=v: fetch_inference(v, "trackers", a.tracker_commit, os.path.join(a.root, "prod", v), a.force))
        if "video" in what:
            jobs.append(lambda v=v: fetch_video(v, os.path.join(a.root, "videos"), force=a.force))
    failures = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for fut in [ex.submit(j) for j in jobs]:
            try:
                print(json.dumps(fut.result()), flush=True)
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(json.dumps({"error": f"{type(e).__name__}: {e}"}), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
