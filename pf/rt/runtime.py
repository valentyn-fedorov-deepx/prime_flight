"""Wall-clock simulation of the real-time branch: CameraBox chunks -> receiver -> decoder -> module adapter -> outputs.

Threads: the CameraBox simulator delivers chunk arrivals on the wall clock (lost chunks are simply not delivered); the
decoder thread takes releases from the receiver in recording order, decodes each chunk file with OpenCV (the pinned decoder,
X4; the decoded frame count is checked against the manifest) and puts frames into a bounded queue; the module loop feeds the
adapter frame by frame and writes every output to the sink the moment it is returned. A module slower than real time fills
the frame queue, then the decoder waits, then chunks pile up in the receiver: the backlog is sampled at every stage, so
falling behind shows up as growing latency and queue depth, never as silently dropped frames.

Per frame the run records: capture (camera clock), chunk closed, chunk arrived, decode start/end, processing start/end.
Per output: the frame it refers to and the moment it was emitted; result latency = emitted - capture time of that frame.
"""

from __future__ import annotations

import io
import json
import os
import queue
import threading
import time
from dataclasses import asdict, dataclass, field

import numpy as np

from pf.rt.cambox import CameraBoxSim, LinkModel
from pf.rt.receiver import ChunkReceiver

_END = object()


@dataclass
class Frame:
    frame_id: int  # absolute, 1-based
    image: object | None  # BGR uint8 array; None for a placeholder of a lost chunk
    capture_t: float  # monotonic moment the camera captured the frame
    chunk_index: int | None
    closed_t: float | None = None  # when its chunk was closed by the camera
    arrived_t: float | None = None  # when its chunk reached the server
    decode_start_t: float = 0.0
    decoded_t: float = 0.0
    missing: bool = False


@dataclass
class Output:
    kind: str  # "event" | "alert" | "verdict" | "note"
    name: str
    frame_id: int | None  # the frame the output refers to (its evidence); None for session-level outputs
    payload: dict = field(default_factory=dict)
    emitted_t: float = 0.0


class Adapter:
    """A CV module seen by the real-time branch: frames in, outputs out, no chunks."""

    name = "adapter"

    def start(self, fps: float) -> None:
        self.fps = fps

    def on_frame(self, frame: Frame) -> list:
        return []

    def close(self) -> list:
        return []


def subset_manifest(manifest: dict, max_seconds: float | None) -> dict:
    """The chunks that close within the first `max_seconds` of recording (for shorter runs)."""
    if not max_seconds:
        return manifest
    chunks = [c for c in manifest["chunks"] if c["t_end"] <= max_seconds + 1e-9]
    return {**manifest, "chunks": chunks, "n_chunks": len(chunks), "n_frames": sum(c["n_frames"] for c in chunks)}


def _pct(values, qs=(50, 95, 99, 100)) -> dict:
    if len(values) == 0:
        return {}
    arr = np.asarray(values, dtype=float)
    return {("max" if q == 100 else f"p{q}"): round(float(np.percentile(arr, q)), 3) for q in qs}


