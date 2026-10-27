"""`scripts/ww_pose_record.py` over a list of test videos: fetch ahead, record one video at a time, drop the mp4s it
fetched. Resumable (a recording that exists is skipped); `out/pose/ww/batch.stop` finishes the current video and exits.

    python scripts/ww_pose_batch.py --videos out/pose/ww_videos.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.testset import fetch  # noqa: E402
from scripts.testset import orchestrate as orch  # noqa: E402
from scripts.testset import profiles  # noqa: E402
from scripts.testset.variant_run import module_command  # noqa: E402

MODULE = "wing-walkers-in-proper-position-and-using-approved-wands"
OUT = os.path.join(ROOT, "out", "pose", "ww")
VIDEOS = os.path.join(orch.TS, "videos")
STOP = os.path.join(OUT, "batch.stop")


def log(text: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
    print(line, flush=True)
    with io.open(os.path.join(OUT, "batch.log"), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", required=True, help="JSON list of video names, in the order to record")
    ap.add_argument("--prefetch", type=int, default=2, help="videos fetched ahead of the one being recorded")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    with io.open(a.videos, encoding="utf-8") as fh:
        videos = [v for v in json.load(fh) if not os.path.exists(os.path.join(OUT, v + ".json"))]
    plan = orch.Plan()
    on_disk = {v for v in videos if os.path.exists(os.path.join(VIDEOS, v))}
    log(f"start: {len(videos)} videos to record, {len(on_disk)} on disk")
    fetched, failed, threads = set(), set(), {}

    def do_fetch(video: str) -> None:
        try:
            r = fetch.fetch_video(video, VIDEOS)
            fetched.add(video)
            log(f"fetched {video}: {r.get('gb')} GB in {r.get('seconds', 0)} s")
        except Exception as e:  # noqa: BLE001 - recorded, the video is skipped
            failed.add(video)
            log(f"fetch FAILED {video}: {type(e).__name__}: {str(e)[:200]}")

    env = dict(os.environ, **profiles.ENV)
    for i, video in enumerate(videos):
        if os.path.exists(STOP):
            log("stop file: exiting")
            return 0
        for nxt in videos[i:i + 1 + a.prefetch]:
            if nxt not in on_disk and nxt not in threads:
                threads[nxt] = threading.Thread(target=do_fetch, args=(nxt,), daemon=True)
                threads[nxt].start()
        if video in threads:
            threads[video].join()
        if video in failed:
            continue
        cmd = module_command(plan, "ww_rec", video, MODULE, orch.paths(video)["v2_inf"], "--pose-timing")
        cmd = [cmd[0], "scripts/ww_pose_record.py", "--dump", os.path.join(OUT, video + ".json"), "--"] + cmd[2:]
        t0 = time.time()
        with io.open(os.path.join(OUT, video + ".log"), "w", encoding="utf-8") as fh:
            rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=env).returncode
        log(f"{video}: rc={rc} in {time.time() - t0:.0f} s")
        if video in fetched and os.path.exists(os.path.join(VIDEOS, video)):
            os.remove(os.path.join(VIDEOS, video))
    log("all done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
