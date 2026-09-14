_English translation of `G:/gat-streaming/docs/plan.md` (Ukrainian original), 2026-09-14._

# Streaming migration plan — one cycle

Full version with tables: [plan.html](plan.html) · [plan.png](plan.png)

## Readiness criteria
| # | criterion | state |
|---|---|---|
| D1 | chunked feed = end-to-end, bit-for-bit | done |
| D2 | production code of the 4 checks in stream mode | done |
| D3 | stage detector yields T_arr / T_dep / BL@door / BL leave causally; modules gated by stage | planned |
| D4 | batch ↔ stream verdict difference measured for each of the 4 | 2 of 4 |
| D5 | Nose wheel anchor shift ≤ 24 s or documented | planned |
| D6 | CI: fast gates + nightly run on a GPU runner | gates exist, no runner |
| D7 | honest report | planned |

**Not counted as delivered:** pushback-pathway, while recall is 0 of 4.

## Critical path
K1 contract v1.0 → K2 receiver + session registry → K3 detector v0 (T_arr, T_dep, BL@door, BL leave)
→ K4 pushback_attached causally → K5 gating → K6 wave 1 through the detector → K7 report.

The detector before the modules: 9 modules recompute the arrival stage themselves, 2 — pushback_attached.
Porting without the detector means touching them twice.

## In parallel
- **Measurements/labelling:** fails for Nose wheel (1 in 90); Main gear on all 30 fails; net per-frame cost
  for the 9 pixel modules; chunk loss fill/shift; pushback-pathway recall (45 s window, classes).
- **Outside our zone — ask in week 1:** GPU runner, uplink, VPN, interface to the alert bus.
- **Hygiene:** schema_version in trackers + field-leakage test; registry (crew-present full_name,
  seat-belts in the breakdown, aircraft/jet); dead model in wing-walkers; foreign model_name in `__main__`; gzip.

## Queue after the four
2a — 8 lightweight ones on dd5b554 in one process (only if fail labels exist) · 2b — bl_rear_cone,
3-stop, cones-are-removed · 3a — pixel modules without their own networks · 3b — with networks (vests last) ·
4 — two-pass ones (pin-verification patch; safety-zone, hand-signals — geometry from the buffer) ·
walk-around — post-processing.

## Weeks
1 decisions, contract, receiver skeleton, detector v0, external requests, hygiene, order the labelling ·
2 pushback_attached, gating, per-frame cost measurement, Main gear on 30 fails ·
3 wave 1 through the detector, discrepancies, chunk loss, pushback-pathway ·
4 nightly (if there is a runner), report, trial run of 2a.
