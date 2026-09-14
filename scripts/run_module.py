"""Run a production CV module (as is, from external/<repo>) on a directory of per-frame inferences — the L2 gate.

Ported from the gat-streaming stand runner (`streaming/runner.py`) and generalised: any module repo, any inference
directory, optional --no-video meta worker for modules that do not read pixels. Used to prove that a new GM/tracker
version does not change module verdicts: run the module on the production inferences and on the v2 inferences of the
same video and diff the results.

    python scripts/run_module.py --module beltloader-chocks --video DjwtQRdZyt0sSk.mp4 \
        --inferences-dir out/l2/prod --no-video --out out/l2/prod_beltloader-chocks.json

The module's `cv_common/` and `db_worker/` submodule folders must be populated (copied from external/) at the pin the
module expects (`git -C external/<module> ls-tree HEAD cv_common db_worker`).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_meta_worker(VideoWorker, fps=8):
    """VideoWorker without a video file — for modules that never touch pixels (stand `workers/meta_worker.py`)."""

    class MetaOnlyWorker(VideoWorker):
        def load_source(self, source=None):
            if source:
                self.source = source
            name = os.path.basename(self.source)
            gm = os.path.join(self.inferences_dir, "general_model" + name + ".ndjson")
            n = 0
            with open(gm, "rb") as fh:
                for _ in fh:
                    n += 1
            self.number_of_frames = n
            self.fps = fps

    return MetaOnlyWorker


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", required=True, help="repo folder name under external/")
    ap.add_argument("--entry", default="main", help="python module with detect(): main | main_stream")
    ap.add_argument("--video", required=True, help="video file name (basename is used for the ndjson names)")
    ap.add_argument("--videos-dir", default=None, help="folder with the mp4 (needed unless --no-video)")
    ap.add_argument("--inferences-dir", required=True)
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--cone-camera", default="true", choices=["true", "false"])
    ap.add_argument("--weights-dir", default="weights")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    moddir = os.path.join(ROOT, "external", a.module)
    inf = os.path.abspath(a.inferences_dir)
    out = os.path.abspath(a.out)
    src = os.path.join(os.path.abspath(a.videos_dir), a.video) if a.videos_dir else a.video
    if not a.no_video and not os.path.exists(src):
        raise SystemExit(f"video not found: {src} (use --videos-dir or --no-video)")

    os.chdir(moddir)
    sys.path.insert(0, moddir)
    import torch

    prod = importlib.import_module(a.entry)
    from cv_common.common import parse_config
    from cv_common.log_utils import JsonLogger
    from db_worker.ML_worker import VideoWorker

    Worker = make_meta_worker(VideoWorker, a.fps) if a.no_video else VideoWorker
    config = parse_config()
    t0 = time.time()
    result = {
        "module": a.module,
        "entry": a.entry,
        "video": a.video,
        "inferences_dir": inf,
        "no_video": a.no_video,
    }
    try:
        vw = Worker(
            model_name="model-name",
            load_tracks=True,
            source=src,
            testing=True,
            auto_download_inference=False,
            inferences_dir=inf,
        )
        jl = JsonLogger(config["status2id"], config["str2id"], None)
        with torch.no_grad():
            status, report, smart = prod.detect(
                source=src,
                output_path=os.path.join(moddir, "output", a.video + ".mkv"),
                device=a.device,
                video_worker=vw,
                write_video=False,
                cone_camera=(a.cone_camera == "true"),
                weights_dir=a.weights_dir,
                json_logger=jl,
            )
        result.update(
            {
                "status": status if isinstance(status, (str, int, float)) else list(status),
                "report": report,
                "smart_timeline": smart,
                "seconds": round(time.time() - t0, 1),
            }
        )
    except Exception as e:  # keep the failure in the artefact instead of crashing the batch
        result.update(
            {
                "error": f"{type(e).__name__}: {str(e)[:500]}",
                "traceback": traceback.format_exc()[-3000:],
                "seconds": round(time.time() - t0, 1),
            }
        )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1, default=str)
    print(
        json.dumps({k: result.get(k) for k in ("module", "video", "status", "seconds", "error")}, default=str)
    )
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
