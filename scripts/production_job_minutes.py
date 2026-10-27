"""Per-video job times of the production pipeline from gs://cv-modules-logs: GM (21.10 production a0157a4, 22.10 the
speed-ups b6e1a3e), trackers (21.10) and the 27 module jobs (22.10 morning).

GM logs hold only their last lines, so the GM time is the start in the file name (UTC) to the upload. Trackers and
modules log from start to end; their clock is not always UTC, so their time is the last minus the first timestamp.
"""
import datetime as dt
import json
import re
import sys
import warnings

warnings.filterwarnings("ignore")
from google.cloud import storage  # noqa: E402

VIDEOS = ["fAkpu3dj2NIj", "ytQDROiCyhBh", "b8ijKDWsLlQi8W", "n96M7fASlhGn", "7PytHarRNqmT"]
TS = re.compile(rb"(20\d\d-\d\d-\d\d \d\d:\d\d:\d\d),\d{3}")
c = storage.Client()
out = {}
for v in VIDEOS:
    jobs = {}
    for b in c.list_blobs("cv-modules-logs", prefix=f"{v}.mp4/"):
        t = b.time_created.replace(tzinfo=None)
        if not (dt.datetime(2026, 10, 21) <= t < dt.datetime(2026, 10, 23)):
            continue
        name = b.name.split("/", 1)[1]
        m = re.match(r"(.+)-(\d{4}-\d\d-\d\dT-\d\d-\d\d-\d\d)\.logs$", name)
        if not m:
            continue
        job, start_s = m.group(1), m.group(2)
        if job == "general_model":
            start = dt.datetime.strptime(start_s, "%Y-%m-%dT-%H-%M-%S")
            key = "gm_prod" if t.day == 21 else "gm_opt"
            minutes = (t - start).total_seconds() / 60
        else:
            stamps = [dt.datetime.strptime(x.decode(), "%Y-%m-%d %H:%M:%S") for x in TS.findall(b.download_as_bytes())]
            if len(stamps) < 2:
                continue
            key = job
            minutes = (max(stamps) - min(stamps)).total_seconds() / 60
        if key not in jobs or t > jobs[key][1]:
            jobs[key] = (round(minutes, 1), t)
    out[v] = {k: m for k, (m, _) in jobs.items()}
json.dump(out, open(sys.argv[1], "w"), indent=1)  # docs/analysis/speed/production_job_minutes_<dates>.json
for v, j in out.items():
    mods = {k: m for k, m in j.items() if k not in ("gm_prod", "gm_opt", "trackers")}
    print(f"{v:15s} gm_prod {j.get('gm_prod')} gm_opt {j.get('gm_opt')} trackers {j.get('trackers')} "
          f"modules {len(mods)}: sum {sum(mods.values()):.1f} max {max(mods.values(), default=0):.1f} "
          f"({max(mods, key=mods.get) if mods else '-'})")