class RealtimeRun:
    def __init__(self, chunk_dir: str, manifest: dict, adapter: Adapter, link: LinkModel | None = None,
                 speed: float = 1.0, frame_queue: int = 64, reorder_timeout_s: float = 2.0, out_dir: str | None = None,
                 sample_s: float = 1.0):
        # absolute paths: a production-module adapter changes the working directory to the module's folder
        self.chunk_dir, self.manifest, self.adapter = os.path.abspath(chunk_dir), manifest, adapter
        self.link, self.speed = link or LinkModel(), speed
        self.frame_queue, self.reorder_timeout_s, self.sample_s = frame_queue, reorder_timeout_s, sample_s
        self.out_dir = os.path.abspath(out_dir) if out_dir else None
        self.fps = float(manifest["fps"])
        self.frames: list = []
        self.outputs: list = []
        self.samples: list = []
        self.decode_mismatches: list = []
        self.error: str | None = None

    # ------------------------------------------------------------------ stages

    def _decode(self, receiver: ChunkReceiver, frames_q: queue.Queue, sim: CameraBoxSim) -> None:
        import cv2

        try:
            while True:
                rel = receiver.next()
                if rel is None:
                    break
                if rel.arrival is None:  # lost range: placeholder frames, ids kept
                    for fid in range(rel.first_frame_id, rel.first_frame_id + rel.n_frames):
                        now = time.monotonic()
                        frames_q.put(Frame(fid, None, sim.capture_time(fid), None, decode_start_t=now, decoded_t=now,
                                           missing=True))
                    continue
                a = rel.arrival
                closed_t = sim.t0 + a.t_end / self.speed
                cap = cv2.VideoCapture(a.path)
                decoded = 0
                for fid in range(a.first_frame_id, a.first_frame_id + a.n_frames):
                    t_start = time.monotonic()
                    ok, image = cap.read()
                    t_end = time.monotonic()
                    if not ok:
                        break
                    decoded += 1
                    frames_q.put(Frame(fid, image, sim.capture_time(fid), a.index, closed_t, a.arrived, t_start, t_end))
                extra = 0
                while decoded == a.n_frames and cap.read()[0]:
                    extra += 1
                cap.release()
                if decoded != a.n_frames or extra:
                    self.decode_mismatches.append({"chunk": a.index, "manifest": a.n_frames, "decoded": decoded, "extra": extra})
                    for fid in range(a.first_frame_id + decoded, a.first_frame_id + a.n_frames):
                        now = time.monotonic()
                        frames_q.put(Frame(fid, None, sim.capture_time(fid), a.index, closed_t, a.arrived, now, now, True))
        except Exception as e:  # surface decoder failures in the report instead of hanging the run
            self.error = f"decoder: {type(e).__name__}: {e}"
        finally:
            frames_q.put(_END)

    def _sample(self, receiver: ChunkReceiver, frames_q: queue.Queue, sim: CameraBoxSim, stop: threading.Event) -> None:
        while not stop.wait(self.sample_s):
            now = time.monotonic()
            last = self.frames[-1] if self.frames else None
            self.samples.append({
                "t": round(now - sim.t0, 3),
                "receiver_pending_chunks": receiver.pending(),
                "frame_queue": frames_q.qsize(),
                "last_processed_frame": last["frame_id"] if last else None,
                "lag_s": round(now - last["capture_t"], 3) if last else None,
            })

    # ------------------------------------------------------------------ run

    def run(self) -> dict:
        m = self.manifest
        sim = CameraBoxSim(m, self.link, self.speed, root=self.chunk_dir)
        receiver = ChunkReceiver(first_frame_id=m["chunks"][0]["first_frame_id"], reorder_timeout_s=self.reorder_timeout_s)
        frames_q: queue.Queue = queue.Queue(maxsize=self.frame_queue)
        sink = None
        if self.out_dir:
            os.makedirs(self.out_dir, exist_ok=True)
            sink = io.open(os.path.join(self.out_dir, "outputs.ndjson"), "w", encoding="utf-8")
        if hasattr(self.adapter, "configure"):
            self.adapter.configure(m)
        self.adapter.start(self.fps)
        arrivals = []

        def deliver(a):
            arrivals.append(a)
            if not a.lost:
                receiver.put(a)

        sim.start(deliver)
        stop = threading.Event()
        closer = threading.Thread(target=lambda: (sim.done.wait(), receiver.close(m["n_frames"])), daemon=True)
        decoder = threading.Thread(target=self._decode, args=(receiver, frames_q, sim), daemon=True, name="decoder")
        sampler = threading.Thread(target=self._sample, args=(receiver, frames_q, sim, stop), daemon=True, name="sampler")
        for t in (closer, decoder, sampler):
            t.start()

        def emit(outs, now):
            for o in outs:
                o.emitted_t = now
                rec = {**asdict(o), "t": round(now - sim.t0, 3),
                       "latency_s": round(now - sim.capture_time(o.frame_id), 3) if o.frame_id else None}
                self.outputs.append(rec)
                if sink:
                    sink.write(json.dumps(rec, default=str) + "\n")
                    sink.flush()

        try:
            while True:
                f = frames_q.get()
                if f is _END:
                    break
                t_proc = time.monotonic()
                outs = self.adapter.on_frame(f)
                t_done = time.monotonic()
                self.frames.append({
                    "frame_id": f.frame_id, "chunk": f.chunk_index, "missing": f.missing, "capture_t": f.capture_t,
                    "closed_t": f.closed_t, "arrived_t": f.arrived_t, "decode_start_t": f.decode_start_t,
                    "decoded_t": f.decoded_t, "proc_start_t": t_proc, "done_t": t_done,
                })
                emit(outs, t_done)
            emit(self.adapter.close(), time.monotonic())
        except Exception as e:
            self.error = f"module: {type(e).__name__}: {e}"
            sim.stop()
        finally:
            stop.set()
            sim.stop()
            if sink:
                sink.close()
        report = self.report(sim, receiver, arrivals)
        if self.out_dir:
            with io.open(os.path.join(self.out_dir, "report.json"), "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=1, default=str)
            with io.open(os.path.join(self.out_dir, "frames.ndjson"), "w", encoding="utf-8") as fh:
                for r in self.frames:
                    fh.write(json.dumps({k: (round(v - sim.t0, 4) if k.endswith("_t") and v is not None else v)
                                         for k, v in r.items()}) + "\n")
        return report

    # ------------------------------------------------------------------ report

    def report(self, sim: CameraBoxSim, receiver: ChunkReceiver, arrivals: list) -> dict:
        real = [r for r in self.frames if not r["missing"]]
        lat = [r["done_t"] - r["capture_t"] for r in real]
        comp = {
            "wait_for_chunk_close_s": [r["closed_t"] - r["capture_t"] for r in real],
            "link_s": [r["arrived_t"] - r["closed_t"] for r in real],
            "receiver_and_decode_queue_s": [r["decode_start_t"] - r["arrived_t"] for r in real],
            "decode_s": [r["decoded_t"] - r["decode_start_t"] for r in real],
            "module_queue_s": [r["proc_start_t"] - r["decoded_t"] for r in real],
            "module_s": [r["done_t"] - r["proc_start_t"] for r in real],
        }
        drift = None
        if len(real) > 10:
            x = np.array([r["capture_t"] - sim.t0 for r in real]) * self.speed / 60.0  # minutes of recording
            drift = float(np.polyfit(x, np.array(lat), 1)[0])
        busy = sum(comp["module_s"])
        video_s = len(self.frames) / self.fps
        lateness = [a.arrived - a.due for a in arrivals if a.arrived]
        return {
            "adapter": self.adapter.name,
            "video": self.manifest.get("video"),
            "chunk_seconds": self.manifest.get("chunk_seconds"),
            "speed": self.speed,
            "link": asdict(self.link),
            "frames": len(self.frames),
            "frames_missing": len(self.frames) - len(real),
            "video_seconds": round(video_s, 2),
            "wall_seconds": round((self.frames[-1]["done_t"] - sim.t0) if self.frames else 0.0, 2),
            "frame_latency_s": _pct(lat),
            "latency_components_s": {k: _pct(v) for k, v in comp.items()},
            "latency_drift_s_per_recording_minute": round(drift, 4) if drift is not None else None,
            "module_ms_per_frame": round(1000 * busy / max(len(real), 1), 2),
            "module_realtime_factor": round((len(real) / self.fps / self.speed) / busy, 2) if busy else None,
            "keeps_up": bool(drift is not None and drift < 0.05 * 60 / self.speed),
            "max_frame_queue": max((s["frame_queue"] for s in self.samples), default=0),
            "max_receiver_pending_chunks": receiver.stats.max_pending,
            "receiver": asdict(receiver.stats),
            "chunk_delivery_lateness_s": _pct(lateness),
            "decode_mismatches": self.decode_mismatches,
            "outputs": len(self.outputs),
            "output_latency_s": _pct([o["latency_s"] for o in self.outputs if o["latency_s"] is not None]),
            "error": self.error,
            "samples": self.samples,
        }
