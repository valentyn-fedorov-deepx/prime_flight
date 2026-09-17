"""Production modules as autonomous components, each in its own process, fed by one real-time pipeline.

A production module imports its own `main`, `cv_common` and `db_worker` packages by name, so two modules cannot share a
process. `ModuleHost` starts one child process per module (spawn) and is the component shell around it:

  * **it is given only what it declared** — `ComponentSpec` / `Subscription` (`pf.rt.component`) say which GM classes and
    tracked classes the module reads; with `filter_rows` on, everything else is dropped before the record is pickled;
  * **it is opened and closed by its gate** — stage events open a component late and close it when its stage is over
    (`pf/rt/gating.json`); until the stage detector publishes events every gate is open;
  * **its outputs leave at once** — a reader thread in the parent drains the child's pipe and publishes to an `OutputBus`
    the moment the module produces an output, so a verdict does not wait for the next frame of the pipeline.

Two one-way pipes, one direction each, so the reader thread and the frame loop never touch the same handle: frames go
parent → child, outputs and slot acknowledgements come child → parent.

Modules that read pixels get the frames through one shared-memory ring (`SharedFrameRing`): the pipeline writes each
published frame into a slot and the host copies it out before the module sees it, so a module may keep frames as long as
its own logic needs. The host acknowledges every copy and the pipeline never overwrites a slot that has not been copied.

    ring = SharedFrameRing()                                   # only if some module reads pixels
    host = ModuleHost("safety-vests-secured-to-body", args, spec=spec, bus=bus)
    host.start(manifest, fps, ring.spec)
    slot = ring.write(frame_id, image, [host])                 # waits if the host has not copied that slot yet
    host.push(frame_id, {"general_model": rows, "trackers": records}, slot, events=["BL_AT_DOOR"])
    outs = bus.drain()                                         # or the bus sinks deliver them directly
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sys
import threading
import time
import traceback
from dataclasses import asdict

import numpy as np

from pf.rt.component import ComponentSpec, Gate, Subscription
from pf.rt.runtime import Output

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _stats(times: list) -> dict:
    if not times:
        return {"frames": 0}
    ordered = sorted(times)
    pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]
    return {"frames": len(times), "mean_ms": round(1000 * sum(times) / len(times), 3), "p95_ms": round(1000 * pick(0.95), 3),
            "max_ms": round(1000 * ordered[-1], 3)}


class SharedFrameRing:
    """One shared-memory ring of decoded frames: written once by the pipeline, copied by every host that reads pixels."""

    def __init__(self, shape=(1080, 1920, 3), slots: int = 16):
        from multiprocessing import shared_memory

        self.shape, self.slots = tuple(int(x) for x in shape), int(slots)
        self.frame_bytes = int(np.prod(self.shape))
        self.shm = shared_memory.SharedMemory(create=True, size=self.frame_bytes * self.slots)
        self.spec = {"name": self.shm.name, "shape": list(self.shape), "slots": self.slots}

    def write(self, frame_id: int, image, hosts=()) -> int | None:
        """Wait until every host has copied the frame that occupies this slot, then write and return the slot."""
        if image is None:
            return None
        for host in hosts:
            host.wait_for_slot(frame_id, self.slots)
        slot = frame_id % self.slots
        view = np.ndarray(self.shape, dtype=np.uint8, buffer=self.shm.buf, offset=slot * self.frame_bytes)
        view[:] = image
        return slot

    def close(self) -> None:
        try:
            self.shm.close()
            self.shm.unlink()
        except (FileNotFoundError, BufferError):
            pass


def _attach_ring(spec):
    from multiprocessing import shared_memory

    shm = shared_memory.SharedMemory(name=spec["name"])
    shape = tuple(int(x) for x in spec["shape"])
    return shm, shape, int(np.prod(shape))


def _host_main(frames_conn, outs_conn, kwargs: dict, manifest: dict, fps: float, frame_spec: dict | None) -> None:
    """Child process: one ProductionModuleAdapter with live metadata (and pixels from the ring, if it reads them)."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    times: list = []
    shm = None
    try:
        from pf.rt.prod_module import ProductionModuleAdapter

        shape = frame_bytes = None
        if frame_spec:
            shm, shape, frame_bytes = _attach_ring(frame_spec)
        adapter = ProductionModuleAdapter(**kwargs)
        adapter.configure(manifest)
        adapter.start(fps)
        outs_conn.send(("ready",))
        while True:
            msg = frames_conn.recv()
            if msg[0] == "frame":
                _, frame_id, meta, slot = msg
                image = None
                if slot is not None and shm is not None:
                    image = np.ndarray(shape, dtype=np.uint8, buffer=shm.buf, offset=slot * frame_bytes).copy()
                    outs_conn.send(("ack", frame_id))  # the slot is free again
                t0 = time.perf_counter()
                outs = adapter.push(frame_id, image, meta)
                times.append(time.perf_counter() - t0)
                if outs:
                    outs_conn.send(("outs", [asdict(o) for o in outs]))
            elif msg[0] == "close":
                outs = adapter.close()
                outs_conn.send(("closed", [asdict(o) for o in outs], _stats(times)))
                return
    except Exception as e:  # report instead of dying silently: the parent turns it into an output
        outs_conn.send(("failed", f"{type(e).__name__}: {str(e)[:400]}", traceback.format_exc()[-3000:], _stats(times)))
    finally:
        if shm is not None:
            shm.close()


