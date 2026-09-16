"""Cut a recorded video into GOP-aligned chunks without re-encoding, the way the CameraBox records them.

The cameras write H.264 at 8 fps with a keyframe every 3.75 s (30 frames). Cutting with stream copy at keyframes keeps every
frame bit-identical to the whole-file decode (verified: 961 of 961 frames on zHxIAF2vUGxJ with the OpenCV decoder), so a
chunk of N GOPs is a pure transport unit. The manifest carries, per chunk, the absolute id of its first frame and its frame
count taken from packet counts, not from container timestamps (the frame id is explicit, X2).

    python -m pf.rt.chunker --video out/testset/videos/zHxIAF2vUGxJ.mp4 --out out/rt/chunks/zHxIAF2vUGxJ --gops-per-chunk 1
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass

MANIFEST = "manifest.json"


@dataclass
class ChunkInfo:
    index: int
    path: str  # file name relative to the manifest folder
    first_frame_id: int  # absolute id of the first frame, 1-based like the frame contract and the modules' enumerate(..., 1)
    n_frames: int
    t_start: float  # recording time of the first frame, seconds from the start of the recording
    t_end: float  # recording time at which the chunk is complete: (first_frame_id - 1 + n_frames) / fps
    bytes: int
    starts_on_keyframe: bool


def _ffprobe(args: list) -> str:
    return subprocess.run(["ffprobe", "-v", "error", *args], capture_output=True, text=True, check=True).stdout


def probe(video: str) -> dict:
    s = json.loads(_ffprobe(["-select_streams", "v:0", "-show_entries",
                             "stream=codec_name,width,height,r_frame_rate,nb_frames", "-of", "json", video]))["streams"][0]
    num, den = (int(x) for x in s["r_frame_rate"].split("/"))
    return {"codec": s["codec_name"], "width": int(s["width"]), "height": int(s["height"]), "fps": num / den,
            "nb_frames": int(s.get("nb_frames") or 0)}


def keyframe_ids(video: str, fps: float) -> list:
    out = _ffprobe(["-select_streams", "v:0", "-skip_frame", "nokey", "-show_entries", "frame=pts_time", "-of", "csv=p=0",
                    video])
    # csv lines can carry trailing empty fields ("0.000000,"), so take the first field of each line
    times = [line.split(",")[0].strip() for line in out.splitlines()]
    return sorted({round(float(t) * fps) for t in times if t})


def packet_sizes(video: str) -> list:
    """(bytes, keyframe) per video packet = per encoded frame, in decode order (for the per-frame delivery model)."""
    out = _ffprobe(["-select_streams", "v:0", "-show_entries", "packet=size,flags", "-of", "csv=p=0", video])
    sizes = []
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0].strip().isdigit():
            sizes.append((int(parts[0]), "K" in parts[1]))
    return sizes


def packet_count(path: str) -> int:
    out = _ffprobe(["-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0",
                    path])
    return int(out.strip().split(",")[0])


def cut(video: str, out_dir: str, gops_per_chunk: int = 1, max_seconds: float | None = None) -> dict:
    """Write chunk_00000.mp4 ... and manifest.json into out_dir (which must not contain chunks yet)."""
    if gops_per_chunk < 1:
        raise ValueError("gops_per_chunk must be >= 1")
    os.makedirs(out_dir, exist_ok=True)
    if any(f.startswith("chunk_") for f in os.listdir(out_dir)):
        raise FileExistsError(f"{out_dir} already holds chunks; use a new folder")
    info = probe(video)
    fps = info["fps"]
    keys = keyframe_ids(video, fps)
    if max_seconds:
        keys = [k for k in keys if k < max_seconds * fps]
    boundaries = keys[gops_per_chunk::gops_per_chunk]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-i", video, "-map", "0:v:0", "-c", "copy", "-f", "segment", "-reset_timestamps", "1", "-segment_format", "mp4"]
    cmd += ["-segment_frames", ",".join(map(str, boundaries))] if boundaries else ["-segment_time", "1000000"]
    cmd.append(os.path.join(out_dir, "chunk_%05d.mp4"))
    t0 = time.perf_counter()
    subprocess.run(cmd, check=True)
    cut_s = time.perf_counter() - t0
    key_set = set(keys)
    chunks, next_id = [], 1
    for i, name in enumerate(sorted(f for f in os.listdir(out_dir) if f.startswith("chunk_") and f.endswith(".mp4"))):
        path = os.path.join(out_dir, name)
        n = packet_count(path)
        chunks.append(ChunkInfo(i, name, next_id, n, (next_id - 1) / fps, (next_id - 1 + n) / fps, os.path.getsize(path),
                                next_id - 1 in key_set))
        next_id += n
    gop = keys[1] - keys[0] if len(keys) > 1 else None
    manifest = {
        "video": os.path.abspath(video), "created": time.strftime("%Y-%m-%d %H:%M:%S"), **info, "gop_frames": gop,
        "gops_per_chunk": gops_per_chunk, "chunk_seconds": gop * gops_per_chunk / fps if gop else None,
        "n_frames": next_id - 1, "n_chunks": len(chunks), "cut_seconds": round(cut_s, 1),
        "chunks": [asdict(c) for c in chunks],
    }
    with io.open(os.path.join(out_dir, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    return manifest


def load_manifest(chunk_dir: str) -> dict:
    with io.open(os.path.join(chunk_dir, MANIFEST), encoding="utf-8") as fh:
        return json.load(fh)


def verify_pixels(chunk_dir: str, max_frames: int | None = None) -> dict:
    """Decode the chunks in order and the source video with OpenCV and compare every frame (md5)."""
    import cv2

    manifest = load_manifest(chunk_dir)
    src = cv2.VideoCapture(manifest["video"])
    compared = identical = 0
    first_diff = None
    for c in manifest["chunks"]:
        cap = cv2.VideoCapture(os.path.join(chunk_dir, c["path"]))
        while max_frames is None or compared < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            ok_src, ref = src.read()
            if not ok_src:
                break
            if hashlib.md5(frame.tobytes()).digest() == hashlib.md5(ref.tobytes()).digest():
                identical += 1
            elif first_diff is None:
                first_diff = compared
            compared += 1
        cap.release()
        if max_frames is not None and compared >= max_frames:
            break
    src.release()
    return {"frames_compared": compared, "frames_identical": identical, "first_different_frame": first_diff}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True, help="new folder for the chunks and manifest.json")
    ap.add_argument("--gops-per-chunk", type=int, default=1, help="1 GOP = 3.75 s on the DXGAT cameras")
    ap.add_argument("--max-seconds", type=float, default=None, help="cut only the beginning of the video")
    ap.add_argument("--verify-frames", type=int, default=0, help="compare this many decoded frames with the source")
    a = ap.parse_args()
    m = cut(a.video, a.out, a.gops_per_chunk, a.max_seconds)
    sizes = [c["bytes"] for c in m["chunks"]]
    aligned = sum(c["starts_on_keyframe"] for c in m["chunks"])
    print(f"{m['n_chunks']} chunks of {m['chunk_seconds']} s, {m['n_frames']} frames (source {m['nb_frames']}), "
          f"{min(sizes) / 1e6:.2f}-{max(sizes) / 1e6:.2f} MB, {aligned} start on a keyframe, cut in {m['cut_seconds']} s")
    if a.verify_frames:
        print("pixel check:", json.dumps(verify_pixels(a.out, a.verify_frames)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
