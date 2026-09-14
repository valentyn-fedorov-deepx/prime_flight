"""Test-set orchestrator: GM v2 + Tracker v2 inference and module runs for every video of the plan, resumable.

Per video (ledger `out/testset/ledger/<video>.json`), steps:
  fetch        video + production GM (8576299) and tracker (bd43c3c) files (scripts/testset/fetch.py). Complete files already
               on disk are adopted; a `.part` modified in the last 3 minutes means another process is downloading it.
  gm           GM v2 variant entity_clip, parallel heads, tolerant L1 vs the production GM file (scripts/gm_v2_run.py)
  tracker      Tracker v2 exact fast paths, seed 0, on the GM v2 rows, L1 vs the production tracker file
  mod:ctl:<m>  module <m> on the production inferences - the control: same machine, code and flags as the v2 run
  mod:v2:<m>   module <m> on the GM v2 + Tracker v2 inferences (`out/testset/v2_inf/<video>/`, hard links)
Module results: `out/testset/modules/{ctl,v2}/<video>/<module>.json` (input of scripts/testset/compare.py).

Camera of a video: plan.json (routing evidence), overridden by `out/testset/camera_overrides.json` {video: "cone"|"wing"};
aircraft type: plan.json per event, overridden by `out/testset/airplane_overrides.json` {video: "JET"|"AIRCRAFT"|null}.
The same flags feed the tracker and both module labels. A result produced with other flags is stale and is redone.

Live control: `out/testset/orchestrator_control.json` is re-read every loop:
  {"steps": [...], "limits": {"fetch", "gm", "tracker", "mod", "mod_gpu", "mod_cpu"}, "disabled_modules": [...],
   "min_free_gb": 60,
   "cleanup": false, "retry_failed": false, "stop": false}
`stop` drains (no new jobs, exit when the running ones finish); `retry_failed` resets failed steps once; `cleanup` deletes the
mp4 and the v2 bus file of a video once all its enabled module jobs have finished.

    python scripts/testset/orchestrate.py run --steps fetch,gm,tracker,mod:ctl,mod:v2 --disabled-modules hair-policy
    python scripts/testset/orchestrate.py run --dry-run
    python scripts/testset/orchestrate.py status
"""

from __future__ import annotations

import argparse
import collections
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.testset import profiles  # noqa: E402  (re-imported every loop: launch facts can change while running)

