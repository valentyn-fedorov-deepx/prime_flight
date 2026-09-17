"""Live view of a real-time run: a page served by the run itself.

    monitor = Monitor(port=8765).start()
    monitor.update({...})            # per frame: cheap dict assignment, no work in the frame loop
    monitor.set_frame(image, rows, records)

The page shows the branch as a diagram — CameraBox, uplink, receiver, decoder, GM heads, causal rows, tracker, module
processes, outputs — with what flows between the blocks and what each costs per frame, next to the current frame with the
GM and tracker boxes drawn on it and the verdicts and alerts as the modules emit them. Everything is served locally, so the
page needs no network: no external scripts, no fonts, no CDN.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLASS_COLOURS = {  # BGR for cv2
    "airplane": (255, 200, 90), "person": (120, 220, 120), "beltloader": (90, 170, 255), "gse": (200, 140, 255),
}


class Monitor:
    def __init__(self, port: int = 8765, host: str = "127.0.0.1", jpeg_width: int = 720, jpeg_quality: int = 62):
        self.port, self.host = port, host
        self.jpeg_width, self.jpeg_quality = jpeg_width, jpeg_quality
        self.state: dict = {"status": "starting"}
        self._frame = None  # (image, gm_rows, tracker_records, frame_id)
        self._lock = threading.Lock()
        self._server = None
        self._id2name: dict = {}

    # ------------------------------------------------------------------ producer side (the run)
    def update(self, state: dict) -> None:
        self.state = state

    def set_frame(self, image, gm_rows=None, records=None, frame_id: int | None = None) -> None:
        with self._lock:
            self._frame = (image, gm_rows or [], records or [], frame_id)

    def set_class_names(self, id2name: dict) -> None:
        self._id2name = dict(id2name)

    # ------------------------------------------------------------------ server
    def start(self) -> "Monitor":
        monitor = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # no request logging into the run output
                pass

            def _send(self, code: int, body: bytes, content_type: str) -> None:
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?")[0]
                if path in ("/", "/index.html"):
                    self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                elif path == "/state":
                    self._send(200, json.dumps(monitor.state, default=str).encode("utf-8"), "application/json")
                elif path == "/frame.jpg":
                    body = monitor.frame_jpeg()
                    if body is None:
                        self._send(503, b"no frame yet", "text/plain")
                    else:
                        self._send(200, body, "image/jpeg")
                else:
                    self._send(404, b"not found", "text/plain")

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True, name="rt-monitor").start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    # ------------------------------------------------------------------ rendering
    def frame_jpeg(self):
        with self._lock:
            item = self._frame
        if item is None:
            return None
        image, rows, records, _fid = item
        if image is None:
            return None
        import cv2

        scale = self.jpeg_width / image.shape[1]
        view = cv2.resize(image, (self.jpeg_width, int(image.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        for row in rows or ():
            try:
                x1, y1, x2, y2, _conf, cls_id = row[:6]
            except (TypeError, ValueError):
                continue
            name = self._id2name.get(int(cls_id), str(int(cls_id)))
            if name == "airplane":
                continue  # the tracker box is drawn instead
            p1 = (int(x1 * scale), int(y1 * scale))
            p2 = (int(x2 * scale), int(y2 * scale))
            cv2.rectangle(view, p1, p2, (90, 90, 90), 1)
        for record in records or ():
            box = record.get("xyxy") if isinstance(record, dict) else None
            if not box:
                continue
            cls_str = record.get("cls_str", "")
            colour = CLASS_COLOURS.get(cls_str, (200, 200, 200))
            p1 = (int(box[0] * scale), int(box[1] * scale))
            p2 = (int(box[2] * scale), int(box[3] * scale))
            cv2.rectangle(view, p1, p2, colour, 2)
            label = f"{cls_str} {record.get('tr_id', '')}".strip()
            cv2.putText(view, label, (p1[0], max(12, p1[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, colour, 1, cv2.LINE_AA)
        ok, buf = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        return buf.tobytes() if ok else None


PAGE = """<title>Real-time branch</title>
<style>
  :root {
    --bg: #0f1216; --panel: #161b22; --line: #263040; --text: #e6edf3; --muted: #8b98a8;
    --accent: #4aa8ff; --ok: #3fb950; --warn: #d29922; --bad: #f85149;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
         font: 13px/1.45 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { display: flex; gap: 18px; align-items: baseline; padding: 10px 16px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
  header h1 { font-size: 15px; margin: 0; font-weight: 600; letter-spacing: .2px; }
  header .k { color: var(--muted); }
  header .v { font-variant-numeric: tabular-nums; }
  main { display: grid; grid-template-columns: minmax(360px, 1fr) minmax(360px, 1fr); gap: 12px; padding: 12px; }
  @media (max-width: 900px) { main { grid-template-columns: 1fr; } }
  section { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px; min-width: 0; }
  section h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: 0 0 10px; }
  svg { width: 100%; height: auto; display: block; }
  .node rect { fill: #1b222c; stroke: var(--line); }
  .node.active rect { stroke: var(--accent); }
  .node text.title { fill: var(--text); font-size: 11px; font-weight: 600; }
  .node text.sub { fill: var(--muted); font-size: 9.5px; font-variant-numeric: tabular-nums; }
  .link { stroke: var(--line); stroke-width: 1.5; fill: none; }
  .pulse { fill: var(--accent); }
  text.edge { fill: var(--muted); font-size: 9px; }
  text.caption { fill: var(--muted); font-size: 9.5px; text-transform: uppercase; letter-spacing: .08em; }
  .bar { display: flex; height: 14px; border-radius: 7px; overflow: hidden; background: #11161d; margin: 4px 0 8px; }
  .bar span { display: block; height: 100%; }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; color: var(--muted); font-variant-numeric: tabular-nums; }
  .legend i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 5px; }
  .s0 { background: #3b4252; } .s1 { background: #4aa8ff; } .s2 { background: #8b6fd6; }
  .s3 { background: #2f9e8f; } .s4 { background: #d29922; } .s5 { background: #f85149; }
  #frame { width: 100%; border-radius: 8px; display: block; background: #000; }
  table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  td { padding: 3px 0; vertical-align: top; }
  td.k { color: var(--muted); width: 48%; }
  .verdict { border-top: 1px solid var(--line); padding: 8px 0; }
  .verdict:first-child { border-top: 0; }
  .verdict .name { font-weight: 600; }
  .verdict .report { color: var(--muted); }
  .pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
  .Pass { background: rgba(63,185,80,.15); color: var(--ok); }
  .Fail { background: rgba(248,81,73,.15); color: var(--bad); }
  .Notobserved, .running { background: rgba(139,152,168,.15); color: var(--muted); }
  .alerts div { padding: 2px 0; color: var(--warn); }
</style>
<header>
  <h1>Real-time branch</h1>
  <span><span class="k">video</span> <span class="v" id="video">—</span></span>
  <span><span class="k">ingest</span> <span class="v" id="ingest">—</span></span>
  <span><span class="k">recording</span> <span class="v" id="vtime">—</span></span>
  <span><span class="k">frame</span> <span class="v" id="frame_id">—</span></span>
  <span><span class="k">latency</span> <span class="v" id="latency">—</span></span>
  <span><span class="k">budget</span> <span class="v" id="budget">—</span></span>
  <span><span class="k">state</span> <span class="v" id="status">—</span></span>
</header>
<main>
  <section>
    <h2>Data flow</h2>
    <svg id="diagram" viewBox="0 0 420 492" role="img" aria-label="components of the real-time branch"></svg>
    <h2 style="margin-top:12px">From the gate to the verdict · <span id="bartotal">—</span> s</h2>
    <div class="bar" id="bar"></div>
    <div class="legend" id="barlegend"></div>
  </section>
  <section>
    <h2>What the modules see</h2>
    <img id="frame" alt="current frame with detections and tracks">
    <table id="counters" style="margin-top:10px"></table>
    <h2 style="margin-top:14px">Verdicts</h2>
    <div id="verdicts"></div>
    <h2 style="margin-top:14px">Alerts and events</h2>
    <div class="alerts" id="alerts"></div>
  </section>
</main>
<script>
const NODES = [
  {id: "cambox",   x: 20,  y: 32,  w: 180, h: 46, title: "CameraBox", sub: s => `${s.ingest?.mode === "frames" ? "frame by frame" : "chunk " + (s.ingest?.chunk_seconds ?? "?") + " s"} · ${s.ingest?.bitrate_mbps ?? "?"} Mbit/s`},
  {id: "uplink",   x: 20,  y: 98,  w: 180, h: 46, title: "Uplink", sub: s => `${s.ingest?.bandwidth_mbps ?? "?"} Mbit/s · ${fmt(s.components_s?.link)} s`},
  {id: "receiver", x: 20,  y: 164, w: 180, h: 46, title: "Receiver / session", sub: s => `${s.ingest?.received ?? 0} in · ${s.ingest?.lost ?? 0} lost · ids kept`},
  {id: "decoder",  x: 20,  y: 230, w: 180, h: 46, title: "Decoder", sub: s => `${fmt(s.components_ms?.decode, 1)} ms · queue ${s.queues?.frame_queue ?? 0}`},
  {id: "gm",       x: 220, y: 98,  w: 180, h: 60, title: "GM v2", sub: s => `${(s.gm?.heads || []).join(" + ") || "—"} heads\n${fmt(s.components_ms?.gm, 1)} ms · ${s.gm?.rows ?? 0} rows`},
  {id: "rows",     x: 220, y: 174, w: 180, h: 46, title: "Causal second run", sub: s => `${fmt(s.components_ms?.second_run_rows, 2)} ms · v1-compat rows`},
  {id: "tracker",  x: 220, y: 236, w: 180, h: 60, title: "Tracker v2", sub: s => `${(s.tracker?.classes || []).join(", ") || "—"}\n${fmt(s.components_ms?.tracker, 1)} ms · publishes +${s.tracker?.publish_lag_frames ?? 0} fr late`},
  {id: "modules",  x: 220, y: 312, w: 180, h: 60, title: "Modules", sub: s => `${(s.modules || []).length} components, own processes\n${(s.components || []).filter(c => c.gate?.open_now).length || (s.modules || []).length} open · ${fmt(s.components_ms?.module, 2)} ms in the frame loop`},
  {id: "outputs",  x: 220, y: 388, w: 180, h: 52, title: "Outputs", sub: s => `${s.counts?.verdicts ?? 0} verdicts · ${s.counts?.alerts ?? 0} alerts\n${s.bus?.outputs ?? 0} on the bus, delivered at once`},
];
const LINKS = [
  ["cambox", "uplink", "encoded frames"], ["uplink", "receiver", "packets"], ["receiver", "decoder", "frames in order"],
  ["decoder", "gm", "BGR frame + frame_id"], ["gm", "rows", "first-run rows"], ["rows", "tracker", "second-run rows"],
  ["tracker", "modules", "rows + track records"], ["modules", "outputs", "verdict · alert · timeline"],
];
const LATENCY = [["camera / chunk", "wait_for_chunk"], ["uplink", "link"], ["queues", "queue"],
                 ["decode", "decode"], ["GM + tracker", "pipeline"], ["tracker publish", "publish"]];
const fmt = (v, d = 3) => (v === undefined || v === null) ? "—" : Number(v).toFixed(d);
const node = id => NODES.find(n => n.id === id);

function drawDiagram(s) {
  const svg = document.getElementById("diagram");
  let out = `<text class="caption" x="20" y="18">at the gate</text>
             <text class="caption" x="220" y="18">server · one process per event</text>`;
  for (const [a, b, label] of LINKS) {
    const na = node(a), nb = node(b);
    const sameColumn = na.x === nb.x;
    const p1 = {x: na.x + na.w / 2, y: na.y + na.h}, p2 = {x: nb.x + nb.w / 2, y: nb.y};
    const d = sameColumn
      ? `M ${p1.x} ${p1.y} L ${p2.x} ${p2.y}`
      : `M ${na.x + na.w} ${na.y + na.h / 2} C ${na.x + na.w + 34} ${na.y + na.h / 2}, ${nb.x - 34} ${nb.y + nb.h / 2}, ${nb.x} ${nb.y + nb.h / 2}`;
    const at = sameColumn ? {x: p1.x + 8, y: (p1.y + p2.y) / 2 + 3, anchor: "start"}
                          : {x: na.x + na.w / 2, y: na.y + na.h + 16, anchor: "middle"};
    out += `<path class="link" d="${d}" id="path-${a}-${b}"/>
            <circle class="pulse" r="2.6"><animateMotion dur="1.6s" repeatCount="indefinite"><mpath href="#path-${a}-${b}"/></animateMotion></circle>
            <text class="edge" x="${at.x}" y="${at.y}" text-anchor="${at.anchor}">${label}</text>`;
  }
  for (const n of NODES) {
    const lines = String(n.sub(s)).split("\\n");
    out += `<g class="node ${s.frame_id ? "active" : ""}">
      <rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="8"/>
      <text class="title" x="${n.x + 12}" y="${n.y + 19}">${n.title}</text>
      ${lines.map((t, i) => `<text class="sub" x="${n.x + 12}" y="${n.y + 34 + i * 12}">${t}</text>`).join("")}
    </g>`;
  }
  svg.innerHTML = out;
}

function drawLatency(s) {
  const c = {...(s.components_s || {})};
  c.publish = (s.tracker?.publish_lag_frames ?? 0) / (s.fps || 8);
  const total = LATENCY.reduce((a, [, k]) => a + (c[k] || 0), 0);
  document.getElementById("bartotal").textContent = total ? fmt(total, 2) : "—";
  document.getElementById("bar").innerHTML = LATENCY
    .map(([name, k], i) => (c[k] > 0 ? `<span class="s${i}" style="width:${(c[k] / total * 100).toFixed(1)}%" title="${name} ${fmt(c[k])} s"></span>` : ""))
    .join("");
  document.getElementById("barlegend").innerHTML = LATENCY
    .map(([name, k], i) => `<span><i class="s${i}"></i>${name} ${fmt(c[k] || 0, 2)} s</span>`).join("");
}

function rows(s) {
  const c = s.counters || {};
  const pairs = [
    ["processed", `${s.frame_id ?? 0} / ${s.frames ?? "?"} frames`],
    ["speed", `${fmt(s.fps_processed, 1)} fps processed · ${s.fps ?? 8} fps recorded`],
    ["frame latency", `${fmt(s.latency_s?.now)} s now · p50 ${fmt(s.latency_s?.p50)} · max ${fmt(s.latency_s?.max)}`],
    ["pipeline", `${fmt(s.components_ms?.total, 1)} ms per frame of ${fmt(s.budget_ms, 0)} available`],
    ["detections", `${s.gm?.rows ?? 0} rows · ${s.tracker?.records ?? 0} tracks`],
    ["queues", `frames ${s.queues?.frame_queue ?? 0} · unpublished ${s.queues?.unpublished ?? 0}`],
    ["memory", `${fmt(s.memory_gb, 1)} GB`],
  ];
  document.getElementById("counters").innerHTML = pairs
    .map(([k, v]) => `<tr><td class="k">${k}</td><td>${v}</td></tr>`).join("");
}

function verdicts(s) {
  const el = document.getElementById("verdicts");
  const components = Object.fromEntries((s.components || []).map(c => [c.module, c]));
  el.innerHTML = (s.modules || []).map(m => {
    const status = m.status || "running";
    const cls = String(status).replace(/\\s/g, "");
    const when = m.decided_at_video_time ? ` · decided at ${m.decided_at_video_time}` : "";
    const rep = (m.report || []).join(" ");
    const c = components[m.name];
    const gate = c ? `<div class="report">own process · gate ${c.gate.open_on} → ${c.gate.close_on} ·
        ${c.gate.open_now ? "open" : (c.gate.closed_at ? "closed" : "waiting")} ·
        ${c.frames_sent} frames${c.frames_skipped ? `, ${c.frames_skipped} held back` : ""}${c.failed ? " · FAILED" : ""}</div>` : "";
    return `<div class="verdict"><div><span class="name">${m.name}</span> <span class="pill ${cls}">${status}</span>${when}</div>
            ${rep ? `<div class="report">${rep}</div>` : ""}${gate}</div>`;
  }).join("") || '<div class="report">no module has answered yet</div>';
  document.getElementById("alerts").innerHTML = (s.alerts || []).slice(-8).reverse()
    .map(a => `<div>${a.video_time ?? ""} ${a.name} ${a.detail ?? ""}</div>`).join("") || '<div class="report">—</div>';
}

async function tick() {
  try {
    const s = await (await fetch("/state", {cache: "no-store"})).json();
    document.getElementById("video").textContent = s.video ?? "—";
    document.getElementById("ingest").textContent = s.ingest?.mode === "frames" ? "per frame" : "chunks";
    document.getElementById("vtime").textContent = s.video_time ?? "—";
    document.getElementById("frame_id").textContent = `${s.frame_id ?? 0} / ${s.frames ?? "?"}`;
    document.getElementById("latency").textContent = `${fmt(s.latency_s?.now)} s`;
    document.getElementById("budget").textContent = `${fmt(s.components_ms?.total, 1)} / ${fmt(s.budget_ms, 0)} ms`;
    const st = document.getElementById("status");
    st.textContent = s.status ?? "—";
    st.style.color = s.status === "keeping up" ? "var(--ok)" : (s.status === "behind" ? "var(--bad)" : "var(--muted)");
    drawDiagram(s); drawLatency(s); rows(s); verdicts(s);
  } catch (e) { /* the run has ended or has not started yet */ }
}
function frameTick() {
  const img = document.getElementById("frame");
  const next = new Image();
  next.onload = () => { img.src = next.src; setTimeout(frameTick, 200); };
  next.onerror = () => setTimeout(frameTick, 800);
  next.src = "/frame.jpg?t=" + Date.now();
}
setInterval(tick, 500); tick(); frameTick();
</script>
"""
