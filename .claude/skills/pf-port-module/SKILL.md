---
name: pf-port-module
description: Checklist for porting one DXGAT CV module to streaming/real-time — audit of passes/pixels/models/private tracker fields, stage and events, causality (main_stream.py template), batch↔stream parity, measurement on fail videos, update of module_map.json and the board. Argument — the module repo name (e.g. beltloader-chocks).
---

Module: `$ARGUMENTS` (repo in `external\<repo>`). Executed by the `module-porter` agent; `qa-parity` closes.

## 0. Card
- Find the module in `docs/04_modules.md` (stage, opens/closes, decision, verdict, components, attention) and in `docs/05_module_logic.md` (client Pass/Fail/NO logic, cameras, tier).
- If there is no card or the verdict is stale — fix `docs/streaming_ref/module_map.json`, run `python scripts/build_docs.py`.

## 1. Code audit (fill in the table in `tasks/notes/<ID>.md`)
| question | how to check |
|---|---|
| passes over the metadata | `grep -n "load_metadata\|enumerate(metadata" main.py` |
| reads pixels | `grep -n "get_im0s\|imread\|VideoCapture" -r .` |
| own models | `grep -n "onnx\|\.pth\|torch.load\|InferenceSession" -r .` |
| private tracker fields / local arrival stage | `grep -n "_p0\|_prev_p0\|_st\b\|arrival_frame\|departure_frame\|pushback" main.py` |
| cv_common / db_worker pin | `git -C <repo> submodule status` |
| frame count/fps without video | whether `dataset` is used after `load_source()` |

## 2. Stage and events
- Replace the local anchor computations with `anchors`/`events` from the contract (the sole owner is the stage detector).
- Define `opens`/`closes`; for lookback — the window from `anchors`.

## 3. Causality
- passes = 2 → find the "quantity from the future"; template `G:\gat-streaming\modules\aircraft-chocks\main_stream.py` (`_STREAM_SKIP`, online accumulation, median at report time; the order "add after the departure check").
- passes = 1 → no logic edits; gating only.

## 4. Parity and measurements (commands in `docs/08_repos.md`)
```
python -m streaming.runner --mod <repo> --entry main        ... --out out/batch.json
python -m streaming.runner --mod <repo> --entry main_stream ... --out out/stream.json   # or --no-video if it does not read pixels
python tools/compare_runs.py --batch out/batch.json --stream out/stream.json --gt data/gt_by_video.json
python tools/pick_balanced.py --check "<check name>"    # all fails + as many passes
python -m streaming.runner --mod <repo> --no-video --drop-at 0.3 0.6 --drop-mode fill ...   # chunk loss
```
- Table: video × batch × stream × shift; every discrepancy — a mechanism. The Not observed coverage change — separately.
- Decoder pinned, machine free, conditions recorded.

## 5. Semantics
- If prevention requires a different decision moment — **do not patch**: tag `trigger-change`, ADR, agreement of Ihor/Oksana.

## 6. Closing
- Branch `pf/<id>-<slug>`, minimal diff by hunks, a note with tables, the row in `tasks/BOARD.md` → `review`; `qa-parity` → `done`.
