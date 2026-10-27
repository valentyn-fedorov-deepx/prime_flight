"""One module run (scripts/run_module.py, same flags) that also records every mmpose pose call: boxes, keypoints, scores.

For diagnosing a verdict that changes with the pose model: run it once with `--pose-timing` (the module's own model) and
once with `--pose-override <model>`; the call sequence is the same until the module's decisions diverge, so the calls can
be paired by index (`scripts/pose_diag_compare.py`). Everything after `--` goes to run_module.py unchanged.

    python scripts/pose_diag_run.py --dump out/pose/diag/wMk1_ctl.json -- --module wing-walkers-... --video wMk1umBGpV8f.mp4 \
        --inferences-dir out/testset/v2_inf/wMk1umBGpV8f.mp4 --videos-dir out/pose/diag_videos --pose-timing --out ...
"""

from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    if "--" not in sys.argv or sys.argv.index("--dump") > sys.argv.index("--"):
        raise SystemExit("usage: pose_diag_run.py --dump PATH -- <run_module.py arguments>")
    dump_path = os.path.abspath(sys.argv[sys.argv.index("--dump") + 1])
    rm_args = sys.argv[sys.argv.index("--") + 1:]
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    sys.path.append(ROOT)
    import numpy as np

    import run_module  # scripts/run_module.py
    from pf.pose import shims

    calls = []

    def recording(install):
        def wrapped(*args, **kwargs):
            record = install(*args, **kwargs)
            import mmpose.apis as apis

            inner = apis.inference_topdown

            def inference_topdown(model, img, bboxes=None, bbox_format="xyxy"):
                out = inner(model, img, bboxes, bbox_format)
                calls.append({
                    "boxes": np.asarray(bboxes, dtype=float).reshape(-1, 4).tolist() if bboxes is not None else [],
                    "kpts": [np.asarray(r.pred_instances.keypoints[0], dtype=float).round(2).tolist() for r in out],
                    "scores": [np.asarray(r.pred_instances.keypoint_scores[0], dtype=float).round(4).tolist() for r in out],
                })
                return out

            apis.inference_topdown = inference_topdown
            return record
        return wrapped

    shims.install = recording(shims.install)
    shims.install_timing = recording(shims.install_timing)
    sys.argv = ["run_module.py"] + rm_args
    rc = run_module.main()
    os.makedirs(os.path.dirname(dump_path), exist_ok=True)
    with io.open(dump_path, "w", encoding="utf-8") as fh:
        json.dump({"args": rm_args, "calls": calls}, fh)
    print(f"{len(calls)} pose calls recorded -> {dump_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
