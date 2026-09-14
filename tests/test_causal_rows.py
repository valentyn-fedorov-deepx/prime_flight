"""Causal second-run rows: nothing before the main track exists; identical to the batch rows once decisions are final."""

import pytest

pytest.importorskip("filterpy")

from pf.gm.compat_writer import second_run_rows  # noqa: E402
from pf.pipeline import GmStream  # noqa: E402
from pf.pipeline.causal_rows import CausalSecondRun  # noqa: E402
from test_gm_stream import CM, rows_provider  # noqa: E402  (pytest puts tests/ on sys.path)


def _run(n):
    gs = GmStream(CM, "ev-causal", rows_provider=rows_provider)
    causal = CausalSecondRun(gs.context, CM, refresh_every=60)
    rows = {}
    for f in range(1, n + 1):
        gs.process(f)
        rows[f] = causal.rows(f, gs.raw_rows[f])
    return gs, causal, rows


def test_no_aircraft_row_before_the_main_track_exists():
    _gs, causal, rows = _run(40)
    airplane = CM.id("airplane")
    first = causal.stats.first_aircraft_row_frame
    assert first is not None and first > 10  # the plane appears at frame 10; the track needs a few frames
    assert all(r[-1] != airplane for f in range(1, first) for r in rows[f])
    assert rows[first][-1][-1] == airplane and rows[first][-1][4] == 680  # mode height of a constant 680 px aircraft


def test_late_frames_equal_the_batch_rows():
    gs, causal, rows = _run(1200)
    gs.close()
    ctx = gs.compat_context()
    for f in range(1100, 1201):
        assert rows[f] == second_run_rows(gs.raw_rows[f], f, ctx, CM), f
    assert causal.stats.main_track_switches == 0
    assert causal.stats.refreshes >= 1200 // 60
