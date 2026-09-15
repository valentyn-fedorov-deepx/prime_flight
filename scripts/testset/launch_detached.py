"""Start a long-running test-set process detached from the calling shell, so it outlives the session that started it (a
closed terminal or agent session tears down its child processes). It does not survive a reboot.

Windows: the process gets a console without a window (CREATE_NO_WINDOW; its children inherit it, so module jobs do not open
windows), its own process group, and breaks away from the caller's job object when the job allows it (recorded as
`breakaway_from_job`). The launcher exits at once, so the process is no longer in the caller's process tree. Output goes to
--log (appended); the PID, command and start time go to out/testset/pids/<name>.json.

Stop the orchestrator gracefully with `"stop": true` in out/testset/orchestrator_control.json (it drains its running jobs);
stop the governor by its PID.

    python scripts/testset/launch_detached.py --name orchestrator --log out/testset/orchestrator.stdout -- \
        python scripts/testset/orchestrate.py run --keep-control
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PID_DIR = os.path.join(ROOT, "out", "testset", "pids")

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="record name in out/testset/pids/")
    ap.add_argument("--log", required=True, help="file that receives stdout and stderr (appended)")
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command ...  ('python' means this interpreter)")
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else list(a.cmd)
    if not cmd:
        ap.error("no command given")
    if cmd[0] == "python":
        cmd[0] = sys.executable

    log_path = a.log if os.path.isabs(a.log) else os.path.join(ROOT, a.log)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log = io.open(log_path, "ab")
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, close_fds=True)
    breakaway = None
    if os.name == "nt":
        flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
            breakaway = True
        except OSError:  # the caller's job does not allow breakaway
            proc = subprocess.Popen(cmd, creationflags=flags, **kw)
            breakaway = False
    else:
        proc = subprocess.Popen(cmd, start_new_session=True, **kw)

    record = {"name": a.name, "pid": proc.pid, "cmd": cmd, "started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "breakaway_from_job": breakaway, "log": log_path}
    os.makedirs(PID_DIR, exist_ok=True)
    with io.open(os.path.join(PID_DIR, f"{a.name}.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
    print(json.dumps(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
