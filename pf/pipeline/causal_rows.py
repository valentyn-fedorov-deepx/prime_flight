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

`main_rule` chooses the main aircraft at frame t:

  * `longest_so_far` (default, the rule above). An aircraft that taxied past earlier keeps the title until the arriving one has
    more frames than it; over the test set that hands the arriving aircraft over late or not at all around T_arr on 16 of 90
    videos and changed 36 module verdicts live (`docs/analysis/rt_module_cost.md`, section 7).
  * `largest_alive`: among the aircraft tracks that had a box within `alive_frames`, the one with the largest box; the held
    track is replaced only when it is no longer alive or another alive box is `switch_factor` times larger. Replayed over the
    test set it matches the batch choice on every frame of the arrival window on 83 of 90 videos, with no video under half.
    The mode height then comes from the held track, not from the longest one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mode

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
    main_rule: str = "longest_so_far"  # or "largest_alive"
    alive_frames: int = 16
    switch_factor: float = 1.5
    stats: CausalRowStats = field(default_factory=CausalRowStats)
    _held: object = None  # the PlaneHistory held by `largest_alive`
    _tid: object = None
    _mode: int | None = None
    _layout: tuple = (None, False, False)
    _refreshed_at: int | None = None

    def _largest_alive(self, frame_id: int, planes: dict):
        def area(hist) -> float:
            x1, y1, x2, y2 = hist.last_xyxy[:4]
            return max(0.0, x2 - x1) * max(0.0, y2 - y1)

        alive, seen = [], set()
        for tid, hist in planes.items():  # several norfair ids may alias one history
            if id(hist) in seen or hist.last_frame is None or frame_id - hist.last_frame > self.alive_frames:
                continue
            seen.add(id(hist))
            alive.append((tid, hist))
        if not alive:
            return None, None
        big_tid, big = max(alive, key=lambda item: area(item[1]))
        held_alive = self._held is not None and any(hist is self._held for _, hist in alive)
        if not held_alive or (big is not self._held and area(big) > self.switch_factor * area(self._held)):
            self._held = big
        tid = next(t for t, hist in alive if hist is self._held)
        return tid, self._held.frames.get(frame_id)

    def _current_box(self, frame_id: int):
        aircraft = self.context.aircraft
        if self.main_rule == "largest_alive" and getattr(aircraft, "planes", None) is not None:
            return self._largest_alive(frame_id, aircraft.planes)
        tid = aircraft.longest()
        if tid is None:
            return None, None
        planes = getattr(aircraft, "planes", None)
        frames = planes[tid].frames if planes is not None else aircraft.tracks[tid]
        return tid, frames.get(frame_id)

    def _refresh(self, frame_id: int) -> None:
        lay = self.context.layout.snapshot()
        if self.main_rule == "largest_alive" and self._held is not None:
            self._mode = mode([round(xyxy[3] - xyxy[1], -1) for xyxy in self._held.frames.values()])
        else:
            self._mode = self.context.aircraft.snapshot().get("mode_plane_height")
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