class ModuleHost:
    def __init__(self, module: str, module_args: dict | None = None, pixels: bool = False,
                 spec: ComponentSpec | None = None, subscription: Subscription | None = None,
                 bus=None, filter_rows: bool = False, gating: bool = False):
        args = dict(module_args or {})
        args.pop("inferences_dir", None)
        args.update(module=module, metadata="live")
        for key in ("module_dir", "work_dir"):  # the parent may change its working directory later
            if args.get(key):
                args[key] = os.path.abspath(args[key])
        args["prepend_path"] = [os.path.abspath(p) for p in args.get("prepend_path") or []]
        self.module, self.args, self.pixels = module, args, pixels
        self.spec = spec or ComponentSpec.for_module(module, pixels=pixels)
        self.subscription = subscription or Subscription(pixels=pixels)
        self.filter_rows = bool(filter_rows and subscription is not None)
        self.gate = Gate(self.spec, enabled=gating)  # without a stage-event source the gate stays open
        self.bus = bus
        self.stats: dict | None = None
        self.failed: str | None = None
        self.proc = self.frames_conn = self.outs_conn = None
        self.waits = 0
        self.wait_s = 0.0
        self.frames_sent = 0
        self.frames_skipped = 0  # the gate was closed on those frames
        self.rows_sent = 0
        self.rows_dropped = 0
        self._last_ack = 0
        self._buffered: list = []
        self._closed = False
        self._reader = None
        self._lock = threading.Lock()
        self._ack = threading.Condition(self._lock)

    # ------------------------------------------------------------------ lifecycle

    def start(self, manifest: dict, fps: float, frame_spec: dict | None = None, timeout_s: float = 600.0) -> None:
        ctx = mp.get_context("spawn")
        frames_r, frames_w = ctx.Pipe(duplex=False)  # pipeline -> module
        outs_r, outs_w = ctx.Pipe(duplex=False)  # module -> pipeline
        self.proc = ctx.Process(target=_host_main,
                                args=(frames_r, outs_w, self.args, manifest, fps, frame_spec if self.pixels else None),
                                name=f"host:{self.module}", daemon=True)
        self.proc.start()
        frames_r.close()
        outs_w.close()
        self.frames_conn, self.outs_conn = frames_w, outs_r
        if not self.outs_conn.poll(timeout_s):
            raise TimeoutError(f"module host {self.module} did not start within {timeout_s} s")
        msg = self.outs_conn.recv()
        if msg[0] != "ready":
            raise RuntimeError(f"module host {self.module} failed to start: {msg[1:3]}")
        self._reader = threading.Thread(target=self._read, name=f"host-reader:{self.module}", daemon=True)
        self._reader.start()

    def _read(self) -> None:
        """Owns the child -> parent pipe: acknowledgements free ring slots, outputs go to the bus at once."""
        while True:
            try:
                msg = self.outs_conn.recv()
            except (EOFError, OSError, BrokenPipeError):
                with self._ack:
                    self._closed = True
                    self._ack.notify_all()
                return
            received_t = time.perf_counter()
            outs = self._handle(msg, received_t)
            if outs:
                if self.bus is not None:
                    for o in outs:
                        o.emitted_t = received_t  # produced by the module, not collected by the frame loop
                        self.bus.publish(o, received_t)
                else:
                    with self._lock:
                        self._buffered.extend(outs)
            if msg[0] in ("closed", "failed"):
                return

    def _handle(self, msg, received_t: float) -> list:
        if msg[0] == "ack":
            with self._ack:
                self._last_ack = max(self._last_ack, int(msg[1]))
                self._ack.notify_all()
            return []
        if msg[0] == "outs":
            return [Output(**o) for o in msg[1]]
        if msg[0] == "closed":
            with self._ack:
                self._closed, self.stats = True, msg[2]
                self._ack.notify_all()
            return [Output(**o) for o in msg[1]]
        if msg[0] == "failed":
            with self._ack:
                self._closed, self.failed, self.stats = True, msg[1], msg[3]
                self._ack.notify_all()
            return [Output("note", "module_host_error", None, {"module": self.module, "error": msg[1], "traceback": msg[2]})]
        return []

    # ------------------------------------------------------------------ frames

    def wait_for_slot(self, frame_id: int, slots: int, timeout_s: float = 300.0) -> None:
        """Block while the module has not yet copied the frame that occupies the slot `frame_id` is about to take."""
        if not self.pixels or self._closed:
            return
        t0 = time.perf_counter()
        waited = False
        with self._ack:
            while frame_id - self._last_ack > slots - 1 and not self._closed:
                waited = True
                if not self._ack.wait(timeout=timeout_s):
                    raise TimeoutError(f"module host {self.module} has not copied frame {self._last_ack + 1}")
        if waited:
            self.waits += 1
            self.wait_s += time.perf_counter() - t0

    def push(self, frame_id: int, meta: dict, slot: int | None = None, events=None) -> list:
        """Hand the component its frame, if its gate is open. Returns whatever it produced before this call."""
        gate_change = self.gate.on_events(frame_id, events)
        if gate_change and self.bus is not None:
            self.bus.publish(Output("event", f"component_{gate_change}", frame_id,
                                    {"module": self.module, "gate": self.gate.as_dict()}))
        if not self.gate.open:
            self.frames_skipped += 1
            return self.poll()
        if self.filter_rows:
            before = self.subscription.size(meta)
            meta = self.subscription.filter(meta)
            after = self.subscription.size(meta)
            self.rows_sent += after
            self.rows_dropped += before - after
        else:
            self.rows_sent += self.subscription.size(meta)
        if not self._closed:
            try:
                self.frames_conn.send(("frame", frame_id, meta, slot if self.pixels else None))
                self.frames_sent += 1
            except (BrokenPipeError, EOFError, OSError):
                self._closed = True
        return self.poll()

    def poll(self) -> list:
        """Outputs collected since the last call. Empty when a bus is set: the reader thread publishes there instead."""
        with self._lock:
            out, self._buffered = self._buffered, []
        return out

    def close(self, timeout_s: float = 900.0) -> list:
        out = self.poll()
        if not self._closed:
            try:
                self.frames_conn.send(("close",))
            except (BrokenPipeError, EOFError, OSError):
                self._closed = True
        if self._reader is not None:
            self._reader.join(timeout=timeout_s)
        out.extend(self.poll())
        if self.proc is not None:
            self.proc.join(timeout=30)
            if self.proc.is_alive():
                self.proc.terminate()
        for conn in (self.frames_conn, self.outs_conn):
            try:
                conn.close()
            except (OSError, AttributeError):
                pass
        return out

    # ------------------------------------------------------------------ report

    def report(self) -> dict:
        return {"per_frame": self.stats, "failed": self.failed, "pixels": self.pixels,
                "ring_waits": self.waits, "ring_wait_s": round(self.wait_s, 2),
                "frames_sent": self.frames_sent, "frames_skipped_gate_closed": self.frames_skipped,
                "rows_sent": self.rows_sent, "rows_dropped_not_subscribed": self.rows_dropped,
                "filter_rows": self.filter_rows, "spec": self.spec.as_dict(), "gate": self.gate.as_dict()}