TS = os.path.join(ROOT, "out", "testset")
PY = sys.executable
CONTROL = os.path.join(TS, "orchestrator_control.json")
GM_WEIGHTS = os.path.join(ROOT, "external", "general_model_prod", "weights")
DEFAULT_CONTROL = {
    "steps": ["fetch", "gm", "tracker", "mod:ctl", "mod:v2"],
    "limits": {"fetch": 2, "gm": 1, "tracker": 2, "mod": 3, "mod_gpu": 1, "mod_cpu": 1},
    "disabled_modules": [],
    "min_free_gb": 60.0,
    "cleanup": False,
    "retry_failed": False,
    "stop": False,
}


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def jload(path: str, default=None):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def jsave(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(tmp, path)


def log(msg: str) -> None:
    line = f"{now()} {msg}"
    print(line, flush=True)
    with io.open(os.path.join(TS, "orchestrator.log"), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def free_gb() -> float:
    return shutil.disk_usage(TS).free / 1e9


def paths(video: str) -> dict:
    return {
        "video": os.path.join(TS, "videos", video),
        "part": os.path.join(TS, "videos", video + ".part"),
        "prod_dir": os.path.join(TS, "prod", video),
        "prod_gm": os.path.join(TS, "prod", video, f"general_model{video}.ndjson"),
        "prod_trk": os.path.join(TS, "prod", video, f"trackers{video}.ndjson"),
        "gm_dir": os.path.join(TS, "gm_v2", video),
        "gm_compat": os.path.join(TS, "gm_v2", video, f"general_model{video}-second_run.ndjson"),
        "gm_report": os.path.join(TS, "gm_v2", video, f"gm_v2_report{video}.json"),
        "trk_dir": os.path.join(TS, "trk_v2", video),
        "trk_compat": os.path.join(TS, "trk_v2", video, f"trackers{video}.ndjson"),
        "trk_bus": os.path.join(TS, "trk_v2", video, f"trackers{video}-v2bus.ndjson"),
        "trk_report": os.path.join(TS, "trk_v2", video, f"tracker_v2_report{video}.json"),
        "v2_inf": os.path.join(TS, "v2_inf", video),
        "logs": os.path.join(TS, "logs", video),
    }


def module_out(label: str, video: str, module: str) -> str:
    return os.path.join(TS, "modules", label, video, f"{module}.json")


def link_into(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


class Plan:
    def __init__(self, videos: list | None = None):
        self.plan = jload(os.path.join(TS, "plan.json"))
        self.inventory = {r["video"]: r for r in jload(os.path.join(TS, "videos_inventory.json"))}
        events = sorted(self.plan["events"], key=lambda e: sum(self.inventory[v]["size"] for v in e["videos"]))
        order = []
        for e in events:
            for v in e["videos"]:
                if v not in order:
                    order.append(v)
        self.order = [v for v in order if videos is None or v in videos]
        self.runs_by_video = collections.defaultdict(list)
        for r in self.plan["runs"]:
            self.runs_by_video[r["video"]].append(r)
        self.camera = {v: c["camera"] for e in self.plan["events"] for v, c in e["cameras"].items()}
        self.airplane = {v: e["airplane_type"] for e in self.plan["events"] for v in e["videos"]}
        self.refresh()

    def refresh(self) -> None:
        self.camera_ov = jload(os.path.join(TS, "camera_overrides.json"), {}) or {}
        self.airplane_ov = jload(os.path.join(TS, "airplane_overrides.json"), {}) or {}

    def cone(self, video: str) -> bool:
        return (self.camera_ov.get(video) or self.camera.get(video, "cone")) == "cone"

    def airplane_type(self, video: str):
        return self.airplane_ov[video] if video in self.airplane_ov else self.airplane.get(video)

    def modules(self, video: str) -> list:
        return sorted({r["module"] for r in self.runs_by_video.get(video, [])})


def upstream(step: str) -> list:
    if step == "gm":
        return ["fetch"]
    if step == "tracker":
        return ["gm"]
    if step.startswith("mod:ctl:"):
        return ["fetch"]
    if step.startswith("mod:v2:"):
        return ["tracker"]
    return []


def step_enabled(step: str, ctl: dict) -> bool:
    if step.startswith("mod:"):
        _, label, module = step.split(":", 2)
        return f"mod:{label}" in ctl["steps"] and module not in set(ctl.get("disabled_modules") or [])
    return step in ctl["steps"]


def job_class(step: str) -> str:
    if step.startswith("mod:"):
        prof = profiles.profile(step.split(":", 2)[2])
        return prof.get("job_class") or ("mod" if prof["pixel_free"] else "mod_gpu")
    return step


def load_ledger(video: str) -> dict:
    led = jload(os.path.join(TS, "ledger", f"{video}.json"), None) or {"video": video, "steps": {}}
    led.setdefault("steps", {})
    return led


def save_ledger(led: dict) -> None:
    jsave(os.path.join(TS, "ledger", f"{led['video']}.json"), led)


# ---------------------------------------------------------------- records built from the artefacts on disk


def gm_record(video: str) -> dict:
    p = paths(video)
    rep = jload(p["gm_report"], {}) or {}
    tol = rep.get("parity_vs_production_tolerant") or {}
    link_into(p["gm_compat"], os.path.join(p["v2_inf"], f"general_model{video}.ndjson"))
    return {
        "status": "done",
        "frames": rep.get("number_of_frames"),
        "ms_per_frame": (rep.get("timings_ms_per_frame") or {}).get("end_to_end"),
        "parity": {k: tol.get(k) for k in ("pair_recall", "frame_parity_tolerant", "dets_a", "dets_b", "unmatched_a",
                                           "unmatched_b")},
        "camera_type": rep.get("camera_type"),
        "airplane_type": rep.get("airplane_type"),
    }


def tracker_record(video: str) -> dict:
    p = paths(video)
    rep = jload(p["trk_report"], {}) or {}
    par = next(iter((rep.get("parity") or {}).values()), {})
    cf = par.get("consumed_fields") or {}
    link_into(p["trk_compat"], os.path.join(p["v2_inf"], f"trackers{video}.ndjson"))
    return {
        "status": "done",
        "cone_camera": rep.get("cone_camera"),
        "frames": rep.get("frames"),
        "ms_per_frame": rep.get("ms_per_frame_total"),
        "parity": {k: cf.get(k) for k in ("frames_compared", "frame_parity", "objects_a", "objects_b", "objects_matched",
                                          "unique_identities_a", "unique_identities_b")},
    }


def module_record(label: str, video: str, module: str) -> dict:
    r = jload(module_out(label, video, module), {}) or {}
    rec = {"status": "failed" if "error" in r or not r else "done", "verdict": r.get("status"),
           "seconds": r.get("seconds"), "cone_camera": r.get("cone_camera"), "airplane_type": r.get("airplane_type"),
           "no_video": r.get("no_video"), "module_dir": r.get("module_dir_arg") or "",
           "module_source": r.get("module_source")}
    if "error" in r:
        rec["error"] = r["error"][:300]
    return rec


def stale(step: str, rec: dict, video: str, plan: Plan) -> bool:
    """A result produced with other camera / aircraft-type flags than the current ones."""
    if step == "tracker":
        return rec.get("cone_camera") is not None and bool(rec["cone_camera"]) != plan.cone(video)
    if step.startswith("mod:"):
        if rec.get("cone_camera") is None:
            return False
        if (rec.get("module_dir") or "") != profiles.profile(step.split(":", 2)[2])["module_dir"]:
            return True
        at = plan.airplane_type(video)
        return (rec["cone_camera"] == "true") != plan.cone(video) or (rec.get("airplane_type") or None) != (at or None)
    return False


def adopt(step: str, video: str, plan: Plan):
    """Record for a step whose artefacts already exist on disk (produced earlier or by another process), else None."""
    p = paths(video)
    if step == "fetch":
        ok = (os.path.exists(p["video"]) and os.path.getsize(p["video"]) == plan.inventory[video]["size"]
              and os.path.exists(p["prod_gm"]) and os.path.exists(p["prod_trk"]))
        return {"status": "done", "adopted": True} if ok else None
    if step == "gm" and os.path.exists(p["gm_report"]) and os.path.exists(p["gm_compat"]):
        return {**gm_record(video), "adopted": True}
    if step == "tracker" and os.path.exists(p["trk_report"]) and os.path.exists(p["trk_compat"]):
        rec = {**tracker_record(video), "adopted": True}
        return None if stale(step, rec, video, plan) else rec
    if step.startswith("mod:"):
        _, label, module = step.split(":", 2)
        if os.path.exists(module_out(label, video, module)):
            rec = {**module_record(label, video, module), "adopted": True}
            return None if stale(step, rec, video, plan) else rec
    return None


# ---------------------------------------------------------------- commands


def build_cmd(step: str, video: str, plan: Plan):
    p = paths(video)
    if step == "fetch":
        return [PY, "scripts/testset/fetch.py", "--videos", video, "--what", "video,gm,trackers", "--workers", "3"], None
    if step == "gm":
        return [PY, "scripts/gm_v2_run.py", "--video", p["video"], "--weights-dir", GM_WEIGHTS, "--variant", "entity_clip",
                "--parallel-heads", "--out-dir", p["gm_dir"], "--compare", p["prod_gm"]], None
    if step == "tracker":
        cmd = [PY, "scripts/tracker_v2_run.py", "--video", p["video"], "--gm-ndjson", p["gm_compat"], "--seed", "0",
               "--exact-fast", "--no-profile", "--out-dir", p["trk_dir"], "--compare", p["prod_trk"]]
        return cmd + (["--cone-camera"] if plan.cone(video) else []), None
    _, label, module = step.split(":", 2)
    prof = profiles.profile(module)
    inf = p["prod_dir"] if label == "ctl" else p["v2_inf"]
    launcher = prof.get("launcher")
    rel = (lambda x: os.path.relpath(x, ROOT).replace("\\", "/")) if launcher else (lambda x: x)
    cmd = (list(launcher) if launcher else [PY, "scripts/run_module.py"]) + [
        "--module", module, "--video", video, "--inferences-dir", rel(inf),
        "--device", prof["device"], "--cone-camera", "true" if plan.cone(video) else "false",
        "--out", rel(module_out(label, video, module))]
    if os.path.exists(p["video"]):
        cmd += ["--videos-dir", rel(os.path.join(TS, "videos"))]
    else:
        cmd.append("--no-video")
    if prof["numpy1"]:
        cmd.append("--numpy1-scalars")
    if plan.airplane_type(video):
        cmd += ["--airplane-type", plan.airplane_type(video)]
    for x in prof["prepend_path"]:
        cmd += ["--prepend-path", x]
    if prof["drop_state_keys"]:
        cmd += ["--drop-state-keys", prof["drop_state_keys"]]
    if prof["module_dir"]:
        cmd += ["--module-dir", prof["module_dir"]]
    return cmd, dict(os.environ, **profiles.ENV)


class Job:
    def __init__(self, video: str, step: str, cmd: list, env):
        self.video, self.step, self.cmd = video, step, cmd
        self.log = os.path.join(paths(video)["logs"], step.replace(":", "_") + ".log")
        os.makedirs(os.path.dirname(self.log), exist_ok=True)
        self.fh = io.open(self.log, "w", encoding="utf-8")
        self.fh.write(" ".join(cmd) + "\n")
        self.fh.flush()
        self.t0 = time.time()
        self.proc = subprocess.Popen(cmd, cwd=ROOT, stdout=self.fh, stderr=subprocess.STDOUT, env=env)

    def poll(self):
        rc = self.proc.poll()
        if rc is not None and not self.fh.closed:
            self.fh.close()
        return rc


def finish(job: Job, rc: int, plan: Plan) -> dict:
    led = load_ledger(job.video)
    p = paths(job.video)
    rec = {"status": "failed", "rc": rc}
    try:
        if job.step == "fetch":
            rec = adopt("fetch", job.video, plan) or {"status": "failed", "rc": rc, "error": "files incomplete"}
        elif job.step == "gm":
            rec = gm_record(job.video) if rc == 0 and os.path.exists(p["gm_report"]) else rec
        elif job.step == "tracker":
            rec = tracker_record(job.video) if rc == 0 and os.path.exists(p["trk_report"]) else rec
        else:
            _, label, module = job.step.split(":", 2)
            rec = module_record(label, job.video, module)
    except Exception as e:  # a broken artefact must not stop the orchestrator
        rec = {"status": "failed", "rc": rc, "error": f"{type(e).__name__}: {e}"}
    rec.update({"seconds_wall": round(time.time() - job.t0, 1), "log": job.log, "finished": now()})
    led["steps"][job.step] = rec
    save_ledger(led)
    return rec


def cleanup_video(video: str, plan: Plan, ctl: dict) -> bool:
    led = load_ledger(video)
    if led.get("cleaned"):
        return False
    mods = [f"mod:{lb}:{m}" for lb in ("ctl", "v2") for m in plan.modules(video)]
    mods = [s for s in mods if step_enabled(s, ctl)]
    if not mods or any(led["steps"].get(s, {}).get("status") not in ("done", "failed") for s in mods):
        return False
    p = paths(video)
    freed = 0
    for f in (p["video"], p["trk_bus"]):
        if os.path.exists(f):
            freed += os.path.getsize(f)
            os.remove(f)
    led["cleaned"] = {"at": now(), "freed_gb": round(freed / 1e9, 2)}
    save_ledger(led)
    return True


# ---------------------------------------------------------------- main loop


def read_control() -> dict:
    ctl = json.loads(json.dumps(DEFAULT_CONTROL))
    ctl.update(jload(CONTROL, {}) or {})
    ctl["limits"] = {**DEFAULT_CONTROL["limits"], **(ctl.get("limits") or {})}
    return ctl


def chain_ok(step: str, led: dict, ctl: dict) -> bool:
    """Every upstream step is done, or enabled and itself able to progress."""
    for u in upstream(step):
        st = led["steps"].get(u, {}).get("status")
        if st == "done":
            continue
        if st == "failed" or not step_enabled(u, ctl) or not chain_ok(u, led, ctl):
            return False
    return True


def run(a) -> int:
    videos = None
    if a.videos:
        raw = io.open(a.videos[1:], encoding="utf-8").read().split() if a.videos.startswith("@") else a.videos.split(",")
        videos = [x.strip() for x in raw if x.strip()]
    plan = Plan(videos)
    if a.limit:
        plan.order = plan.order[: a.limit]
    ctl = read_control() if a.keep_control else json.loads(json.dumps(DEFAULT_CONTROL))
    if a.steps:
        ctl["steps"] = a.steps.split(",")
    if a.disabled_modules is not None:
        ctl["disabled_modules"] = [m for m in a.disabled_modules.split(",") if m]
    for k in ("gm", "tracker", "fetch", "mod", "mod_gpu", "mod_cpu"):
        v = getattr(a, f"limit_{k}")
        if v is not None:
            ctl["limits"][k] = v
    ctl["cleanup"] = a.cleanup or ctl.get("cleanup", False)
    ctl["stop"] = False
    if not a.dry_run:
        jsave(CONTROL, ctl)
    log(f"start: {len(plan.order)} videos, control {json.dumps(ctl)}")
    running: list = []
    last_idle = 0.0
    while True:
        if not a.dry_run:
            ctl = read_control()
        plan.refresh()
        importlib.reload(profiles)
        if ctl.get("retry_failed"):
            n = 0
            for video in plan.order:
                led = load_ledger(video)
                for s, r in list(led["steps"].items()):
                    if r.get("status") == "failed":
                        del led["steps"][s]
                        n += 1
                save_ledger(led)
            ctl["retry_failed"] = False
            jsave(CONTROL, ctl)
            log(f"retry_failed: reset {n} failed steps")
        for job in list(running):
            rc = job.poll()
            if rc is None:
                continue
            running.remove(job)
            rec = finish(job, rc, plan)
            extra = {k: rec[k] for k in ("verdict", "ms_per_frame", "parity", "error") if rec.get(k) is not None}
            log(f"{job.step} {job.video} -> {rec['status']} ({rec['seconds_wall']} s) {json.dumps(extra)[:400]}")
        busy = {(j.video, j.step) for j in running}
        counts = collections.Counter(job_class(j.step) for j in running)
        pending, starts = 0, []
        for video in plan.order:
            led = load_ledger(video)
            p = paths(video)
            steps = [s for s in ("fetch", "gm", "tracker") if step_enabled(s, ctl)]
            steps += [f"mod:{lb}:{m}" for lb in ("v2", "ctl") for m in plan.modules(video)
                      if step_enabled(f"mod:{lb}:{m}", ctl)]
            for step in steps:
                rec = led["steps"].get(step)
                if rec and rec.get("status") == "done" and stale(step, rec, video, plan) and not a.dry_run:
                    log(f"{step} {video}: stale flags, redo")
                    del led["steps"][step]
                    save_ledger(led)
                    rec = None
                if rec and rec.get("status") in ("done", "failed"):
                    continue
                if not chain_ok(step, led, ctl):
                    continue
                pending += 1
                if (video, step) in busy or ctl.get("stop"):
                    continue
                if not all(led["steps"].get(u, {}).get("status") == "done" for u in upstream(step)):
                    continue
                adopted = adopt(step, video, plan)
                if adopted:
                    pending -= 1
                    if a.dry_run:
                        print("would adopt", step, video)
                    else:
                        adopted["finished"] = now()
                        led["steps"][step] = adopted
                        save_ledger(led)
                    continue
                if step.startswith("mod:") and not os.path.exists(p["video"]) \
                        and not profiles.profile(step.split(":", 2)[2])["pixel_free"]:
                    if led["steps"].get("fetch", {}).get("status") == "done" and not a.dry_run:
                        del led["steps"]["fetch"]
                        led.pop("cleaned", None)
                        save_ledger(led)
                        log(f"{video}: video needed again by {step}, fetching")
                    continue
                if step == "fetch" and (free_gb() < ctl["min_free_gb"] or (
                        os.path.exists(p["part"]) and time.time() - os.path.getmtime(p["part"]) < 180)):
                    continue
                klass = job_class(step)
                if counts[klass] >= ctl["limits"].get(klass, 1):
                    continue
                cmd, env = build_cmd(step, video, plan)
                counts[klass] += 1
                busy.add((video, step))
                starts.append((video, step, cmd, env))
        if a.dry_run:
            for video, step, cmd, _ in starts:
                print("would start", step, video, " ".join(cmd)[:300])
            print(f"pending {pending}")
            return 0
        for video, step, cmd, env in starts:
            running.append(Job(video, step, cmd, env))
            log(f"{step} {video} started")
        if ctl.get("cleanup"):
            for video in plan.order:
                if cleanup_video(video, plan, ctl):
                    log(f"{video}: cleaned {load_ledger(video)['cleaned']}")
        if not running and (pending == 0 or ctl.get("stop")):
            log(f"exit: pending {pending}, stop {ctl.get('stop')}")
            return 0
        if not running and not starts and time.time() - last_idle > 600:
            log(f"idle: {pending} pending steps wait for downloads / disk (free {free_gb():.0f} GB)")
            last_idle = time.time()
        time.sleep(a.poll)


def status(a) -> int:
    plan = Plan()
    counts = collections.defaultdict(collections.Counter)
    gm, trk, errors = [], [], collections.Counter()
    for video in plan.order:
        led = load_ledger(video)
        for step, rec in led["steps"].items():
            key = ":".join(step.split(":")[:2])
            counts[key][rec.get("status")] += 1
            if rec.get("status") == "failed":
                errors[(step.split(":")[-1], (rec.get("error") or f"rc {rec.get('rc')}")[:90])] += 1
        if led["steps"].get("gm", {}).get("status") == "done":
            gm.append(led["steps"]["gm"])
        if led["steps"].get("tracker", {}).get("status") == "done":
            trk.append(led["steps"]["tracker"])
    for k, c in counts.items():
        print(f"{k:10s} {dict(c)}")
    if gm:
        frames = sum(r.get("frames") or 0 for r in gm)
        ms = sum((r.get("ms_per_frame") or 0) * (r.get("frames") or 0) for r in gm) / max(frames, 1)
        rec = [r["parity"]["pair_recall"] for r in gm if (r.get("parity") or {}).get("pair_recall") is not None]
        print(f"GM v2: {len(gm)} videos, {frames} frames, {ms:.1f} ms/frame (frame-weighted), pair recall min "
              f"{min(rec) if rec else None}")
    if trk:
        frames = sum(r.get("frames") or 0 for r in trk)
        ms = sum((r.get("ms_per_frame") or 0) * (r.get("frames") or 0) for r in trk) / max(frames, 1)
        om = [r["parity"]["objects_matched"] / max(r["parity"]["objects_a"] or 1, 1) for r in trk
              if (r.get("parity") or {}).get("objects_matched") is not None]
        print(f"Tracker v2: {len(trk)} videos, {frames} frames, {ms:.1f} ms/frame, objects matched min "
              f"{min(om) if om else None}")
    for (m, e), n in errors.most_common(20):
        print(f"  failed x{n}: {m}: {e}")
    print(f"free disk {free_gb():.0f} GB")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--steps", default=None, help="comma list of fetch,gm,tracker,mod:ctl,mod:v2")
    r.add_argument("--disabled-modules", default=None)
    r.add_argument("--videos", default=None, help="comma list or @file")
    r.add_argument("--limit", type=int, default=None, help="first N videos in plan order")
    for k in ("gm", "tracker", "fetch", "mod", "mod_gpu", "mod_cpu"):
        r.add_argument(f"--limit-{k.replace('_', '-')}", dest=f"limit_{k}", type=int, default=None)
    r.add_argument("--cleanup", action="store_true")
    r.add_argument("--keep-control", action="store_true", help="start from the existing control file")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--poll", type=float, default=10.0)
    sub.add_parser("status")
    a = ap.parse_args()
    return run(a) if a.cmd == "run" else status(a)


if __name__ == "__main__":
    raise SystemExit(main())
