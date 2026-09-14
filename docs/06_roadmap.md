# Prime Flight — 12-month roadmap

Sources: the slide "Prime Flight — 12-Month High-Level Roadmap" + the lead's post in Slack (delivery by quarter).
The main business KPI is **Time to Result** (from the end of the event to the result on RampVision). The targets are illustrative,
subject to validation by measurements (baseline: PF-Q1-08).

## September — planning
- Confirm the baseline and the delivery KPI.
- Agree on the architecture direction (two branches, stage detector as the orchestrator, hierarchy GM → group → module).
- Confirm the roadmap priorities and assumptions (roadmap deadline ≥3 months: Sun 14.09.2026).

## Q1 (months 1–3) — Continuous Upload + Faster Post-Processing

**What we do.** A minimal change of the current architecture with the maximum gain in time:
1. CameraBox uploads chunks over **Wi-Fi/SIM during recording**, everything else stays as it is → we remove the long wait before upload.
2. **Stage detector** + we remove merge from the early stage: we do not wait until all chunks are merged, but run GM/tracker/modules
   **per chunk** and get the result faster. Merge stays for the archive and the post modules.
3. In parallel Valentyn + Yurii **fix the GM and Tracker** (contract hygiene, `schema_version`, one tracker per event,
   field leakage, `pushback_attached` causally).

**Owners.** Items 1–2 — Maksym Chernyshev. Item 3 — Valentyn + Yurii Luchko.
**Delivery to the client.** Video starts arriving at the server while the CameraBox is still recording. Time to Result ~24h → ~15h.

## Q2 (months 4–6) — Real-Time Architecture Foundation

**What we do.**
1. Maksym prepares a **separate real-time branch** (per-frame, not per-chunk, upload; target up to ~3 s for the supported checks).
2. Valentyn + Yurii **adapt the GM and Tracker** to the RT branch (budget 125 ms/frame; RT-GM ≈ 6 classes; batching/ONNX).
3. We take **one first module** for integration into RT. Hedge strategy: there are modules that work from the contract alone and do not depend on
   GM/Tracker changes (E0: beltloader-chocks, pushback-does-not-start, pushback-pathway) — even if the GM/Tracker for RT
   are not ready in time, we show the client a module that already works in real-time.

**Delivery to the client.** The first CV modules give a result before the full video is merged and processed.

## Q3 (months 7–9) — Real-Time Expansion + Alerting

**What we do.**
1. We continue porting modules to RT (E0 → E1 → PATCH modules via the detector event).
2. **Aryan Singh — alerting**: backend alerts/notifications for important safety events (deduplication, quiet windows, MongoDB,
   endpoint, rendering on RampVision).
3. Maksym gets time for **architecture fixes**, finishing the branches, tech debt (unification of cv_common pins, gzip, dead models).
4. The "trigger change" track for S1 checks (safety zone, pathway, walkers, hand signals).

**Delivery to the client.** More priority modules in RT; important safety events trigger alerts for station managers.

## Q4 (months 10–12) — Maximum Real-Time Coverage + Optimization

**What we do.**
1. We port **all practically possible modules** to RT (E2 with models, E4/RETHINK; POST modules stay in the post branch).
2. **Optimize the GM and Tracker** (TensorRT/fp16, resolution, resources).
3. Optimization at the level of the architecture / other components (stage detector v1, receiver, reducing compute).
4. **Streaming of gates to RampVision** (live view of the gate).

**Delivery to the client.** The maximum of practical RT checks + optimized post-processing for the rest. Time to Result ~5–6h for the post part.

## Workstreams (horizontal)

| Workstream | Q1 | Q2 | Q3 | Q4 | Agent |
|---|---|---|---|---|---|
| Continuous data upload (CameraBox → SIM/Wi-Fi) | ██ | | | | pipeline-architect |
| Post-processing pipeline (merge + server-side; stays for the whole roadmap) | ██ | ░ | ░ | ░ | pipeline-architect |
| GM / Tracker / Stage Detector (faster post first, then RT) | ██ | ██ | ░ | ██ | gm-tracker-engineer, pipeline-architect |
| Real-time architecture (low-latency branch) | | ██ | ░ | ░ | pipeline-architect |
| CV modules → real-time (selected → progressively) | | ██ | ██ | ██ | module-porter |
| Backend alerts / notifications | | | ██ | ██ | alerting-engineer |
| Performance / resource optimization | | | | ██ | gm-tracker-engineer |
| Parity / measurement / labeling (cross-cutting) | ░ | ░ | ░ | ░ | qa-parity |

## KPI line

`Current ~24h → Q1 ~15h* → Q2 further reduced → Q3 further reduced → Q4 ~5–6h*` (for the post branch; RT checks — seconds
after the event, the lower bound = the tracker's event latency 4 s / 10 s).

## Risks (living section, updated by pm-coordinator)

- Transport from the gate (Wi-Fi/SIM, VPN, ≈4 Mbit/s × 2 cameras × N gates) — outside the CV zone, an infrastructure decision is needed.
- No GPU runner for nightly parity → regressions are visible only manually.
- Fail-case labels are almost empty for 3 of 4 first-queue checks → we do not declare "delivered" without a measurement on fail videos.
- Different cv_common pins in the modules → shared components (stage detector, contract) break modules silently.
- S1 checks are retrospective by their logic → RT without a trigger change gives no prevention.
- Production code differs from the review pins (GM a0157a4, tracker bd43c3c on the cv_common `tracker_optimization` line), and several
  production revisions are not accessible (cv_common d74eb096 for GM; 86731e4c, dd5b5547, 33c188d0 for 11 modules) → exact reproduction
  depends on archives; L2 runs some modules on a substituted revision.
- The workstation runtime differs from production (numpy 2.x vs 1.24, torch weights-only loading, fp16 kernels on another GPU) → some
  module checks fail for environment reasons (lead-marshaller) and GM rows are compared with a tolerance, not bit for bit.
- Streaming cannot reproduce v1's retroactive end-of-video decisions (obstacle rows before the aircraft arrives, the final mode height)
  → modules that depend on them change behaviour in RT; measured by the L2 gate on streaming outputs (`docs/analysis/streaming_v0.md`).
