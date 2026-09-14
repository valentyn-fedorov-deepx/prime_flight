"""Calibrate module versions against the monthly report: run candidate branches of a module on calibration events with the
production inferences and measure agreement with the report's "New output".

The CI that produced the report ran module versions we cannot read (image `ci-cv-module-image`, `ci.py`). Many module repos
carry feature branches newer than their default branch (several with "Fix prod ..." commits), and on event
641a25728471f56e528714e9 two such branches reproduced New output where the default branches did not. This tool turns the
version choice into a measurement: same inferences, flags and machine; only the module checkout differs.

Candidates: `module:branch` (`default` = external/<module>). A branch is exported once to
`external/_branches/<module>@<branch>`: git archive of origin/<branch>, the module's populated cv_common/ and db_worker/
copied from the default checkout, weights/ copied when the branch does not change DVC files, otherwise pulled with DVC
(`PF_DVC.json`). Runs: `out/testset/modules/cal/<module>@<candidate>/<video>/<module>.json`; default-branch results already in
`out/testset/modules/ctl` are reused.

    python scripts/testset/calibrate.py run --candidates handrails-on-gse-being-used:per_component_improvement --events auto:8
    python scripts/testset/calibrate.py summary --out out/testset/calibration.json
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.testset import profiles  # noqa: E402
from scripts.testset.compare import event_verdicts, run_loader  # noqa: E402
from scripts.testset.orchestrate import Plan, paths  # noqa: E402

TS = os.path.join(ROOT, "out", "testset")
CAL = os.path.join(TS, "modules", "cal")
PY = sys.executable


def git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True).stdout.strip()


def pins(repo: str, ref: str) -> dict:
    out = {}
    for line in git(repo, "ls-tree", ref, "cv_common", "db_worker").splitlines():
        parts = line.split()
        if len(parts) >= 4:
            out[parts[3]] = parts[2][:8]
    return out


def export_dir(module: str, candidate: str) -> str:
    return os.path.join(ROOT, "external", module) if candidate == "default" else \
        os.path.join(ROOT, "external", "_branches", f"{module}@{candidate}")


def export_branch(module: str, branch: str) -> str:
    """Branch checkout next to the default clone; the clone's working tree is never touched."""
    src = os.path.join(ROOT, "external", module)
    dst = export_dir(module, branch)
    if os.path.exists(os.path.join(dst, "PF_SOURCE.txt")):
        return dst
    commit = git(src, "rev-parse", "--short", f"origin/{branch}")
    if not commit:
        raise RuntimeError(f"{module}: origin/{branch} not found")
    tmp = dst + ".partial"
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    tar_path = tmp + ".tar"
    subprocess.run(["git", "-C", src, "archive", "--format=tar", "-o", tar_path, f"origin/{branch}"], check=True)
    with tarfile.open(tar_path) as tf:
        tf.extractall(tmp)
    os.remove(tar_path)
    for sub in ("cv_common", "db_worker"):
        if os.path.isdir(os.path.join(src, sub)):
            shutil.copytree(os.path.join(src, sub), os.path.join(tmp, sub), dirs_exist_ok=True)
    dvc_changed = git(src, "diff", "--name-only", "HEAD", f"origin/{branch}", "--", "*.dvc", ".dvc").split()
    if not dvc_changed and os.path.isdir(os.path.join(src, "weights")):
        shutil.copytree(os.path.join(src, "weights"), os.path.join(tmp, "weights"), dirs_exist_ok=True)
    info = {"module": module, "branch": branch, "commit": commit, "pins_default": pins(src, "HEAD"),
            "pins_branch": pins(src, f"origin/{branch}"), "dvc_changed": dvc_changed,
            "requirements_changed": git(src, "diff", "--name-only", "HEAD", f"origin/{branch}", "--", "requirements*.txt").split()}
    with io.open(os.path.join(tmp, "PF_SOURCE.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"{branch}@{commit}\n")
    with io.open(os.path.join(tmp, "PF_EXPORT.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1)
    os.replace(tmp, dst)
    if dvc_changed:
        log = []
        for cmd in (["dvc", "config", "--local", "core.no_scm", "true"], ["dvc", "pull", "-r", "weights_gs"],
                    ["dvc", "pull", "-r", "weights"], ["dvc", "pull"]):
            r = subprocess.run(cmd, cwd=dst, capture_output=True, text=True)
            log.append({"cmd": " ".join(cmd), "rc": r.returncode, "tail": (r.stdout + r.stderr)[-500:]})
        with io.open(os.path.join(dst, "PF_DVC.json"), "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=1)
    return dst


def calibration_events(plan: Plan, spec: str) -> list:
    if not spec.startswith("auto:"):
        return spec.split(",")
    n = int(spec.split(":")[1])
    out = []
    by_id = {e["event_id"]: e for e in plan.plan["events"]}
    seen = []
    for v in plan.order:
        for e in plan.plan["events"]:
            if v in e["videos"] and e["event_id"] not in seen:
                seen.append(e["event_id"])
    for eid in seen:
        e = by_id[eid]
        ok = all(os.path.exists(paths(v)["video"]) and os.path.getsize(paths(v)["video"]) == plan.inventory[v]["size"]
                 and os.path.exists(paths(v)["prod_gm"]) and os.path.exists(paths(v)["prod_trk"]) for v in e["videos"])
        if ok:
            out.append(eid)
        if len(out) == n:
            break
    return out


def module_videos(plan: Plan, module: str, events: list) -> list:
    vids = []
    for e in plan.plan["events"]:
        if e["event_id"] not in events:
            continue
        for t in e["tasks"].values():
            if t["module"] == module:
                vids += [v for v in t["videos"] if v not in vids]
    return vids


def cal_out(module: str, candidate: str, video: str) -> str:
    return os.path.join(CAL, f"{module}@{candidate}", video, f"{module}.json")


def build(module: str, candidate: str, video: str, plan: Plan):
    prof = profiles.profile(module)
    p = paths(video)
    launcher = prof.get("launcher")
    rel = (lambda x: os.path.relpath(x, ROOT).replace("\\", "/")) if launcher else (lambda x: x)
    cmd = (list(launcher) if launcher else [PY, "scripts/run_module.py"]) + [
        "--module", module, "--video", video, "--inferences-dir", rel(p["prod_dir"]), "--device", prof["device"],
        "--cone-camera", "true" if plan.cone(video) else "false", "--out", rel(cal_out(module, candidate, video)),
        "--videos-dir", rel(os.path.join(TS, "videos"))]
    if prof["numpy1"]:
        cmd.append("--numpy1-scalars")
    if plan.airplane_type(video):
        cmd += ["--airplane-type", plan.airplane_type(video)]
    for x in prof["prepend_path"]:
        cmd += ["--prepend-path", x]
    if prof["drop_state_keys"]:
        cmd += ["--drop-state-keys", prof["drop_state_keys"]]
    if candidate != "default":
        cmd += ["--module-dir", os.path.relpath(export_dir(module, candidate), ROOT).replace("\\", "/")]
    return cmd, dict(os.environ, **profiles.ENV)


def run_job(job) -> dict:
    module, candidate, video, cmd, env = job
    out = cal_out(module, candidate, video)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t0 = time.time()
    with io.open(out + ".log", "w", encoding="utf-8") as fh:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=env).returncode
    r = {}
    try:
        r = json.load(io.open(out, encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {"module": module, "candidate": candidate, "video": video, "rc": rc, "status": r.get("status"),
            "error": (r.get("error") or "")[:160], "seconds": round(time.time() - t0, 1)}


def cmd_run(a) -> int:
    plan = Plan()
    events = calibration_events(plan, a.events)
    print(f"calibration events ({len(events)}): {events}")
    cands = [c.split(":", 1) for c in a.candidates.split(",") if c]
    jobs_cpu, jobs_gpu = [], []
    for module, candidate in cands:
        if candidate != "default":
            d = export_dir(module, candidate)
            if not os.path.exists(os.path.join(d, "PF_SOURCE.txt")):
                if a.dry_run:
                    print(f"would export {module}@{candidate}")
                else:
                    export_branch(module, candidate)
            meta = os.path.join(d, "PF_EXPORT.json")
            if os.path.exists(meta):
                info = json.load(io.open(meta, encoding="utf-8"))
                print(f"export {module}@{candidate}: {info['commit']} dvc_changed={info['dvc_changed']} "
                      f"requirements_changed={info['requirements_changed']} pins {info['pins_default']} -> {info['pins_branch']}")
            elif os.path.exists(os.path.join(d, "PF_SOURCE.txt")):
                print(f"export {module}@{candidate}: {open(os.path.join(d, 'PF_SOURCE.txt')).read().strip()} (manual export)")
        for video in module_videos(plan, module, events):
            out = cal_out(module, candidate, video)
            if os.path.exists(out) and not a.force:
                continue
            ctl = os.path.join(TS, "modules", "ctl", video, f"{module}.json")
            if candidate == "default" and os.path.exists(ctl):
                r = json.load(io.open(ctl, encoding="utf-8"))
                if "error" not in r and not r.get("module_dir_arg") and not r.get("no_video"):
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    shutil.copyfile(ctl, out)
                    continue
            cmd, env = build(module, candidate, video, plan)
            (jobs_cpu if profiles.profile(module)["pixel_free"] else jobs_gpu).append((module, candidate, video, cmd, env))
    print(f"jobs: {len(jobs_cpu)} pixel-free, {len(jobs_gpu)} pixel")
    if a.dry_run:
        for j in jobs_cpu + jobs_gpu:
            print(" ".join(j[3])[:300])
        return 0
    with cf.ThreadPoolExecutor(a.cpu_workers) as pc, cf.ThreadPoolExecutor(a.gpu_workers) as pg:
        futs = [pc.submit(run_job, j) for j in jobs_cpu] + [pg.submit(run_job, j) for j in jobs_gpu]
        for f in cf.as_completed(futs):
            print(json.dumps(f.result()), flush=True)
    return cmd_summary(a, plan, events)


def cmd_summary(a, plan: Plan | None = None, events: list | None = None) -> int:
    plan = plan or Plan()
    module_tasks = plan.plan["module_tasks"]
    rows = []
    if not os.path.isdir(CAL):
        print("no calibration runs")
        return 0
    for name in sorted(os.listdir(CAL)):
        if "@" not in name:
            continue
        module, candidate = name.split("@", 1)
        get = run_loader(os.path.join(CAL, name))
        c = collections.Counter()
        diffs = []
        for e in plan.plan["events"]:
            if events and e["event_id"] not in events:
                continue
            merged, detail = event_verdicts(e, get, module_tasks)
            for task, t in e["tasks"].items():
                if t["module"] != module or not t["videos"]:
                    continue
                ours = merged.get(task)
                if ours is None:
                    if any(os.path.exists(os.path.join(CAL, name, v)) for v in t["videos"]):
                        c["failed_or_partial"] += 1
                    continue
                exp = t["expected"]
                c["comparable"] += 1
                c["equal_new"] += ours == exp["new"]
                c["equal_previous"] += ours == exp["previous"]
                if exp["true"] not in ("", None):
                    c["with_truth"] += 1
                    c["correct"] += ours == exp["true"]
                    c["new_correct"] += exp["new"] == exp["true"]
                if ours != exp["new"]:
                    diffs.append(f"{e['event_id'][-6:]}:{task}:{ours}/{exp['new']}")
        rows.append({"module": module, "candidate": candidate, **c, "diffs_vs_new": diffs})
    print(f"{'module':62s} {'candidate':28s} comp =new =prev  acc  newacc fail")
    for r in rows:
        print(f"{r['module'][:62]:62s} {r['candidate'][:28]:28s} {r.get('comparable', 0):4d} {r.get('equal_new', 0):4d} "
              f"{r.get('equal_previous', 0):5d} {r.get('correct', 0):4d} {r.get('new_correct', 0):6d} {r.get('failed_or_partial', 0):4d}"
              f"  {' '.join(r['diffs_vs_new'][:4])}")
    if getattr(a, "out", None):
        with io.open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"events": events, "rows": rows}, fh, indent=1)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--candidates", required=True, help="comma list of module:branch (branch 'default' = external/<module>)")
    r.add_argument("--events", default="auto:8", help="comma list of event ids or auto:N (first N fully downloaded events)")
    r.add_argument("--cpu-workers", type=int, default=2)
    r.add_argument("--gpu-workers", type=int, default=1)
    r.add_argument("--force", action="store_true")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--out", default=os.path.join(TS, "calibration.json"))
    s = sub.add_parser("summary")
    s.add_argument("--events", default=None, help="comma list of event ids (default: all with runs)")
    s.add_argument("--out", default=os.path.join(TS, "calibration.json"))
    a = ap.parse_args()
    if a.cmd == "run":
        return cmd_run(a)
    return cmd_summary(a, None, a.events.split(",") if a.events else None)


if __name__ == "__main__":
    raise SystemExit(main())
