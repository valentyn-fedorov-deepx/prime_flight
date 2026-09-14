---
name: pf-parity
description: Run/assess batch↔stream parity for a Prime Flight module or task on the gat-streaming stand (test bench) G:\gat-streaming (level 1 gates, level 2 runner, level 3 drop test), check the measurement conditions (X4, cache, free machine, fail sample) and issue the verdict review→done or back. Argument — the module repo or a PF-ID.
---

Target: `$ARGUMENTS`. Executed by the `qa-parity` agent.

1. **Level 1** (always): `cd G:\gat-streaming && pytest -q` — contract, feed parity, session/numbering. Red → stop, report.
2. **Level 2** (if inferences/weights are available locally in `G:\gat-streaming\data`): batch vs stream via `streaming.runner`, then `tools/compare_runs.py`.
   No data → write exactly what is missing (inferences of which version, DVC weights, GCP credentials) and do not invent numbers.
3. **Level 3** (for modules without pixels): `--no-video --drop-at 0.3 0.6 --drop-mode fill` and `shift` — the difference = the price of a missing `frame_id`.
4. **Conditions checklist** (everything must be recorded in the task notes): the same decoder on both sides; a full turnaround, not a 60 s excerpt;
   file cache state; whether the machine is free; a balanced sample with fails or the "working eight".
5. **Verdict**:
   - `done` — 0 discrepancies or each one explained by a mechanism + a measurement on fail videos + conditions recorded;
   - back to `in-progress` — with a concrete reason (for example "recall on fail videos not measured", "decoder not pinned").
6. Write the result into `tasks/notes/<ID>.md` (section "How it was verified") and update the status in `tasks/BOARD.md`.
