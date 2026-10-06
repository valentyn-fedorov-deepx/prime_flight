# Reports for people outside the daily work

| File | What | How it is built |
|---|---|---|
| `PF_technical_audit_one_page.docx` (+ `.pdf`) | One-page digest of the architecture review of 7 September and the measurement campaign of 8 September - 1 October: system today, audit findings, what was built, measured results, plan, risks, decisions, next 90 days (6 October 2026) | `node scripts/reports/build_one_pager.js docs/reports/PF_technical_audit_one_page.docx` (needs the `docx` npm package); PDF through Word (`docx2pdf`) |
| `PF_technical_map_one_page.docx` (+ `.pdf`) | One-page technical map: which models run in GM, the tracker and the modules and what each costs, the heaviest modules, what the modules share (inputs, classes, models) and where logic is duplicated (6 October 2026) | `node scripts/reports/build_technical_map.js docs/reports/PF_technical_map_one_page.docx` |
| `PF_technical_audit_state.docx` (+ `.pdf`, `audit_inventory.json`) | The audit as an inventory of the current state for management (7 pages, landscape): the chain and its times, the shared models with files and versions, every module with its check, window, inputs, own models, pins and run times, the models inside the modules with sha256, where the logic repeats, the review's attention notes (6 October 2026) | `python scripts/reports/audit_inventory.py && python scripts/reports/build_audit_docx.py` (python-docx) |

The same digest lives as an editable doc for comments: https://claude.ai/code/artifact/3348e74d-ebd6-4f64-b001-fcaa5523e284
