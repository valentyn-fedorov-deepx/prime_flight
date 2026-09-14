# scripts — what each tool is for

Every script has a docstring with its full usage (`python scripts/<name>.py -h`). GPU scripts write JSON reports; the numbers
that matter are copied into `docs/analysis/` and the task notes.

## Docs and workspace
| script | purpose |
|---|---|
| `build_docs.py` | regenerate `docs/03_components.md`, `04_modules.md`, `05_*` from the inventory JSON and the modules xlsx |
| `bootstrap.ps1` | set up the workstation (clones into `external/`, Python environment) |
| `inspect_ndjson.py` | quick look at a GM / tracker ndjson (classes, keys, sizes) |

## GM v2
| script | purpose |
|---|---|
| `gm_v2_run.py` | GM v2 on a video: first-run rows, v1-compat second-run file, report; `--parallel-heads`, `--provider tensorrt`, `--compare` production |
| `gm_v2_replay.py` | context and v1-compat writer from recorded first-run rows (no GPU); `--video --second-pass` adds camera type and `frame_stopped` |
| `gm_bench.py` | head scheduling benchmark (baseline / shared / parallel / TensorRT) with exact or tolerant parity |
| `gm_ep_probe.py` | which ORT execution provider and cuDNN search mode really runs, and what it costs |
| `gm_second_pass_probe.py` | v1 second pass (MobileSAM aircraft state, camera votes) on a full video; `--impl inline|module --dump-votes` |
| `summarize_gm_runs.py` | per-video table of GM v2 runs: speed and L1 parity against production |

## Tracker v2
| script | purpose |
|---|---|
| `vendor_tracker_v1.py` | regenerate `pf/tracker/_v1` from the pinned production sources (never edit that folder by hand) |
| `tracker_v1_profile.py` | run the unmodified production or master tracker on a slice with component timers; `--pin`, `--seed` |
| `tracker_v2_run.py` | `TrackerStream` on a slice or a video; `--seed`, `--exact-fast`, `--compare` (consumed fields + byte-level lines) |
| `tracker_speed_suite.py` | idle-machine table: production pin vs v2 port vs exact fast paths vs bus-only, with byte identity |
| `tracker_events.py` | T_ARR / T_DEP / BL_AT_DOOR / BL_LEAVE frames per tracker file and their differences |
| `win_shims/` | Windows stand-ins for cupy / cuCIM (bit-identical torch TV denoise) used by the profiling scripts |

## Stage detector and streaming
| script | purpose |
|---|---|
| `pushback_events.py` | PUSHBACK_ATTACHED: causal nose rule vs the offline replication of the production two-pass rule |
| `stream_pipeline.py` | streaming v0: chunks → GM v2 → causal rows → Tracker v2 → events → v2 bus; streaming-vs-batch comparison |

## Modules
| script | purpose |
|---|---|
| `run_module.py` | L2 gate: a production module as is on an inference directory (`--no-video` for pixel-free modules) |
