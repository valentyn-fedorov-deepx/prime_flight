"""Chunk-wise General Model driver (ADR-001 §1–2): frames in, contract frames out, legacy artefact at event end.

    frame source ──► detectors (GM / chocks / vehicle) ──► first-run rows ──► VideoContextV2 (decided_at events)
                                                                  │
                                                                  ├──► pf.contract frames (schema 1.0) through pf.receiver.Session
                                                                  └──► at close(): v1-compat second-run ndjson for the 27 modules

The driver never looks at chunk boundaries: it consumes frames with absolute `frame_id`s (1-based) and lets `Session`
fill gaps. It can run without any model (`rows_provider`), which is how the pipeline mechanics are tested and how
recorded first-run rows can be replayed for parity work.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

from pf.contract import make_frame
from pf.gm.compat_writer import CompatContext, write_second_run_file
from pf.gm.context import VideoContextV2
from pf.gm.preprocessor import ImagePreprocessor
from pf.gm.rows import ClassMap, first_run_rows
from pf.receiver import Session

RowsProvider = Callable[[int, object], list]  # (frame_id, image) -> first-run rows


@dataclass
class Detectors:
    """The three v1 detector heads. Any of them may be None (then it contributes no rows).

    Runs through `MultiHeadRunner`: one upload per frame, one letterbox per input size, optional thread parallelism
    (`parallel=True`) — byte-identical rows to running each head on its own.
    """

    gm: object = None
    chocks: object = None
    vehicle: object = None
    parallel: bool = False
    _runner: object = field(default=None, repr=False)

    def _heads(self) -> dict:
        return {
            n: h
            for n, h in (("gm", self.gm), ("chocks", self.chocks), ("vehicle", self.vehicle))
            if h is not None
        }

    def rows(self, image, cm: ClassMap) -> list:
        heads = self._heads()
        if not heads:
            return []
        if self._runner is None:
            from pf.gm.heads import MultiHeadRunner  # lazy

            self._runner = MultiHeadRunner(heads, parallel=self.parallel)
        out = self._runner.predict_all(image)
        return first_run_rows(out.get("gm"), out.get("chocks"), out.get("vehicle"), cm)

    def timings(self) -> dict:
        return self._runner.timings() if self._runner is not None else {}


@dataclass
class GmStreamEvent:
    """Something the driver decided on a frame (mirrors v1's end-of-video values, but with a time stamp)."""

    frame_id: int
    name: str
    value: object = None


@dataclass
class GmStream:
    """One instance per event (X1). Feed frames in order; read contract frames and events; close to get artefacts."""

    cm: ClassMap
    event_id: str
    fps: int = 8
    detectors: Detectors | None = None
    rows_provider: RowsProvider | None = None
    context: VideoContextV2 = None
    session: Session = None
    raw_rows: dict = field(default_factory=dict)  # frame_id -> first-run rows (kept for the compat writer)
    preprocessor: ImagePreprocessor | None = (
        None  # v1 feeds every first-run frame through it (noise-adaptive blur)
    )
    events: list = field(default_factory=list)
    _closed: bool = False

    def __post_init__(self):
        if self.context is None:
            self.context = VideoContextV2(self.cm, fps=self.fps)
        if self.session is None:
            self.session = Session(self.event_id, fps=self.fps)
        if self.detectors is None and self.rows_provider is None:
            raise ValueError("GmStream needs detectors or a rows_provider")
        if self.preprocessor is None and self.detectors is not None:
            self.preprocessor = ImagePreprocessor()

    # ---------------------------------------------------------------- per frame
    def _rows_for(self, frame_id: int, image) -> list:
        if self.rows_provider is not None:
            return list(self.rows_provider(frame_id, image))
        if self.preprocessor is not None and image is not None:
            self.preprocessor.update(frame_id, image)
            image = self.preprocessor.get_preprocessed()
        return self.detectors.rows(image, self.cm)

    def _ingest(
        self,
        frame_id: int,
        image=None,
        *,
        entity_class_ids=None,
        is_cone=None,
        arrived: bool = False,
        departured: bool = False,
    ) -> dict:
        """Rows + context for one frame (no session I/O). Returns the contract frame."""
        if self._closed:
            raise RuntimeError(f"GmStream {self.event_id} is closed")
        rows = self._rows_for(frame_id, image)
        self.raw_rows[frame_id] = rows
        for name in self.context.update(
            frame_id,
            rows,
            image,
            entity_class_ids=entity_class_ids,
            is_cone=is_cone,
            arrived=arrived,
            departured=departured,
        ):
            self.events.append(GmStreamEvent(frame_id, name, self._decision_value(name)))
        return make_frame(frame_id, rows, [])

    def process(self, frame_id: int, image=None, **kw) -> list:
        """Process one frame delivered on its own (a chunk of one). Returns the contract frames released by the
        session (gap placeholders included)."""
        return self.session.feed_chunk([self._ingest(frame_id, image, **kw)])

    def process_chunk(self, frames: Iterable[tuple[int, object]], **kw) -> list:
        """One transport chunk: frames = iterable of (frame_id, image). Fed to the session as a single chunk."""
        contract_frames = [self._ingest(frame_id, image, **kw) for frame_id, image in frames]
        return self.session.feed_chunk(contract_frames) if contract_frames else []

    def _decision_value(self, name: str):
        snap = self.context.snapshot()
        return {
            "entity": snap.get("entity"),
            "aircraft_type": snap.get("aircraft_type"),
            "camera_type": snap.get("camera_type_cone"),
            "parts_layout": snap.get("main_nose") or snap.get("main_front_wheel"),
            "first_aircraft_seen": snap.get("frame_of_beginning"),
            "first_aircraft_track": snap.get("first_aircraft_track"),
        }.get(name)

    # ---------------------------------------------------------------- end of event
    def close(self, *, freeze_camera: bool = True) -> dict:
        """Freeze the remaining per-video decisions the v1 way (end of event) and return the final snapshot."""
        if not self._closed:
            last = max(self.raw_rows) if self.raw_rows else 0
            if freeze_camera:
                for name in self.context.finalize(last):
                    self.events.append(GmStreamEvent(last, name, self._decision_value(name)))
            self.session.close()
            self._closed = True
        return self.context.snapshot()

    def compat_context(self) -> CompatContext:
        return CompatContext.from_snapshot(self.context.snapshot())

    def iter_first_run(self) -> Iterator[tuple[int, list]]:
        for frame_id in sorted(self.raw_rows):
            yield frame_id, self.raw_rows[frame_id]

    def write_v1_compat(self, path: str) -> int:
        """Regenerate the legacy second-run ndjson (what the tracker and the 27 modules read)."""
        if not self._closed:
            self.close()
        return write_second_run_file(path, self.iter_first_run(), self.compat_context(), self.cm)

    def report(self) -> dict:
        """The subset of v1's Kafka report that GM v2 can produce (stages/statistics are left to the stage detector)."""
        snap = self.context.snapshot()
        return {
            "camera_type": snap.get("camera_type_cone"),
            "confidence_camera": snap.get("confidence_camera"),
            "entity": snap.get("entity"),
            "airplane_type": snap.get("aircraft_type"),
            "fps": self.fps,
            "number_of_frames": max(self.raw_rows) if self.raw_rows else 0,
            "decided_at": snap.get("decided_at", {}),
            "noise": self.preprocessor.snapshot() if self.preprocessor is not None else None,
            "session": {
                "frames_in": self.session.stats.frames_in,
                "frames_filled": self.session.stats.frames_filled,
                "chunks_in": self.session.stats.chunks_in,
            },
        }
