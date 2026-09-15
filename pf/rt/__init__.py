"""Real-time branch prototype: chunked ingestion simulated end to end on the wall clock.

    CameraBox (records GOP-aligned chunks)  ->  uplink (network model)  ->  receiver (order, absolute frame_id, gap fill)
      ->  decoder (pinned OpenCV)  ->  frame bus  ->  module adapter (emits events as soon as they are decided)  ->  sink

A chunk is a unit of transport only (docs/02_target_architecture.md): modules see frames with absolute frame ids and
capture times, never chunks. Every stage stamps its times on the monotonic clock, so the end-to-end latency of a frame
(capture -> output) and the share of it spent waiting for the chunk to close, on the link, in queues and in processing are
measured, not estimated.

    chunker   cut a recorded video into GOP-aligned chunks with stream copy, manifest with frame ids
    cambox    CameraBox + uplink simulator: replays a manifest on the wall clock
"""
