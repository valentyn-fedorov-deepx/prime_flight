"""Causal second-run rows — the rows the tracker and the modules read, produced frame by frame from the decisions made so far.

v1 writes the second-run file after the end of the video with FINAL per-video values: the longest main-aircraft track (its box
on the frames it covers), the mode of its heights (written into the class-2 row), the main front wheel and the side-obstacle
regions. `pf.gm.compat_writer.second_run_rows` is a pure per-frame function of those values, so the streaming branch can call it
with the values as they stand at frame t (ADR-001 §2, "decided at frame X"):

  * main-aircraft box: frame t's box of the CURRENT longest track, looked up live every frame;
  * mode height, front wheel, side regions: refreshed every `refresh_every` frames (one transport chunk by default), and
    immediately when a main track first appears or the longest track changes.

Streaming rows differ from the batch file wherever a decision was not final yet — before the main track is established, while
the mode height or the layout still move, and on frames where the track that is longest at t is not the one that is longest at
the end. `pf.eval.compare_gm_ndjson_tolerant(batch_file, streaming_file)` measures that difference.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pf.gm.compat_writer import CompatContext, second_run_rows
from pf.gm.rows import ClassMap


@dataclass
class CausalRowStats:
    frames: int = 0
    frames_with_aircraft_row: int = 0
    refreshes: int = 0
    main_track_switches: int = 0
    first_aircraft_row_frame: int | None = None


@dataclass
class CausalSecondRun:
    context: object  # VideoContextV2, already updated with frame t before rows(t) is called
    cm: ClassMap
    refresh_every: int = 60
    stats: CausalRowStats = field(default_factory=CausalRowStats)
    _tid: object = None
    _mode: int | None = None
    _layout: tuple = (None, False, False)
    _refreshed_at: int | None = None

    def _current_box(self, frame_id: int):
        aircraft = self.context.aircraft
        tid = aircraft.longest()
        if tid is None:
            return None, None
        planes = getattr(aircraft, "planes", None)
        frames = planes[tid].frames if planes is not None else aircraft.tracks[tid]
        return tid, frames.get(frame_id)

    def _refresh(self, frame_id: int) -> None:
        lay = self.context.layout.snapshot()
        ac = self.context.aircraft.snapshot()
        self._mode = ac.get("mode_plane_height")
        self._layout = (
            lay.get("main_front_wheel"),
            lay.get("left_side_obstacles_roi", False),
            lay.get("right_side_obstacles_roi", False),
        )
        self._refreshed_at = frame_id
        self.stats.refreshes += 1

    def rows(self, frame_id: int, first_run_rows) -> list:
        tid, box = self._current_box(frame_id)
        if tid is not None and tid != self._tid:
            if self._tid is not None:
                self.stats.main_track_switches += 1
            self._tid = tid
            self._refresh(frame_id)
        elif self._refreshed_at is None or frame_id - self._refreshed_at >= self.refresh_every:
            self._refresh(frame_id)
        if box is not None and self._mode is None:
            self._refresh(frame_id)
        wheel, left, right = self._layout
        ctx = CompatContext(
            main_front_wheel=wheel,
            left_side_obstacles_roi=left,
            right_side_obstacles_roi=right,
            plane_history={frame_id: box} if box is not None else {},
            mode_plane_height=self._mode,
        )
        self.stats.frames += 1
        if box is not None:
            self.stats.frames_with_aircraft_row += 1
            if self.stats.first_aircraft_row_frame is None:
                self.stats.first_aircraft_row_frame = frame_id
        return second_run_rows(first_run_rows, frame_id, ctx, self.cm)
