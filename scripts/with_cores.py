"""Run any script pinned to N CPU cores (the pod envelope: a model container of the real-time worker requests one vCPU).

The affinity is set on this process before the target starts, so the target and every child it spawns inherit it.

    python scripts/with_cores.py 1 scripts/tracker_v2_run.py --video ... --gm-ndjson ...
"""

from __future__ import annotations

import os
import runpy
import sys


def main() -> int:
    if len(sys.argv) < 3 or not sys.argv[1].isdigit():
        print(__doc__)
        return 2
    cores = int(sys.argv[1])
    import psutil

    proc = psutil.Process()
    proc.cpu_affinity(list(range(cores)))
    os.environ["OMP_NUM_THREADS"] = str(cores)
    os.environ["PF_CPU_CORES"] = str(cores)
    target = sys.argv[2]
    sys.argv = [target] + sys.argv[3:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(target)))
    runpy.run_path(target, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
