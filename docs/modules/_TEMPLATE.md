# How to write a module page

One page per module repository, `docs/modules/<repo>.md`. The pages are the source of the module documentation on the
shared drive (converted to Word with styling), so they follow this structure exactly.

## Audience and tone

- Readers: an engineer who has never opened the module, a PM, QA, someone from the client's side reading the rule.
- Plain English, short sentences, active voice. Explain abbreviations on first use: GSE (ground support equipment),
  BL (belt loader), GM (General Model).
- The top of the page is for everyone (what, when, the rule, how it decides); code details go only into *For developers*.
- Facts only, from the code and the listed sources. If something is unclear, write "to confirm" — never guess.
- Numbers always with units. Frames are converted to seconds at 8 fps: "**100 frames** (12.5 s)".
- No internal project jargon (no task ids, no agent names, no "E0 / I1 / NOW_PX" codes in the text).
- Length: 600–1200 words.

## Structure (headings exactly as below)

```
# <ID> · <Check name>            (several checks: "M02A, M02B, M02C · Aircraft chocks")

> <One or two sentences in plain language: what the module checks and how it knows.>

## At a glance

| | |
|---|---|
| Checks | <ID> · <check name> (one line per check) |
| Stage | <one or more of: Pre-arrival, Arrival, Post-arrival, Download, Upload, Pre-departure, Departure — comma-separated> |
| Looks at | <the time window in words, e.g. "from the moment the aircraft stops until 30 s later"> |
| Cameras | <cone camera / wing camera / both; for which aircraft type> |
| Uses | <General Model classes; tracks (which objects); video frames yes / no> |
| Own models | <none / name — what it does> |
| Runs on | <GPU / CPU> |
| Real time | <ready as is / ready, needs video frames / needs a small patch / needs a new first pass / post-processing only> — <one short reason> |
| Production version | <branch> @ <short commit> (<date>) |

## The rule (agreed with the client)

| Verdict | When |
|---|---|
| Pass | ... |
| Fail | ... |
| Not observed | ... |
| Not observed — view blocked | ... |

(several checks: one table per check, each under a "### <ID> · <check>" sub-heading)

## How it decides

1. <5–10 numbered steps in plain language, in the order the code runs; thresholds in **bold** with units>

## Settings

| Setting | Value | What it does |
|---|---|---|
| <name as in the config or code> | <value> | <effect on the verdict> |

(only the settings that change the verdict, at most about 12; say where a value in the YAML is NOT used by the code)

## What it reports

- <the verdict, the report fields, the smart-timeline entries, the annotated video if any>

## Known issues and limits

- <from TODO / FIXME in the code, hard-coded values that contradict the config, the known issues given in the sources,
  the "Attention" notes of the architecture review, limits you can see in the code (one camera, needs departure, …)>

## For developers

- **Repository:** `dxgat/detectors/<repo>`; production line `<branch>` @ `<commit>`; default branch `<branch>` @ `<commit>`
  (<what differs, one line; or "the same">).
- **Entry point:** `main.py` → `detect(...)`; key files and what each does.
- **Dependencies:** `cv_common` and `db_worker` submodule commits (`git ls-tree HEAD cv_common db_worker` in the repo, or
  "exported copy" for branch exports), notable Python packages, model weights (file names; DVC or in the repo).
- **Run locally:** how the module is started (arguments of `main.py`, `local_config.yaml`).
- **Code references:** `file.py:line` for each step of *How it decides*.
```

## Sources for each module

1. The code at the production path given in your task (read-only: never edit, never run git commands other than
   `log`, `show`, `ls-tree`, `diff`, `rev-parse`).
2. `G:\prime_flight\docs\04_modules.md` — the module's section (inputs, outputs, local policy, attention, streaming audit).
3. `G:\prime_flight\docs\05_module_logic.md` — the client rule (Pass / Fail / Not observed / obstacles) and cameras.
4. `G:\prime_flight\docs\streaming_ref\module_map.json` — stage, opens / closes, real-time verdict and why.
5. `G:\prime_flight\docs\analysis\module_consumption.md` and `module_dataset_needs.md` — what the module reads from the
   General Model and the trackers, which classes it needs.
6. `G:\prime_flight\docs\analysis\module_compute\*.md` — models, per-frame work (search for the module name).
7. `C:\Users\valik\AppData\Local\Temp\claude\G--prime-flight\1b71bc4e-d91c-441a-8b86-20aec5a75b6e\scratchpad\drive\confluence\modules_extra.json`
   — logic-diagram links and known issues from the Confluence modules database.
8. `G:\prime_flight\docs\reports\PF_our_models_by_module.xlsx` — our trained models per module (sheet "Modules - our models").

Real-time wording from `module_map.json` verdicts: NOW → "ready as is"; NOW_PX → "ready, needs video frames";
PATCH → "needs a small patch"; RETHINK → "needs a new first pass"; POST → "post-processing only".
